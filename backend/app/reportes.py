"""Reportes de emergencia que mandan los usuarios: preguntas de sí/no, prioridad y duplicados.

Funciones puras (no tocan la base de datos), igual que app/flota.py y app/logica.py; se
prueban solas en probar_reportes.py. El router (app/routers/portal.py) las usa al recibir
un reporte.

PREGUNTAS
    Quien reporta contesta con un toque «Sí», «No» o «No sé». Hay preguntas para cualquier
    emergencia (¿está consciente?, ¿respira?, ¿sangra mucho?) y otras según el tipo
    (parto → ¿ya se ve la cabeza del bebé?, accidente → ¿hay personas atrapadas?, …).
    Cada pregunta dice qué respuesta es señal de alarma y qué tan grave es:
        critica   la emergencia pasa a prioridad Alta
        eleva     sube un nivel (Baja → Media → Alta)
    «No sé» (None) no cambia nada.

PRIORIDAD
    Empieza con la del tipo (TIPOS) y se ajusta con las respuestas. Se guardan también los
    motivos ("No respira", "Hay personas atrapadas") para que la central vea por qué.

DUPLICADOS
    Un choque en Paseo Tollocan lo reportan cinco personas. Si llega un reporte del mismo
    tipo, a menos de RADIO_DUPLICADO_M metros (o con la misma dirección si no hay punto en el
    mapa) de una emergencia abierta reportada hace menos de MINUTOS_DUPLICADO, no se crea
    otra emergencia ni se mandan más ambulancias: el reporte se suma a la que ya existe.
"""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime, timezone

# Tipo de emergencia → prioridad con la que llega a la central (antes de las respuestas).
TIPOS = {
    "Accidente de tránsito": "Alta",
    "Dolor de pecho o infarto": "Alta",
    "Dificultad para respirar": "Alta",
    "Persona inconsciente": "Alta",
    "Parto o embarazo": "Alta",
    "Herida o sangrado": "Media",
    "Caída o fractura": "Media",
    "Quemadura": "Media",
    "Intoxicación": "Media",
    "Otro": "Media",
}

NIVELES = ("Baja", "Media", "Alta")


def _p(clave: str, texto: str, alarma: bool, gravedad: str, motivo: str) -> dict:
    """alarma: la respuesta (True = «Sí», False = «No») que es señal de alarma."""
    return {"clave": clave, "texto": texto, "alarma": alarma, "gravedad": gravedad, "motivo": motivo}


# Para cualquier tipo de emergencia.
GENERALES = [
    _p("consciente", "¿Está consciente (responde si le hablas)?", False, "critica", "No está consciente"),
    _p("respira", "¿Respira normalmente?", False, "critica", "No respira normalmente"),
    _p("sangrado", "¿Sangra mucho?", True, "eleva", "Sangrado abundante"),
]

POR_TIPO: dict[str, list[dict]] = {
    "Accidente de tránsito": [
        _p("atrapados", "¿Hay personas atrapadas en los vehículos?", True, "critica", "Hay personas atrapadas"),
        _p("fuego", "¿Hay fuego, humo o fuga de gasolina?", True, "critica", "Fuego o fuga de gasolina"),
        _p("atropellado", "¿Atropellaron a alguien?", True, "eleva", "Persona atropellada"),
    ],
    "Dolor de pecho o infarto": [
        _p("irradia", "¿El dolor se va al brazo, cuello o mandíbula?", True, "eleva", "Dolor que se irradia"),
        _p("sudor", "¿Suda frío o está muy pálido?", True, "eleva", "Sudor frío o palidez"),
    ],
    "Dificultad para respirar": [
        _p("morado", "¿Tiene los labios o las uñas morados?", True, "critica", "Labios o uñas morados"),
        _p("hablar", "¿Puede decir frases completas?", False, "eleva", "No puede hablar de corrido"),
    ],
    "Persona inconsciente": [
        _p("convulsiona", "¿Está convulsionando?", True, "critica", "Convulsiones"),
    ],
    "Parto o embarazo": [
        _p("cabeza", "¿Ya se ve la cabeza del bebé?", True, "critica", "Parto en curso (se ve la cabeza)"),
        _p("fuente", "¿Ya se le rompió la fuente?", True, "eleva", "Ya rompió fuente"),
        _p("sangra_parto", "¿Tiene sangrado vaginal abundante?", True, "critica", "Sangrado abundante en el embarazo"),
    ],
    "Herida o sangrado": [
        _p("arma", "¿La herida es por arma (cuchillo o bala)?", True, "critica", "Herida por arma"),
        _p("para", "¿El sangrado se detiene al presionar?", False, "eleva", "El sangrado no se detiene"),
    ],
    "Caída o fractura": [
        _p("cabeza_golpe", "¿Se golpeó la cabeza?", True, "eleva", "Golpe en la cabeza"),
        _p("altura", "¿Cayó de más de 2 metros (un piso)?", True, "eleva", "Caída de altura"),
        _p("mover", "¿Puede mover brazos y piernas?", False, "critica", "No puede mover brazos o piernas"),
    ],
    "Quemadura": [
        _p("zona", "¿Es en la cara, el cuello, las manos o los genitales?", True, "eleva", "Quemadura en zona delicada"),
        _p("grande", "¿Es más grande que la palma de su mano?", True, "eleva", "Quemadura extensa"),
        _p("electrica", "¿Fue por electricidad o químicos?", True, "eleva", "Quemadura eléctrica o química"),
    ],
    "Intoxicación": [
        _p("reciente", "¿Tomó o comió la sustancia hace menos de una hora?", True, "eleva", "Intoxicación reciente"),
        _p("nino", "¿La persona intoxicada es un niño?", True, "eleva", "Niño intoxicado"),
    ],
}


def preguntas_de(tipo: str) -> list[dict]:
    return GENERALES + POR_TIPO.get(tipo, [])


def catalogo() -> dict:
    """Lo que necesita la pantalla de Reportar: tipos y preguntas (sin las reglas internas)."""
    publica = lambda ps: [{"clave": p["clave"], "texto": p["texto"]} for p in ps]  # noqa: E731
    return {"tipos": list(TIPOS), "generales": publica(GENERALES),
            "por_tipo": {t: publica(ps) for t, ps in POR_TIPO.items()}}


def _subir(prioridad: str, niveles: int = 1) -> str:
    return NIVELES[min(len(NIVELES) - 1, NIVELES.index(prioridad) + niveles)]


def calcular_prioridad(tipo: str, respuestas: dict[str, bool | None]) -> dict:
    """Prioridad del reporte según su tipo y las respuestas de sí/no.

    Regresa {"prioridad", "base", "motivos", "respuestas"}; "respuestas" es la lista legible
    [{"pregunta", "respuesta"}] que se guarda en la emergencia (solo las contestadas).
    """
    tipo = tipo if tipo in TIPOS else "Otro"
    base = TIPOS[tipo]
    prioridad = base
    motivos, legibles = [], []
    criticas = eleva = 0
    for p in preguntas_de(tipo):
        r = respuestas.get(p["clave"])
        if r is None:
            continue
        legibles.append({"pregunta": p["texto"], "respuesta": "Sí" if r else "No"})
        if r == p["alarma"]:
            motivos.append(p["motivo"])
            if p["gravedad"] == "critica":
                criticas += 1
            else:
                eleva += 1
    if criticas:
        prioridad = "Alta"
    elif eleva:
        prioridad = _subir(prioridad)
    return {"prioridad": prioridad, "base": base, "motivos": motivos, "respuestas": legibles,
            "critica": criticas > 0}


def mayor_prioridad(a: str | None, b: str | None) -> str:
    vals = [x for x in (a, b) if x in NIVELES] or ["Media"]
    return max(vals, key=NIVELES.index)


# ─────────────────────────── duplicados ───────────────────────────

RADIO_DUPLICADO_M = 300
MINUTOS_DUPLICADO = 20


def distancia_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distancia en metros entre dos puntos (fórmula del haversine)."""
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"\(referencias:.*?\)", "", t)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _como_utc(momento) -> datetime | None:
    if not isinstance(momento, datetime):
        return None
    # pymongo regresa las fechas sin zona horaria (en UTC).
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def buscar_duplicado(tipo: str, lat: float | None, lng: float | None, direccion: str,
                     abiertas: list[dict], ahora: datetime | None = None) -> tuple[dict | None, float | None]:
    """La emergencia abierta que parece ser la misma que este reporte, o (None, None).

    Mismo tipo, reportada hace menos de MINUTOS_DUPLICADO y a menos de RADIO_DUPLICADO_M
    metros. Si alguno de los dos no tiene punto en el mapa, se compara la dirección escrita.
    Regresa también la distancia en metros (None si se comparó por dirección).
    """
    ahora = ahora or datetime.now(timezone.utc)
    dir_nueva = _normalizar(direccion)
    mejor, mejor_d = None, None
    for em in abiertas:
        if em.get("estado") == "Cerrada" or em.get("tipo") != tipo:
            continue
        creada = _como_utc(em.get("created_at"))
        if creada is None or (ahora - creada).total_seconds() > MINUTOS_DUPLICADO * 60:
            continue
        if None not in (lat, lng, em.get("lat"), em.get("lng")):
            d = distancia_m(lat, lng, em["lat"], em["lng"])
            if d <= RADIO_DUPLICADO_M and (mejor_d is None or d < mejor_d):
                mejor, mejor_d = em, d
        elif dir_nueva and dir_nueva == _normalizar(em.get("direccion", "")) and mejor is None:
            mejor = em
    return mejor, (round(mejor_d) if mejor_d is not None else None)
