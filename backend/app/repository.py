"""Acceso a datos en MongoDB: usuarios, doctores, ambulancias, emergencias y operadores."""
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


def seed_admin() -> None:
    """Crea el administrador inicial (desde .env) solo si aún no hay ningún usuario."""
    if get_db()["users"].count_documents({}) == 0:
        upsert_user(settings.admin_username, settings.admin_password, settings.admin_name, "Administrador")


# ───────────────────────── datos de ejemplo (opcional) ─────────────────────────
def seed_demo() -> None:
    """Rellena las colecciones vacías con datos de ejemplo (SEED_DEMO_DATA=true)."""
    db = get_db()
    samples = {
        "doctors": [
            {"nombres": "Laura", "apellidos": "Méndez", "nombre": "Laura Méndez", "especialidad": "Medicina de urgencias", "cedula_profesional": "8451203", "celular": "55 1234 5601", "turno": "Matutino", "estado": "Activo"},
            {"nombres": "Carlos", "apellidos": "Ortega", "nombre": "Carlos Ortega", "especialidad": "Cardiología", "cedula_profesional": "8451204", "celular": "55 1234 5602", "turno": "Vespertino", "estado": "Activo"},
            {"nombres": "Sofía", "apellidos": "Ramírez", "nombre": "Sofía Ramírez", "especialidad": "Traumatología", "cedula_profesional": "8451205", "celular": "55 1234 5603", "turno": "Nocturno", "estado": "En guardia"},
            {"nombres": "Andrés", "apellidos": "Villalobos", "nombre": "Andrés Villalobos", "especialidad": "Pediatría", "cedula_profesional": "8451206", "celular": "55 1234 5604", "turno": "Matutino", "estado": "Descanso"},
        ],
        "ambulances": [
            {"placa": "AMB-101", "tipo": "Avanzada", "conductor": "Jorge Salinas", "estado": "Disponible"},
            {"placa": "AMB-102", "tipo": "Básica", "conductor": "Marcos Herrera", "estado": "En servicio"},
            {"placa": "AMB-103", "tipo": "Avanzada", "conductor": "Elena Cruz", "estado": "Disponible"},
            {"placa": "AMB-104", "tipo": "Básica", "conductor": "Pablo Núñez", "estado": "Mantenimiento"},
        ],
        "emergencies": [
            {"descripcion": "Accidente vehicular en Av. Reforma", "prioridad": "Alta", "estado": "En curso", "ambulancia": "AMB-102"},
            {"descripcion": "Dolor torácico, adulto mayor", "prioridad": "Alta", "estado": "Asignada", "ambulancia": "AMB-101"},
            {"descripcion": "Caída con posible fractura", "prioridad": "Media", "estado": "Pendiente", "ambulancia": None},
        ],
        "operators": [
            {"nombre": "Mariana Torres", "turno": "Matutino", "extension": "201", "estado": "En línea"},
            {"nombre": "Ricardo Paredes", "turno": "Vespertino", "extension": "202", "estado": "En línea"},
            {"nombre": "Daniela Ibarra", "turno": "Nocturno", "extension": "203", "estado": "Desconectado"},
        ],
    }
    for name, rows in samples.items():
        if db[name].count_documents({}) == 0:
            for row in rows:
                insert_row(name, row)


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
