"""Inicio de sesión y registro con tres tipos de perfil (ver app/security.py):

    Personal (Administrador, Despachador, Supervisor)  usuario y contraseña; todo el sistema
    Operador   NO crea cuenta: la central lo registra en Operadores con su foto, su usuario y
               su contraseña. Entra con su rostro o con ese usuario y contraseña.
    Paramédico NO crea cuenta: la central lo registra en Paramédicos con su foto, su usuario y
               su contraseña. Entra con su rostro o con ese usuario y contraseña.
    Usuario    crea su cuenta y reporta emergencias por mensaje o llamada.

Face ID del operador y del paramédico
    La central registra a cada operador y paramédico con su foto. El navegador del personal
    calcula el descriptor facial de esa foto (128 números, face-api.js) y lo guarda en su
    registro (PUT /api/auth/rostros/{operador|paramedico}/{id}). Al entrar, el navegador
    calcula el descriptor de su cara y lo manda a POST /api/auth/rostro: el servidor busca a
    la persona más parecida entre operadores y paramédicos y, si la distancia pasa el umbral,
    le abre su sesión. (POST /api/auth/operador se conserva por compatibilidad.)
"""
import hashlib
import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from ..mongo import get_db
from ..repository import consume_password_reset, create_password_reset, create_user, find_user, list_rows
from ..schemas import ForgotPasswordIn, LoginIn, RegisterIn, ResetPasswordIn, RostroIn
from ..security import OPERADOR, PARAMEDICO, PERSONAL, create_token, current_user, hash_password, require_roles, verify_password

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


def paramedico_de(user: dict) -> dict | None:
    """El registro de Paramédicos ligado a la cuenta."""
    if user.get("paramedico_id") is None:
        return None
    return next((p for p in list_rows("paramedics") if p.get("id") == user["paramedico_id"]), None)


def _public(user: dict) -> dict:
    datos = {"username": user["username"], "full_name": user["full_name"], "role": user.get("role") or "Administrador"}
    if datos["role"] == OPERADOR:
        op = operador_de(user)
        datos["operador"] = {"id": op["id"], "nombre": op["nombre"]} if op else None
    if datos["role"] == PARAMEDICO:
        pm = paramedico_de(user)
        datos["paramedico"] = {"id": pm["id"], "nombre": pm["nombre"], "nivel": pm.get("nivel")} if pm else None
    if user.get("telefono"):
        datos["telefono"] = user["telefono"]
    return datos


def _sesion(user: dict, metodo: str = "contraseña") -> dict:
    return {"token": create_token(user["username"], metodo=metodo), "user": _public(user)}


def distancia(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


# Personas que pueden entrar con su rostro: tipo → (colección, nombre para los mensajes).
CON_ROSTRO = {"operador": ("operators", "Operadores"), "paramedico": ("paramedics", "Paramédicos")}


def personas_con_rostro() -> list[dict]:
    """Operadores y paramédicos, cada uno marcado con su tipo en "_tipo"."""
    return [{**r, "_tipo": tipo} for tipo, (col, _) in CON_ROSTRO.items() for r in list_rows(col)]


def reconocer(descriptor: list[float], operadores: list[dict]) -> tuple[dict | None, float | None, str]:
    """Busca a la persona cuya foto se parece más. Solo cuenta a quien tiene foto y su
    descriptor está al día con esa foto."""
    candidatos = [(distancia(descriptor, o["rostro"]), o) for o in operadores
                  if o.get("foto") and o.get("rostro") and o.get("rostro_de") == huella_foto(o["foto"])]
    if not candidatos:
        return None, None, "Todavía no hay fotos registradas para entrar con el rostro."
    candidatos.sort(key=lambda c: c[0])
    d, op = candidatos[0]
    if d > UMBRAL_ROSTRO:
        return None, d, "No te reconocimos. Pide a la central que registre o actualice tu foto."
    if len(candidatos) > 1 and candidatos[1][0] - d < MARGEN_ROSTRO:
        return None, d, "No se pudo distinguir tu rostro con claridad. Busca mejor luz y vuelve a intentarlo."
    return op, d, ""


def coincide_con(descriptor: list[float], persona: dict | None) -> tuple[bool, float | None, str]:
    """¿El rostro es de esta persona? Compara contra el descriptor de su foto (lo decide el
    servidor, no el navegador)."""
    if not persona:
        return False, None, "No se encontró a esa persona."
    if not (persona.get("foto") and persona.get("rostro") and persona.get("rostro_de") == huella_foto(persona["foto"])):
        return False, None, (f"La foto de {persona.get('nombre', 'esa persona')} todavía se está preparando o no tiene "
                             "foto. Espera unos segundos y vuelve a intentarlo.")
    d = distancia(descriptor, persona["rostro"])
    if d > UMBRAL_ROSTRO:
        return False, d, f"El rostro no coincide con {persona['nombre']}."
    return True, d, ""


def registrar_verificacion(nombre: str, contexto: str, coincide: bool, distancia_: float | None,
                           folio: str | None = None, tipo: str | None = None, usuario: str | None = None) -> None:
    """Bitácora de verificaciones (la escribe el servidor, que es quien decidió)."""
    get_db()["verificaciones"].insert_one({
        "operador": nombre, "contexto": contexto, "coincide": coincide,
        **({"distancia": round(distancia_, 4)} if distancia_ is not None else {}),
        **({"emergencia_folio": folio} if folio else {}), **({"tipo": tipo} if tipo else {}),
        "verificado_por": usuario or "Face ID", "momento": datetime.now(timezone.utc),
    })


def cuenta_de_operador(op: dict) -> dict | None:
    """La cuenta del operador (la crea el Administrador en su ficha). Ya no se crea sola:
    sin cuenta, no entra."""
    users = get_db()["users"]
    user = users.find_one({"role": OPERADOR, "operador_id": op["id"]}, {"_id": 0})
    if user and user.get("full_name") != op["nombre"]:
        users.update_one({"username": user["username"]}, {"$set": {"full_name": op["nombre"]}})
        user["full_name"] = op["nombre"]
    return user


@router.post("/login")
def login(body: LoginIn):
    user = find_user(body.username)
    if not user or not user.get("active", True) or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos.")
    # Operadores y paramédicos: solo si su registro sigue activo.
    if user.get("role") == OPERADOR:
        op = operador_de(user)
        if op and op.get("estado") == "Baja":
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"{op['nombre']} está dado de baja.")
    if user.get("role") == PARAMEDICO:
        pm = paramedico_de(user)
        if not pm:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu cuenta no está ligada a un paramédico registrado.")
        if pm.get("estado") == "Baja":
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"{pm['nombre']} está dado de baja.")
    return _sesion(user)


def cuenta_de_paramedico(pm: dict) -> dict | None:
    """La cuenta del paramédico (la crea el Administrador en su ficha). Sin cuenta, no entra."""
    return get_db()["users"].find_one({"role": PARAMEDICO, "paramedico_id": pm["id"]}, {"_id": 0})


@router.post("/rostro")
def login_rostro(body: RostroIn):
    """Entrada solo con el rostro, para operadores y paramédicos."""
    persona, d, motivo = reconocer(body.descriptor, personas_con_rostro())
    get_db()["verificaciones"].insert_one({
        "operador": persona["nombre"] if persona else "(no reconocido)", "contexto": "inicio de sesión",
        "coincide": persona is not None, **({"tipo": persona["_tipo"]} if persona else {}),
        **({"distancia": round(d, 4)} if d is not None else {}),
        "verificado_por": "Face ID", "momento": datetime.now(timezone.utc),
    })
    if not persona:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, motivo)
    if persona.get("estado") == "Baja":
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"{persona['nombre']} está dado de baja.")
    cuenta = cuenta_de_paramedico(persona) if persona["_tipo"] == "paramedico" else cuenta_de_operador(persona)
    if not cuenta or not cuenta.get("active", True):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"Te reconocimos, {persona['nombre']}, pero todavía no tienes acceso. "
                            "Pide al administrador que te lo dé en tu ficha.")
    return _sesion(cuenta, metodo="rostro")


@router.post("/operador")
def login_operador(body: RostroIn):
    """Nombre anterior de POST /api/auth/rostro (lo usaban versiones anteriores de la página)."""
    return login_rostro(body)


# ─────────── descriptores de las fotos (los calcula el navegador del personal) ───────────

solo_personal = require_roles(*PERSONAL)


@router.get("/rostros/pendientes", dependencies=[Depends(solo_personal)])
def rostros_pendientes():
    """Operadores y paramédicos con foto cuyo descriptor falta o es de una foto anterior."""
    return [{"tipo": p["_tipo"], "id": p["id"], "nombre": p["nombre"], "foto": p["foto"]} for p in personas_con_rostro()
            if p.get("foto") and p.get("rostro_de") != huella_foto(p["foto"])]


@router.put("/rostros/{tipo}/{persona_id}", dependencies=[Depends(solo_personal)])
def guardar_rostro_de(tipo: str, persona_id: int, body: RostroIn):
    if tipo not in CON_ROSTRO:
        raise HTTPException(404, "Tipo de persona desconocido.")
    col = CON_ROSTRO[tipo][0]
    persona = next((o for o in list_rows(col) if o.get("id") == persona_id), None)
    if not persona or not persona.get("foto"):
        raise HTTPException(404, "Esa persona no tiene foto registrada.")
    get_db()[col].update_one({"id": persona_id},
                             {"$set": {"rostro": body.descriptor, "rostro_de": huella_foto(persona["foto"])}})
    return {"ok": True}


@router.put("/rostros/{operador_id}", dependencies=[Depends(solo_personal)])
def guardar_rostro(operador_id: int, body: RostroIn):
    """Ruta anterior, solo para operadores."""
    return guardar_rostro_de("operador", operador_id, body)


@router.get("/me")
def me(user: dict = Depends(current_user)):
    return _public(user)


@router.post("/register", status_code=201)
def register(body: RegisterIn):
    """Registro público: solo cuentas de Usuario (quien reporta emergencias)."""
    try:
        create_user(body.username, body.password, body.full_name, "Usuario")
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
