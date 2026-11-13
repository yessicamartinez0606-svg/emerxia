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
        # Ambulancias repartidas en los hospitales de app/genetico.py. El conductor es un
        # operador (más abajo), que es quien registra la gasolina de su ambulancia.
        "ambulances": [
            {"placa": "AMB-101", "tipo": "Avanzada", "hospital": "Hospital IMSS 220", "conductor": "Mariana Torres", "estado": "Libre", "tanque_litros": 80, "rendimiento_km_l": 6, "combustible_pct": 85, "kilometraje": 48210},
            {"placa": "AMB-102", "tipo": "Básica", "hospital": "Hospital IMSS 220", "conductor": "Ricardo Paredes", "estado": "Libre", "tanque_litros": 70, "rendimiento_km_l": 7, "combustible_pct": 60, "kilometraje": 61540},
            {"placa": "AMB-103", "tipo": "Avanzada", "hospital": "Hospital IMSS 220", "conductor": "Daniela Ibarra", "estado": "Libre", "tanque_litros": 80, "rendimiento_km_l": 6, "combustible_pct": 92, "kilometraje": 23980},
            {"placa": "AMB-104", "tipo": "Básica", "hospital": "Hospital IMSS 220", "conductor": "Jorge Salinas", "estado": "En reparación", "tanque_litros": 70, "rendimiento_km_l": 7, "combustible_pct": 40, "kilometraje": 90311},
            {"placa": "CRT-201", "tipo": "Avanzada", "hospital": "Cruz Roja Toluca", "conductor": "Elena Cruz", "estado": "Libre", "tanque_litros": 80, "rendimiento_km_l": 6, "combustible_pct": 70, "kilometraje": 35002},
            {"placa": "CRT-202", "tipo": "Básica", "hospital": "Cruz Roja Toluca", "conductor": "Pablo Núñez", "estado": "Libre", "tanque_litros": 70, "rendimiento_km_l": 7, "combustible_pct": 18, "kilometraje": 77120},
            {"placa": "NSJ-301", "tipo": "Avanzada", "hospital": "Hospital General Nicolás San Juan", "conductor": "Marcos Herrera", "estado": "Libre", "tanque_litros": 80, "rendimiento_km_l": 6, "combustible_pct": 66, "kilometraje": 52300},
            {"placa": "MET-401", "tipo": "Básica", "hospital": "Hospital IMSS 251", "conductor": "Lucía Gómez", "estado": "Libre", "tanque_litros": 70, "rendimiento_km_l": 7, "combustible_pct": 95, "kilometraje": 14880},
        ],
        "emergencies": [
            {"paciente_nombre": "Juan Pérez", "direccion": "Av. Independencia 300, Centro, Toluca", "descripcion": "Choque de dos autos, varios lesionados", "prioridad": "Alta", "estado": "Pendiente", "ambulancia": None, "ambulancias_requeridas": 5},
            {"paciente_nombre": "Rosa Díaz", "direccion": "Av. Morelos 1200, Toluca", "descripcion": "Dolor torácico, adulto mayor", "prioridad": "Alta", "estado": "Pendiente", "ambulancia": None, "ambulancias_requeridas": 1},
            {"paciente_nombre": "Luis Romero", "direccion": "Av. Tecnológico 100, Metepec", "descripcion": "Caída con posible fractura", "prioridad": "Media", "estado": "Pendiente", "ambulancia": None, "ambulancias_requeridas": 1},
        ],
        "operators": [
            {"nombre": "Mariana Torres", "experiencia": 8, "turno": "Matutino", "extension": "201", "estado": "En línea"},
            {"nombre": "Ricardo Paredes", "experiencia": 3, "turno": "Vespertino", "extension": "202", "estado": "En línea"},
            {"nombre": "Daniela Ibarra", "experiencia": 12, "turno": "Nocturno", "extension": "203", "estado": "En línea"},
            {"nombre": "Jorge Salinas", "experiencia": 1, "turno": "Matutino", "extension": "204", "estado": "Desconectado"},
            {"nombre": "Elena Cruz", "experiencia": 6, "turno": "Vespertino", "extension": "205", "estado": "En línea"},
            {"nombre": "Pablo Núñez", "experiencia": 10, "turno": "Nocturno", "extension": "206", "estado": "En línea"},
            {"nombre": "Marcos Herrera", "experiencia": 2, "turno": "Matutino", "extension": "207", "estado": "En línea"},
            {"nombre": "Lucía Gómez", "experiencia": 5, "turno": "Vespertino", "extension": "208", "estado": "En línea"},
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
