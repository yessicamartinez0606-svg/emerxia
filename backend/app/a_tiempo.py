"""¿La ambulancia llegará a tiempo (15 min o menos)? — Práctica 04 dentro del sistema.

Es backend/ia/p04_llegada_a_tiempo.py convertida en parte de Emergexia, con los mismos
datos, el mismo procedimiento y los mismos resultados:

    1. 500 servicios sintéticos (semilla 42): distancia, nivel de tráfico, ambulancias
       libres en el IMSS 220 y años de experiencia del operador.
    2. 60 % entrenamiento, 20 % validación, 20 % prueba (estratificado).
    3. Árboles de decisión con profundidad 1, 2, 3, 5, 10 y sin límite: se elige el de
       mejor exactitud en VALIDACIÓN (detecta subajuste y sobreajuste).
    4. El elegido se califica una sola vez con PRUEBA (exactitud, precisión, recall, F1,
       matriz de confusión) y con validación cruzada de 5 particiones.

En el sistema, para cada emergencia los datos ya no se inventan: la distancia sale de la
ubicación de la emergencia, el tráfico de la hora y el clima, las ambulancias libres de la
flota del IMSS 220 y la experiencia del operador asignado.
"""
from __future__ import annotations

from functools import lru_cache

SEMILLA = 42
UMBRAL_MIN = 15
PROFUNDIDADES = [1, 2, 3, 5, 10, None]
COLUMNAS = ["distancia_km", "nivel_trafico", "ambulancias_libres", "experiencia_operador"]
NOMBRES = {
    "distancia_km": "Distancia",
    "nivel_trafico": "Nivel de tráfico",
    "ambulancias_libres": "Ambulancias libres",
    "experiencia_operador": "Experiencia del operador",
}
EXPERIENCIA_SIN_DATO = 5.0     # si el operador no tiene capturados sus años de experiencia


class SinScikitLearn(RuntimeError):
    pass


def _libs():
    try:
        import numpy as np
        import pandas as pd
        from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_score,
                                     recall_score)
        from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
        from sklearn.tree import DecisionTreeClassifier
    except ImportError as exc:   # pragma: no cover
        raise SinScikitLearn("Falta instalar numpy, pandas y scikit-learn: pip install -r requirements.txt") from exc
    return (np, pd, train_test_split, StratifiedKFold, cross_val_score, DecisionTreeClassifier,
            accuracy_score, precision_score, recall_score, f1_score, confusion_matrix)


def _ajuste(entrenamiento: float, validacion: float) -> str:
    """Mismos indicadores didácticos de la práctica."""
    if entrenamiento < 0.70 and validacion < 0.70:
        return "Posible subajuste"
    if entrenamiento - validacion > 0.10:
        return "Posible sobreajuste"
    return "Sin brecha grande"


@lru_cache(maxsize=1)
def entrenar() -> dict:
    (np, pd, train_test_split, StratifiedKFold, cross_val_score, DecisionTreeClassifier,
     accuracy_score, precision_score, recall_score, f1_score, confusion_matrix) = _libs()

    # 3. Datos sintéticos (mismo orden de llamadas que la práctica → mismos números)
    rng = np.random.default_rng(SEMILLA)
    n = 500
    distancia_km = rng.uniform(0.5, 18, n)
    nivel_trafico = rng.uniform(0, 10, n)
    ambulancias_libres = rng.integers(0, 7, n)
    experiencia_operador = rng.uniform(0, 15, n)
    ruido = rng.normal(0, 3.0, n)
    tiempo = (3 + distancia_km * (0.9 + 0.08 * nivel_trafico) + np.where(ambulancias_libres == 0, 4, 0)
              - ambulancias_libres * 0.4 - experiencia_operador * 0.2 + ruido)
    y_todo = (tiempo <= UMBRAL_MIN).astype(int)
    df = pd.DataFrame({"distancia_km": distancia_km, "nivel_trafico": nivel_trafico,
                       "ambulancias_libres": ambulancias_libres, "experiencia_operador": experiencia_operador,
                       "llega_a_tiempo": y_todo})
    X, y = df[COLUMNAS], df["llega_a_tiempo"]

    # 5-6. 60 / 20 / 20
    X_ent, X_tmp, y_ent, y_tmp = train_test_split(X, y, test_size=0.40, random_state=SEMILLA, stratify=y)
    X_val, X_pru, y_val, y_pru = train_test_split(X_tmp, y_tmp, test_size=0.50, random_state=SEMILLA, stratify=y_tmp)

    # 7-8. Una profundidad por modelo
    modelos, comparacion = {}, []
    for p in PROFUNDIDADES:
        m = DecisionTreeClassifier(max_depth=p, random_state=SEMILLA).fit(X_ent, y_ent)
        modelos[p] = m
        e = float(accuracy_score(y_ent, m.predict(X_ent)))
        v = float(accuracy_score(y_val, m.predict(X_val)))
        comparacion.append({"profundidad": "Sin límite" if p is None else str(p), "entrenamiento": round(e, 4),
                            "validacion": round(v, 4), "diferencia": round(e - v, 4), "ajuste": _ajuste(e, v)})

    # 9. Mejor validación (en empate, el más sencillo)
    i = max(range(len(comparacion)), key=lambda k: (comparacion[k]["validacion"], -k))
    prof = PROFUNDIDADES[i]
    mejor = modelos[prof]
    for k, c in enumerate(comparacion):
        c["elegido"] = k == i

    # 10-12. Prueba
    pred = mejor.predict(X_pru)
    vn, fp, fn, vp = (int(x) for x in confusion_matrix(y_pru, pred, labels=[0, 1]).ravel())
    recall_tarde = vn / (vn + fp) if vn + fp else 0.0
    prueba = {"exactitud": float(accuracy_score(y_pru, pred)),
              "precision": float(precision_score(y_pru, pred, zero_division=0)),
              "recall": float(recall_score(y_pru, pred, zero_division=0)),
              "f1": float(f1_score(y_pru, pred, zero_division=0)),
              "recall_tarde": recall_tarde}

    # 13. Validación cruzada (solo entrenamiento)
    cv = cross_val_score(DecisionTreeClassifier(max_depth=prof, random_state=SEMILLA), X_ent, y_ent,
                         cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMILLA), scoring="accuracy")

    importancias = sorted(({"factor": NOMBRES[c], "peso": round(float(w), 3)}
                           for c, w in zip(COLUMNAS, mejor.feature_importances_)), key=lambda x: -x["peso"])
    conteo = df["llega_a_tiempo"].value_counts()
    return {
        "modelo": mejor,
        "servicios": n,
        "clases": {"tarde": int(conteo.get(0, 0)), "a_tiempo": int(conteo.get(1, 0))},
        "conjuntos": {"entrenamiento": len(X_ent), "validacion": len(X_val), "prueba": len(X_pru)},
        "comparacion": comparacion,
        "profundidad": comparacion[i]["profundidad"],
        "prueba": {k: round(v, 4) for k, v in prueba.items()},
        "matriz": {"vn": vn, "fp": fp, "fn": fn, "vp": vp},
        "validacion_cruzada": {"particiones": [round(float(s), 4) for s in cv],
                               "promedio": round(float(cv.mean()), 4), "desviacion": round(float(cv.std()), 4)},
        "importancias": importancias,
    }


def evaluacion() -> dict:
    return {k: v for k, v in entrenar().items() if k != "modelo"} | {"umbral_min": UMBRAL_MIN}


def estimar(distancia_km: float, nivel_trafico: float, ambulancias_libres: int, experiencia_operador: float) -> dict:
    _, pd, *_ = _libs()
    e = entrenar()
    fila = pd.DataFrame([{"distancia_km": distancia_km, "nivel_trafico": nivel_trafico,
                          "ambulancias_libres": ambulancias_libres, "experiencia_operador": experiencia_operador}])[COLUMNAS]
    m = e["modelo"]
    a_tiempo = bool(m.predict(fila)[0] == 1)
    prob = float(m.predict_proba(fila)[0][list(m.classes_).index(1)])
    return {
        "datos": {"distancia_km": round(distancia_km, 1), "nivel_trafico": round(nivel_trafico, 1),
                  "ambulancias_libres": int(ambulancias_libres), "experiencia_operador": round(experiencia_operador, 1)},
        "llega_a_tiempo": a_tiempo,
        "probabilidad": round(prob, 3),
        "umbral_min": UMBRAL_MIN,
        "mensaje": (f"La ambulancia LLEGARÁ A TIEMPO (en {UMBRAL_MIN} min o menos)." if a_tiempo
                    else "La ambulancia LLEGARÁ TARDE. Considera pedir apoyo de otro hospital."),
    }


def trafico_0_10(hora: int, velocidad_clima: float = 1.0) -> float:
    """Convierte el periodo del día (red_vial.periodo) y la lluvia en la escala 0-10 de la
    práctica: noche ≈ 1.5, valle ≈ 4.5, hora pico ≈ 8; la lluvia lo sube (hasta 10)."""
    from .red_vial import periodo
    base = {"noche": 1.5, "valle": 4.5, "pico": 8.0}[periodo(hora)]
    return round(min(10.0, base + (1 / velocidad_clima - 1) * 6), 1)
