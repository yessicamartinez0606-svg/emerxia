"""Flota de ambulancias por hospital, gasolina, historial y reporte de emergencias (ver app/flota.py).

    GET   /api/flota/hospitales                       ambulancias agrupadas por hospital
    GET   /api/flota/ambulancias/{id}                 ficha: conductor, gasolina, cargas e historial
    PATCH /api/flota/ambulancias/{id}                 cambiar estatus, hospital o conductor
    POST  /api/flota/ambulancias/{id}/combustible     carga de gasolina (solo su conductor)
    GET   /api/flota/historial                        historial (filtros: ambulancia, emergencia, tipo)
    POST  /api/flota/emergencias/{id}/asignar         plan de ambulancias (confirmar=true lo aplica)
    POST  /api/flota/emergencias/{id}/operador        operador validado por Face ID (sale en su ambulancia)
    POST  /api/flota/emergencias/{id}/evento          salida, llegada, traslado o cierre
    GET   /api/flota/emergencias/{id}/reporte         reporte completo de la emergencia
"""
from fastapi import APIRouter, Depends, HTTPException, Query

from .. import flota
from ..repository import insert_row, list_rows, update_row
from ..schemas import AmbulanciaPatch, AsignarIn, CargaCombustibleIn, EventoEmergenciaIn, OperadorEmergenciaIn
from ..security import current_username

router = APIRouter(prefix="/api/flota", tags=["flota"], dependencies=[Depends(current_username)])

TIPOS_HISTORIAL = {
    "estado": "Cambio de estatus",
    "asignacion": "Asignada a emergencia",
    "salida": "Salida",
    "llegada": "Llegada al lugar",
    "traslado": "Traslado a hospital",
    "liberacion": "Regresa libre",
    "combustible": "Carga de gasolina",
    "consumo": "Gasolina usada",
    "conductor": "Cambio de conductor",
    "hospital": "Cambio de hospital",
    "aviso": "Aviso",
}


# ─────────────────────────── utilidades ───────────────────────────

def registrar(tipo: str, detalle: str, usuario: str | None = None, **campos) -> dict:
    """Agrega un renglón al historial."""
    return insert_row("historial", {
        "tipo": tipo,
        "detalle": detalle,
        "ambulancia": campos.get("ambulancia"),
        "operador": campos.get("operador"),
        "emergencia": campos.get("emergencia"),
        "hospital": campos.get("hospital"),
        "usuario": usuario,
    })


def _sin_foto(doc: dict | None) -> dict | None:
    return {k: v for k, v in doc.items() if k != "foto"} if doc else None


def _por(nombre: str, campo: str, valor) -> dict | None:
    if valor in (None, ""):
        return None
    return next((r for r in list_rows(nombre) if str(r.get(campo, "")).strip().lower() == str(valor).strip().lower()), None)


def _ambulancia(amb_id: int) -> dict:
    amb = _por("ambulances", "id", amb_id)
    if not amb:
        raise HTTPException(404, "No existe esa ambulancia.")
    return amb


def _emergencia(em_id: int) -> dict:
    em = _por("emergencies", "id", em_id)
    if not em:
        raise HTTPException(404, "No existe esa emergencia.")
    return em


def _placas(em: dict) -> list[str]:
    if em.get("ambulancias"):
        return list(em["ambulancias"])
    return [p.strip() for p in (em.get("ambulancia") or "").split(",") if p.strip()]


def _ubicacion(em: dict) -> dict | None:
    """Coordenadas de la emergencia: las que marcó quien la reportó o, si no, las de su dirección."""
    if em.get("lat") is not None and em.get("lng") is not None:
        return {"lat": em["lat"], "lng": em["lng"]}
    try:
        from .. import red_vial
        lugar = red_vial.geocodificar(em.get("direccion", ""))
        return {"lat": lugar["lat"], "lng": lugar["lng"]}
    except Exception:  # noqa: BLE001  sin internet o dirección incompleta: se ordena por el hospital base
        return None


def _historial(**filtros) -> list[dict]:
    filas = list_rows("historial")
    for campo, valor in filtros.items():
        if valor:
            filas = [f for f in filas if str(f.get(campo) or "").lower() == str(valor).lower()]
    return sorted(filas, key=lambda f: f["id"], reverse=True)


# ─────────────────────────── hospitales y ambulancias ───────────────────────────

@router.get("/hospitales")
def hospitales():
    hs = flota.resumen_hospitales(list_rows("ambulances"))
    total = sum(len(h["ambulancias"]) for h in hs)
    return {
        "hospitales": hs,
        "estados": flota.ESTADOS,
        "combustible_minimo": flota.COMBUSTIBLE_MINIMO,
        "totales": {e: sum(h["conteo"][e] for h in hs) for e in flota.ESTADOS} | {"total": total},
    }


@router.get("/ambulancias/{amb_id}")
def ficha_ambulancia(amb_id: int):
    amb = flota.normalizar(_ambulancia(amb_id))
    cargas = sorted((c for c in list_rows("cargas_combustible") if c.get("ambulancia") == amb["placa"]),
                    key=lambda c: c["id"], reverse=True)
    return {
        "ambulancia": amb,
        "conductor": _sin_foto(_por("operators", "nombre", amb["conductor"])),
        "conductor_foto": (_por("operators", "nombre", amb["conductor"]) or {}).get("foto"),
        "emergencia": _sin_foto(_por("emergencies", "folio", amb["emergencia_actual"])),
        "cargas": cargas,
        "litros_cargados": round(sum(c.get("litros", 0) for c in cargas), 1),
        "gasto_total": round(sum(c.get("costo") or 0 for c in cargas), 2),
        "historial": _historial(ambulancia=amb["placa"])[:100],
        "hospitales": flota.NOMBRES_HOSPITALES,
        "combustible_minimo": flota.COMBUSTIBLE_MINIMO,
    }


@router.patch("/ambulancias/{amb_id}")
def cambiar_ambulancia(amb_id: int, body: AmbulanciaPatch, usuario: str = Depends(current_username)):
    amb = flota.normalizar(_ambulancia(amb_id))
    placa = amb["placa"]
    cambios: dict = {}
    motivo = f" Motivo: {body.motivo.strip()}." if body.motivo.strip() else ""

    if body.estado and body.estado != amb["estado"]:
        if amb["estado"] == "Ocupada":
            raise HTTPException(409, f"{placa} está atendiendo {amb['emergencia_actual'] or 'una emergencia'}. "
                                     "Ciérrala desde el reporte de la emergencia para liberar la ambulancia.")
        cambios["estado"] = body.estado
        registrar("estado", f"{placa}: {amb['estado']} → {body.estado}.{motivo}", usuario,
                  ambulancia=placa, hospital=amb["hospital"], operador=amb["conductor"] or None)

    if body.hospital and body.hospital != amb["hospital"]:
        if body.hospital not in flota.NOMBRES_HOSPITALES:
            raise HTTPException(422, "Elige uno de los hospitales de la lista.")
        if amb["estado"] == "Ocupada":
            raise HTTPException(409, f"{placa} está en una emergencia; cámbiala de hospital cuando regrese.")
        cambios["hospital"] = body.hospital
        registrar("hospital", f"{placa} pasa de {amb['hospital']} a {body.hospital}.{motivo}", usuario,
                  ambulancia=placa, hospital=body.hospital)

    if body.conductor is not None and body.conductor != amb["conductor"]:
        if body.conductor:
            if not _por("operators", "nombre", body.conductor):
                raise HTTPException(422, f"No hay un operador llamado {body.conductor}.")
            otra = next((a for a in list_rows("ambulances")
                         if a["id"] != amb_id and (a.get("conductor") or "").lower() == body.conductor.lower()), None)
            if otra:
                raise HTTPException(409, f"{body.conductor} ya conduce {otra['placa']}. Quítalo de esa ambulancia primero.")
        cambios["conductor"] = body.conductor
        registrar("conductor", f"{placa}: conductor {amb['conductor'] or 'sin asignar'} → {body.conductor or 'sin asignar'}.",
                  usuario, ambulancia=placa, operador=body.conductor or None, hospital=amb["hospital"])

    for campo in ("tanque_litros", "rendimiento_km_l"):
        valor = getattr(body, campo)
        if valor is not None and valor != amb[campo]:
            cambios[campo] = valor

    if not cambios:
        return ficha_ambulancia(amb_id)
    update_row("ambulances", amb_id, cambios)
    return ficha_ambulancia(amb_id)


@router.post("/ambulancias/{amb_id}/combustible", status_code=201)
def cargar_combustible(amb_id: int, body: CargaCombustibleIn, usuario: str = Depends(current_username)):
    amb = _ambulancia(amb_id)
    try:
        carga = flota.aplicar_carga(amb, body.operador, body.litros, body.kilometraje)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    placa = amb["placa"]
    insert_row("cargas_combustible", {
        "ambulancia": placa,
        "operador": body.operador.strip(),
        "litros": body.litros,
        "costo": body.costo,
        "kilometraje": body.kilometraje,
        "combustible_antes": carga["antes"],
        "combustible_despues": carga["despues"],
        "estacion": body.estacion.strip(),
        "notas": body.notas.strip(),
        "verificado_facial": body.verificado_facial,
        "registrado_por": usuario,
    })
    update_row("ambulances", amb_id, carga["cambios"])
    costo = f" (${body.costo:,.2f})" if body.costo else ""
    registrar("combustible",
              f"{body.operador} cargó {body.litros:g} L a {placa}{costo}: {int(carga['antes'])} % → {int(carga['despues'])} %."
              + (" Identidad verificada con Face ID." if body.verificado_facial else ""),
              usuario, ambulancia=placa, operador=body.operador.strip(), hospital=flota.normalizar(amb)["hospital"])
    return ficha_ambulancia(amb_id)


@router.get("/historial")
def historial(ambulancia: str | None = None, emergencia: str | None = None, tipo: str | None = None,
              operador: str | None = None, limite: int = Query(300, ge=1, le=2000)):
    filas = _historial(ambulancia=ambulancia, emergencia=emergencia, tipo=tipo, operador=operador)
    return {"total": len(filas), "items": filas[:limite], "tipos": TIPOS_HISTORIAL}


# ─────────────────────────── emergencias ───────────────────────────

@router.post("/emergencias/{em_id}/asignar")
def asignar(em_id: int, body: AsignarIn, usuario: str = Depends(current_username)):
    em = _emergencia(em_id)
    if em.get("estado") == "Cerrada":
        raise HTTPException(409, "La emergencia ya está cerrada.")
    ya = _placas(em)
    cantidad = body.cantidad or int(em.get("ambulancias_requeridas") or 1)
    faltan = cantidad - len(ya)
    destino = _ubicacion(em)
    if faltan <= 0:
        return {"plan": None, "asignadas": ya, "mensaje": f"Ya tiene las {len(ya)} ambulancia(s) que necesita."}

    # Primero las que eligió el administrador; si la emergencia ya tiene operador asignado,
    # también su ambulancia, para que salga en la que maneja.
    preferidas = list(body.placas)
    amb_op = _ambulancia_de(em.get("operador"))
    if amb_op and amb_op["placa"] not in ya:
        preferidas.append(amb_op["placa"])
    plan = flota.planear(list_rows("ambulances"), faltan, destino, preferidas)
    plan["ubicada"] = destino is not None
    plan["manual"] = bool(body.placas)
    if not body.confirmar:
        return {"plan": plan, "asignadas": ya}
    if not plan["elegidas"]:
        raise HTTPException(409, "No hay ambulancias libres con conductor y gasolina suficiente en la zona.")

    folio = em["folio"]
    nuevas = [a["placa"] for a in plan["elegidas"]]
    for a in plan["elegidas"]:
        update_row("ambulances", a["id"], {"estado": "Ocupada", "emergencia_actual": folio})
        registrar("asignacion", f"{a['placa']} ({a['hospital']}) asignada a {folio}. Conduce {a['conductor']}.",
                  usuario, ambulancia=a["placa"], operador=a["conductor"], emergencia=folio, hospital=a["hospital"])
    if plan["usa_otros_hospitales"] or plan["faltan"]:
        registrar("aviso", plan["resumen"], usuario, emergencia=folio)
    todas = ya + nuevas
    update_row("emergencies", em_id, {
        "ambulancias": todas,
        "ambulancia": ", ".join(todas),
        "ambulancias_requeridas": cantidad,
        "hospital_salida": em.get("hospital_salida") or plan["elegidas"][0]["hospital"],
        "estado": "Asignada" if em.get("estado") == "Pendiente" else em.get("estado"),
        "asignada_en": em.get("asignada_en") or flota.ahora(),
        # El operador de la emergencia es quien maneja la primera ambulancia (si no había uno).
        "operador": em.get("operador") or plan["elegidas"][0]["conductor"],
    })
    return {"plan": plan, "asignadas": todas}


def _ambulancia_de(operador: str | None) -> dict | None:
    if not operador:
        return None
    return next((a for a in list_rows("ambulances") if (a.get("conductor") or "").strip().lower() == operador.strip().lower()), None)


@router.post("/emergencias/{em_id}/operador")
def asignar_operador(em_id: int, body: OperadorEmergenciaIn, usuario: str = Depends(current_username)):
    """El operador validado por Face ID queda en la emergencia y, si su ambulancia está
    lista, sale en ella. Así le aparece en su perfil de Operador."""
    em = _emergencia(em_id)
    if em.get("estado") == "Cerrada":
        raise HTTPException(409, "La emergencia ya está cerrada.")
    op = _por("operators", "nombre", body.operador)
    if not op:
        raise HTTPException(422, f"No hay un operador llamado {body.operador}.")
    folio = em["folio"]
    update_row("emergencies", em_id, {"operador": op["nombre"],
                                      "estado": "Asignada" if em.get("estado") == "Pendiente" else em.get("estado")})
    registrar("asignacion", f"{op['nombre']} queda a cargo de {folio} (Face ID).", usuario, operador=op["nombre"], emergencia=folio)

    amb = _ambulancia_de(op["nombre"])
    ya = _placas(em)
    if not amb:
        mensaje = f"{op['nombre']} no maneja ninguna ambulancia. Asígnale una en Ambulancias o elige una para la emergencia."
        return {"operador": op["nombre"], "ambulancia": None, "mensaje": mensaje, "listo": False}
    if amb["placa"] in ya:
        return {"operador": op["nombre"], "ambulancia": amb["placa"], "mensaje": f"{op['nombre']} sale con {amb['placa']}.", "listo": True}
    motivo = flota.motivo_no_disponible(amb)
    if motivo:
        mensaje = f"{amb['placa']}, la ambulancia de {op['nombre']}, no puede salir ({motivo}). Elige otra para la emergencia."
        return {"operador": op["nombre"], "ambulancia": amb["placa"], "mensaje": mensaje, "listo": False}
    requeridas = max(int(em.get("ambulancias_requeridas") or 1), len(ya) + 1)
    asignar(em_id, AsignarIn(cantidad=len(ya) + 1, placas=[amb["placa"]], confirmar=True), usuario)
    if requeridas > len(ya) + 1:
        update_row("emergencies", em_id, {"ambulancias_requeridas": requeridas})
    return {"operador": op["nombre"], "ambulancia": amb["placa"], "mensaje": f"{op['nombre']} sale con {amb['placa']}.", "listo": True}


@router.post("/emergencias/{em_id}/evento")
def evento(em_id: int, body: EventoEmergenciaIn, usuario: str = Depends(current_username)):
    em = _emergencia(em_id)
    folio = em["folio"]
    placas = _placas(em)
    if em.get("estado") == "Cerrada":
        raise HTTPException(409, "La emergencia ya está cerrada.")
    if not placas:
        raise HTTPException(409, "Primero asigna las ambulancias.")
    nota = body.observaciones.strip()
    ambs = [a for a in list_rows("ambulances") if a.get("placa") in placas]
    cambios: dict = {}

    if body.tipo == "salida":
        cambios = {"estado": "En curso", "hora_salida": flota.ahora()}
        for a in ambs:
            registrar("salida", f"{a['placa']} sale de {flota.normalizar(a)['hospital']} rumbo a {folio}." + (f" {nota}" if nota else ""),
                      usuario, ambulancia=a["placa"], operador=a.get("conductor"), emergencia=folio)
    elif body.tipo == "llegada":
        cambios = {"hora_llegada": flota.ahora()}
        registrar("llegada", f"Las ambulancias llegan al lugar ({em.get('direccion', '')})." + (f" {nota}" if nota else ""),
                  usuario, emergencia=folio)
    elif body.tipo == "traslado":
        if body.hospital_destino and body.hospital_destino not in flota.NOMBRES_HOSPITALES:
            raise HTTPException(422, "Elige uno de los hospitales de la lista.")
        destino = body.hospital_destino or flota.HOSPITAL_BASE
        cambios = {"hora_traslado": flota.ahora(), "hospital_destino": destino}
        registrar("traslado", f"Paciente trasladado a {destino}." + (f" {nota}" if nota else ""),
                  usuario, emergencia=folio, hospital=destino)
    else:  # cierre
        km = body.km_recorridos or 0
        total_litros = 0.0
        for a in ambs:
            c = flota.consumo_por_km(a, km)
            total_litros += c["litros"]
            update_row("ambulances", a["id"], {**c["cambios"], "estado": "Libre", "emergencia_actual": None})
            registrar("consumo", f"{a['placa']} recorrió {km:g} km y gastó {c['litros']:g} L: {int(c['antes'])} % → {int(c['despues'])} %.",
                      usuario, ambulancia=a["placa"], operador=a.get("conductor"), emergencia=folio)
            registrar("liberacion", f"{a['placa']} termina {folio} y queda libre.", usuario,
                      ambulancia=a["placa"], operador=a.get("conductor"), emergencia=folio, hospital=flota.normalizar(a)["hospital"])
            if c["despues"] < flota.COMBUSTIBLE_MINIMO:
                registrar("aviso", f"{a['placa']} quedó con {int(c['despues'])} % de gasolina: debe cargar antes de su siguiente salida.",
                          usuario, ambulancia=a["placa"], operador=a.get("conductor"))
        cambios = {"estado": "Cerrada", "hora_cierre": flota.ahora(), "km_recorridos": km,
                   "litros_consumidos": round(total_litros, 1)}
    if nota:
        cambios["observaciones"] = ((em.get("observaciones") or "") + ("\n" if em.get("observaciones") else "") + nota).strip()
    update_row("emergencies", em_id, cambios)
    return reporte(em_id)


@router.get("/emergencias/{em_id}/reporte")
def reporte(em_id: int):
    em = _emergencia(em_id)
    folio = em["folio"]
    placas = _placas(em)
    ambulancias = []
    for p in placas:
        a = _por("ambulances", "placa", p)
        if not a:
            continue
        a = flota.normalizar(a)
        ambulancias.append({**a, "conductor_info": _sin_foto(_por("operators", "nombre", a["conductor"]))})
    verificaciones = [v for v in list_rows("verificaciones") if v.get("emergencia_folio") == folio]
    return {
        "emergencia": em,
        "ambulancias": ambulancias,
        "operador": _sin_foto(_por("operators", "nombre", em.get("operador"))),
        "doctor": _sin_foto(_por("doctors", "nombre", em.get("doctor"))),
        "hospital_salida": em.get("hospital_salida"),
        "linea_tiempo": sorted(_historial(emergencia=folio), key=lambda f: f["id"]),
        "verificaciones": [_sin_foto(v) for v in verificaciones],
        "requeridas": int(em.get("ambulancias_requeridas") or 1),
        "hospitales": flota.NOMBRES_HOSPITALES,
    }
