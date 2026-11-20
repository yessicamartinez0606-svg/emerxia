"""Portales de los perfiles Operador y Usuario (ver app/security.py y app/routers/auth.py).

Operador (conductor de ambulancia; entra con Face ID)
    GET  /api/portal/operador                 su ficha, su ambulancia y su emergencia actual
    POST /api/portal/operador/combustible     registra una carga de gasolina de SU ambulancia
    POST /api/portal/operador/estado          reporta su ambulancia en reparación o fuera de servicio
    POST /api/portal/operador/evento          salida, llegada, traslado o cierre de SU emergencia

Paramédico (entra con su rostro o con su usuario y contraseña). Van 2 por emergencia: la
central los confirma con su rostro y van en la ambulancia de esa emergencia.
    GET  /api/portal/paramedico               su ficha, la emergencia a la que lo mandaron (paciente,
                                              ambulancia, compañeros), qué tan grave parece y sus
                                              atenciones anteriores
    POST /api/portal/paramedico/atencion      signos vitales y atención brindada a SU paciente

Usuario (reporta emergencias)
    GET  /api/portal/usuario/tipos            tipos de emergencia, preguntas de sí/no y número de la central
    GET  /api/portal/usuario/buscar?q=        ubica una dirección en el mapa
    POST /api/portal/usuario/reportes         reporta una emergencia por mensaje o llamada. La prioridad
                                              sale del tipo y de las respuestas; si ya la habían
                                              reportado (mismo tipo y lugar, hace poco), el reporte
                                              se suma a esa emergencia (app/reportes.py)
    GET  /api/portal/usuario/reportes         sus reportes y cómo van
"""
import math

from fastapi import APIRouter, Depends, HTTPException

from .. import flota, reportes
from ..config import settings
from ..repository import insert_row, list_rows, update_row
from ..schemas import (AmbulanciaPatch, AtencionParamedicoIn, CargaCombustibleIn, CargaOperadorIn, EventoEmergenciaIn,
                       ReporteUsuarioIn)
from ..security import OPERADOR, PARAMEDICO, USUARIO, metodo_de_sesion, require_roles
from . import flota as flota_api
from .auth import operador_de, paramedico_de

router = APIRouter(prefix="/api/portal", tags=["portal"])

solo_operador = require_roles(OPERADOR)
solo_paramedico = require_roles(PARAMEDICO)
solo_usuario = require_roles(USUARIO)

TIPOS = reportes.TIPOS
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


def _mi_emergencia(op: dict) -> dict | None:
    """La emergencia abierta del operador: la que atiende su ambulancia o en la que la
    central lo dejó a cargo."""
    amb = _mi_ambulancia(op)
    folio = flota.normalizar(amb)["emergencia_actual"] if amb else None
    abiertas = [e for e in list_rows("emergencies") if e.get("estado") != "Cerrada"]
    if folio:
        em = next((e for e in abiertas if e.get("folio") == folio), None)
        if em:
            return em
    nombre = op["nombre"].strip().lower()
    return next((e for e in sorted(abiertas, key=lambda e: e["id"], reverse=True)
                 if (e.get("operador") or "").strip().lower() == nombre), None)


def _mi_emergencia_id(op: dict) -> int:
    em = _mi_emergencia(op)
    if not em:
        raise HTTPException(409, "No tienes una emergencia asignada en este momento.")
    return em["id"]


@router.get("/operador")
def portal_operador(user: dict = Depends(solo_operador)):
    op = _mi_operador(user)
    amb = _mi_ambulancia(op)
    ficha = flota_api.ficha_ambulancia(amb["id"]) if amb else None
    em = _mi_emergencia(op)
    reporte = flota_api.reporte(em["id"]) if em else None
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
def operador_combustible(body: CargaOperadorIn, user: dict = Depends(solo_operador),
                         metodo: str | None = Depends(metodo_de_sesion)):
    op = _mi_operador(user)
    amb = _mi_ambulancia(op)
    if not amb:
        raise HTTPException(409, "No tienes una ambulancia asignada. Pide a la central que te asigne una.")
    # Cuenta como verificada con el rostro solo si esta sesión se abrió con el rostro.
    carga = CargaCombustibleIn(operador=op["nombre"], **body.model_dump())
    flota_api.registrar_carga(amb["id"], carga, user["username"], verificado=metodo == "rostro")
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


# ─────────────────────────── Paramédico ───────────────────────────

CAMPOS_ATENCION = ("saturacion_oxigeno", "frecuencia_cardiaca", "escala_glasgow", "presion_arterial",
                   "temperatura", "glucosa")
CAMPOS_PACIENTE = {"paciente_nombre": "nombre", "paciente_edad": "edad", "paciente_sexo": "sexo",
                   "paciente_telefono": "teléfono"}


def _mi_paramedico(user: dict) -> dict:
    pm = paramedico_de(user)
    if not pm:
        raise HTTPException(403, "Tu cuenta no está ligada a un paramédico registrado.")
    return pm


def _emergencia_de_paramedico(pm: dict) -> dict | None:
    """La emergencia abierta a la que la central lo mandó (confirmado con su rostro)."""
    return flota_api.emergencia_de_paramedico(pm["id"])


def _ambulancia_de_emergencia(em: dict | None) -> dict | None:
    """Va en la ambulancia de la emergencia (la primera asignada, la del operador a cargo)."""
    if not em:
        return None
    placas = flota_api._placas(em)
    if not placas:
        return None
    amb = next((a for a in list_rows("ambulances") if a.get("placa") == placas[0]), None)
    return flota.normalizar(amb) if amb else None


def _triaje(em: dict) -> dict | None:
    """Qué tan grave parece según sus signos vitales (modelo de la práctica 05); None si no se puede."""
    from .. import triaje
    try:
        if not triaje.tiene_signos(em):
            return None
        return triaje.clasificar(triaje.signos_de(em))
    except Exception:  # noqa: BLE001  sin scikit-learn o modelo sin entrenar: el portal sigue funcionando
        return None


def _paciente(em: dict) -> dict:
    campos = ("id", "folio", "estado", "prioridad", "prioridad_motivos", "respuestas", "descripcion", "direccion",
              "lat", "lng", "tipo", "canal", "paciente_nombre", "paciente_edad", "paciente_sexo", "paciente_telefono",
              "operador", "ambulancia", "hospital_destino", "created_at", "hora_salida", "hora_llegada",
              "hora_traslado", "hora_cierre", "observaciones_paramedico", "atendio_paramedico", "atencion_registrada",
              "atenciones_paramedico", *CAMPOS_ATENCION)
    return {k: em.get(k) for k in campos}


@router.get("/paramedico")
def portal_paramedico(user: dict = Depends(solo_paramedico)):
    pm = _mi_paramedico(user)
    em = _emergencia_de_paramedico(pm)
    amb = _ambulancia_de_emergencia(em)
    companeros = []
    if em:
        por_id = {p["id"]: p for p in list_rows("paramedics")}
        companeros = [{"nombre": p["nombre"], "nivel": p.get("nivel"), "celular": por_id.get(p["id"], {}).get("celular")}
                      for p in flota_api.paramedicos_de(em) if p.get("id") != pm["id"]]
    conductor = None
    if amb and amb.get("conductor"):
        op = next((o for o in list_rows("operators") if (o.get("nombre") or "").lower() == amb["conductor"].lower()), None)
        conductor = {"nombre": amb["conductor"], "celular": (op or {}).get("celular"), "extension": (op or {}).get("extension")}
    cerradas = [e for e in list_rows("emergencies") if e.get("estado") == "Cerrada"
                and any(p.get("id") == pm["id"] for p in flota_api.paramedicos_de(e))]
    return {
        "paramedico": {k: v for k, v in pm.items() if k not in ("foto", "rostro", "rostro_de")},
        "foto": pm.get("foto"),
        "ambulancia": ({k: amb.get(k) for k in ("id", "placa", "tipo", "hospital", "estado", "vehiculo",
                                                "combustible_pct", "emergencia_actual")} if amb else None),
        "conductor": conductor,
        "companeros": companeros,
        "emergencia": _paciente(em) if em else None,
        "triaje": _triaje(em) if em else None,
        "atendidas": [_paciente(e) for e in sorted(cerradas, key=lambda e: e["id"], reverse=True)[:20]],
    }


@router.post("/paramedico/atencion")
def paramedico_atencion(body: AtencionParamedicoIn, user: dict = Depends(solo_paramedico)):
    pm = _mi_paramedico(user)
    em = _emergencia_de_paramedico(pm)
    if not em:
        raise HTTPException(409, "No estás en ninguna emergencia en este momento. La central te asigna al salir.")
    datos = body.model_dump()
    cambios = {k: datos[k] for k in CAMPOS_ATENCION if datos[k] not in (None, "")}
    # Datos del paciente: solo los que cambiaron de verdad.
    paciente = {k: datos[k].strip() for k in CAMPOS_PACIENTE
                if datos[k] is not None and datos[k].strip() and datos[k].strip() != (em.get(k) or "")}
    obs = datos["observaciones"].strip()
    if not cambios and not obs and not paciente:
        raise HTTPException(422, "Anota al menos un dato del paciente, un signo vital o la atención que le diste.")
    momento = flota.ahora()
    # Cada captura queda en la lista (para ver cómo evoluciona el paciente); los campos sueltos
    # guardan la última, que es la que ve la central y usa el triaje.
    captura = {**cambios, "observaciones": obs, "paramedico": pm["nombre"], "momento": momento}
    if paciente and not cambios and not obs:
        captura = None          # solo corrigió datos del paciente: no es una toma de signos
    if obs:
        cambios["observaciones_paramedico"] = obs
    if captura:
        cambios.update(atendio_paramedico=pm["nombre"], atencion_registrada=momento,
                       atenciones_paramedico=[*(em.get("atenciones_paramedico") or []), captura])
    cambios.update(paciente)
    update_row("emergencies", em["id"], cambios)
    resumen = ", ".join([f"{k.replace('_', ' ')} {v}" for k, v in cambios.items() if k in CAMPOS_ATENCION]
                        + [f"{CAMPOS_PACIENTE[k]} del paciente: {v}" for k, v in paciente.items()])
    placas = flota_api._placas(em)
    flota_api.registrar("atención", f"{pm['nombre']} registró la atención del paciente de {em['folio']}"
                        + (f": {resumen}." if resumen else "."), user["username"],
                        ambulancia=placas[0] if placas else None, emergencia=em["folio"])
    return portal_paramedico(user)


# ─────────────────────────── Usuario ───────────────────────────

@router.get("/usuario/tipos")
def tipos(user: dict = Depends(solo_usuario)):
    return {**reportes.catalogo(), "telefono_central": TELEFONO_CENTRAL}


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
    calc = reportes.calcular_prioridad(tipo, body.respuestas)
    canal = "llamada" if body.canal == "llamada" else "mensaje"
    lat, lng = (body.lat, body.lng) if tiene_punto else (None, None)
    detalle = body.descripcion.strip().rstrip(".")
    telefono = body.telefono.strip() or user.get("telefono", "")

    # ¿Ya la habían reportado? Entonces este reporte se suma a esa emergencia.
    abiertas = [e for e in list_rows("emergencies") if e.get("estado") != "Cerrada"]
    previa, metros = reportes.buscar_duplicado(tipo, lat, lng, direccion, abiertas)
    if previa:
        return _sumar_reporte(previa, metros, user, body, calc, canal, detalle, telefono)

    descripcion = f"{tipo}." + (f" {detalle}." if detalle else "")
    if calc["motivos"]:
        descripcion += " Señales de alarma: " + ", ".join(calc["motivos"]) + "."
    if body.personas > 1:
        descripcion += f" Personas afectadas: {body.personas}."
    em = insert_row("emergencies", {
        "paciente_nombre": body.paciente_nombre.strip() or f"Sin nombre (reportó {user['full_name']})",
        "paciente_edad": body.paciente_edad.strip(),
        "paciente_sexo": "Otro",
        "paciente_telefono": telefono,
        "direccion": direccion,
        "descripcion": descripcion,
        "prioridad": calc["prioridad"],
        "prioridad_base": calc["base"],
        "prioridad_motivos": calc["motivos"],
        "respuestas": calc["respuestas"],
        "estado": "Pendiente",
        "operador": None, "ambulancia": None,
        "ambulancias_requeridas": _ambulancias_para(body.personas),
        "personas": body.personas,
        "canal": canal,
        "tipo": tipo,
        "lat": lat,
        "lng": lng,
        "reportado_por": user["username"],
        "reportante": user["full_name"],
        "num_reportes": 1,
    })
    alarma = f" Señales de alarma: {', '.join(calc['motivos'])}." if calc["motivos"] else ""
    flota_api.registrar("aviso", f"Nueva emergencia {em['folio']} reportada por {canal} por {user['full_name']}: {tipo}. "
                        f"Prioridad {calc['prioridad']}.{alarma}", user["username"], emergencia=em["folio"])
    # Las ambulancias salen solas: no espera a que la central la atienda.
    flota_api.asignar_automatico(em["id"], user["username"])
    return {**_reporte_publico(flota_api._emergencia(em["id"])), "duplicado": False}


def _ambulancias_para(personas: int) -> int:
    """Una ambulancia por cada dos personas afectadas (máximo 10)."""
    return min(10, max(1, math.ceil(personas / 2)))


def _sumar_reporte(em: dict, metros: float | None, user: dict, body: ReporteUsuarioIn, calc: dict,
                   canal: str, detalle: str, telefono: str) -> dict:
    """Otro reporte de una emergencia que ya existe: se anota, puede subirle la prioridad o
    las ambulancias necesarias, pero no crea otra emergencia."""
    folio = em["folio"]
    extra = {"usuario": user["username"], "nombre": user["full_name"], "telefono": telefono, "canal": canal,
             "descripcion": detalle, "personas": body.personas, "motivos": calc["motivos"],
             "respuestas": calc["respuestas"], "momento": flota.ahora(),
             **({"distancia_m": metros} if metros is not None else {})}
    cambios: dict = {
        "reportes_adicionales": [*(em.get("reportes_adicionales") or []), extra],
        "num_reportes": int(em.get("num_reportes") or 1) + 1,
        "tambien_reportado_por": sorted({*(em.get("tambien_reportado_por") or []), user["username"]}),
    }
    avisos = []
    nueva = reportes.mayor_prioridad(em.get("prioridad"), calc["prioridad"])
    if nueva != em.get("prioridad"):
        cambios["prioridad"] = nueva
        avisos.append(f"sube a prioridad {nueva}")
    motivos = [m for m in calc["motivos"] if m not in (em.get("prioridad_motivos") or [])]
    if motivos:
        cambios["prioridad_motivos"] = [*(em.get("prioridad_motivos") or []), *motivos]
        avisos.append("nuevas señales: " + ", ".join(motivos))
    personas = max(int(em.get("personas") or 1), body.personas)
    requeridas = max(int(em.get("ambulancias_requeridas") or 1), _ambulancias_para(personas))
    if requeridas > int(em.get("ambulancias_requeridas") or 1):
        cambios["ambulancias_requeridas"] = requeridas
        avisos.append(f"ahora se necesitan {requeridas} ambulancias")
    cambios["personas"] = personas
    update_row("emergencies", em["id"], cambios)
    donde = f" a {metros} m" if metros is not None else " en la misma dirección"
    flota_api.registrar("aviso", f"{user['full_name']} también reportó {folio} ({canal}{donde}). "
                        f"Ya son {cambios['num_reportes']} reportes" + (f"; {'; '.join(avisos)}" if avisos else "") + ".",
                        user["username"], emergencia=folio)
    if "ambulancias_requeridas" in cambios:
        flota_api.asignar_automatico(em["id"], user["username"])
    return {**_reporte_publico(flota_api._emergencia(em["id"])), "duplicado": True,
            "mensaje": f"Esta emergencia ya la habían reportado ({folio}). Sumamos tu reporte: ya son "
                       f"{cambios['num_reportes']} y la ambulancia ya está asignada o en camino."}


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
              "hospital_destino", "ambulancias_requeridas", "num_reportes", "prioridad_motivos")
    return {**{k: em.get(k) for k in campos}, "ambulancias": ambs}


@router.get("/usuario/reportes")
def mis_reportes(user: dict = Depends(solo_usuario)):
    mios = [e for e in list_rows("emergencies") if e.get("reportado_por") == user["username"]
            or user["username"] in (e.get("tambien_reportado_por") or [])]
    return {"items": [_reporte_publico(e) for e in sorted(mios, key=lambda e: e["id"], reverse=True)],
            "telefono_central": TELEFONO_CENTRAL}
