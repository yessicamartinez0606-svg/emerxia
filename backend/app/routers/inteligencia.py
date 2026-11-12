"""Clima de las zonas y tiempo estimado de llegada (ver app/clima.py y app/eta.py).

    GET  /api/clima                          clima de cada zona y cuánto se frena el tránsito
    POST /api/clima/simular                  simula lluvia (o la quita) en una zona para demostrar
    GET  /api/eta/modelo                     calificación del modelo contra la fórmula fija
    POST /api/eta/estimar                    estima minutos para datos que se escriben a mano
    GET  /api/eta/emergencias/{id}           tiempo estimado de llegada a una emergencia

    Práctica 04 (app/a_tiempo.py): ¿la ambulancia llegará en 15 min o menos?
    GET  /api/ia/a-tiempo/modelo             profundidades, validación, prueba, matriz y validación cruzada
    POST /api/ia/a-tiempo/estimar            datos escritos a mano
    GET  /api/ia/a-tiempo/emergencias/{id}   con los datos reales de la emergencia

    Práctica 05 (app/triaje.py): ¿la emergencia es crítica?
    GET  /api/ia/triaje/modelo               árbol vs bosque aleatorio vs KNN y experimentos A, B, C
    POST /api/ia/triaje/estimar              signos vitales escritos a mano
    GET  /api/ia/triaje/cola                 emergencias abiertas ordenadas por probabilidad de ser críticas
    GET  /api/ia/triaje/emergencias/{id}

    Práctica 06 (app/optimizacion.py): GridSearchCV y RandomizedSearchCV del triaje
    GET  /api/ia/optimizacion                estado ("entrenando" / "listo") y resultados
    POST /api/ia/optimizacion/iniciar        vuelve a lanzarla si falló

    Práctica 07 (app/segmentacion.py): perfiles de servicio con K-Means
    GET  /api/ia/segmentacion/modelo         codo, silhouette, perfiles y puntos
    POST /api/ia/segmentacion/estimar        datos escritos a mano
    GET  /api/ia/segmentacion/emergencias/{id}
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .. import a_tiempo, clima, eta, flota, optimizacion, readiness, segmentacion, triaje
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
    except (eta.SinScikitLearn, a_tiempo.SinScikitLearn, triaje.SinScikitLearn, segmentacion.SinScikitLearn) as exc:
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


def _emergencia(emergencia_id: int) -> dict:
    em = next((e for e in list_rows("emergencies") if e.get("id") == emergencia_id), None)
    if not em:
        raise HTTPException(404, "No existe esa emergencia.")
    return em


def _ubicacion(em: dict) -> tuple[float, float]:
    if em.get("lat") is not None and em.get("lng") is not None:
        return em["lat"], em["lng"]
    from .. import red_vial
    try:
        lugar = red_vial.geocodificar(em.get("direccion", ""))
    except red_vial.ServicioMapasError as exc:
        raise HTTPException(503, f"No se pudo ubicar la emergencia: {exc}") from exc
    return lugar["lat"], lugar["lng"]


def _distancia(em: dict, km: float | None) -> float:
    if km:
        return km
    from .. import red_vial
    lat, lng = _ubicacion(em)
    h = red_vial.HOSPITAL
    return eta.distancia_desde_hospital(lat, lng, h["lat"], h["lng"])


ETA_CLIMA = ("zona", "descripcion", "temperatura", "lluvia", "tormenta", "simulado", "velocidad_relativa")


@router.get("/api/eta/emergencias/{emergencia_id}",
            dependencies=[Depends(readiness.require_mongo), Depends(personal_y_operador)])
def eta_emergencia(emergencia_id: int, km: float | None = Query(None, gt=0, le=100,
                                                                  description="Km de la ruta, si ya se calculó")):
    em = _emergencia(emergencia_id)

    def calcular():
        lat, lng = _ubicacion(em)
        distancia = _distancia(em, km)
        cond = clima.lluvia_en(lat, lng)
        ahora = eta.ahora_mx()
        finde = int(ahora.weekday() >= 5)
        r = eta.estimar(cond["zona"], distancia, ahora.hour, finde, int(cond["lluvia"]))
        return {**r, "folio": em.get("folio"), "distancia_fuente": "ruta" if km else "aproximada",
                "clima": {k: cond.get(k) for k in ETA_CLIMA}}
    return _modelo(calcular)


# ─────────────── Práctica 04: ¿llega a tiempo? ───────────────

class ATiempoIn(BaseModel):
    distancia_km: float = Field(gt=0, le=100)
    nivel_trafico: float = Field(ge=0, le=10)
    ambulancias_libres: int = Field(ge=0, le=50)
    experiencia_operador: float = Field(ge=0, le=50)


@router.get("/api/ia/a-tiempo/modelo", dependencies=[Depends(solo_personal)])
def a_tiempo_modelo():
    return _modelo(a_tiempo.evaluacion)


@router.post("/api/ia/a-tiempo/estimar", dependencies=[Depends(solo_personal)])
def a_tiempo_estimar(body: ATiempoIn):
    return _modelo(lambda: a_tiempo.estimar(body.distancia_km, body.nivel_trafico, body.ambulancias_libres,
                                            body.experiencia_operador))


def _libres_en_base() -> int:
    return sum(1 for a in map(flota.normalizar, list_rows("ambulances"))
               if a.get("hospital") == flota.HOSPITAL_BASE and a.get("estado") == "Libre"
               and not flota.motivo_no_disponible(a))


def _experiencia(em: dict) -> tuple[float, str]:
    nombre = (em.get("operador") or "").strip().lower()
    op = next((o for o in list_rows("operators") if (o.get("nombre") or "").strip().lower() == nombre), None) if nombre else None
    if not op:
        return a_tiempo.EXPERIENCIA_SIN_DATO, "sin operador asignado (se usa el promedio)"
    if op.get("experiencia") is None:
        return a_tiempo.EXPERIENCIA_SIN_DATO, f"{op['nombre']} sin años capturados (se usa el promedio)"
    return float(op["experiencia"]), op["nombre"]


@router.get("/api/ia/a-tiempo/emergencias/{emergencia_id}",
            dependencies=[Depends(readiness.require_mongo), Depends(personal_y_operador)])
def a_tiempo_emergencia(emergencia_id: int, km: float | None = Query(None, gt=0, le=100)):
    em = _emergencia(emergencia_id)

    def calcular():
        lat, lng = _ubicacion(em)
        cond = clima.lluvia_en(lat, lng)
        ahora = eta.ahora_mx()
        trafico = a_tiempo.trafico_0_10(ahora.hour, cond["velocidad_relativa"])
        experiencia, de_quien = _experiencia(em)
        # Si la emergencia ya tiene ambulancias, cuentan las que quedaban libres más las suyas
        # (el modelo pregunta cuántas había libres al momento del reporte).
        libres = _libres_en_base() + (len(em.get("ambulancias") or []) if em.get("estado") != "Pendiente" else 0)
        r = a_tiempo.estimar(_distancia(em, km), trafico, libres, experiencia)
        return {**r, "folio": em.get("folio"), "operador": de_quien, "hora": ahora.hour,
                "lluvia": cond["lluvia"], "zona": cond["zona"], "distancia_fuente": "ruta" if km else "aproximada"}
    return _modelo(calcular)


# ─────────────── Práctica 05: triaje (¿es crítica?) ───────────────

class SignosIn(BaseModel):
    saturacion_oxigeno: float = Field(ge=50, le=100)
    frecuencia_cardiaca: float = Field(ge=20, le=250)
    escala_glasgow: int = Field(ge=3, le=15)
    edad: float = Field(ge=0, le=120)


@router.get("/api/ia/triaje/modelo", dependencies=[Depends(solo_personal)])
def triaje_modelo():
    return _modelo(triaje.evaluacion)


@router.post("/api/ia/triaje/estimar", dependencies=[Depends(solo_personal)])
def triaje_estimar(body: SignosIn):
    return _modelo(lambda: triaje.clasificar(body.model_dump()))


def _triaje_de(em: dict) -> dict | None:
    if not triaje.tiene_signos(em):
        return None
    try:
        return triaje.clasificar(triaje.signos_de(em))
    except ValueError:
        return None


@router.get("/api/ia/triaje/cola", dependencies=[Depends(readiness.require_mongo), Depends(solo_personal)])
def triaje_cola():
    def calcular():
        abiertas = [e for e in list_rows("emergencies") if e.get("estado") != "Cerrada"]
        con, sin = [], []
        for e in abiertas:
            base = {k: e.get(k) for k in ("id", "folio", "descripcion", "prioridad", "estado", "paciente_nombre")}
            t = _triaje_de(e)
            (con if t else sin).append({**base, "triaje": t} if t else base)
        con.sort(key=lambda x: -x["triaje"]["probabilidad"])
        return {"cola": con, "sin_signos": sin, "algoritmo": triaje.entrenar()["elegido"]}
    return _modelo(calcular)


@router.get("/api/ia/triaje/emergencias/{emergencia_id}",
            dependencies=[Depends(readiness.require_mongo), Depends(personal_y_operador)])
def triaje_emergencia(emergencia_id: int):
    em = _emergencia(emergencia_id)

    def calcular():
        if not triaje.tiene_signos(em):
            return {"folio": em.get("folio"), "sin_signos": True,
                    "mensaje": "Captura saturación, frecuencia cardiaca y Glasgow para estimar si es crítica."}
        edad_capturada = str(em.get("paciente_edad") or "").strip() != ""
        return {**triaje.clasificar(triaje.signos_de(em)), "folio": em.get("folio"), "sin_signos": False,
                "edad_estimada": not edad_capturada}
    return _modelo(calcular)


# ─────────────── Práctica 06: optimización de hiperparámetros ───────────────

def _sin_sklearn() -> str | None:
    try:
        import sklearn  # noqa: F401
        return None
    except ImportError:
        return "Falta instalar numpy, pandas y scikit-learn: pip install -r requirements.txt"


@router.get("/api/ia/optimizacion", dependencies=[Depends(solo_personal)])
def ver_optimizacion():
    if (falta := _sin_sklearn()):
        raise HTTPException(503, falta)
    if optimizacion.estado()["estado"] == "pendiente":
        optimizacion.iniciar()
    return optimizacion.estado()


@router.post("/api/ia/optimizacion/iniciar", dependencies=[Depends(solo_personal)])
def iniciar_optimizacion():
    if (falta := _sin_sklearn()):
        raise HTTPException(503, falta)
    return optimizacion.iniciar()


# ─────────────── Práctica 07: perfiles de servicio (K-Means) ───────────────

class ServicioIn(BaseModel):
    distancia_km: float = Field(gt=0, le=100)
    nivel_trafico: float = Field(ge=0, le=10)
    tiempo_respuesta_min: float = Field(gt=0, le=180)
    ambulancias_libres: float = Field(ge=0, le=50)


@router.get("/api/ia/segmentacion/modelo", dependencies=[Depends(solo_personal)])
def segmentacion_modelo():
    return _modelo(segmentacion.evaluacion)


@router.post("/api/ia/segmentacion/estimar", dependencies=[Depends(solo_personal)])
def segmentacion_estimar(body: ServicioIn):
    return _modelo(lambda: segmentacion.clasificar(body.distancia_km, body.nivel_trafico, body.tiempo_respuesta_min,
                                                   body.ambulancias_libres))


@router.get("/api/ia/segmentacion/emergencias/{emergencia_id}",
            dependencies=[Depends(readiness.require_mongo), Depends(personal_y_operador)])
def segmentacion_emergencia(emergencia_id: int, km: float | None = Query(None, gt=0, le=100)):
    em = _emergencia(emergencia_id)

    def calcular():
        lat, lng = _ubicacion(em)
        cond = clima.lluvia_en(lat, lng)
        ahora = eta.ahora_mx()
        distancia = _distancia(em, km)
        trafico = a_tiempo.trafico_0_10(ahora.hour, cond["velocidad_relativa"])
        # El tiempo de respuesta todavía no ocurre: se usa el que estima el modelo de llegada.
        minutos = eta.estimar(cond["zona"], distancia, ahora.hour, int(ahora.weekday() >= 5), int(cond["lluvia"]))["modelo_min"]
        libres = _libres_en_base() + (len(em.get("ambulancias") or []) if em.get("estado") != "Pendiente" else 0)
        return {**segmentacion.clasificar(distancia, trafico, minutos, libres), "folio": em.get("folio"),
                "tiempo_estimado": True}
    return _modelo(calcular)
