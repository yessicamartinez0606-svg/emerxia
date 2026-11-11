"""Portales de los perfiles Operador y Usuario (ver app/security.py y app/routers/auth.py).

Operador (conductor de ambulancia; entra con Face ID)
    GET  /api/portal/operador                 su ficha, su ambulancia y su emergencia actual
    POST /api/portal/operador/combustible     registra una carga de gasolina de SU ambulancia
    POST /api/portal/operador/estado          reporta su ambulancia en reparación o fuera de servicio
    POST /api/portal/operador/evento          salida, llegada, traslado o cierre de SU emergencia

Usuario (reporta emergencias)
    GET  /api/portal/usuario/tipos            tipos de emergencia y número de la central
    GET  /api/portal/usuario/buscar?q=        ubica una dirección en el mapa
    POST /api/portal/usuario/reportes         reporta una emergencia por mensaje o llamada
    GET  /api/portal/usuario/reportes         sus reportes y cómo van
"""
import math

from fastapi import APIRouter, Depends, HTTPException

from .. import flota
from ..config import settings
from ..repository import insert_row, list_rows
from ..schemas import (AmbulanciaPatch, CargaCombustibleIn, CargaOperadorIn, EventoEmergenciaIn,
                       ReporteUsuarioIn)
from ..security import OPERADOR, USUARIO, require_roles
from . import flota as flota_api
from .auth import operador_de

router = APIRouter(prefix="/api/portal", tags=["portal"])

solo_operador = require_roles(OPERADOR)
solo_usuario = require_roles(USUARIO)

# Tipo de emergencia → prioridad con la que llega a la central.
TIPOS = {
    "Accidente de tránsito": "Alta",
    "Dolor de pecho o infarto": "Alta",
    "Dificultad para respirar": "Alta",
    "Persona inconsciente": "Alta",
    "Parto o embarazo": "Alta",
    "Herida o sangrado": "Media",
    "Caída o fractura": "Media",
    "Quemadura": "Media",
    "Intoxicación": "Media",
    "Otro": "Media",
}
TELEFONO_CENTRAL = getattr(settings, "telefono_central", None) or "911"


# ─────────────────────────── Operador ───────────────────────────

def _mi_operador(user: dict) -> dict:
    op = operador_de(user)
    if not op:
        raise HTTPException(403, "Tu cuenta no está ligada a un operador registrado.")
    return op


def _mi_ambulancia(op: dict) -> dict | None:
    return next((a for a in list_rows("ambulances")
                 if (a.get("conductor") or "").strip().lower() == op["nombre"].strip().lower()), None)


def _mi_emergencia_id(op: dict) -> int:
    amb = _mi_ambulancia(op)
    folio = flota.normalizar(amb)["emergencia_actual"] if amb else None
    em = next((e for e in list_rows("emergencies") if e.get("folio") == folio), None) if folio else None
    if not em:
        raise HTTPException(409, "No tienes una emergencia asignada en este momento.")
    return em["id"]


@router.get("/operador")
def portal_operador(user: dict = Depends(solo_operador)):
    op = _mi_operador(user)
    amb = _mi_ambulancia(op)
    ficha = flota_api.ficha_ambulancia(amb["id"]) if amb else None
    reporte = None
    if ficha and ficha["emergencia"]:
        reporte = flota_api.reporte(ficha["emergencia"]["id"])
    verificaciones = sorted((v for v in list_rows("verificaciones") if v.get("operador") == op["nombre"]),
                            key=lambda v: str(v.get("momento", "")), reverse=True)[:5]
    return {
        "operador": {k: v for k, v in op.items() if k != "foto"},
        "foto": op.get("foto"),
        "ficha": ficha,
        "emergencia": reporte,
        "verificaciones": verificaciones,
        "combustible_minimo": flota.COMBUSTIBLE_MINIMO,
    }


@router.post("/operador/combustible", status_code=201)
def operador_combustible(body: CargaOperadorIn, user: dict = Depends(solo_operador)):
    op = _mi_operador(user)
    amb = _mi_ambulancia(op)
    if not amb:
        raise HTTPException(409, "No tienes una ambulancia asignada. Pide a la central que te asigne una.")
    # Ya entró con su rostro: la carga queda como verificada con Face ID.
    carga = CargaCombustibleIn(operador=op["nombre"], verificado_facial=True, **body.model_dump())
    flota_api.cargar_combustible(amb["id"], carga, user["username"])
    return portal_operador(user)


@router.post("/operador/estado")
def operador_estado(body: AmbulanciaPatch, user: dict = Depends(solo_operador)):
    op = _mi_operador(user)
    amb = _mi_ambulancia(op)
    if not amb:
        raise HTTPException(409, "No tienes una ambulancia asignada.")
    # El operador solo puede cambiar el estatus (no el hospital ni el conductor).
    flota_api.cambiar_ambulancia(amb["id"], AmbulanciaPatch(estado=body.estado, motivo=body.motivo), user["username"])
    return portal_operador(user)


@router.post("/operador/evento")
def operador_evento(body: EventoEmergenciaIn, user: dict = Depends(solo_operador)):
    op = _mi_operador(user)
    flota_api.evento(_mi_emergencia_id(op), body, user["username"])
    return portal_operador(user)


# ─────────────────────────── Usuario ───────────────────────────

@router.get("/usuario/tipos")
def tipos(user: dict = Depends(solo_usuario)):
    return {"tipos": list(TIPOS), "telefono_central": TELEFONO_CENTRAL}


@router.get("/usuario/buscar")
def buscar_direccion(q: str, user: dict = Depends(solo_usuario)):
    from .. import red_vial
    try:
        return red_vial.geocodificar(q)
    except red_vial.ServicioMapasError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/usuario/reportes", status_code=201)
def reportar(body: ReporteUsuarioIn, user: dict = Depends(solo_usuario)):
    tiene_punto = body.lat is not None and body.lng is not None
    direccion = body.direccion.strip()
    if not tiene_punto and len(direccion) < 5:
        raise HTTPException(422, "Marca el lugar en el mapa, usa tu ubicación o escribe la dirección.")
    if tiene_punto and not direccion:
        from .. import red_vial
        direccion = red_vial.direccion_de_punto(body.lat, body.lng)
    if body.referencias.strip():
        direccion = f"{direccion} (Referencias: {body.referencias.strip()})"
    tipo = body.tipo if body.tipo in TIPOS else "Otro"
    detalle = body.descripcion.strip().rstrip(".")
    descripcion = f"{tipo}." + (f" {detalle}." if detalle else "")
    if body.personas > 1:
        descripcion += f" Personas afectadas: {body.personas}."
    canal = "llamada" if body.canal == "llamada" else "mensaje"
    em = insert_row("emergencies", {
        "paciente_nombre": body.paciente_nombre.strip() or f"Sin nombre (reportó {user['full_name']})",
        "paciente_edad": body.paciente_edad.strip(),
        "paciente_sexo": "Otro",
        "paciente_telefono": body.telefono.strip() or user.get("telefono", ""),
        "direccion": direccion,
        "descripcion": descripcion,
        "prioridad": TIPOS.get(tipo, "Media"),
        "estado": "Pendiente",
        "operador": None, "ambulancia": None, "doctor": None,
        # Una ambulancia por cada dos personas afectadas (máximo 10).
        "ambulancias_requeridas": min(10, max(1, math.ceil(body.personas / 2))),
        "canal": canal,
        "tipo": tipo,
        "lat": body.lat if tiene_punto else None,
        "lng": body.lng if tiene_punto else None,
        "reportado_por": user["username"],
        "reportante": user["full_name"],
    })
    flota_api.registrar("aviso", f"Nueva emergencia {em['folio']} reportada por {canal} por {user['full_name']}: {tipo}.",
                        user["username"], emergencia=em["folio"])
    return _reporte_publico(em)


def _reporte_publico(em: dict) -> dict:
    """Lo que ve quien reportó: avance, ambulancias y quién las maneja (sin datos internos)."""
    placas = flota_api._placas(em)
    ambs = []
    for p in placas:
        a = next((x for x in list_rows("ambulances") if x.get("placa") == p), None)
        if a:
            a = flota.normalizar(a)
            ambs.append({"placa": a["placa"], "tipo": a.get("tipo"), "hospital": a["hospital"], "conductor": a["conductor"]})
    campos = ("id", "folio", "tipo", "canal", "descripcion", "direccion", "lat", "lng", "prioridad", "estado",
              "created_at", "asignada_en", "hora_salida", "hora_llegada", "hora_traslado", "hora_cierre",
              "hospital_destino", "ambulancias_requeridas")
    return {**{k: em.get(k) for k in campos}, "ambulancias": ambs}


@router.get("/usuario/reportes")
def mis_reportes(user: dict = Depends(solo_usuario)):
    mios = [e for e in list_rows("emergencies") if e.get("reportado_por") == user["username"]]
    return {"items": [_reporte_publico(e) for e in sorted(mios, key=lambda e: e["id"], reverse=True)],
            "telefono_central": TELEFONO_CENTRAL}
