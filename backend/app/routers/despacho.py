"""Despacho de ambulancia con algoritmo genético (ver app/genetico.py).

    GET  /api/despacho/hospitales   hospitales y bases de ambulancias de la zona
    POST /api/despacho/resolver     elige de qué hospital sale la ambulancia y a cuál regresa
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import genetico
from ..security import current_username

router = APIRouter(prefix="/api/despacho", tags=["despacho"], dependencies=[Depends(current_username)])


class Punto(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class ResolverIn(BaseModel):
    accidente: Punto
    ambulancias: dict[str, int] = {}               # id del hospital → ambulancias disponibles
    mismo_hospital: bool = True
    poblacion: int = Field(100, ge=2, le=2000)
    generaciones: int = Field(100, ge=1, le=1000)
    prob_mutacion: float = Field(0.2, ge=0, le=1)
    velocidad_kmh: float = Field(40, gt=0, le=200)
    minutos_en_lugar: float = Field(10, ge=0, le=240)


@router.get("/hospitales")
def hospitales():
    return {"hospitales": genetico.HOSPITALES}


@router.post("/resolver")
def resolver(body: ResolverIn):
    try:
        return genetico.despachar(
            body.accidente.model_dump(), body.ambulancias, body.mismo_hospital, body.poblacion,
            body.generaciones, body.prob_mutacion, body.velocidad_kmh, body.minutos_en_lugar,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
