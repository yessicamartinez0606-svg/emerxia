"""Carga el modelo de triage y predice pacientes nuevos. Lo usa el router /api/ml.

Si todavía no se ha corrido `python entrenar_ml.py`, el modelo se entrena aquí mismo la
primera vez (tarda un par de segundos) con la configuración base, para que la API funcione.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import joblib
import pandas as pd

from .datos import VARIABLES, generar_datos
from .entrenamiento import comparar, dividir, entrenar_final

CARPETA = Path(__file__).resolve().parents[2] / "ml_resultados"
ARCHIVO_MODELO = CARPETA / "modelo_triage.joblib"
ARCHIVO_REPORTE = CARPETA / "reporte.json"

_lock = threading.Lock()
_cache: dict = {}


def _entrenar_y_guardar() -> dict:
    d = dividir(generar_datos())
    tabla = comparar(d)
    nombre = tabla.iloc[0]["algoritmo"]
    final = entrenar_final(nombre, d)
    paquete = {"modelo": final["modelo"], "algoritmo": nombre,
               "metricas_prueba": final["metricas_prueba"], "variables": VARIABLES}
    CARPETA.mkdir(exist_ok=True)
    joblib.dump(paquete, ARCHIVO_MODELO)
    return paquete


def cargar() -> dict:
    with _lock:
        if "paquete" not in _cache:
            _cache["paquete"] = joblib.load(ARCHIVO_MODELO) if ARCHIVO_MODELO.exists() else _entrenar_y_guardar()
        return _cache["paquete"]


def predecir(paciente: dict) -> dict:
    paquete = cargar()
    fila = pd.DataFrame([{v: paciente[v] for v in paquete["variables"]}])
    prob = float(paquete["modelo"].predict_proba(fila)[0][1])
    requiere = prob >= 0.5
    return {
        "requiere_avanzada": requiere,
        "probabilidad": round(prob, 3),
        "recomendacion": "Ambulancia Avanzada" if requiere else "Ambulancia Básica",
        "algoritmo": paquete["algoritmo"],
        "recall_prueba": round(paquete["metricas_prueba"]["recall"], 3),
        "aviso": "Sugerencia de un modelo educativo con datos sintéticos; la decisión es del personal médico.",
    }


def reporte() -> dict | None:
    """Resultados completos del último `python entrenar_ml.py` (comparación, experimentos, etc.)."""
    if not ARCHIVO_REPORTE.exists():
        return None
    return json.loads(ARCHIVO_REPORTE.read_text(encoding="utf-8"))
