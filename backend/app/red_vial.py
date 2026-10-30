"""Red vial real de Toluca para la ruta de la ambulancia.

De dónde salen los datos
    Calles      OpenStreetMap, por medio de la API de Overpass (overpass-api.de).
    Direcciones Nominatim (nominatim.openstreetmap.org) convierte la dirección escrita de la
                emergencia en coordenadas.
    Tráfico     ESTIMADO (simulado): no hay datos de tráfico en vivo. Se calcula según la
                hora del día (pico, valle o noche) y el tipo de vía; las avenidas grandes se
                cargan más en hora pico.

Las respuestas de Overpass y Nominatim se guardan en DATA_DIR/osm para no volver a
pedirlas (y para respetar los límites de uso de esos servicios).

Con las calles se arma el espacio de estados de app/busqueda.py: cada esquina es un estado
y cada tramo de calle entre dos esquinas es un operador.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import busqueda
from .config import settings

# ─────────────────────────── Lugares fijos ───────────────────────────

HOSPITAL = {
    "id": "IMSS220",
    "nombre": "Hospital General Regional No. 220 IMSS",
    "corto": "Hospital IMSS 220",
    "direccion": "Paseo Tollocan 620 esq. Nezahualcóyotl, Col. Vértice, Toluca",
    "lat": 19.2828591,
    "lng": -99.6393513,
}

# Zona de Toluca que se muestra en el mapa general (sur, oeste, norte, este).
ZONA_TOLUCA = (19.245, -99.715, 19.320, -99.585)

# ─────────────────────────── Vías y tráfico ───────────────────────────

# Velocidad de la ambulancia con la vía libre (km/h), según el tipo de vía de OSM.
VELOCIDAD = {
    "motorway": 70, "trunk": 55, "primary": 45, "secondary": 40, "tertiary": 35,
    "motorway_link": 35, "trunk_link": 35, "primary_link": 30, "secondary_link": 30,
    "tertiary_link": 30, "unclassified": 30, "residential": 25, "living_street": 15,
    "service": 15,
}
PRINCIPALES = ("motorway", "trunk", "primary", "secondary", "tertiary")
LOCALES = ("unclassified", "residential", "living_street", "service")

TIPO_VIA = {
    "motorway": "Autopista", "trunk": "Vía rápida", "primary": "Avenida principal",
    "secondary": "Avenida", "tertiary": "Calle colectora",
}


def periodo(hora: int) -> str:
    """pico | valle | noche, según la hora (0-23)."""
    if 7 <= hora < 10 or 13 <= hora < 16 or 18 <= hora < 21:
        return "pico"
    if hora >= 22 or hora < 6:
        return "noche"
    return "valle"


NOMBRE_PERIODO = {"pico": "Hora pico", "valle": "Tráfico normal", "noche": "Noche, calles despejadas"}


def _azar(way_id: int) -> float:
    """Número fijo entre 0 y 1 para cada calle, para que no todas las avenidas tengan el
    mismo tráfico pero el resultado sea siempre igual."""
    return (way_id * 2654435761 % 1000) / 1000


def nivel_trafico(highway: str, way_id: int, hora: int) -> str:
    base = highway.removesuffix("_link")
    r = _azar(way_id)
    p = periodo(hora)
    if p == "noche":
        return "libre"
    if p == "pico":
        if highway.endswith("_link"):
            return "moderado"
        if base in ("motorway", "trunk", "primary"):
            return "denso" if r < 0.7 else "moderado"
        if base == "secondary":
            return "denso" if r < 0.35 else "moderado" if r < 0.8 else "libre"
        if base == "tertiary":
            return "moderado" if r < 0.5 else "libre"
        return "libre"
    # valle
    if base in ("motorway", "trunk", "primary"):
        return "moderado" if r < 0.6 else "libre"
    if base == "secondary":
        return "moderado" if r < 0.35 else "libre"
    return "libre"


# ─────────────────────────── Utilidades geográficas ───────────────────────────

def distancia_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def rumbo_grados(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Rumbo de 0 a 360 (0 = norte, 90 = oriente)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lng2 - lng1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


RUMBOS = ["norte", "noreste", "oriente", "sureste", "sur", "suroeste", "poniente", "noroeste"]


def rumbo_texto(grados: float) -> str:
    return RUMBOS[int((grados + 22.5) // 45) % 8]


# ─────────────────────────── Servicios externos con caché ───────────────────────────

USER_AGENT = "Emergexia/1.0 (sistema escolar de gestion de emergencias)"
OVERPASS = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")
NOMINATIM = "https://nominatim.openstreetmap.org/search"


class ServicioMapasError(RuntimeError):
    """No se pudieron obtener calles o coordenadas (sin internet, servicio caído, etc.)."""


def _cache_dir() -> Path:
    d = Path(settings.data_dir) / "osm"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _leer_cache(nombre: str):
    f = _cache_dir() / nombre
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    return None


def _guardar_cache(nombre: str, datos) -> None:
    try:
        (_cache_dir() / nombre).write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _http(url: str, data: bytes | None = None, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 (URLs fijas de OSM)
        return r.read()


def overpass(consulta: str) -> dict:
    clave = "overpass-" + hashlib.sha1(consulta.encode()).hexdigest()[:16] + ".json"
    if (datos := _leer_cache(clave)) is not None:
        return datos
    ultimo_error = None
    for url in OVERPASS:
        try:
            datos = json.loads(_http(url, urllib.parse.urlencode({"data": consulta}).encode()))
            _guardar_cache(clave, datos)
            return datos
        except Exception as exc:  # noqa: BLE001
            ultimo_error = exc
    raise ServicioMapasError(
        "No se pudieron descargar las calles de OpenStreetMap. Revisa la conexión a internet "
        f"del servidor ({ultimo_error})."
    )


_ultimo_geocode = 0.0


def geocodificar(direccion: str) -> dict:
    """Convierte una dirección escrita en {lat, lng, encontrado}. Busca dentro de Toluca."""
    global _ultimo_geocode
    texto = " ".join((direccion or "").split())
    if not texto:
        raise ValueError("La emergencia no tiene dirección.")
    consulta = texto
    if not any(z in texto.lower() for z in ("toluca", "metepec", "zinacantepec", "lerma", "estado de m")):
        consulta += ", Toluca, Estado de México"

    cache = _leer_cache("geocode.json") or {}
    if consulta in cache:
        return cache[consulta]

    def pedir(acotar: bool) -> list:
        global _ultimo_geocode
        espera = 1.1 - (time.time() - _ultimo_geocode)       # Nominatim: máximo 1 por segundo
        if espera > 0:
            time.sleep(espera)
        params = {"format": "jsonv2", "limit": 1, "countrycodes": "mx", "q": consulta,
                  "addressdetails": 0, "accept-language": "es"}
        if acotar:
            params.update(viewbox="-99.80,19.38,-99.50,19.18", bounded=1)
        try:
            return json.loads(_http(NOMINATIM + "?" + urllib.parse.urlencode(params), timeout=20))
        except Exception as exc:  # noqa: BLE001
            raise ServicioMapasError(f"No se pudo buscar la dirección en el mapa ({exc}).") from exc
        finally:
            _ultimo_geocode = time.time()

    res = pedir(True) or pedir(False)
    if not res:
        raise ValueError(f"No se encontró en el mapa la dirección «{texto}». Escríbela con calle, número y colonia.")
    punto = {"lat": float(res[0]["lat"]), "lng": float(res[0]["lon"]), "texto": res[0].get("display_name", texto)}
    cache[consulta] = punto
    _guardar_cache("geocode.json", cache)
    return punto


# ─────────────────────────── Grafo de esquinas ───────────────────────────

@dataclass
class Tramo:
    id: int
    a: int                    # esquina de salida (id de nodo OSM)
    b: int                    # esquina de llegada
    geom: list[tuple[float, float]]
    metros: float
    way_id: int
    nombre: str | None
    highway: str


@dataclass
class Grafo:
    coords: dict[int, tuple[float, float]] = field(default_factory=dict)
    nombres: dict[int, set[str]] = field(default_factory=dict)   # calles que pasan por la esquina
    salidas: dict[int, list[Tramo]] = field(default_factory=dict)
    tramos: list[Tramo] = field(default_factory=list)

    def nombre_esquina(self, nid: int) -> str:
        n = sorted(self.nombres.get(nid, ()))
        if len(n) >= 2:
            return f"{n[0]} y {n[1]}"
        if n:
            return n[0]
        return "Esquina sin nombre"


def _via_valida(tags: dict) -> bool:
    hw = tags.get("highway", "")
    if hw not in VELOCIDAD:
        return False
    if tags.get("access") in ("private", "no") or tags.get("motor_vehicle") in ("private", "no"):
        return False
    if hw == "service" and tags.get("service") in ("parking_aisle", "drive-through"):
        return False
    return True


def _sentido(tags: dict) -> tuple[bool, bool]:
    """(se puede ir hacia adelante, se puede ir hacia atrás) según el sentido de la vía."""
    ow = tags.get("oneway", "")
    if ow in ("yes", "true", "1"):
        return True, False
    if ow == "-1":
        return False, True
    if ow == "no":
        return True, True
    if tags.get("junction") in ("roundabout", "circular") or tags.get("highway") == "motorway":
        return True, False
    return True, True


def construir_grafo(datos: dict, conservar: set[int] = frozenset()) -> Grafo:
    """Arma el grafo de esquinas a partir de la respuesta de Overpass.

    Un nodo de OSM es esquina si lo comparten dos o más calles, si es el extremo de una calle
    o si está en `conservar` (los puntos de salida y llegada). Los nodos intermedios solo
    dan forma al tramo.
    """
    nodos = {e["id"]: (e["lat"], e["lon"]) for e in datos.get("elements", []) if e["type"] == "node"}
    vias = [e for e in datos.get("elements", []) if e["type"] == "way" and _via_valida(e.get("tags", {}))]

    uso: dict[int, int] = {}
    for w in vias:
        ns = [n for n in w["nodes"] if n in nodos]
        for n in ns:
            uso[n] = uso.get(n, 0) + 1
        if ns:
            uso[ns[0]] = uso.get(ns[0], 0) + 1
            uso[ns[-1]] = uso.get(ns[-1], 0) + 1

    g = Grafo()
    for w in vias:
        tags = w.get("tags", {})
        nombre = tags.get("name") or tags.get("ref")
        hw = tags["highway"]
        adelante, atras = _sentido(tags)
        ns = [n for n in w["nodes"] if n in nodos]
        if len(ns) < 2:
            continue
        if nombre:
            for n in ns:
                if uso.get(n, 0) >= 2:
                    g.nombres.setdefault(n, set()).add(nombre)
        inicio = ns[0]
        geom = [nodos[inicio]]
        metros = 0.0
        for prev, n in zip(ns, ns[1:]):
            metros += distancia_m(*nodos[prev], *nodos[n])
            geom.append(nodos[n])
            if uso.get(n, 0) >= 2 or n in conservar or n == ns[-1]:
                if inicio != n:
                    for desde, hasta, forma, ok in ((inicio, n, geom, adelante), (n, inicio, geom[::-1], atras)):
                        if not ok:
                            continue
                        t = Tramo(len(g.tramos), desde, hasta, list(forma), metros, w["id"], nombre, hw)
                        g.tramos.append(t)
                        g.salidas.setdefault(desde, []).append(t)
                        g.coords[desde] = nodos[desde]
                        g.coords[hasta] = nodos[hasta]
                inicio, geom, metros = n, [nodos[n]], 0.0
    return g


def nodo_mas_cercano(datos: dict, lat: float, lng: float) -> int:
    """El nodo de calle (no de estacionamiento ni privada) más cercano a un punto."""
    nodos = {e["id"]: (e["lat"], e["lon"]) for e in datos.get("elements", []) if e["type"] == "node"}
    candidatos: set[int] = set()
    for e in datos.get("elements", []):
        if e["type"] == "way" and _via_valida(e.get("tags", {})) and e["tags"]["highway"] != "service":
            candidatos.update(n for n in e["nodes"] if n in nodos)
    if not candidatos:
        raise ServicioMapasError("No hay calles cerca de ese punto.")
    cos = math.cos(math.radians(lat))
    return min(candidatos, key=lambda n: (nodos[n][0] - lat) ** 2 + ((nodos[n][1] - lng) * cos) ** 2)


# ─────────────────────────── Descarga de la zona ───────────────────────────

def _bbox(puntos: list[tuple[float, float]], margen_km: float) -> tuple[float, float, float, float]:
    lats = [p[0] for p in puntos]
    lngs = [p[1] for p in puntos]
    dlat = margen_km / 111
    dlng = margen_km / (111 * math.cos(math.radians(sum(lats) / len(lats))))
    return (round(min(lats) - dlat, 3), round(min(lngs) - dlng, 3), round(max(lats) + dlat, 3), round(max(lngs) + dlng, 3))


def calles_para_ruta(puntos: list[tuple[float, float]], radio_local_m: int = 900) -> dict:
    """Avenidas de toda el área entre los puntos y, alrededor de cada punto, también las
    calles de colonia (para poder salir y llegar a la puerta)."""
    s, w, n, e = _bbox(puntos, margen_km=1.5)
    principales = "|".join(PRINCIPALES)
    locales = "|".join(LOCALES)
    alrededor = "".join(
        f'way["highway"~"^({locales}|tertiary)$"](around:{radio_local_m},{lat:.5f},{lng:.5f});'
        for lat, lng in puntos
    )
    consulta = (
        "[out:json][timeout:90];("
        f'way["highway"~"^({principales})(_link)?$"]({s},{w},{n},{e});'
        f"{alrededor});(._;>;);out body qt;"
    )
    return overpass(consulta)


def calles_principales_zona() -> dict:
    s, w, n, e = ZONA_TOLUCA
    consulta = (
        "[out:json][timeout:90];("
        f'way["highway"~"^(motorway|trunk|primary|secondary)(_link)?$"]({s},{w},{n},{e});'
        ");(._;>;);out body qt;"
    )
    return overpass(consulta)


# ─────────────────────────── Ruta ───────────────────────────

def hora_actual() -> int:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Mexico_City")).hour
    except Exception:  # noqa: BLE001  (Windows sin tzdata)
        return datetime.now(timezone(timedelta(hours=-6))).hour


def _minutos(t: Tramo, hora: int, cerradas: set[int]) -> float | None:
    nivel = "bloqueado" if t.way_id in cerradas else nivel_trafico(t.highway, t.way_id, hora)
    factor = busqueda.NIVELES[nivel]
    if factor is None:
        return None
    return t.metros / 1000 / VELOCIDAD[t.highway] * 60 * factor


def problema(grafo: Grafo, inicial: int, meta: int, hora: int, cerradas: set[int] = frozenset()) -> busqueda.Problema:
    def sucesores(estado: int):
        out = []
        for t in grafo.salidas.get(estado, ()):
            m = _minutos(t, hora, cerradas)
            if m is not None:                       # calle cerrada: el operador no aplica
                out.append((t.b, t.id, m))
        return out
    return busqueda.Problema(inicial, meta, sucesores, grafo.nombre_esquina)


def _redondear(geom) -> list[list[float]]:
    return [[round(lat, 6), round(lng, 6)] for lat, lng in geom]


def describir_ruta(grafo: Grafo, aristas: list[int], hora: int) -> dict:
    """Geometría, distancia, tramos coloreados por tráfico e indicaciones vuelta por vuelta."""
    tramos = [grafo.tramos[i] for i in aristas]
    coords: list[tuple[float, float]] = []
    for t in tramos:
        coords.extend(t.geom if not coords else t.geom[1:])

    # Tramos seguidos con el mismo tráfico, para pintar la ruta por colores.
    # Cada uno lleva sus km y minutos (con y sin tráfico) para simular el avance de la ambulancia.
    por_trafico: list[dict] = []
    for t in tramos:
        nivel = nivel_trafico(t.highway, t.way_id, hora)
        km = t.metros / 1000
        libre = km / VELOCIDAD[t.highway] * 60
        minutos = libre * (busqueda.NIVELES[nivel] or 1)
        if por_trafico and por_trafico[-1]["nivel"] == nivel:
            ult = por_trafico[-1]
            ult["coords"].extend(_redondear(t.geom[1:]))
            ult["km"] += km
            ult["minutos"] += minutos
            ult["minutos_libre"] += libre
        else:
            por_trafico.append({"nivel": nivel, "coords": _redondear(t.geom), "km": km,
                                "minutos": minutos, "minutos_libre": libre})
    for pt in por_trafico:
        for k in ("km", "minutos", "minutos_libre"):
            pt[k] = round(pt[k], 3)

    # Indicaciones: se juntan los tramos seguidos de la misma calle.
    grupos: list[dict] = []
    for t in tramos:
        nombre = t.nombre or "calle sin nombre"
        minutos = _minutos(t, hora, set()) or 0
        nivel = nivel_trafico(t.highway, t.way_id, hora)
        if grupos and grupos[-1]["calle"] == nombre:
            gr = grupos[-1]
            gr["metros"] += t.metros
            gr["minutos"] += minutos
            gr["fin"] = t.geom[-2:]
            gr["hasta"] = t.b
            if busqueda.NIVELES[nivel] > busqueda.NIVELES[gr["nivel"]]:
                gr["nivel"] = nivel
        else:
            grupos.append({"calle": nombre, "metros": t.metros, "minutos": minutos, "nivel": nivel,
                           "inicio": t.geom[:2], "fin": t.geom[-2:], "hasta": t.b})
    # Calles sin nombre muy cortas (entradas, retornos) se suman a la siguiente instrucción.
    limpios: list[dict] = []
    for gr in grupos:
        if limpios and limpios[-1]["calle"] == "calle sin nombre" and limpios[-1]["metros"] < 60:
            corto = limpios.pop()
            gr = {**gr, "metros": gr["metros"] + corto["metros"], "minutos": gr["minutos"] + corto["minutos"],
                  "inicio": corto["inicio"]}
        limpios.append(gr)

    indicaciones = []
    for i, gr in enumerate(limpios):
        r_ini = rumbo_grados(*gr["inicio"][0], *gr["inicio"][-1])
        hacia = rumbo_texto(r_ini)
        if i == 0:
            texto = f"Sal por {gr['calle']} hacia el {hacia}"
        else:
            prev = limpios[i - 1]
            r_prev = rumbo_grados(*prev["fin"][0], *prev["fin"][-1])
            giro = (r_ini - r_prev + 540) % 360 - 180
            if abs(giro) < 30:
                verbo = "Continúa por"
            elif abs(giro) > 150:
                verbo = "Da vuelta en U en"
            elif giro > 0:
                verbo = "Gira a la derecha en"
            else:
                verbo = "Gira a la izquierda en"
            texto = f"{verbo} {gr['calle']} hacia el {hacia}"
        indicaciones.append({
            "texto": texto,
            "calle": gr["calle"],
            "km": round(gr["metros"] / 1000, 2),
            "minutos": round(gr["minutos"], 1),
            "nivel": gr["nivel"],
            "hasta": grafo.nombre_esquina(gr["hasta"]),
        })

    return {
        "coords": _redondear(coords),
        "tramos": por_trafico,
        "km": round(sum(t.metros for t in tramos) / 1000, 2),
        "minutos_sin_trafico": round(sum(pt["minutos_libre"] for pt in por_trafico), 1),
        "indicaciones": indicaciones,
    }


def calcular_ruta(origen: dict, destino: dict, hora: int | None = None,
                  algoritmos: tuple[str, ...] = busqueda.ALGORITMOS) -> dict:
    """Ruta real de `origen` a `destino` ({lat, lng}) con cada algoritmo de búsqueda ciega."""
    hora = hora_actual() if hora is None else hora
    puntos = [(origen["lat"], origen["lng"]), (destino["lat"], destino["lng"])]
    datos = calles_para_ruta(puntos)
    a = nodo_mas_cercano(datos, *puntos[0])
    b = nodo_mas_cercano(datos, *puntos[1])
    grafo = construir_grafo(datos, conservar={a, b})
    if a == b:
        raise ValueError("La salida y el destino quedan en la misma esquina.")

    resultados = []
    for alg in algoritmos:
        r = busqueda.buscar(problema(grafo, a, b, hora), alg)
        salida = {k: r[k] for k in ("algoritmo", "nombre", "encontrado", "minutos", "num_tramos",
                                    "expandidos", "generados", "frontera_max", "traza", "traza_completa")}
        if r["encontrado"]:
            salida.update(describir_ruta(grafo, r["aristas"], hora))
            salida["minutos"] = round(r["minutos"], 1)
        resultados.append(salida)

    encontrados = [r for r in resultados if r["encontrado"]]
    return {
        "hora": hora,
        "periodo": periodo(hora),
        "periodo_nombre": NOMBRE_PERIODO[periodo(hora)],
        "origen": {**origen, "esquina": grafo.nombre_esquina(a)},
        "destino": {**destino, "esquina": grafo.nombre_esquina(b)},
        "esquinas": len(grafo.coords),
        "resultados": resultados,
        # En empate gana costo uniforme, que es el que garantiza la ruta más rápida.
        "mas_rapido": min(encontrados, key=lambda r: (r["minutos"], r["algoritmo"] != "costo_uniforme"))["algoritmo"]
        if encontrados else None,
    }


def zona(hora: int | None = None) -> dict:
    """Avenidas principales de Toluca con su tráfico estimado, para el mapa general."""
    hora = hora_actual() if hora is None else hora
    datos = calles_principales_zona()
    nodos = {e["id"]: (e["lat"], e["lon"]) for e in datos.get("elements", []) if e["type"] == "node"}
    vias = []
    for w in datos.get("elements", []):
        if w["type"] != "way" or not _via_valida(w.get("tags", {})):
            continue
        geom = [nodos[n] for n in w["nodes"] if n in nodos]
        if len(geom) < 2:
            continue
        hw = w["tags"]["highway"]
        vias.append({
            "id": w["id"],
            "nombre": w["tags"].get("name") or w["tags"].get("ref"),
            "tipo": hw,
            "nivel": nivel_trafico(hw, w["id"], hora),
            "coords": _redondear(geom),
        })
    return {
        "hora": hora,
        "periodo": periodo(hora),
        "periodo_nombre": NOMBRE_PERIODO[periodo(hora)],
        "zona": ZONA_TOLUCA,
        "hospital": HOSPITAL,
        "vias": vias,
    }
