"""Colecciones ("tablas") de Emergexia en MongoDB: validación de campos e índices.

Se crean automáticamente al arrancar el backend (si ya existen, se actualizan sin perder datos).
Las validaciones exigen los campos esenciales y su tipo; los valores de estado/prioridad
se validan en la API (schemas.py), así puedes cambiarlos sin tocar la base.
"""
import logging

from pymongo import ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid, OperationFailure

from .mongo import get_db

log = logging.getLogger("emergexia")

STR = "string"
NUM = "number"          # cubre int32 / int64 / double


def _schema(required: dict[str, object], optional: dict[str, object] | None = None) -> dict:
    props = {**required, **(optional or {})}
    return {"$jsonSchema": {"bsonType": "object", "required": list(required), "properties": {k: {"bsonType": v} for k, v in props.items()}}}


DEFINITIONS: dict[str, dict] = {
    # Personas que pueden iniciar sesión en el sistema
    "users": {
        "validator": _schema(
            {"id": NUM, "username": STR, "password_hash": STR, "full_name": STR, "role": STR, "active": "bool"},
            {"created_at": "date"},
        ),
        "indexes": [("id", True), ("username", True)],
    },
    # Personal médico
    "doctors": {
        "validator": _schema(
            {"id": NUM, "nombre": STR, "especialidad": STR, "estado": STR},
            {"telefono": STR, "celular": STR, "correo": STR, "created_at": "date"},
        ),
        "indexes": [("id", True), ("estado", False)],
    },
    # Flota de ambulancias
    "ambulances": {
        "validator": _schema(
            {"id": NUM, "placa": STR, "tipo": STR, "estado": STR},
            {"conductor": STR, "created_at": "date"},
        ),
        "indexes": [("id", True), ("placa", True), ("estado", False)],
    },
    # Emergencias atendidas
    "emergencies": {
        "validator": _schema(
            {"id": NUM, "folio": STR, "descripcion": STR, "prioridad": STR, "estado": STR},
            {"ambulancia": [STR, "null"], "created_at": "date"},
        ),
        "indexes": [("id", True), ("folio", True), ("estado", False), ("created_at", False)],
    },
    # Operadores de la central
    "operators": {
        "validator": _schema(
            {"id": NUM, "nombre": STR, "turno": STR, "estado": STR},
            # "foto" no es requerida aquí (a nivel de MongoDB) para no romper
            # operadores que ya existían antes de esta función; la API
            # (schemas.py) sí la exige para operadores nuevos.
            {"extension": STR, "foto": STR, "celular": STR, "correo": STR, "created_at": "date"},
        ),
        "indexes": [("id", True), ("estado", False)],
    },
    # Bitácora de verificaciones por reconocimiento facial: queda registro de
    # cada vez que se comparó la cara de un operador contra su foto de
    # referencia, al asignarlo a una emergencia y al confirmar la salida de
    # la ambulancia.
    "verificaciones": {
        "validator": _schema(
            {"operador": STR, "contexto": STR, "coincide": "bool"},
            {"distancia": NUM, "emergencia_folio": [STR, "null"], "verificado_por": STR, "momento": "date"},
        ),
        "indexes": [("operador", False), ("momento", False)],
    },
    # Contadores internos para los id autoincrementales (sin validación)
    "counters": {"validator": None, "indexes": []},
}


def ensure_schema() -> list[str]:
    """Crea (o actualiza) las colecciones y sus índices. Devuelve el nombre de las creadas."""
    db = get_db()
    created: list[str] = []
    for name, spec in DEFINITIONS.items():
        validator = spec["validator"]
        try:
            try:
                if validator:
                    db.create_collection(name, validator=validator, validationLevel="strict", validationAction="error")
                else:
                    db.create_collection(name)
            except CollectionInvalid:
                raise
            except OperationFailure as exc:
                # Si el servidor no acepta la validación, se crea la colección igual (sin validar).
                log.warning("Se crea %s sin validación: %s", name, exc)
                db.create_collection(name)
            created.append(name)
        except CollectionInvalid:
            # Ya existía: se actualiza la validación en modo "moderate" (no rechaza datos previos).
            if validator:
                try:
                    db.command("collMod", name, validator=validator, validationLevel="moderate")
                except OperationFailure as exc:
                    log.warning("No se pudo actualizar la validación de %s: %s", name, exc)
        for field, unique in spec["indexes"]:
            direction = DESCENDING if field == "created_at" else ASCENDING
            try:
                db[name].create_index([(field, direction)], unique=unique, name=f"{field}_{'uniq' if unique else 'idx'}")
            except OperationFailure as exc:
                log.warning("No se pudo crear el índice %s.%s: %s", name, field, exc)
    return created
