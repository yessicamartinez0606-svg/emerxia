"""Búsqueda ciega para la ruta de la ambulancia con tráfico (ver app/busqueda.py).

    GET  /api/busqueda/mapa       intersecciones, calles y tráfico por defecto
    POST /api/busqueda/resolver   ruta de inicial a meta con anchura, profundidad y costo uniforme
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import busqueda
from ..security import current_username

router = APIRouter(prefix="/api/busqueda", tags=["busqueda"], dependencies=[Depends(current_username)])

Algoritmo = Literal["anchura", "profundidad", "costo_uniforme"]


class ResolverIn(BaseModel):
    inicial: str = "BASE"
    meta: str = "IMSS"
    # Cambios al tráfico por defecto: {"c16": "libre", "c05": "bloqueado", ...}
    trafico: dict[str, Literal["libre", "moderado", "denso", "bloqueado"]] = Field(default_factory=dict)
    algoritmos: list[Algoritmo] = Field(default_factory=lambda: list(busqueda.ALGORITMOS))


@router.get("/mapa")
def obtener_mapa():
    return busqueda.mapa()


@router.post("/resolver")
def resolver_ruta(body: ResolverIn):
    if body.inicial == body.meta:
        raise HTTPException(422, "El punto de salida y el destino deben ser distintos.")
    try:
        return busqueda.resolver(body.inicial, body.meta, body.trafico, tuple(body.algoritmos))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
