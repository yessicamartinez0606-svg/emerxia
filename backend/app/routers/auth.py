from fastapi import APIRouter, Depends, HTTPException, status

from ..repository import consume_password_reset, create_password_reset, create_user, find_user
from ..schemas import ForgotPasswordIn, LoginIn, RegisterIn, ResetPasswordIn
from ..security import create_token, current_username, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _public(user: dict) -> dict:
    return {"username": user["username"], "full_name": user["full_name"], "role": user["role"]}


@router.post("/login")
def login(body: LoginIn):
    user = find_user(body.username)
    if not user or not user.get("active", True) or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos.")
    return {"token": create_token(user["username"]), "user": _public(user)}


@router.get("/me")
def me(username: str = Depends(current_username)):
    user = find_user(username)
    if not user or not user.get("active", True):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La cuenta ya no existe o está desactivada.")
    return _public(user)


@router.post("/register", status_code=201)
def register(body: RegisterIn):
    try:
        create_user(body.username, body.password, body.full_name, body.role)
    except ValueError:
        raise HTTPException(status.HTTP_409_CONFLICT, f'Ya existe una cuenta con el usuario "{body.username}". Elige otro o inicia sesión.')
    user = find_user(body.username)
    # Se deja la sesión iniciada de una vez, para no pedirle a la persona que
    # vuelva a escribir sus credenciales justo después de registrarse.
    return {"token": create_token(user["username"]), "user": _public(user)}


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
