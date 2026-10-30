"""Despacho de ambulancia para UN accidente con un algoritmo genético.

La ambulancia SALE de un hospital, va al accidente y REGRESA a un hospital. El algoritmo
genético elige el hospital de salida y el de regreso (o el mismo, si así se pide).

Distancia: heurística euclidiana  d = sqrt((x2 - x1)^2 + (y2 - y1)^2)
    Los puntos están en latitud/longitud; se pasan a un plano en kilómetros alrededor de
    Toluca (proyección equirectangular), así la distancia euclidiana sale en km. Es la
    distancia en línea recta, no por calles: sirve como estimación rápida.

Cromosoma = (hospital_de_salida, hospital_de_regreso)
Costo     = distancia(salida → accidente) + distancia(accidente → regreso)
            + castigo si el hospital de salida no tiene ambulancias.

Como solo hay H × H opciones, también se revisan TODAS para comprobar que el algoritmo
genético llegó al óptimo exacto.
"""
from __future__ import annotations

import math
import random

# Hospitales y bases de ambulancias reales (coordenadas de OpenStreetMap).
# ambulancias = cuántas tiene disponibles por defecto; en pantalla se pueden cambiar.
HOSPITALES = [
    {"id": "imss220", "nombre": "Hospital IMSS 220", "municipio": "Toluca", "lat": 19.2828591, "lng": -99.6393513, "ambulancias": 3},
    {"id": "nsj", "nombre": "Hospital General Nicolás San Juan", "municipio": "Toluca", "lat": 19.31674, "lng": -99.63658, "ambulancias": 2},
    {"id": "cr-toluca", "nombre": "Cruz Roja Toluca", "municipio": "Toluca", "lat": 19.27180, "lng": -99.65815, "ambulancias": 2},
    {"id": "issste", "nombre": "Hospital General ISSSTE", "municipio": "Metepec", "lat": 19.25697, "lng": -99.63585, "ambulancias": 1},
    {"id": "imss251", "nombre": "Hospital IMSS 251", "municipio": "Metepec", "lat": 19.24661, "lng": -99.57636, "ambulancias": 2},
    {"id": "cr-metepec", "nombre": "Cruz Roja Metepec", "municipio": "Metepec", "lat": 19.27160, "lng": -99.59536, "ambulancias": 1},
    {"id": "cr-sma", "nombre": "Cruz Roja San Mateo Atenco", "municipio": "San Mateo Atenco", "lat": 19.28352, "lng": -99.54039, "ambulancias": 1},
    {"id": "cr-lerma", "nombre": "Cruz Roja Lerma", "municipio": "Lerma", "lat": 19.28568, "lng": -99.47873, "ambulancias": 1},
    {"id": "hm-lerma", "nombre": "Hospital Municipal Lerma", "municipio": "Lerma", "lat": 19.32629, "lng": -99.47575, "ambulancias": 1},
]

PENALIZ_SIN_AMBULANCIA = 1000   # castigo si el hospital de salida no tiene ambulancias
LAT0 = 19.28                    # latitud de referencia para pasar a km


def a_plano(lat: float, lng: float) -> tuple[float, float]:
    """(x, y) en km: x hacia el oriente, y hacia el norte."""
    return lng * 111.32 * math.cos(math.radians(LAT0)), lat * 110.57


def euclidiana(p, q):
    return math.sqrt((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2)


# ----------------------------------------------------------------------
# Algoritmo genético
# ----------------------------------------------------------------------
def costo_recorrido(ind, D, caps):
    o, r = ind
    c = D[o] + D[r]
    if caps[o] <= 0:
        c += PENALIZ_SIN_AMBULANCIA
    return c


def algoritmo_genetico(D, caps, mismo_hospital, tam_pob=100, generaciones=100,
                       prob_mut=0.2, elitismo=2, semilla=None):
    """Devuelve (mejor, costo, historial). historial[g] = {mejor, promedio} de la generación g."""
    rnd = random.Random(semilla)
    H = len(D)
    fit = lambda ind: costo_recorrido(ind, D, caps)  # noqa: E731
    norm = (lambda ind: (ind[0], ind[0])) if mismo_hospital else (lambda ind: ind)

    poblacion = [norm((rnd.randrange(H), rnd.randrange(H))) for _ in range(tam_pob)]

    def torneo(k=3):
        return min(rnd.sample(poblacion, min(k, len(poblacion))), key=fit)

    mejor = min(poblacion, key=fit)
    historial = []
    for _ in range(generaciones):
        poblacion.sort(key=fit)
        if fit(poblacion[0]) < fit(mejor):
            mejor = poblacion[0]
        historial.append({"mejor": fit(mejor), "promedio": sum(map(fit, poblacion)) / len(poblacion)})

        nueva = poblacion[:min(elitismo, tam_pob)]
        while len(nueva) < tam_pob:
            p1, p2 = torneo(), torneo()
            hijo = (p1[0], p2[1])                       # cruce: salida de uno, regreso del otro
            if rnd.random() < prob_mut:                 # mutación
                hijo = (rnd.randrange(H), hijo[1]) if rnd.random() < 0.5 \
                    else (hijo[0], rnd.randrange(H))
            nueva.append(norm(hijo))
        poblacion = nueva

    return mejor, fit(mejor), historial


# ----------------------------------------------------------------------
# Despacho completo: distancias, algoritmo genético y comprobación exacta
# ----------------------------------------------------------------------
def despachar(accidente: dict, ambulancias: dict[str, int] | None = None, mismo_hospital: bool = True,
              poblacion: int = 100, generaciones: int = 100, prob_mutacion: float = 0.2,
              velocidad_kmh: float = 40, minutos_en_lugar: float = 10, semilla: int | None = None) -> dict:
    ambulancias = ambulancias or {}
    hosp = [{**h, "ambulancias": int(ambulancias.get(h["id"], h["ambulancias"]))} for h in HOSPITALES]
    if any(h["ambulancias"] < 0 for h in hosp):
        raise ValueError("Las ambulancias no pueden ser negativas.")
    if not any(h["ambulancias"] > 0 for h in hosp):
        raise ValueError("Ningún hospital tiene ambulancias disponibles.")

    acc = a_plano(accidente["lat"], accidente["lng"])
    D = [euclidiana(a_plano(h["lat"], h["lng"]), acc) for h in hosp]
    caps = [h["ambulancias"] for h in hosp]
    minutos = lambda km: km / velocidad_kmh * 60  # noqa: E731

    (o, r), costo, hist = algoritmo_genetico(D, caps, mismo_hospital, poblacion, generaciones, prob_mutacion,
                                             semilla=semilla)

    # Todas las opciones (solo pueden salir hospitales con ambulancia), de menor a mayor.
    opciones = sorted(
        (D[i] + D[j], i, j)
        for i in range(len(hosp)) if caps[i] > 0
        for j in ([i] if mismo_hospital else range(len(hosp)))
    )
    exacto = opciones[0][0]
    orden = sorted(range(len(hosp)), key=lambda h: D[h])
    cercano = orden[0]

    return {
        "accidente": accidente,
        "mismo_hospital": mismo_hospital,
        "parametros": {"poblacion": poblacion, "generaciones": generaciones, "prob_mutacion": prob_mutacion,
                       "velocidad_kmh": velocidad_kmh, "minutos_en_lugar": minutos_en_lugar},
        "hospitales": [
            {**h, "distancia_km": round(D[i], 3), "minutos": round(minutos(D[i]), 1), "cercania": orden.index(i) + 1}
            for i, h in enumerate(hosp)
        ],
        "mejor": {
            "salida": hosp[o]["id"],
            "regreso": hosp[r]["id"],
            "ida_km": round(D[o], 3),
            "regreso_km": round(D[r], 3),
            "total_km": round(costo, 3),
            "ida_min": round(minutos(D[o]), 1),
            "regreso_min": round(minutos(D[r]), 1),
            "total_min": round(minutos(D[o]) + minutos_en_lugar + minutos(D[r]), 1),
        },
        # Si el más cercano no pudo salir (sin ambulancias), se avisa en pantalla.
        "mas_cercano": hosp[cercano]["id"],
        "opciones": [
            {"salida": hosp[i]["id"], "regreso": hosp[j]["id"], "ida_km": round(D[i], 3), "regreso_km": round(D[j], 3),
             "total_km": round(c, 3), "total_min": round(minutos(c) + minutos_en_lugar, 1)}
            for c, i, j in opciones
        ],
        "optimo_exacto_km": round(exacto, 3),
        "coincide_con_optimo": abs(costo - exacto) < 1e-9,
        "historial": [{"mejor": round(g["mejor"], 3), "promedio": round(g["promedio"], 3)} for g in hist],
    }
