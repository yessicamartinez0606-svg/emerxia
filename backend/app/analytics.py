"""Análisis con Spark sobre los datos que viven en MongoDB."""
from .repository import list_rows
from .spark import get_spark

SOURCES = {"ambulancias": "ambulances", "emergencias": "emergencies", "operadores": "operators"}


def count_by_state() -> dict[str, dict[str, int]]:
    """Conteo por estado de cada módulo: los documentos de Mongo se procesan con un DataFrame de Spark."""
    spark = get_spark()
    result: dict[str, dict[str, int]] = {}
    for key, collection in SOURCES.items():
        states = [(row.get("estado") or "Sin dato",) for row in list_rows(collection)]
        if not states:
            result[key] = {}
            continue
        df = spark.createDataFrame(states, ["estado"])
        result[key] = {r["estado"]: r["count"] for r in df.groupBy("estado").count().collect()}
    return result
