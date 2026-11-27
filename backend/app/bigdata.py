"""Prácticas 20 a 27 (backend/ia_bigdata): Big Data con Spark y Deep Learning con PyTorch.

Esas prácticas son scripts pesados (50,000 registros, Spark, CNN), así que no corren dentro de
la API. Al terminarlas, `backend/ia_bigdata/exportar_resumen_sistema.py` guarda sus resultados en
`app/datos_ia/bigdata_resumen.json` y este módulo solo los lee para el panel
«Big Data y predicción» del Asistente de despacho.
"""
import json
from functools import lru_cache
from pathlib import Path

RUTA = Path(__file__).resolve().parent / "datos_ia" / "bigdata_resumen.json"


class SinResumen(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _leer(mtime: float) -> dict:
    with open(RUTA, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def resumen() -> dict:
    if not RUTA.exists():
        raise SinResumen(
            "Todavía no hay resultados de las prácticas 20 a 27. Córrelas en backend/ia_bigdata "
            "y después ejecuta exportar_resumen_sistema.py."
        )
    return _leer(RUTA.stat().st_mtime)
