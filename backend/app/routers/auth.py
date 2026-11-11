"""Inicio de sesión y registro con tres tipos de perfil (ver app/security.py):

    Personal (Administrador, Despachador, Supervisor)  todo el sistema
    Operador   conductor de ambulancia. Entra con contraseña Y Face ID: si no tiene su foto
               registrada en Operadores, no puede entrar.
    Usuario    reporta emergencias por mensaje o llamada y ve cómo van sus reportes.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from ..mongo import get_db
from ..repository import consume_password_reset, create_password_reset, create_user, find_user, list_rows
from ..schemas import FaceLoginIn, ForgotPasswordIn, LoginIn, RegisterIn, ResetPasswordIn
from ..security import OPERADOR, create_token, current_user, decode_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Distancia máxima entre rostros para considerarlos la misma persona (igual que en
# frontend/src/lib/faceVerify.js).
UMBRAL_ROSTRO = 0.55

SIN_FOTO = ("Tu foto no está registrada. Pide a la central que te tome la foto en Operadores; "
            "sin ella no puedes entrar como operador.")


def operador_de(user: dict) -> dict | None:
    """El registro de Operadores ligado a la cuenta (por id o, si no, por nombre)."""
    ops = list_rows("operators")
    if user.get("operador_id") is not None:
        op = next((o for o in ops if o.get("id") == user["operador_id"]), None)
        if op:
            return op
    nombre = (user.get("full_name") or "").strip().lower()
    return next((o for o in ops if (o.get("nombre") or "").strip().lower() == nombre), None)


def _public(user: dict) -> dict:
    datos = {"username": user["username"], "full_name": user["full_name"], "role": user.get("role") or "Administrador"}
    if datos["role"] == OPERADOR:
        op = operador_de(user)
        datos["operador"] = {"id": op["id"], "nombre": op["nombre"]} if op else None
    if user.get("telefono"):
        datos["telefono"] = user["telefono"]
    return datos


def _sesion(user: dict) -> dict:
    return {"token": create_token(user["username"]), "user": _public(user)}


def _paso_face(user: dict) -> dict:
    """Primer paso de un operador: la contraseña es correcta, falta su rostro."""
    op = operador_de(user)
    if not op:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Tu cuenta de operador no está ligada a ningún operador registrado. Pide a la central que te registre.")
    if not op.get("foto"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, SIN_FOTO)
    return {
        "face_required": True,
        "face_token": create_token(user["username"], purpose="face", minutes=5),
        "operador": {"nombre": op["nombre"], "foto": op["foto"]},
    }


@router.post("/login")
def login(body: LoginIn):
    user = find_user(body.username)
    if not user or not user.get("active", True) or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos.")
    if user.get("role") == OPERADOR:
        return _paso_face(user)
    return _sesion(user)


@router.post("/face")
def login_face(body: FaceLoginIn):
    """Segundo paso del operador: solo con el rostro correcto recibe su sesión."""
    username = decode_token(body.face_token, purpose="face")
    user = find_user(username)
    if not user or user.get("role") != OPERADOR:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Vuelve a iniciar sesión.")
    op = operador_de(user)
    if not op or not op.get("foto"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, SIN_FOTO)
    ok = body.coincide and (body.distancia is None or body.distancia <= UMBRAL_ROSTRO)
    get_db()["verificaciones"].insert_one({
        "operador": op["nombre"], "contexto": "inicio de sesión", "coincide": bool(ok),
        **({"distancia": body.distancia} if body.distancia is not None else {}),
        "verificado_por": username, "momento": datetime.now(timezone.utc),
    })
    if not ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"El rostro no coincide con la foto de {op['nombre']}. Inténtalo de nuevo.")
    return _sesion(user)


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return _public(user)


@router.post("/register", status_code=201)
def register(body: RegisterIn):
    operador_id = None
    if body.role == OPERADOR:
        nombre = body.full_name.strip().lower()
        op = next((o for o in list_rows("operators") if (o.get("nombre") or "").strip().lower() == nombre), None)
        if not op:
            raise HTTPException(422, f'No hay un operador registrado como "{body.full_name}". Escribe tu nombre igual que en Operadores '
                                     "o pide a la central que te registre.")
        if not op.get("foto"):
            raise HTTPException(422, SIN_FOTO)
        if any(u.get("operador_id") == op["id"] for u in get_db()["users"].find({"role": OPERADOR}, {"_id": 0})):
            raise HTTPException(409, f"{op['nombre']} ya tiene una cuenta. Inicia sesión o recupera tu contraseña.")
        operador_id = op["id"]
    try:
        create_user(body.username, body.password, body.full_name, body.role)
    except ValueError:
        raise HTTPException(status.HTTP_409_CONFLICT, f'Ya existe una cuenta con el usuario "{body.username}". Elige otro o inicia sesión.')
    extra = {k: v for k, v in {"operador_id": operador_id, "telefono": body.telefono.strip()}.items() if v not in (None, "")}
    if extra:
        get_db()["users"].update_one({"username": body.username.strip().lower()}, {"$set": extra})
    user = find_user(body.username)
    # El operador todavía tiene que pasar su Face ID; los demás quedan con la sesión iniciada.
    if body.role == OPERADOR:
        return _paso_face(user)
    return _sesion(user)


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordIn):
    token = create_password_reset(body.username)
    # Este proyecto no tiene un servicio de correo configurado todavía: en
    # producción, aquí se enviaría `token` por email en vez de regresarlo en
    # la respuesta. El frontend se lo enseña directo a la persona con un
    # aviso claro de que es un modo temporal.
    if token:
        return {"found": True, "reset_token": token}
    return {"found": False}


@router.post("/reset-password")
def reset_password(body: ResetPasswordIn):
    ok = consume_password_reset(body.token, body.password)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El enlace para restablecer la contraseña no es válido o ya expiró. Solicita uno nuevo.")
    return {"ok": True}
