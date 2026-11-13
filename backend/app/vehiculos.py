"""Ambulancias con datos reales de vehículos (marca, modelo y año) desde una API pública.

De dónde salen los datos
    - API vPIC de la NHTSA (vpic.nhtsa.dot.gov), del Departamento de Transporte de EE. UU.:
      gratuita, sin clave. Con GetModelsForMakeYear confirma qué modelos fabricó cada marca
      en cada año, con su nombre oficial e identificador (Model_ID). Se usa para los chasises
      con los que se construyen ambulancias en México: Ford Transit, Mercedes-Benz Sprinter,
      Chevrolet Express y RAM ProMaster.
    - Tanque de gasolina: fichas técnicas del fabricante (citadas abajo en FICHAS). La API
      no trae ese dato.
    - Rendimiento (km/L): estimado para una ambulancia ya equipada (más peso y equipo
      encendido). La EPA no publica rendimiento de estas camionetas por ser vehículos pesados.

Lo que NO es real
    Las placas (son números económicos de la central), el kilometraje, la gasolina actual y el
    conductor: la API no da datos de unidades concretas de ningún hospital.

Si no hay internet, se usa una copia de respaldo con los mismos modelos (FICHAS) y la ficha
lo indica en "fuente_vehiculo".
"""
from __future__ import annotations

import json
import random
import time
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMakeYear/make/{marca}/modelyear/{anio}?format=json"
FUENTE_API = "API vPIC · NHTSA"
FUENTE_RESPALDO = "Respaldo sin conexión (mismos modelos de la API vPIC)"
ANIOS = list(range(2018, 2026))
CADUCIDAD_S = 7 * 24 * 3600          # los modelos de un año no cambian: se guardan una semana
_sin_red_hasta = 0.0                 # tras un error de red no se reintenta en 2 min (no atora nada)

# Chasises que se usan para ambulancias en México. "base" es como aparece el modelo en vPIC.
FICHAS = [
    {"marca": "Ford", "api": "ford", "base": "Transit", "excluir": ["Connect"],
     "motor": "3.5 L V6 gasolina", "tanque_litros": 94.6, "rendimiento_km_l": 6.0, "tipo": "Avanzada",
     "ficha": "Transit-350 2022: tanque de 25 gal (cars.com)"},
    {"marca": "Mercedes-Benz", "api": "mercedes-benz", "base": "Sprinter", "excluir": [],
     "motor": "2.0 L diésel", "tanque_litros": 93.0, "rendimiento_km_l": 8.0, "tipo": "Avanzada",
     "ficha": "Sprinter 2022: tanque de 93 L (guideautoweb.com)"},
    {"marca": "Chevrolet", "api": "chevrolet", "base": "Express", "excluir": [],
     "motor": "4.3 L V6 gasolina", "tanque_litros": 117.3, "rendimiento_km_l": 5.0, "tipo": "Básica",
     "ficha": "Express 3500 2022: tanque de 31 gal (cars.com)"},
    {"marca": "RAM", "api": "ram", "base": "ProMaster", "excluir": ["City"],
     "motor": "3.6 L V6 gasolina", "tanque_litros": 90.8, "rendimiento_km_l": 6.0, "tipo": "Básica",
     "ficha": "ProMaster Cutaway 3500 2022: tanque de 90.8 L (auto123.com)"},
]
MARCAS = [f["marca"] for f in FICHAS]

# Prefijo del número económico de cada hospital (app/genetico.py).
PREFIJO = {"imss220": "I220", "nsj": "NSJ", "cr-toluca": "CRT", "issste": "ISS", "imss251": "I251",
           "cr-metepec": "CRM", "cr-sma": "CRS", "cr-lerma": "CRL", "hm-lerma": "HML"}


def ficha(marca: str) -> dict:
    f = next((x for x in FICHAS if x["marca"].lower() == (marca or "").lower()), None)
    if not f:
        raise ValueError(f"Marca no disponible. Usa una de: {', '.join(MARCAS)}.")
    return f


# ─────────────────────────── consulta a la API ───────────────────────────

def _archivo(marca: str, anio: int) -> Path | None:
    try:
        from .config import settings
        d = Path(settings.data_dir) / "vpic"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{marca.lower()}_{anio}.json"
    except Exception:  # noqa: BLE001  (sin configuración: no se guarda copia)
        return None


def _pedir(marca_api: str, anio: int) -> list[dict]:
    url = URL.format(marca=urllib.parse.quote(marca_api), anio=anio)
    req = urllib.request.Request(url, headers={"User-Agent": "Emergexia/1.0 (proyecto escolar)"})
    with urllib.request.urlopen(req, timeout=10) as r:   # noqa: S310 (URL fija)
        datos = json.loads(r.read())
    return datos.get("Results") or []


def modelos_api(marca: str, anio: int) -> dict:
    """Todos los modelos que la API vPIC registra para esa marca y año (guardados una semana)."""
    f = ficha(marca)
    archivo = _archivo(f["marca"], anio)
    if archivo and archivo.exists() and time.time() - archivo.stat().st_mtime < CADUCIDAD_S:
        try:
            return json.loads(archivo.read_text(encoding="utf-8"))
        except ValueError:
            pass
    global _sin_red_hasta
    try:
        if time.time() < _sin_red_hasta:
            raise ConnectionError("sin conexión reciente")
        resultados = _pedir(f["api"], anio)
        out = {"marca": f["marca"], "anio": anio, "fuente": FUENTE_API,
               "modelos": sorted({(r.get("Model_Name") or "").strip(): r.get("Model_ID") for r in resultados}.items())}
        out["modelos"] = [{"modelo": m, "model_id": i} for m, i in out["modelos"] if m]
        if archivo:
            try:
                archivo.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
        return out
    except Exception as exc:  # noqa: BLE001  (sin internet: copia guardada aunque sea vieja, o respaldo)
        _sin_red_hasta = time.time() + 120
        if archivo and archivo.exists():
            try:
                return {**json.loads(archivo.read_text(encoding="utf-8")), "aviso": "Sin conexión: se usa la última consulta guardada."}
            except ValueError:
                pass
        return {"marca": f["marca"], "anio": anio, "fuente": FUENTE_RESPALDO,
                "modelos": [{"modelo": f["base"], "model_id": None}],
                "aviso": f"No se pudo consultar la API vPIC ({exc.__class__.__name__}): se usa el respaldo."}


def modelos_ambulancia(marca: str, anio: int) -> dict:
    """Solo los modelos de esa marca que sirven de chasis de ambulancia, con su ficha técnica."""
    f = ficha(marca)
    r = modelos_api(marca, anio)
    utiles = [m for m in r["modelos"]
              if f["base"].lower() in m["modelo"].lower() and not any(x.lower() in m["modelo"].lower() for x in f["excluir"])]
    return {
        "marca": f["marca"], "anio": anio, "fuente": r["fuente"], "aviso": r.get("aviso"),
        "total_modelos_marca": len(r["modelos"]),
        "modelos": [{**m, "motor": f["motor"], "tanque_litros": f["tanque_litros"],
                     "rendimiento_km_l": f["rendimiento_km_l"], "tipo_sugerido": f["tipo"], "ficha": f["ficha"]}
                    for m in utiles],
    }


# ─────────────────────────── flota ───────────────────────────

def _vehiculo(rng: random.Random, consultas: dict) -> dict:
    """Elige un chasis real (marca, modelo de la API, año) para una ambulancia."""
    for _ in range(12):
        f = rng.choice(FICHAS)
        anio = rng.choice(ANIOS)
        clave = (f["marca"], anio)
        if clave not in consultas:
            consultas[clave] = modelos_ambulancia(f["marca"], anio)
        r = consultas[clave]
        if r["modelos"]:
            m = rng.choice(r["modelos"])
            return {"marca": f["marca"], "modelo": m["modelo"], "anio": anio, "model_id": m["model_id"],
                    "motor": f["motor"], "tanque_litros": f["tanque_litros"], "rendimiento_km_l": f["rendimiento_km_l"],
                    "tipo": f["tipo"], "fuente_vehiculo": r["fuente"]}
    f = FICHAS[0]
    return {"marca": f["marca"], "modelo": f["base"], "anio": ANIOS[-1], "model_id": None, "motor": f["motor"],
            "tanque_litros": f["tanque_litros"], "rendimiento_km_l": f["rendimiento_km_l"], "tipo": f["tipo"],
            "fuente_vehiculo": FUENTE_RESPALDO}


def _uso(anio: int, rng: random.Random) -> dict:
    """Kilometraje según los años de uso (~25 a 35 mil km por año) y gasolina actual."""
    anios_uso = max(0.5, 2026 - anio)
    return {"kilometraje": round(anios_uso * rng.uniform(25000, 35000)),
            "combustible_pct": rng.choice([45, 55, 62, 70, 78, 85, 90, 96, 100])}


def plan_flota(ambulancias: list[dict], operadores: list[dict], semilla: int = 220) -> dict:
    """Qué hacer para tener la flota con vehículos reales:
    - a las ambulancias que ya existen y no tienen marca se les pone un vehículo real
      (conservan su placa e historial);
    - se crean las que faltan para que cada hospital tenga las de app/genetico.py.
    Regresa {"actualizar": [(id, cambios)], "crear": [ambulancia], "fuente": ...}."""
    from .genetico import HOSPITALES

    rng = random.Random(semilla)
    consultas: dict = {}
    actualizar = []
    for a in sorted(ambulancias, key=lambda x: x.get("id", 0)):
        if not a.get("marca"):
            v = _vehiculo(rng, consultas)
            # Conserva el tipo que ya tenía (Básica/Avanzada) y su gasolina/kilometraje.
            actualizar.append((a["id"], {k: v[k] for k in ("marca", "modelo", "anio", "model_id", "motor",
                                                              "tanque_litros", "rendimiento_km_l", "fuente_vehiculo")}))

    placas = {a.get("placa") for a in ambulancias}
    con_ambulancia = {(a.get("conductor") or "").strip().lower() for a in ambulancias}
    libres = [o["nombre"] for o in operadores if o.get("nombre") and o["nombre"].strip().lower() not in con_ambulancia]
    crear = []
    for h in HOSPITALES:
        tiene = sum(1 for a in ambulancias if a.get("hospital") == h["nombre"])
        n = 1
        for _ in range(max(0, h["ambulancias"] - tiene)):
            while f"{PREFIJO.get(h['id'], 'AMB')}-{n:02d}" in placas:
                n += 1
            placa = f"{PREFIJO.get(h['id'], 'AMB')}-{n:02d}"
            placas.add(placa)
            v = _vehiculo(rng, consultas)
            crear.append({"placa": placa, "hospital": h["nombre"], "estado": "Libre",
                          "conductor": libres.pop(0) if libres else "", **v, **_uso(v["anio"], rng)})
    fuentes = {r["fuente"] for r in consultas.values()}
    return {"actualizar": actualizar, "crear": crear,
            "fuente": FUENTE_API if fuentes == {FUENTE_API} else (FUENTE_RESPALDO if FUENTE_API not in fuentes else "API vPIC y respaldo"),
            "consultas": len(consultas)}
