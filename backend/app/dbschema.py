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
    # Flota de ambulancias
    "ambulances": {
        "validator": _schema(
            {"id": NUM, "placa": STR, "tipo": STR, "estado": STR},
            {"conductor": STR, "hospital": STR, "tanque_litros": NUM, "rendimiento_km_l": NUM,
             "combustible_pct": NUM, "kilometraje": NUM, "emergencia_actual": [STR, "null"], "created_at": "date"},
        ),
        "indexes": [("id", True), ("placa", True), ("estado", False), ("hospital", False)],
    },
    # Emergencias atendidas
    "emergencies": {
        "validator": _schema(
            {"id": NUM, "folio": STR, "descripcion": STR, "prioridad": STR, "estado": STR},
            {"ambulancia": [STR, "null"], "ambulancias": "array", "ambulancias_requeridas": NUM,
             "hospital_salida": [STR, "null"],
             "saturacion_oxigeno": [NUM, "null"], "frecuencia_cardiaca": [NUM, "null"], "escala_glasgow": [NUM, "null"], "hospital_destino": [STR, "null"], "km_recorridos": [NUM, "null"],
             "respuestas": "array", "prioridad_motivos": "array", "reportes_adicionales": "array", "num_reportes": NUM,
             "paramedicos": "array", "atenciones_paramedico": "array",
             "created_at": "date"},
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
            {"extension": STR, "experiencia": [NUM, "null"], "foto": STR, "celular": STR, "correo": STR, "rostro": "array", "rostro_de": STR,
             "usuario": STR, "created_at": "date"},
        ),
        "indexes": [("id", True), ("estado", False)],
    },
    # Paramédicos (TUM) que van en las ambulancias. Su contraseña vive cifrada en su cuenta
    # (users, ligada con paramedico_id); aquí solo queda el nombre de usuario.
    "paramedics": {
        "validator": _schema(
            {"id": NUM, "nombre": STR, "nivel": STR, "turno": STR, "estado": STR},
            {"nombres": STR, "apellidos": STR, "celular": STR, "correo": STR, "cedula": STR, "ambulancia": STR,
             "tipo_sangre": STR, "contacto_emergencia": STR, "usuario": STR,
             "foto": STR, "rostro": "array", "rostro_de": STR, "created_at": "date"},
        ),
        "indexes": [("id", True), ("estado", False), ("ambulancia", False)],
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
    # Cargas de gasolina: las registra el operador que conduce la ambulancia.
    "cargas_combustible": {
        "validator": _schema(
            {"id": NUM, "ambulancia": STR, "operador": STR, "litros": NUM},
            {"costo": [NUM, "null"], "kilometraje": [NUM, "null"], "combustible_antes": NUM,
             "combustible_despues": NUM, "estacion": STR, "notas": STR, "verificado_facial": "bool",
             "registrado_por": STR, "created_at": "date"},
        ),
        "indexes": [("id", True), ("ambulancia", False), ("created_at", False)],
    },
    # Historial: cada cambio de estatus, asignación, carga de gasolina y paso de una emergencia.
    "historial": {
        "validator": _schema(
            {"id": NUM, "tipo": STR, "detalle": STR},
            {"ambulancia": [STR, "null"], "operador": [STR, "null"], "emergencia": [STR, "null"],
             "hospital": [STR, "null"], "usuario": [STR, "null"], "created_at": "date"},
        ),
        "indexes": [("id", True), ("ambulancia", False), ("emergencia", False), ("created_at", False)],
    },
    # Contadores internos para los id autoincrementales (sin validación)
    "counters": {"validator": None, "indexes": []},

    # ── Colecciones de las prácticas de IA (backend/ia_sistema_inteligente y backend/ia_bigdata) ──
    # Las llenan los scripts, no la API. Se declaran aquí para que existan con la misma
    # validación e índices que crean los scripts (mismos nombres de índice, así no chocan).
    # Análisis de emergencias con Random Forest, K-Means y PCA (p15, p18 y p19).
    "analisis_emergencias_ia": {
        "validator": _schema(
            {"id_analisis": STR, "sistema": STR, "fecha_registro": "date"},
            {"folio_emergencia": [STR, "null"], "id_atencion": STR, "etapa": NUM, "archivo_origen": STR},
        ),
        "indexes": [("id_analisis", True, "id_analisis_1"), ("fecha_registro", False, "fecha_registro_1"),
                    ("prioridad", False, "prioridad_1"), ("clasificacion.critica", False, "clasificacion.critica_1"),
                    ("folio_emergencia", False, "folio_emergencia_1")],
    },
    # Expediente de pacientes (p19): un documento por paciente.
    "pacientes_ia": {
        "validator": _schema({"id_paciente": STR}, {"nombre": STR, "fecha_creacion": "date"}),
        "indexes": [("id_paciente", True, "id_paciente_1")],
    },
    # Atenciones con sus tomas de signos vitales (p19); folio_emergencia liga con emergencies.folio.
    "atenciones_ia": {
        "validator": _schema(
            {"id_atencion": STR, "id_paciente": STR, "fecha_registro": "date"},
            {"folio_emergencia": [STR, "null"], "id_analisis": STR, "sistema": STR, "tomas": "array"},
        ),
        "indexes": [("id_atencion", True, "id_atencion_1"),
                    ([("id_paciente", ASCENDING), ("fecha_registro", DESCENDING)], False, "id_paciente_1_fecha_registro_-1"),
                    ("folio_emergencia", False, "folio_emergencia_1")],
    },
    # 50,000 servicios sintéticos de Big Data (p20 → p21 → p22); hospital_base usa los
    # mismos nombres que app/genetico.py.
    "servicios_ambulancia_masivos": {
        "validator": _schema(
            {"id_lote": STR, "id_registro": NUM, "id_ambulancia": STR, "hospital_base": STR, "tipo_emergencia": STR},
            {"fecha_carga": "date"},
        ),
        "indexes": [([("id_lote", ASCENDING), ("id_registro", ASCENDING)], True, "indice_lote_registro_unico"),
                    ("id_ambulancia", False, "indice_ambulancia"), ("hospital_base", False, "indice_hospital"),
                    ("tipo_emergencia", False, "indice_tipo")],
    },
}

# Colecciones que llenan los scripts de prácticas (no la API).
COLECCIONES_IA = ("analisis_emergencias_ia", "pacientes_ia", "atenciones_ia", "servicios_ambulancia_masivos")


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
        for index in spec["indexes"]:
            field, unique = index[0], index[1]
            if isinstance(field, list):            # índice compuesto: [(campo, dirección), ...]
                keys = field
            else:
                keys = [(field, DESCENDING if field == "created_at" else ASCENDING)]
            index_name = index[2] if len(index) > 2 else f"{field}_{'uniq' if unique else 'idx'}"
            try:
                db[name].create_index(keys, unique=unique, name=index_name)
            except OperationFailure as exc:
                log.warning("No se pudo crear el índice %s.%s: %s", name, index_name, exc)
    return created
