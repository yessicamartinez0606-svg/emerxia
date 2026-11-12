"""Triage con Machine Learning (ver app/ml/).

POST /api/ml/predecir  → ¿esta emergencia requiere ambulancia Avanzada? (signos vitales → sugerencia)
GET  /api/ml/reporte   → comparación de algoritmos y experimentos del último `python entrenar_ml.py`
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..security import current_username

router = APIRouter(prefix="/api/ml", tags=["ml"], dependencies=[Depends(current_username)])


class SignosVitalesIn(BaseModel):
    edad: float = Field(ge=0, le=120)
    frecuencia_cardiaca: float = Field(ge=20, le=250, description="latidos por minuto")
    saturacion_oxigeno: float = Field(ge=50, le=100, description="SpO2 en %")
    presion_sistolica: float = Field(ge=40, le=260, description="mmHg")
    glasgow: int = Field(ge=3, le=15)
    dolor_toracico: bool = False


def _modulo():
    # Import tardío: si scikit-learn no está instalado, el resto de la API sigue funcionando.
    try:
        from ..ml import prediccion
    except ImportError as exc:
        raise HTTPException(503, f"Falta instalar las dependencias de ML ({exc.name}). "
                                 "En la carpeta backend: pip install -r requirements.txt")
    return prediccion


@router.post("/predecir")
def predecir(body: SignosVitalesIn):
    datos = body.model_dump()
    datos["dolor_toracico"] = int(datos["dolor_toracico"])
    return _modulo().predecir(datos)


@router.get("/reporte")
def reporte():
    r = _modulo().reporte()
    if r is None:
        raise HTTPException(404, "Aún no hay reporte. En la carpeta backend ejecuta: python entrenar_ml.py")
    return r
