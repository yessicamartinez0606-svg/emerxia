"""Acceso a datos en MongoDB: usuarios, ambulancias, emergencias y operadores."""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument

from .config import settings
from .mongo import get_db
from .security import hash_password

log = logging.getLogger("emergexia")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ───────────────────────── ids autoincrementales ─────────────────────────
def _next_id(name: str) -> int:
    """Contador por colección (colección 'counters')."""
    doc = get_db()["counters"].find_one_and_update(
        {"_id": name}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER
    )
    return doc["seq"]


# ───────────────────────── módulos de datos ─────────────────────────
def list_rows(name: str) -> list[dict]:
    return list(get_db()[name].find({}, {"_id": 0}).sort("id", 1))


def insert_row(name: str, data: dict) -> dict:
    row_id = _next_id(name)
    doc = {"id": row_id, **data, "created_at": _now()}
    if name == "emergencies":
        doc["folio"] = f"EMG-{row_id:04d}"
    db = get_db()
    db[name].insert_one(dict(doc))   # copia: pymongo agrega _id al dict que recibe
    log.info("Guardado en MongoDB %s.%s (id=%s)", db.name, name, row_id)
    return doc


def update_row(name: str, row_id: int, changes: dict) -> dict | None:
    """Actualiza solo los campos indicados de un registro. Regresa el documento
    completo ya actualizado, o None si no existe ese id."""
    db = get_db()
    if changes:
        db[name].update_one({"id": row_id}, {"$set": {**changes, "updated_at": _now()}})
    return db[name].find_one({"id": row_id}, {"_id": 0})


def delete_row(name: str, row_id: int) -> bool:
    """Borra un registro. Regresa False si no existía."""
    return get_db()[name].delete_one({"id": row_id}).deleted_count > 0


def source_name(name: str) -> str:
    """'base.colección', para mostrar dónde viven los datos."""
    return f"{get_db().name}.{name}"


# ───────────────────────── usuarios ─────────────────────────
def find_user(username: str) -> dict | None:
    return get_db()["users"].find_one({"username": username.strip().lower()}, {"_id": 0})


def upsert_user(username: str, password: str, full_name: str | None = None, role: str = "Administrador") -> dict:
    """Crea el usuario, o si ya existe le cambia la contraseña (y nombre/rol si se indican)."""
    username = username.strip().lower()
    users = get_db()["users"]
    existing = users.find_one({"username": username})
    if existing:
        changes = {"password_hash": hash_password(password), "active": True}
        if full_name:
            changes["full_name"] = full_name
        if role:
            changes["role"] = role
        users.update_one({"username": username}, {"$set": changes})
        return {"username": username, "created": False}
    users.insert_one({
        "id": _next_id("users"),
        "username": username,
        "password_hash": hash_password(password),
        "full_name": full_name or username,
        "role": role,
        "active": True,
        "created_at": _now(),
    })
    return {"username": username, "created": True}


def create_user(username: str, password: str, full_name: str, role: str = "Despachador") -> dict:
    """Registro de una cuenta nueva. Lanza ValueError si el usuario ya existe
    (el router la traduce a un 409 para el formulario)."""
    username = username.strip().lower()
    users = get_db()["users"]
    if users.find_one({"username": username}):
        raise ValueError("username_taken")
    users.insert_one({
        "id": _next_id("users"),
        "username": username,
        "password_hash": hash_password(password),
        "full_name": full_name,
        "role": role,
        "active": True,
        "created_at": _now(),
    })
    return {"username": username}


# ─────────────── cuentas de operadores y paramédicos ───────────────
# Cada operador o paramédico tiene una cuenta en "users" ligada a su registro con
# operador_id / paramedico_id. El registro guarda solo el nombre de usuario (para que la
# central lo vea en su módulo); la contraseña vive cifrada en la cuenta.

def cuenta_ligada(campo: str, registro_id: int) -> dict | None:
    return get_db()["users"].find_one({campo: registro_id}, {"_id": 0})


def usuario_disponible(username: str, campo: str | None = None, registro_id: int | None = None) -> bool:
    """True si nadie usa ese usuario, o si lo usa la misma cuenta ligada a ese registro."""
    otro = find_user(username)
    return otro is None or (campo is not None and otro.get(campo) == registro_id)


def guardar_credenciales(coleccion: str, campo: str, rol: str, registro_id: int, nombre: str,
                         usuario: str | None = None, password: str | None = None) -> dict:
    """Crea o actualiza la cuenta de un operador/paramédico. Lanza ValueError si el usuario
    ya lo usa otra persona. Regresa {"usuario": ...}."""
    db = get_db()
    users = db["users"]
    cuenta = cuenta_ligada(campo, registro_id)
    if usuario is not None:
        usuario = usuario.strip().lower()
        if not usuario_disponible(usuario, campo, registro_id):
            raise ValueError(f'El usuario "{usuario}" ya lo tiene otra persona. Elige otro.')
    if cuenta is None:
        if not usuario or not password:
            raise ValueError("Para crear su acceso escribe un usuario y una contraseña.")
        create_user(usuario, password, nombre, rol)
        users.update_one({"username": usuario}, {"$set": {campo: registro_id}})
    else:
        cambios: dict = {"full_name": nombre, "role": rol, "active": True}
        if usuario and usuario != cuenta["username"]:
            cambios["username"] = usuario
            db["password_resets"].delete_many({"username": cuenta["username"]})
        if password:
            cambios["password_hash"] = hash_password(password)
        users.update_one({"username": cuenta["username"]}, {"$set": cambios})
        usuario = cambios.get("username", cuenta["username"])
    db[coleccion].update_one({"id": registro_id}, {"$set": {"usuario": usuario}})
    return {"usuario": usuario}


def seed_admin() -> None:
    """Crea el administrador inicial (ADMIN_USERNAME / ADMIN_PASSWORD) solo si aún no hay
    ningún usuario. Es lo único que el sistema crea por su cuenta."""
    if get_db()["users"].count_documents({}) > 0:
        return
    if len(settings.admin_password) < 8:
        log.warning("La base no tiene usuarios y ADMIN_PASSWORD no está definida (o tiene menos de 8 "
                    "caracteres): no se creó el administrador inicial.")
        return
    upsert_user(settings.admin_username, settings.admin_password, settings.admin_name, "Administrador")


# ───────────────────────── recuperar contraseña ─────────────────────────
# NOTA: este proyecto no tiene un servicio de correo configurado. El token se
# genera y se guarda igual que en un flujo real; el router de /auth se lo
# regresa directo al frontend (en vez de mandarlo por email) para que la
# función sea usable ya mismo. El día que se conecte un servicio de correo
# (SMTP, SES, etc.), basta con enviar ese mismo `token` por email en vez de
# incluirlo en la respuesta — el resto del flujo no cambia.
RESET_TOKEN_MINUTES = 30


def create_password_reset(username: str) -> str | None:
    """Genera un token de un solo uso para restablecer la contraseña. Regresa
    None si el usuario no existe o está desactivado (sin revelar cuál de las
    dos cosas pasó, para no filtrar qué usuarios existen)."""
    user = find_user(username)
    if not user or not user.get("active", True):
        return None
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db = get_db()
    db["password_resets"].delete_many({"username": user["username"]})  # invalida enlaces anteriores
    db["password_resets"].insert_one({
        "username": user["username"],
        "token_hash": token_hash,
        # datetime "naive" en UTC: pymongo regresa las fechas guardadas sin
        # zona horaria por defecto, así que se compara siempre naive-vs-naive
        # para no mezclar con datetime.now(timezone.utc).
        "expires_at": datetime.utcnow() + timedelta(minutes=RESET_TOKEN_MINUTES),
        "used": False,
        "created_at": _now(),
    })
    return token


def consume_password_reset(token: str, new_password: str) -> bool:
    """Valida el token (sin usar, no expirado) y cambia la contraseña. Regresa
    False si el token es inválido, ya se usó, o expiró."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db = get_db()
    record = db["password_resets"].find_one({"token_hash": token_hash, "used": False})
    if not record or record["expires_at"] < datetime.utcnow():
        return False
    db["users"].update_one({"username": record["username"]}, {"$set": {"password_hash": hash_password(new_password)}})
    db["password_resets"].update_one({"_id": record["_id"]}, {"$set": {"used": True}})
    return True
