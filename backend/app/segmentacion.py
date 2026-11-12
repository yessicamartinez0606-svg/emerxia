"""Perfiles de servicio con K-Means — Práctica 07 dentro del sistema.

Es backend/ia/p07_segmentacion_kmeans_emergexia.py: 500 servicios de ambulancia sintéticos
(distancia desde el IMSS 220, nivel de tráfico, tiempo de respuesta y ambulancias libres) se
escalan con StandardScaler y K-Means los agrupa SIN etiquetas. Se revisan el método del codo
y el Silhouette Score, se entrena con K = 3 y cada grupo recibe un nombre según su tiempo de
respuesta promedio: Respuesta rápida, Respuesta intermedia y Requiere apoyo.

En el sistema, cada emergencia abierta se acomoda en el perfil al que más se parece (con sus
datos reales y el tiempo que estima el modelo de llegada) y se muestra la estrategia de ese
perfil.
"""
from __future__ import annotations

from functools import lru_cache

SEMILLA = 42
K_FINAL = 3
COLUMNAS = ["distancia_km", "nivel_trafico", "tiempo_respuesta_min", "ambulancias_libres"]
NOMBRES_COL = {"distancia_km": "Distancia (km)", "nivel_trafico": "Tráfico (0-10)",
               "tiempo_respuesta_min": "Tiempo de respuesta (min)", "ambulancias_libres": "Ambulancias libres"}
PERFILES = ["Respuesta rápida", "Respuesta intermedia", "Requiere apoyo"]
ESTRATEGIAS = {
    "Respuesta rápida": "Sale la unidad del IMSS 220 de forma normal.",
    "Respuesta intermedia": "Revisa el tráfico y las rutas alternas antes de salir.",
    "Requiere apoyo": "Pide apoyo al hospital más cercano y avisa al paciente del tiempo de espera.",
}


class SinScikitLearn(RuntimeError):
    pass


def _libs():
    try:
        import numpy as np
        import pandas as pd
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:   # pragma: no cover
        raise SinScikitLearn("Falta instalar numpy, pandas y scikit-learn: pip install -r requirements.txt") from exc
    return np, pd, KMeans, silhouette_score, StandardScaler


@lru_cache(maxsize=1)
def entrenar() -> dict:
    np, pd, KMeans, silhouette_score, StandardScaler = _libs()

    # 2-3. Tres perfiles simulados (solo para generar datos; K-Means no los ve) y mezcla
    rng = np.random.default_rng(SEMILLA)
    n = [180, 170, 150]
    rapido = np.column_stack([rng.normal(3.5, 1.2, n[0]), rng.normal(3.0, 1.2, n[0]),
                              rng.normal(9.0, 1.8, n[0]), rng.normal(4.0, 1.0, n[0])])
    intermedio = np.column_stack([rng.normal(8.0, 1.8, n[1]), rng.normal(5.5, 1.3, n[1]),
                                  rng.normal(16.0, 2.5, n[1]), rng.normal(2.5, 1.0, n[1])])
    apoyo = np.column_stack([rng.normal(13.0, 2.5, n[2]), rng.normal(8.0, 1.2, n[2]),
                             rng.normal(27.0, 4.0, n[2]), rng.normal(1.0, 0.8, n[2])])
    datos = np.vstack([rapido, intermedio, apoyo])
    rng.shuffle(datos)

    # 4. DataFrame en rangos realistas
    df = pd.DataFrame(datos, columns=COLUMNAS)
    df["distancia_km"] = df["distancia_km"].clip(0.5, 25)
    df["nivel_trafico"] = df["nivel_trafico"].clip(0, 10)
    df["tiempo_respuesta_min"] = df["tiempo_respuesta_min"].clip(3, 60)
    df["ambulancias_libres"] = df["ambulancias_libres"].round().clip(0, 6)

    # 7. Escalar
    escalador = StandardScaler()
    X = escalador.fit_transform(df[COLUMNAS])

    # 8-9. Codo y Silhouette
    codo = [{"k": k, "inercia": round(float(KMeans(n_clusters=k, random_state=SEMILLA, n_init=20).fit(X).inertia_), 2)}
            for k in range(1, 9)]
    silueta = []
    for k in range(2, 9):
        et = KMeans(n_clusters=k, random_state=SEMILLA, n_init=20).fit_predict(X)
        silueta.append({"k": k, "silhouette": round(float(silhouette_score(X, et)), 4)})

    # 10-11. Modelo final y nombres por tiempo de respuesta
    modelo = KMeans(n_clusters=K_FINAL, random_state=SEMILLA, n_init=20)
    df["cluster"] = modelo.fit_predict(X)
    promedios = df.groupby("cluster")[COLUMNAS].mean()
    orden = promedios["tiempo_respuesta_min"].sort_values().index.tolist()
    nombre_de = {int(c): PERFILES[i] for i, c in enumerate(orden)}
    df["perfil"] = df["cluster"].map(nombre_de)

    centroides = escalador.inverse_transform(modelo.cluster_centers_)
    conteo = df["cluster"].value_counts()
    perfiles = []
    for c in orden:
        perfiles.append({"cluster": int(c), "perfil": nombre_de[int(c)], "servicios": int(conteo[c]),
                         "estrategia": ESTRATEGIAS[nombre_de[int(c)]],
                         "promedio": {col: round(float(promedios.loc[c, col]), 2) for col in COLUMNAS},
                         "centroide": {col: round(float(v), 2) for col, v in zip(COLUMNAS, centroides[c])}})

    return {
        "modelo": modelo,
        "escalador": escalador,
        "nombre_de": nombre_de,
        "servicios": len(df),
        "k": K_FINAL,
        "codo": codo,
        "silhouette": silueta,
        "silhouette_final": round(float(silhouette_score(X, df["cluster"])), 4),
        "inercia_final": round(float(modelo.inertia_), 2),
        "perfiles": perfiles,
        # Para la gráfica de dispersión (distancia vs. tiempo).
        "puntos": [{"km": round(float(r.distancia_km), 2), "min": round(float(r.tiempo_respuesta_min), 2),
                    "perfil": r.perfil} for r in df.itertuples()],
        "columnas": NOMBRES_COL,
    }


def evaluacion() -> dict:
    return {k: v for k, v in entrenar().items() if k not in ("modelo", "escalador", "nombre_de")}


def clasificar(distancia_km: float, nivel_trafico: float, tiempo_respuesta_min: float, ambulancias_libres: float) -> dict:
    _, pd, *_ = _libs()
    e = entrenar()
    fila = pd.DataFrame([{"distancia_km": distancia_km, "nivel_trafico": nivel_trafico,
                          "tiempo_respuesta_min": tiempo_respuesta_min,
                          "ambulancias_libres": ambulancias_libres}])[COLUMNAS]
    c = int(e["modelo"].predict(e["escalador"].transform(fila))[0])
    perfil = e["nombre_de"][c]
    return {"datos": {k: round(float(v), 1) for k, v in fila.iloc[0].items()}, "perfil": perfil,
            "estrategia": ESTRATEGIAS[perfil], "nivel": PERFILES.index(perfil)}
