import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import readiness
from .config import settings
from .mongo import close_client
from .routers import auth, busqueda, despacho, flota, modules, portal, system, verificaciones
from .security import OPERADOR, PERSONAL, require_roles, solo_personal
from .spark import stop_spark

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("emergexia")
VERSION = "2.0-mongodb"


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("Emergexia API v%s · base de datos '%s' · %s", VERSION, settings.mongo_db, "MongoDB")
    try:
        readiness.mongo_service.ensure()   # conecta con MongoDB y crea datos de ejemplo la primera vez
    except Exception:                      # noqa: BLE001
        pass                               # la API arranca igual; el error se ve en /api/health y en la app
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
