"""Inicio de sesión y registro con tres tipos de perfil (ver app/security.py):

    Personal (Administrador, Despachador, Supervisor)  usuario y contraseña; todo el sistema
    Operador   NO crea cuenta: está registrado con su foto en Operadores y entra solo con su
               rostro. Si su foto no está registrada, no lo reconoce y no puede entrar.
    Usuario    crea su cuenta y reporta emergencias por mensaje o llamada.

Face ID del operador
    La central registra al operador con su foto. El navegador del personal calcula el
    descriptor facial de esa foto (128 números, face-api.js) y lo guarda en el operador
    (PUT /api/auth/rostros/{id}). Al entrar, el navegador del operador calcula el descriptor
    de su cara y lo manda a POST /api/auth/operador: el servidor busca al operador más
    parecido y, si la distancia pasa el umbral, le abre su sesión.
"""
import hashlib
import math
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from ..mongo import get_db
from ..repository import consume_password_reset, create_password_reset, create_user, find_user, list_rows
from ..schemas import ForgotPasswordIn, LoginIn, RegisterIn, ResetPasswordIn, RostroIn
from ..security import OPERADOR, PERSONAL, create_token, current_user, hash_password, require_roles, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Distancia máxima entre rostros para considerarlos la misma persona (igual que en
# frontend/src/lib/faceVerify.js).
UMBRAL_ROSTRO = 0.55

# Si dos operadores se parecen casi igual a la cara, no se adivina: se pide repetir.
MARGEN_ROSTRO = 0.04


def huella_foto(foto: str) -> str:
    """Identifica la foto con la que se calculó el descriptor (si cambian la foto, se recalcula)."""
    return hashlib.sha1((foto or "").encode()).hexdigest()[:16]


def operador_de(user: dict) -> dict | None:
    """El registro de Operadores ligado a la cuenta."""
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


def distancia(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def reconocer(descriptor: list[float], operadores: list[dict]) -> tuple[dict | None, float | None, str]:
    """Busca al operador cuya foto se parece más. Solo cuenta a quien tiene foto y su
    descriptor está al día con esa foto."""
    candidatos = [(distancia(descriptor, o["rostro"]), o) for o in operadores
                  if o.get("foto") and o.get("rostro") and o.get("rostro_de") == huella_foto(o["foto"])]
    if not candidatos:
        return None, None, "No hay operadores con foto registrada todavía."
    candidatos.sort(key=lambda c: c[0])
    d, op = candidatos[0]
    if d > UMBRAL_ROSTRO:
        return None, d, "No te reconocimos. Si eres operador, pide a la central que registre tu foto en Operadores."
    if len(candidatos) > 1 and candidatos[1][0] - d < MARGEN_ROSTRO:
        return None, d, "No se pudo distinguir tu rostro con claridad. Busca mejor luz y vuelve a intentarlo."
    return op, d, ""


def cuenta_de_operador(op: dict) -> dict:
    """La cuenta interna del operador; se crea sola la primera vez que entra con su rostro."""
    users = get_db()["users"]
    user = users.find_one({"role": OPERADOR, "operador_id": op["id"]}, {"_id": 0})
    if user:
        if user.get("full_name") != op["nombre"]:
            users.update_one({"username": user["username"]}, {"$set": {"full_name": op["nombre"]}})
            user["full_name"] = op["nombre"]
        return user
    username = f"operador-{op['id']}"
    # Sin contraseña utilizable: el operador solo entra con su rostro.
    create_user(username, secrets.token_urlsafe(24), op["nombre"], OPERADOR)
    users.update_one({"username": username}, {"$set": {"operador_id": op["id"]}})
    return find_user(username)


@router.post("/login")
def login(body: LoginIn):
    user = find_user(body.username)
    if not user or not user.get("active", True) or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos.")
    if user.get("role") == OPERADOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Los operadores entran con su rostro: usa «Soy operador».")
    return _sesion(user)


@router.post("/operador")
def login_operador(body: RostroIn):
    """Entrada del operador solo con su rostro."""
    op, d, motivo = reconocer(body.descriptor, list_rows("operators"))
    get_db()["verificaciones"].insert_one({
        "operador": op["nombre"] if op else "(no reconocido)", "contexto": "inicio de sesión", "coincide": op is not None,
        **({"distancia": round(d, 4)} if d is not None else {}),
        "verificado_por": "Face ID", "momento": datetime.now(timezone.utc),
    })
    if not op:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, motivo)
    if op.get("estado") == "Baja":
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"{op['nombre']} está dado de baja.")
    return _sesion(cuenta_de_operador(op))


# ─────────── descriptores de las fotos (los calcula el navegador del personal) ───────────

solo_personal = require_roles(*PERSONAL)


@router.get("/rostros/pendientes", dependencies=[Depends(solo_personal)])
def rostros_pendientes():
    """Operadores con foto cuyo descriptor falta o es de una foto anterior."""
    return [{"id": o["id"], "nombre": o["nombre"], "foto": o["foto"]} for o in list_rows("operators")
            if o.get("foto") and o.get("rostro_de") != huella_foto(o["foto"])]


@router.put("/rostros/{operador_id}", dependencies=[Depends(solo_personal)])
def guardar_rostro(operador_id: int, body: RostroIn):
    op = next((o for o in list_rows("operators") if o.get("id") == operador_id), None)
    if not op or not op.get("foto"):
        raise HTTPException(404, "Ese operador no tiene foto registrada.")
    get_db()["operators"].update_one({"id": operador_id},
                                     {"$set": {"rostro": body.descriptor, "rostro_de": huella_foto(op["foto"])}})
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return _public(user)


@router.post("/register", status_code=201)
def register(body: RegisterIn):
    try:
        create_user(body.username, body.password, body.full_name, body.role)
    except ValueError:
        raise HTTPException(status.HTTP_409_CONFLICT, f'Ya existe una cuenta con el usuario "{body.username}". Elige otro o inicia sesión.')
    if body.telefono.strip():
        get_db()["users"].update_one({"username": body.username.strip().lower()}, {"$set": {"telefono": body.telefono.strip()}})
    return _sesion(find_user(body.username))


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
