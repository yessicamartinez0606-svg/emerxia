"""Arranque perezoso y seguro de MongoDB y Spark.

Si uno falla, la API sigue viva, explica el motivo (503) y reintenta en la siguiente petición.
"""
import logging
import re
import threading

from fastapi import HTTPException

from . import dbschema, mongo, repository
from .config import settings
from .spark import get_spark

log = logging.getLogger("emergexia")


def _short(exc: Exception) -> str:
    """La línea más útil de un error (la causa 'Caused by' de Java si existe)."""
    text = str(exc).strip() or type(exc).__name__
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    causes = [ln for ln in lines if ln.startswith("Caused by") or re.match(r"^[\w.$]+(Exception|Error)\b", ln)]
    return (causes[-1] if causes else (lines[0] if lines else type(exc).__name__))[:300]


class Service:
    def __init__(self, name: str, start):
        self.name = name
        self._start = start
        self._lock = threading.Lock()
        self.ready = False
        self.last_error: str | None = None

    def ensure(self) -> None:
        if self.ready:
            return
        with self._lock:
            if self.ready:
                return
            try:
                self._start()
                self.ready = True
                self.last_error = None
            except Exception as exc:  # noqa: BLE001
                self.last_error = str(exc) if isinstance(exc, RuntimeError) else f"{type(exc).__name__}: {_short(exc)}"
                log.exception("No se pudo iniciar %s", self.name)
                raise

    def require(self) -> None:
        """Dependencia de FastAPI: 503 con el motivo si el servicio no está disponible."""
        try:
            self.ensure()
        except Exception:  # noqa: BLE001
            raise HTTPException(503, f"{self.name} no está disponible. {self.last_error}")


def _start_mongo() -> None:
    mongo.connect()
    created = dbschema.ensure_schema()      # crea colecciones, validaciones e índices
    if created:
        log.info("Colecciones creadas en MongoDB: %s", ", ".join(created))
    # Solo si la base está vacía: el primer administrador (datos de ADMIN_* en el entorno),
    # para poder entrar y crear lo demás. No se crea ningún otro dato de ejemplo.
    repository.seed_admin()


mongo_service = Service("MongoDB", _start_mongo)
spark_service = Service("Spark", get_spark)   # se inicia bajo demanda (tarda unos segundos)

require_mongo = mongo_service.require
require_spark = spark_service.require
