"""Búsqueda ciega (no informada) sobre un espacio de estados: ruta de una ambulancia con tráfico.

Funciones puras, igual que app/logica.py: no tocan la base de datos, así que se pueden
probar solas (ver probar_busqueda.py).

PROBLEMA
    Una ambulancia sale de su base y tiene que llegar al lugar de la emergencia (o a un
    hospital). Hay calles con tráfico libre, moderado o denso, calles bloqueadas (una
    marcha, un choque, una obra) y calles de un solo sentido.

ESPACIO DE ESTADOS
    Estado          la intersección en la que está la ambulancia.
    Estado inicial  la intersección de salida (por ejemplo, la base).
    Estado meta     la intersección de destino (la emergencia o el hospital).
    Operadores      avanzar(i → j): moverse a la intersección j por una calle que une i con j,
                    si la calle NO está bloqueada y se respeta su sentido.
    Costo           minutos para recorrer la calle = distancia / velocidad × factor de tráfico.

ALGORITMOS (búsqueda ciega: no usan ninguna estimación de qué tan lejos está la meta)
    anchura          frontera FIFO (cola).  Encuentra la ruta con MENOS calles.
    profundidad      frontera LIFO (pila).  Encuentra una ruta, no necesariamente buena.
    costo_uniforme   frontera ordenada por costo acumulado g(n).  Encuentra la ruta MÁS RÁPIDA.

Las tres son búsqueda en grafo: un estado ya expandido no se vuelve a expandir, para no
dar vueltas en círculos entre dos cruces.
"""
from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass

# ─────────────────────────── Tráfico ───────────────────────────

VELOCIDAD_KMH = 40.0          # velocidad de la ambulancia con la calle libre
PX_POR_KM = 300.0             # escala del esquema: 330 px ≈ 1.1 km

# Cuánto más tarda una calle según su nivel de tráfico. None = no se puede pasar.
NIVELES: dict[str, float | None] = {
    "libre": 1.0,
    "moderado": 1.8,
    "denso": 3.0,
    "bloqueado": None,
}

ALGORITMOS = ("anchura", "profundidad", "costo_uniforme")

NOMBRES_ALGORITMO = {
    "anchura": "Primero en anchura",
    "profundidad": "Primero en profundidad",
    "costo_uniforme": "Costo uniforme",
}


# ─────────────────────────── Mapa ───────────────────────────
# Esquema simplificado de la zona del Hospital General Regional No. 220 del IMSS, en
# Paseo Tollocan esquina Nezahualcóyotl, Col. Vértice, Toluca. Las calles son reales pero
# el dibujo no está a escala: x, y son coordenadas para dibujar (oriente = derecha,
# norte = arriba). Solo el hospital lleva coordenadas geográficas reales (lat, lng).

@dataclass(frozen=True)
class Nodo:
    id: str
    nombre: str
    corto: str                # nombre breve para el mapa y las tablas
    x: int
    y: int
    tipo: str = "cruce"       # cruce | base | hospital
    lat: float | None = None
    lng: float | None = None


@dataclass(frozen=True)
class Calle:
    id: str
    a: str
    b: str
    nombre: str
    trafico: str = "libre"    # nivel por defecto
    sentido: str = "doble"    # doble | ida  (ida = solo de a hacia b)
    nota: str = ""


NODOS: tuple[Nodo, ...] = (
    # Av. Sebastián Lerdo de Tejada (norte)
    Nodo("BASE", "Base de ambulancias (Lerdo e Isidro Fabela)", "Base de ambulancias", 140, 80, "base"),
    Nodo("L2", "Lerdo y Pino Suárez", "Lerdo / Pino Suárez", 470, 80),
    Nodo("L3", "Lerdo y Nezahualcóyotl", "Lerdo / Nezahualcóyotl", 800, 80),
    # Av. Morelos
    Nodo("M1", "Morelos e Isidro Fabela", "Morelos / Fabela", 140, 210),
    Nodo("M2", "Morelos y Pino Suárez", "Morelos / Pino Suárez", 470, 210),
    Nodo("M3", "Morelos y Nezahualcóyotl", "Morelos / Nezahualcóyotl", 800, 210),
    # Paseo Tollocan
    Nodo("T1", "Paseo Tollocan e Isidro Fabela", "Tollocan / Fabela", 140, 360),
    Nodo("T2", "Paseo Tollocan y Pino Suárez", "Tollocan / Pino Suárez", 470, 360),
    Nodo("IMSS", "Hospital General Regional No. 220 IMSS (Paseo Tollocan esq. Nezahualcóyotl)",
         "Hospital IMSS 220", 800, 360, "hospital", 19.2828591, -99.6393513),
    # Av. Solidaridad Las Torres (sur)
    Nodo("S1", "Las Torres e Isidro Fabela", "Las Torres / Fabela", 140, 500),
    Nodo("S2", "Las Torres y Pino Suárez", "Las Torres / Pino Suárez", 470, 500),
    Nodo("S3", "Las Torres y Nezahualcóyotl", "Las Torres / Nezahualcóyotl", 800, 500),
)

CALLES: tuple[Calle, ...] = (
    # Calles de oriente a poniente
    Calle("c01", "BASE", "L2", "Av. Lerdo", "moderado"),
    Calle("c02", "L2", "L3", "Av. Lerdo", "moderado"),
    Calle("c03", "M1", "M2", "Av. Morelos", "denso"),
    Calle("c04", "M2", "M3", "Av. Morelos", "moderado"),
    Calle("c05", "T1", "T2", "Paseo Tollocan", "denso"),
    Calle("c06", "T2", "IMSS", "Paseo Tollocan", "denso"),
    Calle("c07", "S1", "S2", "Av. Las Torres", "libre"),
    Calle("c08", "S2", "S3", "Av. Las Torres", "libre"),
    # Calles de norte a sur
    Calle("c09", "BASE", "M1", "Av. Isidro Fabela", "moderado"),
    Calle("c10", "M1", "T1", "Av. Isidro Fabela", "moderado"),
    Calle("c11", "T1", "S1", "Av. Isidro Fabela", "libre"),
    Calle("c12", "L2", "M2", "Av. Pino Suárez", "denso"),
    Calle("c13", "M2", "T2", "Av. Pino Suárez", "denso"),
    Calle("c14", "T2", "S2", "Av. Pino Suárez", "moderado"),
    Calle("c15", "L3", "M3", "Nezahualcóyotl", "libre"),
    Calle("c16", "M3", "IMSS", "Nezahualcóyotl", "bloqueado", nota="Cerrada por obra"),
    Calle("c17", "IMSS", "S3", "Nezahualcóyotl", "libre"),
)

_NODO = {n.id: n for n in NODOS}
_CALLE = {c.id: c for c in CALLES}


def distancia_km(calle: Calle) -> float:
    a, b = _NODO[calle.a], _NODO[calle.b]
    px = ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5
    return round(px / PX_POR_KM, 2)


def minutos(calle: Calle, nivel: str) -> float | None:
    factor = NIVELES[nivel]
    if factor is None:
        return None
    return round(distancia_km(calle) / VELOCIDAD_KMH * 60 * factor, 2)


def mapa() -> dict:
    """El mapa completo con el tráfico por defecto, para dibujarlo en el frontend."""
    return {
        "nodos": [vars(n) for n in NODOS],
        "calles": [{**vars(c), "distancia_km": distancia_km(c)} for c in CALLES],
        "niveles": {k: v for k, v in NIVELES.items()},
        "velocidad_kmh": VELOCIDAD_KMH,
        "zona": "Toluca, Estado de México · alrededores del Hospital General Regional No. 220 del IMSS",
    }


# ─────────────────────────── Espacio de estados ───────────────────────────

class EspacioEstados:
    """Define el problema: estado inicial, meta y la función sucesor (los operadores)."""

    def __init__(self, inicial: str, meta: str, trafico: dict[str, str] | None = None):
        for nid in (inicial, meta):
            if nid not in _NODO:
                raise ValueError(f"No existe la intersección '{nid}'.")
        trafico = trafico or {}
        for cid, nivel in trafico.items():
            if cid not in _CALLE:
                raise ValueError(f"No existe la calle '{cid}'.")
            if nivel not in NIVELES:
                raise ValueError(f"Nivel de tráfico inválido: '{nivel}'.")
        self.inicial = inicial
        self.meta = meta
        self.trafico = {c.id: trafico.get(c.id, c.trafico) for c in CALLES}

    def es_meta(self, estado: str) -> bool:
        return estado == self.meta

    def sucesores(self, estado: str) -> list[tuple[str, str, float]]:
        """Aplica los operadores avanzar(estado → j). Devuelve (j, id_calle, minutos),
        ordenados por id de intersección para que el resultado sea siempre el mismo."""
        out = []
        for c in CALLES:
            costo = minutos(c, self.trafico[c.id])
            if costo is None:                       # calle bloqueada: el operador no aplica
                continue
            if c.a == estado:
                out.append((c.b, c.id, costo))
            elif c.b == estado and c.sentido == "doble":
                out.append((c.a, c.id, costo))
        return sorted(out)


# ─────────────────────────── Algoritmos ───────────────────────────

@dataclass
class _Nodo:
    estado: str
    padre: "_Nodo | None"
    calle: str | None
    g: float        # minutos acumulados
    profundidad: int


def _camino(n: _Nodo) -> list[_Nodo]:
    out = []
    while n:
        out.append(n)
        n = n.padre
    return out[::-1]


def buscar(problema: EspacioEstados, algoritmo: str, max_pasos: int = 500) -> dict:
    """Ejecuta un algoritmo de búsqueda ciega y devuelve la ruta y la traza paso a paso."""
    if algoritmo not in ALGORITMOS:
        raise ValueError(f"Algoritmo desconocido: '{algoritmo}'.")

    inicio = _Nodo(problema.inicial, None, None, 0.0, 0)
    contador = 0                                    # desempate estable para el heap
    if algoritmo == "anchura":
        frontera: deque | list = deque([inicio])
    elif algoritmo == "profundidad":
        frontera = [inicio]
    else:
        frontera = [(0.0, contador, inicio)]

    expandidos: set[str] = set()
    traza: list[dict] = []
    generados = 1
    frontera_max = 1
    encontrado: _Nodo | None = None

    def sacar() -> _Nodo:
        if algoritmo == "anchura":
            return frontera.popleft()
        if algoritmo == "profundidad":
            return frontera.pop()
        return heapq.heappop(frontera)[2]

    def en_frontera() -> list[str]:
        if algoritmo == "costo_uniforme":
            # sin repetir: de cada estado se muestra solo su copia más barata
            return list(dict.fromkeys(n.estado for _, _, n in sorted(frontera, key=lambda t: t[:2])
                                      if n.estado not in expandidos))
        if algoritmo == "profundidad":
            return [n.estado for n in reversed(frontera)]     # el tope de la pila primero
        return [n.estado for n in frontera]

    while frontera and len(traza) < max_pasos:
        nodo = sacar()
        if nodo.estado in expandidos:               # ya se expandió por un camino anterior
            continue

        if problema.es_meta(nodo.estado):
            traza.append({
                "paso": len(traza) + 1, "estado": nodo.estado, "g": nodo.g,
                "meta": True, "agregados": [], "frontera": en_frontera(),
                "expandidos": sorted(expandidos | {nodo.estado}),
            })
            encontrado = nodo
            break

        expandidos.add(nodo.estado)
        # Anchura y profundidad tampoco repiten un estado que ya espera en la frontera.
        # Costo uniforme sí lo permite: el camino nuevo puede ser más barato, y el heap
        # sacará primero el de menor costo (el otro se descarta al salir).
        ya_en_frontera = set(en_frontera()) if algoritmo != "costo_uniforme" else set()
        hijos = [
            _Nodo(j, nodo, cid, round(nodo.g + costo, 2), nodo.profundidad + 1)
            for j, cid, costo in problema.sucesores(nodo.estado)
            if j not in expandidos and j not in ya_en_frontera
        ]
        if algoritmo == "anchura":
            frontera.extend(hijos)
        elif algoritmo == "profundidad":
            frontera.extend(reversed(hijos))        # así el primer sucesor queda en el tope
        else:
            for h in hijos:
                contador += 1
                heapq.heappush(frontera, (h.g, contador, h))
        generados += len(hijos)
        frontera_max = max(frontera_max, len(frontera))

        traza.append({
            "paso": len(traza) + 1, "estado": nodo.estado, "g": nodo.g, "meta": False,
            "agregados": [h.estado for h in hijos], "frontera": en_frontera(),
            "expandidos": sorted(expandidos),
        })

    resultado = {
        "algoritmo": algoritmo,
        "nombre": NOMBRES_ALGORITMO[algoritmo],
        "inicial": problema.inicial,
        "meta": problema.meta,
        "encontrado": encontrado is not None,
        "ruta": [],
        "calles": [],
        "minutos": None,
        "distancia_km": None,
        "num_calles": None,
        "expandidos": len(expandidos) + (1 if encontrado else 0),
        "generados": generados,
        "frontera_max": frontera_max,
        "traza": traza,
    }
    if encontrado:
        camino = _camino(encontrado)
        calles = [n.calle for n in camino[1:]]
        resultado.update(
            ruta=[n.estado for n in camino],
            calles=calles,
            minutos=round(encontrado.g, 1),
            distancia_km=round(sum(distancia_km(_CALLE[c]) for c in calles), 2),
            num_calles=len(calles),
        )
    return resultado


def resolver(inicial: str, meta: str, trafico: dict[str, str] | None = None,
             algoritmos: tuple[str, ...] = ALGORITMOS) -> dict:
    """Resuelve el mismo problema con varios algoritmos para poder compararlos."""
    problema = EspacioEstados(inicial, meta, trafico)
    resultados = [buscar(problema, a) for a in algoritmos]
    encontrados = [r for r in resultados if r["encontrado"]]
    mejor = min(encontrados, key=lambda r: r["minutos"])["algoritmo"] if encontrados else None
    return {
        "inicial": inicial,
        "meta": meta,
        "trafico": problema.trafico,
        "resultados": resultados,
        "mas_rapido": mejor,
    }
