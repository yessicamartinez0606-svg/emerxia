"""Entrenamiento, validación y prueba de los modelos de triage (Prácticas 04 y 05 aplicadas).

Flujo:
    1. División 60 % entrenamiento / 20 % validación / 20 % prueba (estratificada).
    2. Se entrenan Decision Tree, Random Forest y KNN con el conjunto de entrenamiento.
    3. Se comparan con el conjunto de validación y se elige uno.
    4. El elegido se reentrena con entrenamiento + validación (80 %).
    5. Solo al final se usa el conjunto de prueba para estimar el rendimiento real.
    6. Validación cruzada estratificada (StratifiedKFold) sobre el 80 %, sin tocar la prueba.

Criterio de selección: F2-score.
En una emergencia, un FALSO NEGATIVO (paciente grave al que se le manda ambulancia Básica)
es mucho peor que un falso positivo (mandar Avanzada a quien no la necesitaba). El F2 pesa
el recall el doble que la precisión, sin premiar a un modelo que diga "Avanzada" a todo
(eso tendría recall 100 % pero precisión baja y un F2 menor).
"""
from __future__ import annotations

import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from .datos import OBJETIVO, SEMILLA, VARIABLES

CRITERIO = "f2_score"


# ------------------------------------------------------------------
# Modelos (misma configuración base de la Práctica 05)
# ------------------------------------------------------------------
def crear_arbol(max_depth=5) -> DecisionTreeClassifier:
    return DecisionTreeClassifier(max_depth=max_depth, min_samples_leaf=4, random_state=SEMILLA)


def crear_bosque(n_estimators=200) -> RandomForestClassifier:
    return RandomForestClassifier(
        n_estimators=n_estimators, max_depth=None, min_samples_leaf=2, n_jobs=-1, random_state=SEMILLA
    )


def crear_knn(n_neighbors=7) -> Pipeline:
    # KNN mide distancias: sin escalar, la presión (60-210) pesaría más que el Glasgow (3-15).
    return Pipeline([
        ("escalador", StandardScaler()),
        ("clasificador", KNeighborsClassifier(n_neighbors=n_neighbors, weights="distance")),
    ])


def modelos_base() -> dict:
    return {"Decision Tree": crear_arbol(), "Random Forest": crear_bosque(), "KNN": crear_knn()}


# ------------------------------------------------------------------
# División de datos
# ------------------------------------------------------------------
def dividir(df: pd.DataFrame) -> dict:
    X, y = df[VARIABLES], df[OBJETIVO]

    # 80 % (entrenamiento + validación) / 20 % prueba
    X_ev, X_prueba, y_ev, y_prueba = train_test_split(
        X, y, test_size=0.20, random_state=SEMILLA, stratify=y
    )
    # Del 80 %: 75 % entrenamiento y 25 % validación → 60 / 20 / 20 del total
    X_ent, X_val, y_ent, y_val = train_test_split(
        X_ev, y_ev, test_size=0.25, random_state=SEMILLA, stratify=y_ev
    )
    return {
        "X_ent": X_ent, "y_ent": y_ent,
        "X_val": X_val, "y_val": y_val,
        "X_prueba": X_prueba, "y_prueba": y_prueba,
        "X_ev": X_ev, "y_ev": y_ev,
    }


# ------------------------------------------------------------------
# Métricas
# ------------------------------------------------------------------
def metricas(y_real, y_pred) -> dict:
    return {
        "exactitud": accuracy_score(y_real, y_pred),
        "precision": precision_score(y_real, y_pred, zero_division=0),
        "recall": recall_score(y_real, y_pred, zero_division=0),
        "f1_score": f1_score(y_real, y_pred, zero_division=0),
        "f2_score": fbeta_score(y_real, y_pred, beta=2, zero_division=0),
    }


def evaluar_en_validacion(modelo, d: dict) -> dict:
    """Entrena con 'entrenamiento' y mide en entrenamiento y validación (para ver sobreajuste)."""
    modelo.fit(d["X_ent"], d["y_ent"])
    m = metricas(d["y_val"], modelo.predict(d["X_val"]))
    m["exactitud_entrenamiento"] = accuracy_score(d["y_ent"], modelo.predict(d["X_ent"]))
    m["brecha"] = m["exactitud_entrenamiento"] - m["exactitud"]
    return m


def diagnostico_ajuste(exac_ent: float, exac_val: float) -> str:
    """Indicador didáctico (Práctica 04), no una prueba definitiva."""
    if exac_ent < 0.70 and exac_val < 0.70:
        return "Posible subajuste"
    if exac_ent - exac_val > 0.10:
        return "Posible sobreajuste"
    return "Buen ajuste"


# ------------------------------------------------------------------
# Comparación y selección (Práctica 05)
# ------------------------------------------------------------------
def comparar(d: dict, modelos: dict | None = None) -> pd.DataFrame:
    filas = []
    for nombre, modelo in (modelos or modelos_base()).items():
        m = evaluar_en_validacion(modelo, d)
        filas.append({"algoritmo": nombre, **m,
                      "ajuste": diagnostico_ajuste(m["exactitud_entrenamiento"], m["exactitud"])})
    return (pd.DataFrame(filas)
            .sort_values(by=[CRITERIO, "recall"], ascending=False)
            .reset_index(drop=True))


def entrenar_final(nombre: str, d: dict, modelos: dict | None = None) -> dict:
    """Reentrena el algoritmo elegido con el 80 % y lo evalúa UNA vez con la prueba."""
    base = (modelos or modelos_base())[nombre]
    modelo = clone(base).fit(d["X_ev"], d["y_ev"])
    pred = modelo.predict(d["X_prueba"])

    cv = cross_val_score(
        clone(base), d["X_ev"], d["y_ev"],
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMILLA),
        scoring="recall", n_jobs=-1,
    )
    return {
        "modelo": modelo,
        "predicciones": pred,
        "metricas_prueba": metricas(d["y_prueba"], pred),
        "matriz": confusion_matrix(d["y_prueba"], pred, labels=[0, 1]),
        "cv_recall": cv,
    }


# ------------------------------------------------------------------
# Experimentos de la actividad de modificación (Práctica 05)
# ------------------------------------------------------------------
EXPERIMENTOS = {
    "A_knn_n_neighbors": ("n_neighbors", [3, 5, 7, 9, 15], crear_knn),
    "B_rf_n_estimators": ("n_estimators", [50, 100, 200, 500], crear_bosque),
    "C_dt_max_depth": ("max_depth", [2, 3, 5, 8, None], crear_arbol),
}


def correr_experimento(clave: str, d: dict) -> pd.DataFrame:
    parametro, valores, fabrica = EXPERIMENTOS[clave]
    filas = []
    for v in valores:
        m = evaluar_en_validacion(fabrica(v), d)
        filas.append({
            parametro: "Sin limite" if v is None else v,
            "exactitud_entrenamiento": m["exactitud_entrenamiento"],
            "exactitud_validacion": m["exactitud"],
            "recall": m["recall"],
            "f2_score": m["f2_score"],
            "ajuste": diagnostico_ajuste(m["exactitud_entrenamiento"], m["exactitud"]),
        })
    return pd.DataFrame(filas)
