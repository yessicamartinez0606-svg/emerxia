"""Búsqueda ciega (no informada) sobre un espacio de estados.

Funciones puras, igual que app/logica.py: no tocan la red ni la base de datos, así que se
pueden probar solas (ver probar_busqueda.py). El problema concreto de la ambulancia en
Toluca (calles reales, tráfico) se arma en app/red_vial.py y se resuelve con estas mismas
funciones.

ESPACIO DE ESTADOS (ruta de la ambulancia)
    Estado          la esquina (intersección) en la que está la ambulancia.
    Estado inicial  la esquina más cercana al punto de salida (el Hospital IMSS 220).
    Estado meta     la esquina más cercana a la emergencia (o al hospital, de regreso).
    Operadores      avanzar(i → j): ir a la siguiente esquina j por una calle que sale de i,
                    si la calle no está cerrada y se respeta su sentido.
    Costo           minutos del tramo = distancia / velocidad de la vía × factor de tráfico.

ALGORITMOS (búsqueda ciega: ninguno usa una estimación de qué tan lejos está la meta)
    anchura          frontera FIFO (cola).  Encuentra la ruta con MENOS tramos.
    profundidad      frontera LIFO (pila).  Encuentra una ruta, no necesariamente buena.
    costo_uniforme   frontera ordenada por costo acumulado g(n).  Encuentra la ruta MÁS RÁPIDA.

Las tres son búsqueda en grafo: un estado ya expandido no se vuelve a expandir.
"""
from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Hashable

# Cuánto más tarda un tramo según su nivel de tráfico. None = no se puede pasar.
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

Estado = Hashable
# sucesores(estado) -> [(estado_siguiente, id_arista, costo_en_minutos), ...]
Sucesores = Callable[[Estado], list[tuple[Estado, Hashable, float]]]


@dataclass
class Problema:
    """Un problema de búsqueda: estado inicial, estado meta y función sucesor (operadores)."""
    inicial: Estado
    meta: Estado
    sucesores: Sucesores
    nombre: Callable[[Estado], str] = field(default=str)   # para mostrar la traza

    def es_meta(self, estado: Estado) -> bool:
        return estado == self.meta


@dataclass
class _Nodo:
    estado: Estado
    padre: "_Nodo | None"
    arista: Hashable | None
    g: float          # minutos acumulados


def _camino(n: _Nodo) -> list[_Nodo]:
    out = []
    while n:
        out.append(n)
        n = n.padre
    return out[::-1]


def buscar(problema: Problema, algoritmo: str, max_expansiones: int = 300_000,
           max_traza: int = 120) -> dict:
    """Ejecuta un algoritmo de búsqueda ciega.

    Devuelve la ruta (estados y aristas), su costo, estadísticas y los primeros `max_traza`
    pasos de la búsqueda (en una ciudad real son miles; con unos cuantos basta para ver
    cómo avanza cada algoritmo).
    """
    if algoritmo not in ALGORITMOS:
        raise ValueError(f"Algoritmo desconocido: '{algoritmo}'.")

    inicio = _Nodo(problema.inicial, None, None, 0.0)
    contador = 0                                     # desempate estable en el heap
    if algoritmo == "anchura":
        frontera: deque | list = deque([inicio])
    elif algoritmo == "profundidad":
        frontera = [inicio]
    else:
        frontera = [(0.0, 0, inicio)]
    en_frontera: set = {problema.inicial}            # solo anchura y profundidad

    expandidos: set = set()
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

    while frontera and len(expandidos) < max_expansiones:
        nodo = sacar()
        en_frontera.discard(nodo.estado)
        if nodo.estado in expandidos:                # copia vieja (costo uniforme)
            continue

        if problema.es_meta(nodo.estado):
            encontrado = nodo
            if len(traza) < max_traza:
                traza.append({"paso": len(expandidos) + 1, "estado": problema.nombre(nodo.estado),
                              "g": round(nodo.g, 2), "meta": True, "agregados": [],
                              "frontera": len(frontera)})
            break

        expandidos.add(nodo.estado)
        hijos = []
        for sig, arista, costo in problema.sucesores(nodo.estado):
            if sig in expandidos:
                continue
            # Anchura y profundidad no repiten un estado que ya espera en la frontera.
            # Costo uniforme sí: el camino nuevo puede ser más barato.
            if algoritmo != "costo_uniforme" and sig in en_frontera:
                continue
            hijos.append(_Nodo(sig, nodo, arista, nodo.g + costo))

        if algoritmo == "anchura":
            frontera.extend(hijos)
        elif algoritmo == "profundidad":
            frontera.extend(reversed(hijos))         # el primer sucesor queda en el tope
        else:
            for h in hijos:
                contador += 1
                heapq.heappush(frontera, (h.g, contador, h))
        if algoritmo != "costo_uniforme":
            en_frontera.update(h.estado for h in hijos)
        generados += len(hijos)
        frontera_max = max(frontera_max, len(frontera))

        if len(traza) < max_traza:
            traza.append({"paso": len(expandidos), "estado": problema.nombre(nodo.estado),
                          "g": round(nodo.g, 2), "meta": False,
                          "agregados": [problema.nombre(h.estado) for h in hijos],
                          "frontera": len(frontera)})

    total = len(expandidos) + (1 if encontrado else 0)
    resultado = {
        "algoritmo": algoritmo,
        "nombre": NOMBRES_ALGORITMO[algoritmo],
        "encontrado": encontrado is not None,
        "estados": [],
        "aristas": [],
        "minutos": None,
        "num_tramos": None,
        "expandidos": total,
        "generados": generados,
        "frontera_max": frontera_max,
        "traza": traza,
        "traza_completa": len(traza) >= total,
    }
    if encontrado:
        camino = _camino(encontrado)
        resultado.update(
            estados=[n.estado for n in camino],
            aristas=[n.arista for n in camino[1:]],
            minutos=round(encontrado.g, 2),
            num_tramos=len(camino) - 1,
        )
    return resultado
