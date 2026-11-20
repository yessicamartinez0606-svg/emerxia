"""Ambulancias, Emergencias, Operadores y Paramédicos: mismo patrón, colecciones distintas (MongoDB).

Operadores y Paramédicos además tienen acceso al sistema (usuario y contraseña):
    POST /api/{operadores|paramedicos}                    el formulario trae usuario y contraseña;
                                                          la contraseña se guarda cifrada en su
                                                          cuenta (users), nunca en el registro
    PUT  /api/{operadores|paramedicos}/{id}/credenciales  solo el Administrador: cambia el usuario
                                                          y/o la contraseña

Editar
    PUT    /api/ambulancias/{id}                         cambia los datos de la ambulancia (mismas reglas
                                                          que al registrarla; una ocupada conserva su
                                                          estatus, placa y hospital hasta que termine)

Eliminar (solo el Administrador)
    DELETE /api/{ambulancias|operadores|paramedicos}/{id}  borra el registro (y la cuenta de la
                                                          persona). No se puede si está ocupado en
                                                          una emergencia abierta.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError, WriteError

from .. import flota
from ..mongo import get_db
from ..repository import (cuenta_ligada, delete_row, guardar_credenciales, insert_row, list_rows, source_name,
                          update_row, usuario_disponible)
from ..schemas import AmbulanceIn, CredencialesIn, EmergencyIn, EmergencyPatch, OperatorIn, ParamedicIn
from ..security import ADMINISTRADOR, OPERADOR, PARAMEDICO, current_username, require_roles

solo_admin = require_roles(ADMINISTRADOR)
log = logging.getLogger("emergexia")


def build_router(
    path: str, collection: str, model: type[BaseModel], derive=None, patch_model: type[BaseModel] | None = None,
    normalize=None, check=None, after_create=None, credenciales: tuple[str, str] | None = None,
    antes_de_borrar=None, al_borrar=None, al_editar=None,
) -> APIRouter:
    """credenciales=(rol, campo): el registro tiene cuenta propia en "users" con ese rol,
    ligada con `campo` (p. ej. ("Operador", "operador_id"))."""
    router = APIRouter(prefix=f"/api/{path}", tags=[path], dependencies=[Depends(current_username)])

    def con_acceso(row: dict) -> dict:
        """Agrega el usuario con el que entra (los operadores que solo entraban con su rostro
        tienen una cuenta interna "operador-N")."""
        if not credenciales:
            return row
        cuenta = cuenta_ligada(credenciales[1], row["id"])
        return {**row, "usuario": cuenta["username"] if cuenta else row.get("usuario") or None,
                "tiene_acceso": cuenta is not None}

    @router.get("")
    def list_items():
        rows = list_rows(collection)
        if normalize:
            rows = [normalize(r) for r in rows]
        rows = [con_acceso(r) for r in rows]
        return {"total": len(rows), "items": rows, "source": source_name(collection)}

    @router.post("", status_code=201)
    def create_item(body: model):  # type: ignore[valid-type]
        try:
            data = body.model_dump()
            acceso = None
            if credenciales:
                # La contraseña nunca se guarda en el registro, solo cifrada en la cuenta.
                acceso = {"usuario": data.pop("usuario"), "password": data.pop("password")}
                if not usuario_disponible(acceso["usuario"]):
                    raise HTTPException(409, f'El usuario "{acceso["usuario"]}" ya existe. Elige otro.')
            if check:
                check(data)   # reglas extra; lanza ValueError con el mensaje para el usuario
            if derive:
                # p. ej. operadores: junta nombres + apellidos en un campo "nombre"
                # para poder mostrarlo/enlazarlo igual que en los demás módulos.
                data = {**data, **derive(data)}
            saved = insert_row(collection, data)
            if acceso:
                saved = {**saved, **guardar_credenciales(collection, credenciales[1], credenciales[0], saved["id"],
                                                         saved.get("nombre") or "", **acceso), "tiene_acceso": True}
            extra = after_create(saved) if after_create else {}
            return {**saved, **(extra or {}), "saved_in": source_name(collection)}
        except DuplicateKeyError as exc:
            field = next(iter((exc.details or {}).get("keyPattern", {"valor": 1})))
            nombre = {"placa": "esa placa", "folio": "ese folio", "id": "ese número"}.get(field, f"ese dato ({field})")
            raise HTTPException(409, f"Ya hay otro registro con {nombre}.")
        except WriteError as exc:
            log.warning("MongoDB rechazó el documento de %s: %s", collection, exc)
            raise HTTPException(422, "No se pudo guardar: falta un dato o tiene un formato que no es válido.")
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    if patch_model is not None:
        @router.patch("/{item_id}")
        def patch_item(item_id: int, body: patch_model):  # type: ignore[valid-type]
            changes = body.model_dump(exclude_unset=True)
            updated = update_row(collection, item_id, changes)
            if updated is None:
                raise HTTPException(404, "No se encontró ese registro.")
            return {**updated, "saved_in": source_name(collection)}

    if al_editar is not None:
        @router.put("/{item_id}")
        def edit_item(item_id: int, body: model, usuario: str = Depends(current_username)):  # type: ignore[valid-type]
            row = next((r for r in list_rows(collection) if r.get("id") == item_id), None)
            if row is None:
                raise HTTPException(404, "No se encontró ese registro. Puede que lo hayan eliminado.")
            try:
                cambios = al_editar(row, body.model_dump())   # reglas; lanza ValueError con el motivo
                if not cambios:
                    return {**(normalize(row) if normalize else row), "cambios": [], "saved_in": source_name(collection)}
                guardado = update_row(collection, item_id, cambios)
            except DuplicateKeyError as exc:
                field = next(iter((exc.details or {}).get("keyPattern", {"valor": 1})))
                raise HTTPException(409, f"Ya hay otro registro con esa {field}.")
            except ValueError as exc:
                raise HTTPException(422, str(exc))
            from .flota import registrar
            nombre = row.get("nombre") or row.get("placa") or f"#{item_id}"
            registrar("edicion", f"Se editó {nombre}: {', '.join(sorted(cambios))}.", usuario,
                      **({"ambulancia": guardado.get("placa")} if guardado.get("placa") else {}))
            return {**(normalize(guardado) if normalize else guardado), "cambios": sorted(cambios),
                    "saved_in": source_name(collection)}

    if antes_de_borrar is not None:
        @router.delete("/{item_id}", dependencies=[Depends(solo_admin)])
        def delete_item(item_id: int, usuario: str = Depends(current_username)):
            row = next((r for r in list_rows(collection) if r.get("id") == item_id), None)
            if row is None:
                raise HTTPException(404, "No se encontró ese registro. Puede que ya lo hayan eliminado.")
            try:
                antes_de_borrar(row)     # lanza ValueError con el motivo si no se puede
            except ValueError as exc:
                raise HTTPException(409, str(exc))
            delete_row(collection, item_id)
            if credenciales:
                get_db()["users"].delete_many({credenciales[1]: item_id})
            if al_borrar:
                al_borrar(row)
            nombre = row.get("nombre") or row.get("placa") or f"#{item_id}"
            from .flota import registrar
            registrar("baja", f"Se eliminó a {nombre} de {path.capitalize()}.", usuario,
                      **({"ambulancia": row["placa"]} if row.get("placa") else {}))
            return {"ok": True, "mensaje": f"{nombre} se eliminó."}

    if credenciales:
        rol, campo = credenciales

        @router.put("/{item_id}/credenciales", dependencies=[Depends(solo_admin)])
        def cambiar_credenciales(item_id: int, body: CredencialesIn):
            row = next((r for r in list_rows(collection) if r.get("id") == item_id), None)
            if row is None:
                raise HTTPException(404, "No se encontró ese registro.")
            if body.usuario is None and body.password is None:
                raise HTTPException(422, "Escribe el usuario nuevo, la contraseña nueva o los dos.")
            try:
                r = guardar_credenciales(collection, campo, rol, item_id, row.get("nombre") or "",
                                         body.usuario, body.password)
            except ValueError as exc:
                raise HTTPException(409, str(exc))
            return {**r, "tiene_acceso": True, "mensaje": "Acceso actualizado."}

    return router


def _abiertas() -> list[dict]:
    return [e for e in list_rows("emergencies") if e.get("estado") != "Cerrada"]


def _editar_ambulancia(amb: dict, data: dict) -> dict:
    """Regresa solo lo que cambió. Mientras atiende una emergencia no cambian su estatus, su
    placa ni su hospital (las emergencias la buscan por su placa)."""
    actual = flota.normalizar(amb)
    if actual["estado"] == "Ocupada":
        for campo, texto in (("placa", "la placa"), ("hospital", "el hospital")):
            if data[campo] != amb.get(campo):
                raise ValueError(f"{amb['placa']} está atendiendo una emergencia: no se puede cambiar {texto} hasta que termine.")
        data["estado"] = "Ocupada"
    _check_ambulancia(data, propia_id=amb["id"])
    if data["placa"].strip().upper() != (amb.get("placa") or "").upper() and any(
            (a.get("placa") or "").upper() == data["placa"].strip().upper() for a in list_rows("ambulances")):
        raise ValueError(f"Ya hay otra ambulancia con la placa {data['placa']}.")
    return {k: v for k, v in data.items() if amb.get(k) != v}


def _borrar_ambulancia(amb: dict) -> None:
    placa = amb["placa"]
    em = next((e for e in _abiertas() if placa in ((e.get("ambulancias") or []) +
                                                   [p.strip() for p in (e.get("ambulancia") or "").split(",")])), None)
    if amb.get("estado") == "Ocupada" or em:
        raise ValueError(f"{placa} está atendiendo {em['folio'] if em else 'una emergencia'}. Espera a que termine.")


def _borrar_operador(op: dict) -> None:
    nombre = op["nombre"].strip().lower()
    em = next((e for e in _abiertas() if (e.get("operador") or "").strip().lower() == nombre), None)
    if em:
        raise ValueError(f"{op['nombre']} está a cargo de {em['folio']}. Espera a que termine o cambia de operador.")
    amb = next((a for a in list_rows("ambulances") if (a.get("conductor") or "").strip().lower() == nombre
                and a.get("estado") == "Ocupada"), None)
    if amb:
        raise ValueError(f"{op['nombre']} va manejando {amb['placa']} en una emergencia. Espera a que termine.")


def _operador_borrado(op: dict) -> None:
    """Sus ambulancias quedan sin conductor."""
    nombre = op["nombre"].strip().lower()
    for a in list_rows("ambulances"):
        if (a.get("conductor") or "").strip().lower() == nombre:
            update_row("ambulances", a["id"], {"conductor": ""})


def _borrar_paramedico(pm: dict) -> None:
    from .flota import emergencia_de_paramedico
    em = emergencia_de_paramedico(pm["id"])
    if em:
        raise ValueError(f"{pm['nombre']} está atendiendo {em['folio']}. Espera a que termine o quítalo de la emergencia.")


def _paramedico_con_emergencia(pm: dict) -> dict:
    """Para la tabla: a qué emergencia va ahora (la ambulancia es la de esa emergencia)."""
    from .flota import _placas, emergencia_de_paramedico
    em = emergencia_de_paramedico(pm["id"])
    placas = _placas(em) if em else []
    return {**pm, "emergencia_actual": em["folio"] if em else None, "ambulancia": placas[0] if placas else None}


def _check_ambulancia(data: dict, propia_id: int | None = None) -> None:
    """Un operador conduce una sola ambulancia."""
    conductor = (data.get("conductor") or "").strip().lower()
    if not conductor:
        return
    if not any((o.get("nombre") or "").lower() == conductor for o in list_rows("operators")):
        raise ValueError(f"No hay un operador llamado {data['conductor']}. Regístralo primero en Operadores.")
    otra = next((a for a in list_rows("ambulances") if (a.get("conductor") or "").lower() == conductor
                 and a.get("id") != propia_id), None)
    if otra:
        raise ValueError(f"{data['conductor']} ya conduce {otra['placa']}. Elige otro operador.")


def _emergencia_nueva(em: dict) -> dict:
    """Al guardar una emergencia, sus ambulancias (y el operador) se asignan solas."""
    from .flota import asignar_automatico
    return {"asignacion": asignar_automatico(em["id"])}


def _ambulancia_nueva(_: dict) -> dict:
    """Una ambulancia nueva y libre atiende a las emergencias que esperan."""
    from .flota import asignar_pendientes
    asignar_pendientes()
    return {}


routers = [
    build_router("ambulancias", "ambulances", AmbulanceIn, normalize=flota.normalizar, check=_check_ambulancia,
                 after_create=_ambulancia_nueva, antes_de_borrar=_borrar_ambulancia, al_editar=_editar_ambulancia),
    build_router("emergencias", "emergencies", EmergencyIn, patch_model=EmergencyPatch, after_create=_emergencia_nueva),
    build_router(
        "operadores", "operators", OperatorIn,
        derive=lambda d: {"nombre": f"{d['nombres']} {d['apellidos']}".strip()},
        credenciales=(OPERADOR, "operador_id"), antes_de_borrar=_borrar_operador, al_borrar=_operador_borrado,
    ),
    build_router(
        "paramedicos", "paramedics", ParamedicIn, normalize=_paramedico_con_emergencia,
        derive=lambda d: {"nombre": f"{d['nombres']} {d['apellidos']}".strip()},
        credenciales=(PARAMEDICO, "paramedico_id"), antes_de_borrar=_borrar_paramedico,
    ),
]
