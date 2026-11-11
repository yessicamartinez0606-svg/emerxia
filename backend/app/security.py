import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

ITERATIONS = 200_000
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


# ─────────────────────────── perfiles ───────────────────────────
# Personal de la central: ve todo el sistema.
PERSONAL = ("Administrador", "Despachador", "Supervisor")
# Conductor de ambulancia: entra con contraseña + Face ID y ve su ambulancia, su gasolina,
# su emergencia y las rutas.
OPERADOR = "Operador"
# Persona que reporta emergencias (por mensaje o llamada) y ve el avance de sus reportes.
USUARIO = "Usuario"
ROLES = (*PERSONAL, OPERADOR, USUARIO)


def create_token(username: str, purpose: str = "sesion", minutes: int | None = None) -> str:
    """purpose="sesion" es la sesión normal. purpose="face" es un pase de 5 minutos que
    solo sirve para terminar el inicio de sesión de un operador con Face ID."""
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes or settings.jwt_expire_minutes)
    return jwt.encode({"sub": username, "exp": exp, "purpose": purpose}, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str, purpose: str = "sesion") -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tu sesión expiró. Vuelve a iniciar sesión.")
    if payload.get("purpose", "sesion") != purpose:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Termina de verificar tu rostro para entrar.")
    return payload["sub"]


def current_username(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inicia sesión para continuar.")
    return decode_token(creds.credentials)


def current_user(username: str = Depends(current_username)) -> dict:
    from .repository import find_user   # evita importación circular
    user = find_user(username)
    if not user or not user.get("active", True):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "La cuenta ya no existe o está desactivada.")
    user.setdefault("role", "Administrador")
    return user


def require_roles(*roles: str):
    """Dependencia: solo deja pasar a los perfiles indicados."""
    def check(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu perfil no tiene acceso a esta sección.")
        return user
    return check


solo_personal = require_roles(*PERSONAL)
