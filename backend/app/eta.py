"""¿Cuánto tarda en llegar la ambulancia? Fórmula fija vs. modelo que aprende.

Es la práctica de regresión (backend/ia/enfoque2_tiempo_llegada.py) convertida en parte del
sistema, con los mismos datos, el mismo modelo y los mismos resultados:

    A) FÓRMULA FIJA: 2 min para salir + distancia / 40 km/h. Siempre igual.
    B) MODELO QUE APRENDE: un árbol de regresión (DecisionTreeRegressor) que estudió 300
       servicios pasados y descubrió solo cómo influyen la hora pico, la lluvia y la zona.

La diferencia en el sistema es que, para cada emergencia, la LLUVIA ya no se inventa: viene
del clima actual de la zona (app/clima.py, Open-Meteo), y la hora y el fin de semana son los
de ese momento.

Los servicios del historial son ficticios (semilla 42), como en la práctica.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from .clima import ZONAS

ZONA_KM = {z["nombre"]: z["km"] for z in ZONAS}
META_MIN = 15             # meta de servicio (ficticia): llegar en 15 minutos o menos
FACTOR_CALLE = 1.3        # de distancia en línea recta a distancia por calle (aprox.)

NOMBRES_CLAROS = {
    "distancia_km": "Distancia",
    "hora": "Hora exacta",
    "hora_pico": "Hora pico",
    "fin_de_semana": "Fin de semana",
    "lluvia": "Lluvia",
}


class SinScikitLearn(RuntimeError):
    pass


def _libs():
    try:
        import numpy as np
        import pandas as pd
        from sklearn.metrics import mean_absolute_error, r2_score
        from sklearn.model_selection import train_test_split
        from sklearn.tree import DecisionTreeRegressor
    except ImportError as exc:   # pragma: no cover
        raise SinScikitLearn("Falta instalar numpy, pandas y scikit-learn: pip install -r requirements.txt") from exc
    return np, pd, train_test_split, DecisionTreeRegressor, mean_absolute_error, r2_score


def es_hora_pico(hora: int, finde: int) -> int:
    """De 7 a 9 y de 18 a 20 h, solo entre semana (igual que en la práctica)."""
    return int(finde == 0 and (7 <= hora <= 9 or 18 <= hora <= 20))


def formula_fija(distancia_km: float) -> float:
    """Supone que la ambulancia siempre va a 40 km/h y tarda 2 min en salir."""
    return 2 + distancia_km / 40 * 60


@lru_cache(maxsize=1)
def entrenar() -> dict:
    """Crea el historial de 300 servicios, entrena el árbol y lo califica. Se hace una sola
    vez (tarda menos de un segundo)."""
    np, pd, train_test_split, DecisionTreeRegressor, mean_absolute_error, r2_score = _libs()

    # 2. Historial de servicios (ficticio, semilla 42: siempre salen los mismos datos)
    rng = np.random.default_rng(42)
    n = 300
    zona = rng.choice(list(ZONA_KM.keys()), n)
    distancia_km = (np.array([ZONA_KM[z] for z in zona]) + rng.uniform(-1.5, 1.5, n)).clip(0.5).round(1)
    hora = rng.integers(0, 24, n)
    fin_de_semana = (rng.random(n) < 2 / 7).astype(int)
    lluvia = (rng.random(n) < 0.25).astype(int)
    hora_pico = ((((hora >= 7) & (hora <= 9)) | ((hora >= 18) & (hora <= 20))) & (fin_de_semana == 0)).astype(int)

    # Así se calcula "en secreto" el tiempo real; el modelo solo ve los resultados.
    velocidad = np.full(n, 42.0)
    velocidad = np.where(hora_pico == 1, 22.0, velocidad)
    velocidad = np.where(lluvia == 1, velocidad * 0.75, velocidad)
    velocidad = np.where(fin_de_semana == 1, velocidad * 1.10, velocidad)
    velocidad = np.where(zona == "Lerma", velocidad * 0.85, velocidad)
    minutos = (2 + distancia_km / velocidad * 60 + rng.normal(0, 1.5, n)).clip(3).round(1)

    df = pd.DataFrame({"zona": zona, "distancia_km": distancia_km, "hora": hora, "hora_pico": hora_pico,
                       "fin_de_semana": fin_de_semana, "lluvia": lluvia, "minutos_llegada": minutos})

    # 4. Preparar: una columna 0/1 por zona; 70 % para aprender, 30 % para examinar
    df_modelo = pd.get_dummies(df, columns=["zona"], dtype=int)
    X = df_modelo.drop(columns=["minutos_llegada"])
    y = df_modelo["minutos_llegada"]
    X_ent, X_prueba, y_ent, y_prueba = train_test_split(X, y, test_size=0.30, random_state=42)

    # 6. El modelo que aprende
    modelo = DecisionTreeRegressor(max_depth=5, min_samples_leaf=5, random_state=42)
    modelo.fit(X_ent, y_ent)

    # 7-8. Comparar y calificar
    pred_ml = modelo.predict(X_prueba)
    pred_formula = X_prueba["distancia_km"].map(formula_fija)
    calif = {}
    for nombre, pred in (("formula", pred_formula), ("modelo", pred_ml)):
        calif[nombre] = {"mae": round(float(mean_absolute_error(y_prueba, pred)), 2),
                         "r2": round(float(r2_score(y_prueba, pred)), 3)}

    comparacion = []
    for idx, real, f, m in list(zip(X_prueba.index, y_prueba, pred_formula, pred_ml))[:10]:
        comparacion.append({"zona": df.loc[idx, "zona"], "km": float(df.loc[idx, "distancia_km"]),
                            "hora": int(df.loc[idx, "hora"]), "lluvia": bool(df.loc[idx, "lluvia"]),
                            "hora_pico": bool(df.loc[idx, "hora_pico"]),
                            "real": round(float(real), 1), "formula": round(float(f), 1), "modelo": round(float(m), 1),
                            "mas_cercano": "modelo" if abs(m - real) < abs(f - real) else "formula"})

    # 9. ¿En qué se fija el modelo?
    importancias = []
    for col, peso in zip(X.columns, modelo.feature_importances_):
        if peso > 0.01:
            importancias.append({"factor": NOMBRES_CLAROS.get(col, "Zona " + col.replace("zona_", "")),
                                 "peso": round(float(peso), 3)})
    importancias.sort(key=lambda i: -i["peso"])

    promedios = df.groupby("zona")["minutos_llegada"].mean().sort_values()
    efectos = {}
    for col in ("hora_pico", "lluvia"):
        efectos[col] = {"con": round(float(df[df[col] == 1]["minutos_llegada"].mean()), 1),
                        "sin": round(float(df[df[col] == 0]["minutos_llegada"].mean()), 1)}

    return {
        "modelo": modelo,
        "columnas": list(X.columns),
        "servicios": n,
        "entrenamiento": len(X_ent),
        "prueba": len(X_prueba),
        "calificacion": calif,
        "ganador": "modelo" if calif["modelo"]["mae"] < calif["formula"]["mae"] else "formula",
        "comparacion": comparacion,
        "importancias": importancias,
        "promedio_por_zona": [{"zona": z, "minutos": round(float(m), 1)} for z, m in promedios.items()],
        "efectos": efectos,
        "muestra": df.head(8).to_dict(orient="records"),
    }


def evaluacion() -> dict:
    """Lo que la pantalla muestra del modelo (sin el objeto de scikit-learn)."""
    e = entrenar()
    return {k: v for k, v in e.items() if k != "modelo"} | {"meta_min": META_MIN, "zonas": list(ZONA_KM)}


def estimar(zona: str, distancia_km: float, hora: int, fin_de_semana: int, lluvia: int) -> dict:
    """Minutos estimados con la fórmula y con el modelo, y si se cumple la meta."""
    if zona not in ZONA_KM:
        raise ValueError(f"Zona desconocida: {zona}.")
    _, pd, *_ = _libs()
    e = entrenar()
    fila = {"distancia_km": distancia_km, "hora": hora, "hora_pico": es_hora_pico(hora, fin_de_semana),
            "fin_de_semana": fin_de_semana, "lluvia": lluvia}
    for col in e["columnas"]:
        if col.startswith("zona_"):
            fila[col] = int(col == f"zona_{zona}")
    t_modelo = float(e["modelo"].predict(pd.DataFrame([fila])[e["columnas"]])[0])
    t_formula = formula_fija(distancia_km)
    cumple = t_modelo <= META_MIN
    return {
        "zona": zona, "distancia_km": round(distancia_km, 1), "hora": hora, "fin_de_semana": bool(fin_de_semana),
        "hora_pico": bool(fila["hora_pico"]), "lluvia": bool(lluvia),
        "formula_min": round(t_formula, 1), "modelo_min": round(t_modelo, 1),
        "diferencia_min": round(t_modelo - t_formula, 1),
        "meta_min": META_MIN, "cumple_meta": cumple,
        "mensaje": (f"Según el modelo sí se cumple la meta de {META_MIN} min."
                    if cumple else f"Según el modelo NO se cumple la meta de {META_MIN} min: conviene enviar la unidad disponible más cercana."),
    }


def ahora_mx() -> datetime:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Mexico_City"))
    except Exception:  # noqa: BLE001
        return datetime.now(timezone(timedelta(hours=-6)))


def distancia_desde_hospital(lat: float, lng: float, hosp_lat: float, hosp_lng: float) -> float:
    """Distancia aproximada por calle: línea recta × 1.3."""
    r = 6371.0
    p1, p2 = math.radians(hosp_lat), math.radians(lat)
    dp, dl = p2 - p1, math.radians(lng - hosp_lng)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return max(0.5, 2 * r * math.asin(math.sqrt(a)) * FACTOR_CALLE)
