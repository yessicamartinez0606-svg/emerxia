"""Doctores, Ambulancias, Emergencias y Operadores: mismo patrón, colecciones distintas (MongoDB)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError, WriteError

from ..repository import insert_row, list_rows, source_name, update_row
from ..schemas import AmbulanceIn, DoctorIn, EmergencyIn, EmergencyPatch, OperatorIn
from ..security import current_username


def build_router(
    path: str, collection: str, model: type[BaseModel], derive=None, patch_model: type[BaseModel] | None = None
) -> APIRouter:
    router = APIRouter(prefix=f"/api/{path}", tags=[path], dependencies=[Depends(current_username)])

    @router.get("")
    def list_items():
        rows = list_rows(collection)
        return {"total": len(rows), "items": rows, "source": source_name(collection)}

    @router.post("", status_code=201)
    def create_item(body: model):  # type: ignore[valid-type]
        try:
            data = body.model_dump()
            if derive:
                # p. ej. doctores: junta nombres + apellidos en un campo "nombre"
                # para poder mostrarlo/enlazarlo igual que en los demás módulos.
                data = {**data, **derive(data)}
            saved = insert_row(collection, data)
            return {**saved, "saved_in": source_name(collection)}
        except DuplicateKeyError as exc:
            field = next(iter((exc.details or {}).get("keyPattern", {"valor": 1})))
            raise HTTPException(409, f"Ya existe un registro con ese valor de '{field}'.")
        except WriteError as exc:
            raise HTTPException(422, f"MongoDB rechazó el documento: {exc}")

    if patch_model is not None:
        @router.patch("/{item_id}")
        def patch_item(item_id: int, body: patch_model):  # type: ignore[valid-type]
            changes = body.model_dump(exclude_unset=True)
            updated = update_row(collection, item_id, changes)
            if updated is None:
                raise HTTPException(404, "No se encontró ese registro.")
            return {**updated, "saved_in": source_name(collection)}

    return router


routers = [
    build_router(
        "doctores", "doctors", DoctorIn,
        derive=lambda d: {"nombre": f"{d['nombres']} {d['apellidos']}".strip()},
    ),
    build_router("ambulancias", "ambulances", AmbulanceIn),
    build_router("emergencias", "emergencies", EmergencyIn, patch_model=EmergencyPatch),
    build_router(
        "operadores", "operators", OperatorIn,
        derive=lambda d: {"nombre": f"{d['nombres']} {d['apellidos']}".strip()},
    ),
]
