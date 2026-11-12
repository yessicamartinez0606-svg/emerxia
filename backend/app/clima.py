"""Clima de las zonas que cubre Emergexia y cómo frena el tránsito.

De dónde salen los datos
    Open-Meteo (open-meteo.com): API meteorológica gratuita y sin clave. Se pide el clima
    actual de todas las zonas en una sola llamada y se guarda 10 minutos en memoria (y en
    DATA_DIR/osm/clima.json para tener el último dato si se cae el internet).

Cómo se usa
    - Si está lloviendo en una zona, las ambulancias van más lento ahí: los minutos de cada
      calle de esa zona se multiplican por FACTOR_LLUVIA (en app/red_vial.py), así que la
      búsqueda de rutas evita la zona si hay un camino mejor.
    - El modelo de tiempo de llegada (app/eta.py) recibe "lluvia = sí/no" de la zona destino.
    - Para presentar el proyecto en un día sin lluvia, el personal puede SIMULAR lluvia en una
      zona; la pantalla lo marca como simulado.
"""
from __future__ import annotations

import json
import math
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path


# Zonas de destino (las mismas de la práctica de regresión) con un punto de referencia y la
# distancia aproximada por calle desde el Hospital IMSS 220.
ZONAS = [
    {"id": "centro", "nombre": "Centro Toluca", "lat": 19.2925, "lng": -99.6569, "km": 3},
    {"id": "metepec", "nombre": "Metepec", "lat": 19.2517, "lng": -99.6045, "km": 7},
    {"id": "autopan", "nombre": "San Pablo Autopan", "lat": 19.3460, "lng": -99.6560, "km": 9},
    {"id": "atenco", "nombre": "San Mateo Atenco", "lat": 19.2667, "lng": -99.5333, "km": 9},
    {"id": "zinacantepec", "nombre": "Zinacantepec", "lat": 19.2840, "lng": -99.7340, "km": 10},
    {"id": "lerma", "nombre": "Lerma", "lat": 19.2850, "lng": -99.5110, "km": 14},
]

# Con lluvia la ambulancia va al 75 % de su velocidad (minutos × 1.33); con tormenta, al 60 %.
VELOCIDAD_LLUVIA = 0.75
VELOCIDAD_TORMENTA = 0.60

CADUCIDAD_S = 600
URL = "https://api.open-meteo.com/v1/forecast"

# Códigos WMO que usa Open-Meteo.
DESCRIPCION = {
    0: "Despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado", 3: "Nublado",
    45: "Niebla", 48: "Niebla con escarcha",
    51: "Llovizna ligera", 53: "Llovizna", 55: "Llovizna intensa", 56: "Llovizna helada", 57: "Llovizna helada",
    61: "Lluvia ligera", 63: "Lluvia", 65: "Lluvia fuerte", 66: "Lluvia helada", 67: "Lluvia helada fuerte",
    71: "Nevada ligera", 73: "Nevada", 75: "Nevada fuerte", 77: "Granizo fino",
    80: "Chubascos ligeros", 81: "Chubascos", 82: "Chubascos fuertes",
    85: "Chubascos de nieve", 86: "Chubascos de nieve",
    95: "Tormenta eléctrica", 96: "Tormenta con granizo", 99: "Tormenta con granizo fuerte",
}
LLUVIA = set(range(51, 68)) | {80, 81, 82, 95, 96, 99}
TORMENTA = {65, 82, 95, 96, 99}

_lock = threading.Lock()
_estado: dict = {"zonas": {}, "momento": 0.0, "fuente": None, "error": None}
_simulado: dict[str, bool] = {}          # zona id -> lluvia simulada (True) o despejado (False)
_cache_factor: dict[tuple[float, float], str] = {}


# ─────────────────────────── consulta a Open-Meteo ───────────────────────────

def _archivo() -> Path:
    from .config import settings
    d = Path(settings.data_dir) / "osm"
    d.mkdir(parents=True, exist_ok=True)
    return d / "clima.json"


def _pedir() -> dict[str, dict]:
    params = {
        "latitude": ",".join(f"{z['lat']}" for z in ZONAS),
        "longitude": ",".join(f"{z['lng']}" for z in ZONAS),
        "current": "temperature_2m,precipitation,rain,showers,weather_code,wind_speed_10m,cloud_cover",
        "timezone": "America/Mexico_City",
    }
    req = urllib.request.Request(URL + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": "Emergexia/1.0 (proyecto escolar)"})
    with urllib.request.urlopen(req, timeout=8) as r:   # noqa: S310 (URL fija)
        datos = json.loads(r.read())
    if isinstance(datos, dict):
        datos = [datos]
    out = {}
    for z, d in zip(ZONAS, datos):
        c = d.get("current", {})
        out[z["id"]] = {
            "temperatura": c.get("temperature_2m"),
            "precipitacion_mm": c.get("precipitation") or 0,
            "codigo": c.get("weather_code"),
            "viento_kmh": c.get("wind_speed_10m"),
            "nubosidad": c.get("cloud_cover"),
            "hora_dato": c.get("time"),
        }
    return out


def actualizar(forzar: bool = False) -> None:
    """Pide el clima si el dato tiene más de 10 minutos. Nunca lanza error: si no hay
    internet se queda con el último dato guardado (o sin dato)."""
    with _lock:
        if not forzar and time.time() - _estado["momento"] < CADUCIDAD_S and _estado["zonas"]:
            return
        try:
            _estado["zonas"] = _pedir()
            _estado.update(momento=time.time(), fuente="Open-Meteo", error=None)
            try:
                _archivo().write_text(json.dumps({"zonas": _estado["zonas"], "momento": _estado["momento"]}), encoding="utf-8")
            except Exception:  # noqa: BLE001  (guardar el respaldo es opcional)
                pass
        except Exception as exc:  # noqa: BLE001
            _estado["error"] = f"No se pudo consultar el clima ({exc.__class__.__name__})."
            _estado["momento"] = time.time() - CADUCIDAD_S + 60    # reintenta en 1 minuto
            if not _estado["zonas"]:
                try:
                    guardado = json.loads(_archivo().read_text(encoding="utf-8"))
                    _estado["zonas"] = guardado["zonas"]
                    _estado["fuente"] = "Open-Meteo (último dato guardado)"
                except Exception:  # noqa: BLE001  (no hay respaldo)
                    pass
        _cache_factor.clear()


# ─────────────────────────── lectura ───────────────────────────

def _zona_mas_cercana(lat: float, lng: float) -> dict:
    cos = math.cos(math.radians(lat))
    return min(ZONAS, key=lambda z: (z["lat"] - lat) ** 2 + ((z["lng"] - lng) * cos) ** 2)


def zona_de(lat: float, lng: float) -> dict:
    return _zona_mas_cercana(lat, lng)


def _condicion(zona_id: str) -> dict:
    d = _estado["zonas"].get(zona_id)
    if zona_id in _simulado:
        llueve = _simulado[zona_id]
        codigo = 63 if llueve else 1
        return {"lluvia": llueve, "tormenta": False, "codigo": codigo, "descripcion": DESCRIPCION[codigo],
                "simulado": True, **({k: d[k] for k in ("temperatura", "viento_kmh")} if d else {})}
    if not d:
        return {"lluvia": False, "tormenta": False, "codigo": None, "descripcion": "Sin datos", "simulado": False}
    codigo = d.get("codigo")
    llueve = (d.get("precipitacion_mm") or 0) >= 0.1 or codigo in LLUVIA
    return {**d, "lluvia": llueve, "tormenta": codigo in TORMENTA, "descripcion": DESCRIPCION.get(codigo, "—"),
            "simulado": False}


def velocidad_relativa(cond: dict) -> float:
    if not cond["lluvia"]:
        return 1.0
    return VELOCIDAD_TORMENTA if cond["tormenta"] else VELOCIDAD_LLUVIA


def factor_minutos(lat: float, lng: float) -> float:
    """Cuánto más tardan los minutos en ese punto por el clima (1 = nada, 1.33 = lluvia).
    Solo lee lo que ya está en memoria: no hace llamadas a internet."""
    clave = (round(lat, 3), round(lng, 3))
    zid = _cache_factor.get(clave)
    if zid is None:
        zid = _cache_factor[clave] = _zona_mas_cercana(lat, lng)["id"]
    return 1 / velocidad_relativa(_condicion(zid))


def resumen() -> dict:
    """Clima de cada zona y cuánto se frena el tránsito."""
    actualizar()
    zonas = []
    for z in ZONAS:
        c = _condicion(z["id"])
        v = velocidad_relativa(c)
        zonas.append({**z, **c, "velocidad_relativa": v,
                      "retraso_pct": round((1 / v - 1) * 100)})
    con_lluvia = [z["nombre"] for z in zonas if z["lluvia"]]
    return {
        "zonas": zonas,
        "con_lluvia": con_lluvia,
        "mensaje": (f"Llueve en {', '.join(con_lluvia)}: las ambulancias tardan más ahí y las rutas lo toman en cuenta."
                    if con_lluvia else "Sin lluvia en las zonas: el tránsito no se frena por el clima."),
        "fuente": _estado["fuente"] or "Sin conexión",
        "actualizado": _estado["momento"] if _estado["zonas"] else None,
        "error": _estado["error"] if not _estado["zonas"] else None,
        "simulacion": dict(_simulado),
    }


def lluvia_en(lat: float, lng: float) -> dict:
    actualizar()
    z = _zona_mas_cercana(lat, lng)
    c = _condicion(z["id"])
    return {"zona": z["nombre"], "zona_id": z["id"], **c, "velocidad_relativa": velocidad_relativa(c)}


def simular(zona_id: str, lluvia: bool | None) -> dict:
    """lluvia=True/False fija el clima de la zona para una demostración; None lo quita."""
    if zona_id not in {z["id"] for z in ZONAS}:
        raise ValueError("Esa zona no existe.")
    if lluvia is None:
        _simulado.pop(zona_id, None)
    else:
        _simulado[zona_id] = lluvia
    _cache_factor.clear()
    return resumen()
