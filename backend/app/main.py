import logging
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import readiness
from .config import settings
from .mongo import close_client
from .routers import auth, busqueda, despacho, flota, inteligencia, modules, portal, system, verificaciones
from .security import OPERADOR, PERSONAL, require_roles, solo_personal
from .spark import stop_spark

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("emergexia")
VERSION = "2.0-mongodb"


def _preparar_modelos():
    """Entrena los modelos de IA al arrancar (tardan unos segundos) para que la primera
    pantalla que los use no espere. Si falta scikit-learn, no pasa nada."""
    from . import a_tiempo, eta, optimizacion, segmentacion, triaje
    for m in (eta, a_tiempo, triaje, segmentacion):
        try:
            m.entrenar()
        except Exception:  # noqa: BLE001
            pass
    try:
        import sklearn  # noqa: F401
        optimizacion.iniciar()     # práctica 06: ~1 minuto en segundo plano (o al instante si ya se guardó)
    except ImportError:
        pass


def _flota_real_una_vez():
    """La primera vez que arranca, la flota toma vehículos reales de la API vPIC
    (app/vehiculos.py): marca, modelo y año a las ambulancias que no tienen y las que faltan
    en cada hospital. Queda anotado en "counters" para no repetirlo."""
    if not readiness.mongo_service.ready:
        return
    try:
        from .mongo import get_db
        from .routers.flota import importar_flota_real
        db = get_db()
        if db["counters"].find_one({"_id": "flota_real"}):
            return
        r = importar_flota_real("sistema")
        db["counters"].update_one({"_id": "flota_real"}, {"$set": {"hecho": True, "fuente": r["fuente"]}}, upsert=True)
        log.info("Flota con vehículos reales: %s", r["mensaje"])
    except Exception:  # noqa: BLE001
        log.exception("No se pudo preparar la flota con vehículos reales")


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("Emergexia API v%s · base de datos '%s' · %s", VERSION, settings.mongo_db, "MongoDB")
    try:
        readiness.mongo_service.ensure()   # conecta con MongoDB y crea datos de ejemplo la primera vez
    except Exception:                      # noqa: BLE001
        pass                               # la API arranca igual; el error se ve en /api/health y en la app
    threading.Thread(target=_preparar_modelos, daemon=True).start()
    threading.Thread(target=_flota_real_una_vez, daemon=True).start()
    yield
    stop_spark()
    close_client()


app = FastAPI(title="Emergexia API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, dependencies=[Depends(readiness.require_mongo)])   # usuarios en MongoDB
app.include_router(system.router)

# Perfiles (app/security.py): el personal de la central ve todo; el Operador y el Usuario
# solo usan su portal (app/routers/portal.py). El Operador también puede ver las rutas.
PERSONAL_DB = [Depends(readiness.require_mongo), Depends(solo_personal)]
for r in modules.routers:
    app.include_router(r, dependencies=PERSONAL_DB)
app.include_router(verificaciones.router, dependencies=PERSONAL_DB)
app.include_router(flota.router, dependencies=PERSONAL_DB)   # flota, gasolina, historial y reportes
app.include_router(portal.router, dependencies=[Depends(readiness.require_mongo)])   # portales Operador y Usuario
app.include_router(busqueda.router, dependencies=[Depends(require_roles(*PERSONAL, OPERADOR))])   # rutas (búsqueda ciega y heurística)
app.include_router(despacho.router, dependencies=[Depends(solo_personal)])   # algoritmo genético
app.include_router(inteligencia.router)   # clima de las zonas y tiempo estimado de llegada (regresión)

@app.get("/api/health")
def health():
    m, s = readiness.mongo_service, readiness.spark_service
    return {
        "status": "ok",
        "app": "Emergexia",
        "version": VERSION,
        "database": settings.mongo_db,
        "mongo_ready": m.ready,
        "mongo_error": m.last_error,
        "spark_ready": s.ready,          # Spark arranca bajo demanda
        "spark_error": s.last_error,
    }
