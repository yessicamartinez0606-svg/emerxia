"""Cuentas del sistema: el Administrador crea y administra las cuentas de la central.

    GET    /api/cuentas                   todas las cuentas (sin contraseñas)
    POST   /api/cuentas                   crea una cuenta de la central (Administrador,
                                          Despachador o Supervisor)
    PUT    /api/cuentas/{usuario}         cambia nombre, rol, contraseña o la activa/desactiva
    DELETE /api/cuentas/{usuario}         borra la cuenta

Las de operadores y paramédicos se crean en sus módulos (van ligadas a su registro y a su
foto), y las de Usuario las crea cada persona al registrarse para reportar emergencias. Aquí
se ven todas, pero solo se crean las de la central. Nunca se puede quedar el sistema sin
ningún Administrador activo.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..mongo import get_db
from ..repository import create_user, find_user
from ..schemas import _valida_usuario
from ..security import ADMINISTRADOR, OPERADOR, PARAMEDICO, PERSONAL, current_user, hash_password, require_roles

router = APIRouter(prefix="/api/cuentas", tags=["cuentas"], dependencies=[Depends(require_roles(ADMINISTRADOR))])


class CuentaIn(BaseModel):
    full_name: str = Field(min_length=2)
    username: str = Field(min_length=3)
    password: str = Field(min_length=6)
    role: str = "Despachador"
    _usuario = field_validator("username")(_valida_usuario)

    @field_validator("role")
    @classmethod
    def _rol(cls, v: str) -> str:
        if v not in PERSONAL:
            raise ValueError("Aquí solo se crean cuentas de la central: Administrador, Despachador o Supervisor.")
        return v


class CuentaPatch(BaseModel):
    full_name: str | None = Field(None, min_length=2)
    role: str | None = None
    password: str | None = Field(None, min_length=6)
    active: bool | None = None


def _publica(u: dict) -> dict:
    ligada = ("Operadores" if u.get("operador_id") is not None
              else "Paramédicos" if u.get("paramedico_id") is not None else None)
    return {"username": u["username"], "full_name": u.get("full_name"), "role": u.get("role") or ADMINISTRADOR,
            "active": u.get("active", True), "telefono": u.get("telefono"), "created_at": u.get("created_at"),
            "ligada_a": ligada}


def _admins_activos(excepto: str | None = None) -> int:
    return sum(1 for u in get_db()["users"].find({"role": ADMINISTRADOR, "active": {"$ne": False}}, {"username": 1})
               if u["username"] != excepto)


@router.get("")
def listar():
    cuentas = [_publica(u) for u in get_db()["users"].find({}, {"_id": 0, "password_hash": 0})]
    orden = {ADMINISTRADOR: 0, "Despachador": 1, "Supervisor": 2, OPERADOR: 3, PARAMEDICO: 4, "Usuario": 5}
    cuentas.sort(key=lambda c: (orden.get(c["role"], 9), (c["full_name"] or "").lower()))
    return {"total": len(cuentas), "items": cuentas}


@router.post("", status_code=201)
def crear(body: CuentaIn):
    try:
        create_user(body.username, body.password, body.full_name.strip(), body.role)
    except ValueError:
        raise HTTPException(409, f'Ya existe una cuenta con el usuario "{body.username}". Elige otro.')
    return _publica(find_user(body.username))


def _cuenta(usuario: str) -> dict:
    u = find_user(usuario)
    if not u:
        raise HTTPException(404, "No se encontró esa cuenta.")
    return u


@router.put("/{usuario}")
def cambiar(usuario: str, body: CuentaPatch, yo: dict = Depends(current_user)):
    u = _cuenta(usuario)
    cambios: dict = {}
    if body.full_name is not None:
        cambios["full_name"] = body.full_name.strip()
    if body.role is not None and body.role != u.get("role"):
        if u.get("role") in (OPERADOR, PARAMEDICO, "Usuario") or body.role not in PERSONAL:
            raise HTTPException(422, "El rol solo se cambia entre Administrador, Despachador y Supervisor.")
        if u.get("role") == ADMINISTRADOR and _admins_activos(excepto=u["username"]) == 0:
            raise HTTPException(409, "Es el único Administrador: crea otro antes de cambiarle el rol.")
        cambios["role"] = body.role
    if body.active is not None and body.active != u.get("active", True):
        if not body.active and u["username"] == yo["username"]:
            raise HTTPException(409, "No puedes desactivar tu propia cuenta.")
        if not body.active and u.get("role") == ADMINISTRADOR and _admins_activos(excepto=u["username"]) == 0:
            raise HTTPException(409, "Es el único Administrador activo: no se puede desactivar.")
        cambios["active"] = body.active
    if body.password:
        cambios["password_hash"] = hash_password(body.password)
    if not cambios:
        raise HTTPException(422, "No hay nada que cambiar.")
    get_db()["users"].update_one({"username": u["username"]}, {"$set": cambios})
    return {**_publica(find_user(u["username"])), "mensaje": "Cuenta actualizada."}


@router.delete("/{usuario}")
def borrar(usuario: str, yo: dict = Depends(current_user)):
    u = _cuenta(usuario)
    if u["username"] == yo["username"]:
        raise HTTPException(409, "No puedes borrar tu propia cuenta.")
    if u.get("role") == ADMINISTRADOR and _admins_activos(excepto=u["username"]) == 0:
        raise HTTPException(409, "Es el único Administrador: crea otro antes de borrarlo.")
    db = get_db()
    db["users"].delete_one({"username": u["username"]})
    db["password_resets"].delete_many({"username": u["username"]})
    # El registro del operador/paramédico se queda; solo pierde su usuario (se ve «sin acceso»).
    for col, campo in (("operators", "operador_id"), ("paramedics", "paramedico_id")):
        if u.get(campo) is not None:
            db[col].update_one({"id": u[campo]}, {"$unset": {"usuario": ""}})
    return {"ok": True, "mensaje": f"Se borró la cuenta {u['username']}."}
