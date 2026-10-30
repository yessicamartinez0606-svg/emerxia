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
PX_POR_KM = 137.5             # escala del mapa: 220 px ≈ 1.6 km

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
# Mapa simplificado de una zona de la ciudad. x, y son coordenadas para dibujarlo.

@dataclass(frozen=True)
class Nodo:
    id: str
    nombre: str
    x: int
    y: int
    tipo: str = "cruce"       # cruce | base | hospital


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
    Nodo("BASE", "Base de ambulancias Polanco", 80, 80, "base"),
    Nodo("P1", "Ejército Nacional y Gandhi", 300, 80),
    Nodo("P2", "Ejército Nacional y Mariano Escobedo", 520, 80),
    Nodo("P3", "Ejército Nacional e Insurgentes", 740, 80),
    Nodo("HN", "Hospital General Norte", 940, 80, "hospital"),
    Nodo("R1", "Reforma y Periférico", 80, 300),
    Nodo("R2", "Reforma y Gandhi", 300, 300),
    Nodo("R3", "Reforma y Mariano Escobedo", 520, 300),
    Nodo("R4", "Reforma e Insurgentes", 740, 300),
    Nodo("R5", "Reforma y Bucareli", 940, 300),
    Nodo("S1", "Constituyentes y Periférico", 80, 520),
    Nodo("S2", "Av. Chapultepec y Gandhi", 300, 520),
    Nodo("S3", "Av. Chapultepec y Mariano Escobedo", 520, 520),
    Nodo("S4", "Av. Chapultepec e Insurgentes", 740, 520),
    Nodo("HS", "Hospital General Centro", 940, 520, "hospital"),
)

CALLES: tuple[Calle, ...] = (
    # Ejército Nacional (arriba)
    Calle("c01", "BASE", "P1", "Ejército Nacional", "moderado"),
    Calle("c02", "P1", "P2", "Ejército Nacional", "denso"),
    Calle("c03", "P2", "P3", "Ejército Nacional", "moderado", "ida", "Un solo sentido hacia el oriente"),
    Calle("c04", "P3", "HN", "Ejército Nacional", "libre"),
    # Paseo de la Reforma (en medio)
    Calle("c05", "R1", "R2", "Paseo de la Reforma", "libre"),
    Calle("c06", "R2", "R3", "Paseo de la Reforma", "moderado"),
    Calle("c07", "R3", "R4", "Paseo de la Reforma", "bloqueado", nota="Marcha sobre Reforma"),
    Calle("c08", "R4", "R5", "Paseo de la Reforma", "denso"),
    # Av. Chapultepec (abajo)
    Calle("c09", "S1", "S2", "Constituyentes", "libre"),
    Calle("c10", "S2", "S3", "Av. Chapultepec", "moderado"),
    Calle("c11", "S3", "S4", "Av. Chapultepec", "libre"),
    Calle("c12", "S4", "HS", "Av. Chapultepec", "moderado"),
    # Calles verticales
    Calle("c13", "BASE", "R1", "Periférico", "denso"),
    Calle("c14", "R1", "S1", "Periférico", "denso"),
    Calle("c15", "P1", "R2", "Gandhi", "libre"),
    Calle("c16", "R2", "S2", "Gandhi", "libre"),
    Calle("c17", "P2", "R3", "Mariano Escobedo", "moderado"),
    Calle("c18", "R3", "S3", "Mariano Escobedo", "libre"),
    Calle("c19", "P3", "R4", "Insurgentes", "denso"),
    Calle("c20", "R4", "S4", "Insurgentes", "moderado"),
    Calle("c21", "HN", "R5", "Bucareli", "libre"),
    Calle("c22", "R5", "HS", "Bucareli", "moderado", "ida", "Un solo sentido hacia el sur"),
    # Diagonal
    Calle("c23", "R2", "S3", "Calzada Chivatito", "denso", nota="Obra: un solo carril abierto"),
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
