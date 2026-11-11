"""Flota de ambulancias: hospital, estatus, conductor, gasolina e historial.

Reglas (funciones puras, se prueban sin MongoDB en probar_flota.py):

ESTATUS de una ambulancia
    Libre              en su hospital, lista para salir.
    Ocupada            atendiendo una emergencia (la asigna el sistema, no se pone a mano).
    En reparación      en el taller.
    Fuera de servicio  sin conductor, sin papeles, etc.

CONDUCTOR
    Cada ambulancia tiene un operador que la maneja (se elige de Operadores). Ese mismo
    operador es quien registra las cargas de gasolina de su ambulancia.

GASOLINA
    Se guarda el nivel del tanque en %. Sube con cada carga (litros / tanque) y baja al
    cerrar una emergencia según los km recorridos (km / rendimiento = litros gastados).
    Con menos de COMBUSTIBLE_MINIMO % la ambulancia no se manda a emergencias.

VARIAS AMBULANCIAS (más de tres)
    Una emergencia puede pedir varias ambulancias. Primero salen las libres del hospital
    base (IMSS 220, que tiene 3). Si se necesitan más, se piden a los otros hospitales,
    del más cercano a la emergencia al más lejano.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .genetico import HOSPITALES, a_plano, euclidiana

ESTADOS = ("Libre", "Ocupada", "En reparación", "Fuera de servicio")
ESTADOS_MANUALES = ("Libre", "En reparación", "Fuera de servicio")   # "Ocupada" solo por asignación

# Nombres que usaba la versión anterior del sistema.
ESTADOS_ANTERIORES = {"Disponible": "Libre", "En servicio": "Ocupada", "Mantenimiento": "En reparación"}

HOSPITAL_BASE = "Hospital IMSS 220"
NOMBRES_HOSPITALES = tuple(h["nombre"] for h in HOSPITALES)

COMBUSTIBLE_MINIMO = 25        # % mínimo para salir a una emergencia
TANQUE_LITROS = 80.0           # valores por defecto si la ambulancia no los trae
RENDIMIENTO_KM_L = 6.0


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def hospital(nombre: str | None) -> dict:
    return next((h for h in HOSPITALES if h["nombre"] == nombre), HOSPITALES[0])


def normalizar(amb: dict) -> dict:
    """Completa los campos nuevos de una ambulancia guardada con la versión anterior."""
    a = dict(amb)
    a["estado"] = ESTADOS_ANTERIORES.get(a.get("estado"), a.get("estado") or "Libre")
    if a["estado"] not in ESTADOS:
        a["estado"] = "Libre"
    a["hospital"] = a.get("hospital") if a.get("hospital") in NOMBRES_HOSPITALES else HOSPITAL_BASE
    a["conductor"] = a.get("conductor") or ""
    a["tanque_litros"] = float(a.get("tanque_litros") or TANQUE_LITROS)
    a["rendimiento_km_l"] = float(a.get("rendimiento_km_l") or RENDIMIENTO_KM_L)
    pct = a.get("combustible_pct")
    a["combustible_pct"] = round(min(100.0, max(0.0, float(100 if pct is None else pct))), 1)
    a["kilometraje"] = float(a.get("kilometraje") or 0)
    a["emergencia_actual"] = a.get("emergencia_actual") or None
    a["combustible_bajo"] = a["combustible_pct"] < COMBUSTIBLE_MINIMO
    return a


# ─────────────────────────── Gasolina ───────────────────────────

def aplicar_carga(amb: dict, operador: str, litros: float, kilometraje: float | None = None) -> dict:
    """Valida una carga de gasolina y regresa los cambios para la ambulancia.

    Lanza ValueError con un mensaje para el usuario si algo no cuadra.
    """
    a = normalizar(amb)
    if not a["conductor"]:
        raise ValueError(f"La ambulancia {a['placa']} no tiene conductor asignado. Asígnale uno antes de registrar gasolina.")
    if operador.strip().lower() != a["conductor"].strip().lower():
        raise ValueError(f"Solo {a['conductor']}, el conductor de {a['placa']}, puede registrar su gasolina.")
    if litros <= 0:
        raise ValueError("Los litros deben ser mayores a cero.")
    faltan = a["tanque_litros"] * (100 - a["combustible_pct"]) / 100
    if litros > faltan + 0.5:
        raise ValueError(f"No caben {litros:g} L: al tanque le faltan {faltan:.1f} L para llenarse.")
    if kilometraje is not None and kilometraje < a["kilometraje"]:
        raise ValueError(f"El kilometraje no puede ser menor al último registrado ({a['kilometraje']:,.0f} km).")
    nuevo = min(100.0, a["combustible_pct"] + litros / a["tanque_litros"] * 100)
    cambios = {"combustible_pct": round(nuevo, 1)}
    if kilometraje is not None:
        cambios["kilometraje"] = kilometraje
    return {"antes": a["combustible_pct"], "despues": round(nuevo, 1), "cambios": cambios}


def consumo_por_km(amb: dict, km: float) -> dict:
    """Gasolina gastada en un recorrido de `km` kilómetros."""
    a = normalizar(amb)
    litros = max(0.0, km) / a["rendimiento_km_l"]
    nuevo = max(0.0, a["combustible_pct"] - litros / a["tanque_litros"] * 100)
    return {
        "litros": round(litros, 1),
        "antes": a["combustible_pct"],
        "despues": round(nuevo, 1),
        "cambios": {"combustible_pct": round(nuevo, 1), "kilometraje": round(a["kilometraje"] + max(0.0, km), 1)},
    }


# ─────────────────────────── Asignación ───────────────────────────

def motivo_no_disponible(amb: dict) -> str | None:
    a = normalizar(amb)
    if a["estado"] != "Libre":
        return a["estado"].lower()
    if not a["conductor"]:
        return "sin conductor"
    if a["combustible_bajo"]:
        return f"gasolina baja ({a['combustible_pct']:.0f} %)"
    return None


def orden_hospitales(destino: dict | None) -> list[dict]:
    """Hospital base primero; después los demás del más cercano al más lejano a la emergencia
    (distancia en línea recta). Sin ubicación, se ordenan por cercanía al hospital base."""
    base = hospital(HOSPITAL_BASE)
    ref = destino or base
    p = a_plano(ref["lat"], ref["lng"])
    otros = sorted((h for h in HOSPITALES if h["nombre"] != HOSPITAL_BASE),
                   key=lambda h: euclidiana(p, a_plano(h["lat"], h["lng"])))
    return [base, *otros]


def planear(ambulancias: list[dict], cantidad: int, destino: dict | None = None) -> dict:
    """Elige `cantidad` ambulancias: primero del hospital base y, si no alcanzan, de los
    hospitales más cercanos. Regresa el plan y un resumen en lenguaje sencillo."""
    if cantidad < 1:
        raise ValueError("Se necesita al menos una ambulancia.")
    flota = [normalizar(a) for a in ambulancias]
    p = a_plano(destino["lat"], destino["lng"]) if destino else None

    elegidas, por_hospital = [], []
    for h in orden_hospitales(destino):
        propias = sorted((a for a in flota if a["hospital"] == h["nombre"]), key=lambda a: a["placa"])
        libres = [a for a in propias if motivo_no_disponible(a) is None]
        # Entre las libres, primero las de tipo Avanzada y con más gasolina.
        libres.sort(key=lambda a: (a.get("tipo") != "Avanzada", -a["combustible_pct"], a["placa"]))
        toma = libres[: max(0, cantidad - len(elegidas))]
        elegidas += toma
        por_hospital.append({
            "hospital": h["nombre"],
            "municipio": h["municipio"],
            "km": round(euclidiana(p, a_plano(h["lat"], h["lng"])), 1) if p else None,
            "total": len(propias),
            "libres": len(libres),
            "aporta": [a["placa"] for a in toma],
            "no_disponibles": [{"placa": a["placa"], "motivo": motivo_no_disponible(a)}
                               for a in propias if motivo_no_disponible(a)],
        })

    base = por_hospital[0]
    apoyos = [h for h in por_hospital[1:] if h["aporta"]]
    faltan = cantidad - len(elegidas)
    if not apoyos and not faltan:
        resumen = f"Salen {len(elegidas)} ambulancia(s) del {base['hospital']}."
    else:
        partes = [f"Se necesitan {_n(cantidad, 'ambulancia')}.",
                  f"El {base['hospital']} aporta {len(base['aporta'])}"
                  + (f" (de sus {base['total']}, solo {base['libres']} están listas para salir)." if base['libres'] < base['total'] else ".")]
        if apoyos:
            partes.append("Se piden " + _lista([f"{len(h['aporta'])} a {h['hospital']}" for h in apoyos]) + ".")
        if faltan:
            partes.append(f"Faltan {faltan}: no hay más ambulancias libres en la zona.")
        resumen = " ".join(partes)

    return {
        "cantidad": cantidad,
        "elegidas": [{k: a[k] for k in ("id", "placa", "tipo", "hospital", "conductor", "combustible_pct")} for a in elegidas],
        "por_hospital": por_hospital,
        "faltan": faltan,
        "usa_otros_hospitales": bool(apoyos),
        "resumen": resumen,
    }


def _n(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def _lista(partes: list[str]) -> str:
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]


def resumen_hospitales(ambulancias: list[dict]) -> list[dict]:
    """Ambulancias agrupadas por hospital, con cuántas hay en cada estatus."""
    flota = [normalizar(a) for a in ambulancias]
    out = []
    for h in HOSPITALES:
        propias = sorted((a for a in flota if a["hospital"] == h["nombre"]), key=lambda a: a["placa"])
        out.append({
            **h,
            "ambulancias": propias,
            "conteo": {e: sum(1 for a in propias if a["estado"] == e) for e in ESTADOS},
            "listas": sum(1 for a in propias if motivo_no_disponible(a) is None),
        })
    return out
