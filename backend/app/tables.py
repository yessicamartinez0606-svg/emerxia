"""Tablas de Emergexia guardadas como Parquet y procesadas con Spark."""
from datetime import datetime, timezone

from functools import lru_cache

from .config import settings
from .spark import get_spark

# Esquemas como datos simples: así este módulo se puede importar aunque
# pyspark no esté instalado (los tipos reales se construyen al usarlos).
COLUMNS: dict[str, list[tuple[str, str]]] = {
    "ambulances": [
        ("id", "int"), ("placa", "str"), ("tipo", "str"),
        ("conductor", "str"), ("estado", "str"),
    ],
    "emergencies": [
        ("id", "int"), ("folio", "str"), ("descripcion", "str"),
        ("prioridad", "str"), ("estado", "str"), ("ambulancia", "str"),
        ("creado", "str"),
    ],
    "operators": [
        ("id", "int"), ("nombre", "str"), ("turno", "str"),
        ("extension", "str"), ("estado", "str"),
    ],
}


@lru_cache(maxsize=None)
def schema(name: str):
    """Construye el StructType de una tabla (importa pyspark solo al llamarse)."""
    from pyspark.sql.types import IntegerType, StringType, StructField, StructType

    kinds = {"int": IntegerType, "str": StringType}
    return StructType([StructField(n, kinds[k](), True) for n, k in COLUMNS[name]])


def _path(name: str) -> str:
    return f"{settings.data_dir.rstrip('/')}/{name}"


def _exists(name: str) -> bool:
    spark = get_spark()
    jvm = spark._jvm
    hadoop_path = jvm.org.apache.hadoop.fs.Path(_path(name))
    fs = hadoop_path.getFileSystem(spark._jsc.hadoopConfiguration())
    return fs.exists(hadoop_path)


def read_table(name: str):
    return get_spark().read.schema(schema(name)).parquet(_path(name))


def _write(name: str, rows: list[tuple], mode: str = "append") -> None:
    df = get_spark().createDataFrame(rows, schema(name))
    df.coalesce(1).write.mode(mode).parquet(_path(name))


def list_rows(name: str) -> list[dict]:
    return [r.asDict() for r in read_table(name).orderBy("id").collect()]


def next_id(name: str) -> int:
    from pyspark.sql import functions as F

    top = read_table(name).agg(F.max("id")).collect()[0][0]
    return (top or 0) + 1


def insert_row(name: str, data: dict) -> dict:
    row_id = next_id(name)
    data = {"id": row_id, **data}
    fields = [n for n, _ in COLUMNS[name]]
    _write(name, [tuple(data.get(f) for f in fields)])
    return data


def count_by(name: str, column: str) -> dict[str, int]:
    rows = read_table(name).groupBy(column).count().collect()
    return {(r[column] or "Sin dato"): r["count"] for r in rows}


def seed_if_empty() -> None:
    """Crea las tablas con datos de ejemplo la primera vez que arranca."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if not _exists("ambulances"):
        _write("ambulances", [
            (1, "AMB-101", "Avanzada", "Jorge Salinas", "Disponible"),
            (2, "AMB-102", "Básica", "Marcos Herrera", "En servicio"),
            (3, "AMB-103", "Avanzada", "Elena Cruz", "Disponible"),
            (4, "AMB-104", "Básica", "Pablo Núñez", "Mantenimiento"),
        ], "overwrite")

    if not _exists("emergencies"):
        _write("emergencies", [
            (1, "EMG-0001", "Accidente vehicular en Av. Reforma", "Alta", "En curso", "AMB-102", now),
            (2, "EMG-0002", "Dolor torácico, adulto mayor", "Alta", "Asignada", "AMB-101", now),
            (3, "EMG-0003", "Caída con posible fractura", "Media", "Pendiente", None, now),
        ], "overwrite")

    if not _exists("operators"):
        _write("operators", [
            (1, "Mariana Torres", "Matutino", "201", "En línea"),
            (2, "Ricardo Paredes", "Vespertino", "202", "En línea"),
            (3, "Daniela Ibarra", "Nocturno", "203", "Desconectado"),
        ], "overwrite")
