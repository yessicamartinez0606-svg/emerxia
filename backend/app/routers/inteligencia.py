"""Clima de las zonas y tiempo estimado de llegada (ver app/clima.py y app/eta.py).

    GET  /api/clima                          clima de cada zona y cuánto se frena el tránsito
    POST /api/clima/simular                  simula lluvia (o la quita) en una zona para demostrar
    GET  /api/eta/modelo                     calificación del modelo contra la fórmula fija
    POST /api/eta/estimar                    estima minutos para datos que se escriben a mano
    GET  /api/eta/emergencias/{id}           tiempo estimado de llegada a una emergencia
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .. import clima, eta, readiness
from ..repository import list_rows
from ..security import OPERADOR, PERSONAL, require_roles

router = APIRouter(tags=["inteligencia"])
personal_y_operador = require_roles(*PERSONAL, OPERADOR)
solo_personal = require_roles(*PERSONAL)


class SimularIn(BaseModel):
    zona: str
    lluvia: bool | None = None       # None = volver al clima real


class EstimarIn(BaseModel):
    zona: str
    distancia_km: float = Field(gt=0, le=100)
    hora: int = Field(ge=0, le=23)
    fin_de_semana: bool = False
    lluvia: bool | None = None       # None = usar el clima actual de la zona


def _modelo(fn):
    try:
        return fn()
    except eta.SinScikitLearn as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/api/clima", dependencies=[Depends(personal_y_operador)])
def ver_clima():
    return clima.resumen()


@router.post("/api/clima/simular", dependencies=[Depends(solo_personal)])
def simular_clima(body: SimularIn):
    try:
        return clima.simular(body.zona, body.lluvia)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/api/eta/modelo", dependencies=[Depends(solo_personal)])
def modelo():
    return _modelo(eta.evaluacion)


@router.post("/api/eta/estimar", dependencies=[Depends(solo_personal)])
def estimar(body: EstimarIn):
    def calcular():
        z = next((x for x in clima.ZONAS if x["nombre"] == body.zona), None)
        if not z:
            raise ValueError("Elige una de las zonas de la lista.")
        llueve = body.lluvia if body.lluvia is not None else clima.lluvia_en(z["lat"], z["lng"])["lluvia"]
        return eta.estimar(body.zona, body.distancia_km, body.hora, int(body.fin_de_semana), int(llueve))
    return _modelo(calcular)


@router.get("/api/eta/emergencias/{emergencia_id}",
            dependencies=[Depends(readiness.require_mongo), Depends(personal_y_operador)])
def eta_emergencia(emergencia_id: int, km: float | None = Query(None, gt=0, le=100,
                                                                  description="Km de la ruta, si ya se calculó")):
    em = next((e for e in list_rows("emergencies") if e.get("id") == emergencia_id), None)
    if not em:
        raise HTTPException(404, "No existe esa emergencia.")
    from .. import red_vial

    def calcular():
        if em.get("lat") is not None and em.get("lng") is not None:
            lat, lng = em["lat"], em["lng"]
        else:
            try:
                lugar = red_vial.geocodificar(em.get("direccion", ""))
            except red_vial.ServicioMapasError as exc:
                raise HTTPException(503, f"No se pudo ubicar la emergencia para estimar el tiempo: {exc}") from exc
            lat, lng = lugar["lat"], lugar["lng"]
        h = red_vial.HOSPITAL
        distancia = km or eta.distancia_desde_hospital(lat, lng, h["lat"], h["lng"])
        cond = clima.lluvia_en(lat, lng)
        ahora = eta.ahora_mx()
        finde = int(ahora.weekday() >= 5)
        r = eta.estimar(cond["zona"], distancia, ahora.hour, finde, int(cond["lluvia"]))
        return {**r, "folio": em.get("folio"), "distancia_fuente": "ruta" if km else "aproximada",
                "clima": {k: cond.get(k) for k in ("zona", "descripcion", "temperatura", "lluvia", "tormenta", "simulado",
                                                   "velocidad_relativa")}}
    return _modelo(calcular)
