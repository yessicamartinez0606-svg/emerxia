"""Avisos al instante para la central cuando un usuario reporta una emergencia.

    GET /api/eventos/emergencias?desde=ID   flujo de eventos (Server-Sent Events, text/event-stream)

Cada conexión dura como máximo DURACION_MAX segundos y luego se cierra sola; la pantalla se
vuelve a conectar al instante pidiendo «desde» el último id que vio, y el servidor le manda
primero las emergencias nuevas que hubo en ese hueco. Así ningún aviso se pierde y el
servidor nunca se queda esperando una conexión eterna al reiniciarse (uvicorn --reload o un
redespliegue en Render esperan a que se cierren todas las conexiones).

Cómo se entera: con los «change streams» de MongoDB. El servidor se queda escuchando la
colección emergencies y, en cuanto se guarda una emergencia reportada por un usuario (o
alguien más reporta la misma), manda el aviso a las pantallas de la central conectadas. No
hay que recargar ni esperar.

Los change streams solo existen en MongoDB con réplicas (Atlas siempre lo es). Si la base es
un MongoDB local sin réplicas, se usa el plan B: revisar la colección cada SEGUNDOS_CONSULTA
segundos. Lo que llega a la pantalla es igual en los dos casos; el primer evento («listo»)
dice qué modo se usa.

Eventos (cada uno es una línea «data: {json}»):
    {"evento": "listo", "modo": "change_stream" | "consulta", "ultimo_id": N}
    {"evento": "nueva", ...emergencia}          un usuario reportó una emergencia nueva
    {"evento": "otro_reporte", ...emergencia}   otra persona reportó la misma (app/reportes.py)
"""
import asyncio
import json
import logging
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pymongo.errors import OperationFailure, PyMongoError

from ..mongo import get_db
from ..security import solo_personal

log = logging.getLogger("emergexia")
router = APIRouter(prefix="/api/eventos", tags=["eventos"])

SEGUNDOS_CONSULTA = 3
DURACION_MAX = 25             # segundos por conexión (luego la pantalla se reconecta sola)
SEGUNDOS_LATIDO = 15          # comentario «: latido» para que proxys y navegador no corten

# Solo interesan las emergencias que reportan los usuarios: las nuevas y cuando otra persona
# reporta la misma (sube num_reportes).
PIPELINE = [{"$match": {"$or": [
    {"operationType": "insert", "fullDocument.reportado_por": {"$exists": True}},
    {"operationType": "update", "updateDescription.updatedFields.num_reportes": {"$exists": True}},
]}}]

CAMPOS = ("id", "folio", "tipo", "prioridad", "prioridad_motivos", "direccion", "canal", "reportante",
          "num_reportes", "estado", "created_at", "personas", "ambulancias_requeridas")


def resumen(em: dict, evento: str) -> dict:
    return {"evento": evento, **{k: em.get(k) for k in CAMPOS}}


def evento_de_cambio(change: dict) -> dict | None:
    """Convierte un cambio de MongoDB en el aviso para la pantalla (o None si no aplica)."""
    em = change.get("fullDocument")
    if not em:
        return None
    if change.get("operationType") == "insert":
        return resumen(em, "nueva") if em.get("reportado_por") else None
    if change.get("operationType") == "update" and int(em.get("num_reportes") or 1) > 1:
        return resumen(em, "otro_reporte")
    return None


def _sse(datos: dict) -> str:
    return f"data: {json.dumps(datos, default=str, ensure_ascii=False)}\n\n"


async def _con_change_stream(request: Request, stream, fin: float):
    ultimo = time.monotonic()
    try:
        while time.monotonic() < fin and not await request.is_disconnected():
            change = await asyncio.to_thread(stream.try_next)   # espera hasta 1 s
            ev = evento_de_cambio(change) if change else None
            if ev:
                ultimo = time.monotonic()
                yield _sse(ev)
            elif time.monotonic() - ultimo > SEGUNDOS_LATIDO:
                ultimo = time.monotonic()
                yield ": latido\n\n"
    finally:
        stream.close()


def _foto_de_reportes(col) -> tuple[int, dict[int, int]]:
    """Último id y cuántos reportes tiene cada emergencia abierta reportada por usuarios."""
    ultimo = col.find_one({}, {"id": 1}, sort=[("id", -1)])
    abiertas = {e["id"]: int(e.get("num_reportes") or 1)
                for e in col.find({"estado": {"$ne": "Cerrada"}, "reportado_por": {"$exists": True}},
                                  {"_id": 0, "id": 1, "num_reportes": 1})}
    return (ultimo or {}).get("id", 0), abiertas


async def _con_consultas(request: Request, col, fin: float, ultimo_id: int):
    """Plan B sin change streams: revisa la colección cada pocos segundos."""
    _, reportes = await asyncio.to_thread(_foto_de_reportes, col)
    latido = time.monotonic()
    while time.monotonic() < fin and not await request.is_disconnected():
        await asyncio.sleep(SEGUNDOS_CONSULTA)
        nuevas = await asyncio.to_thread(lambda: list(col.find({"id": {"$gt": ultimo_id}}, {"_id": 0}).sort("id", 1)))
        for em in nuevas:
            ultimo_id = max(ultimo_id, em["id"])
            if em.get("reportado_por"):
                reportes[em["id"]] = int(em.get("num_reportes") or 1)
                yield _sse(resumen(em, "nueva"))
        if reportes:
            actuales = await asyncio.to_thread(lambda: list(col.find({"id": {"$in": list(reportes)}}, {"_id": 0})))
            for em in actuales:
                n = int(em.get("num_reportes") or 1)
                if n > reportes.get(em["id"], 1):
                    yield _sse(resumen(em, "otro_reporte"))
                reportes[em["id"]] = n
        if time.monotonic() - latido > SEGUNDOS_LATIDO:
            latido = time.monotonic()
            yield ": latido\n\n"


@router.get("/emergencias", dependencies=[Depends(solo_personal)])
async def eventos_emergencias(request: Request, desde: int | None = None):
    col = get_db()["emergencies"]
    fin = time.monotonic() + DURACION_MAX
    ultimo_id = (await asyncio.to_thread(_foto_de_reportes, col))[0]
    try:
        stream = await asyncio.to_thread(col.watch, PIPELINE, full_document="updateLookup", max_await_time_ms=1000)
        modo = "change_stream"
    except OperationFailure as exc:       # p. ej. MongoDB local sin réplicas (código 40573)
        log.info("Sin change streams (%s): avisos por consulta cada %s s", exc.code, SEGUNDOS_CONSULTA)
        stream, modo = None, "consulta"

    async def flujo():
        yield _sse({"evento": "listo", "modo": modo, "ultimo_id": ultimo_id})
        try:
            # Lo que llegó mientras la pantalla se reconectaba (solo si dice desde dónde).
            if desde is not None and desde < ultimo_id:
                hueco = await asyncio.to_thread(lambda: list(col.find(
                    {"id": {"$gt": desde, "$lte": ultimo_id}, "reportado_por": {"$exists": True}}, {"_id": 0}).sort("id", 1)))
                for em in hueco[-10:]:
                    yield _sse(resumen(em, "nueva"))
            if stream is not None:
                async for x in _con_change_stream(request, stream, fin):
                    yield x
            else:
                async for x in _con_consultas(request, col, fin, ultimo_id):
                    yield x
            yield _sse({"evento": "reconectar"})
        except PyMongoError as exc:
            log.warning("Se cortó el flujo de avisos: %s", exc)
            yield _sse({"evento": "error", "mensaje": "Se perdió la conexión con los avisos. Reconectando…"})
        finally:
            if stream is not None:
                stream.close()

    return StreamingResponse(flujo(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
