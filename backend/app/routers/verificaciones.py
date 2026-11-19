"""Bitácora de verificaciones por reconocimiento facial.

La decisión de si un rostro coincide la toma el servidor (routers/auth.py: reconocer y
coincide_con), que también escribe aquí cada intento. El navegador solo calcula los 128
números del rostro de la foto recién tomada.

POST /api/verificaciones se conserva solo por compatibilidad (las pantallas ya no lo usan):
lo que se registra por aquí queda marcado como "reportado por el navegador".
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..mongo import get_db
from ..schemas import VerificacionIn
from ..security import current_username

router = APIRouter(prefix="/api/verificaciones", tags=["verificaciones"], dependencies=[Depends(current_username)])


@router.post("", status_code=201)
def registrar_verificacion(body: VerificacionIn, usuario: str = Depends(current_username)):
    doc = {
        **body.model_dump(),
        "verificado_por": usuario,
        "reportado_por_navegador": True,
        "momento": datetime.now(timezone.utc),
    }
    get_db()["verificaciones"].insert_one(dict(doc))
    return {"ok": True}


@router.get("")
def listar_verificaciones(operador: str | None = None, limit: int = 50):
    query = {"operador": operador} if operador else {}
    rows = list(
        get_db()["verificaciones"]
        .find(query, {"_id": 0})
        .sort("momento", -1)
        .limit(max(1, min(limit, 200)))
    )
    return {"total": len(rows), "items": rows}
