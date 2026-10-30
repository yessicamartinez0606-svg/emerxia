"""Rutas de la ambulancia sobre calles reales de Toluca, Metepec, San Mateo Atenco y Lerma (ver app/red_vial.py y app/busqueda.py).

    GET  /api/rutas/zona                 avenidas de la zona con su tráfico estimado
    GET  /api/rutas/geocodificar?q=      coordenadas de una dirección de la zona
    POST /api/rutas/calcular             ruta entre dos puntos con los cinco algoritmos (ciegos y heurísticos)
    GET  /api/rutas/emergencias/{id}     ruta del IMSS 220 a la emergencia y de regreso
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .. import readiness, red_vial
from ..repository import list_rows
from ..security import current_username

router = APIRouter(prefix="/api/rutas", tags=["rutas"], dependencies=[Depends(current_username)])

Hora = Query(None, ge=0, le=23, description="Hora del día (0-23) para estimar el tráfico. Sin valor: la hora actual.")


class Punto(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class CalcularIn(BaseModel):
    origen: Punto
    destino: Punto | None = None          # sin destino: el Hospital IMSS 220
    hora: int | None = Field(None, ge=0, le=23)


def _errores(fn):
    try:
        return fn()
    except red_vial.ServicioMapasError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/zona")
def zona(hora: int | None = Hora):
    return _errores(lambda: red_vial.zona(hora))


@router.get("/geocodificar")
def geocodificar(q: str = Query(..., min_length=3, description="Dirección a buscar (Toluca, Metepec, San Mateo Atenco o Lerma)")):
    return _errores(lambda: red_vial.geocodificar(q))


@router.post("/calcular")
def calcular(body: CalcularIn):
    destino = body.destino.model_dump() if body.destino else {"lat": red_vial.HOSPITAL["lat"], "lng": red_vial.HOSPITAL["lng"]}
    return _errores(lambda: red_vial.calcular_ruta(body.origen.model_dump(), destino, body.hora))


@router.get("/emergencias/{emergencia_id}", dependencies=[Depends(readiness.require_mongo)])
def ruta_emergencia(emergencia_id: int, hora: int | None = Hora):
    emergencia = next((r for r in list_rows("emergencies") if r.get("id") == emergencia_id), None)
    if not emergencia:
        raise HTTPException(404, "No existe esa emergencia.")

    def armar():
        lugar = red_vial.geocodificar(emergencia.get("direccion", ""))
        hospital = {"lat": red_vial.HOSPITAL["lat"], "lng": red_vial.HOSPITAL["lng"]}
        punto = {"lat": lugar["lat"], "lng": lugar["lng"]}
        ida = red_vial.calcular_ruta(hospital, punto, hora)
        regreso = red_vial.calcular_ruta(punto, hospital, ida["hora"], algoritmos=("costo_uniforme",))
        return {
            "emergencia": {"id": emergencia["id"], "folio": emergencia.get("folio"),
                           "direccion": emergencia.get("direccion"), "prioridad": emergencia.get("prioridad")},
            "hospital": red_vial.HOSPITAL,
            "lugar": lugar,
            "hora": ida["hora"],
            "periodo": ida["periodo"],
            "periodo_nombre": ida["periodo_nombre"],
            "ida": ida,
            "regreso": regreso["resultados"][0],
        }

    return _errores(armar)
