"""¿La emergencia es CRÍTICA? — Práctica 05 (comparación de algoritmos) dentro del sistema.

Es backend/ia/p05_comparacion_algoritmos_emergexia.py convertida en parte de Emergexia:

    - 500 reportes sintéticos (semilla 42) con saturación de oxígeno, frecuencia cardiaca,
      escala de Glasgow y edad. La etiqueta "crítica" sale de un riesgo sintético; NO es
      un protocolo clínico real de triaje.
    - 60 % entrenamiento, 20 % validación, 20 % prueba.
    - Se comparan Árbol de decisión, Bosque aleatorio (Random Forest) y KNN con escalado;
      se elige el de mayor F1 en validación, se reentrena con entrenamiento + validación y
      se califica con prueba y validación cruzada (F1).
    - Experimentos A, B y C: cambiar un hiperparámetro de cada algoritmo.

En el sistema, el modelo elegido calcula la probabilidad de que cada emergencia con signos
vitales capturados sea crítica, para ordenar la cola cuando hay pocas ambulancias libres.
"""
from __future__ import annotations

from functools import lru_cache

SEMILLA = 42
COLUMNAS = ["saturacion_oxigeno", "frecuencia_cardiaca", "escala_glasgow", "edad"]
NOMBRES = {"saturacion_oxigeno": "Saturación de oxígeno", "frecuencia_cardiaca": "Frecuencia cardiaca",
           "escala_glasgow": "Escala de Glasgow", "edad": "Edad"}
UMBRAL = 0.5
RANGOS = {"saturacion_oxigeno": (50, 100), "frecuencia_cardiaca": (20, 250), "escala_glasgow": (3, 15),
          "edad": (0, 120)}


class SinScikitLearn(RuntimeError):
    pass


def _libs():
    try:
        import numpy as np
        import pandas as pd
        from sklearn.base import clone
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
        from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
        from sklearn.neighbors import KNeighborsClassifier
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.tree import DecisionTreeClassifier
    except ImportError as exc:   # pragma: no cover
        raise SinScikitLearn("Falta instalar numpy, pandas y scikit-learn: pip install -r requirements.txt") from exc
    return dict(np=np, pd=pd, clone=clone, RF=RandomForestClassifier, acc=accuracy_score, cm=confusion_matrix,
                f1=f1_score, prec=precision_score, rec=recall_score, SKF=StratifiedKFold, cvs=cross_val_score,
                tts=train_test_split, KNN=KNeighborsClassifier, Pipeline=Pipeline, Scaler=StandardScaler,
                DT=DecisionTreeClassifier)


def _constructores(L):
    def arbol(max_depth=5):
        return L["DT"](max_depth=max_depth, min_samples_leaf=4, random_state=SEMILLA)

    def bosque(n_estimators=200):
        # n_jobs=1 (la práctica usa -1): mismo resultado, sin abrir procesos en el servidor.
        return L["RF"](n_estimators=n_estimators, max_depth=None, min_samples_leaf=2, n_jobs=1, random_state=SEMILLA)

    def knn(n_neighbors=7):
        return L["Pipeline"]([("escalador", L["Scaler"]()),
                              ("clasificador", L["KNN"](n_neighbors=n_neighbors, weights="distance"))])
    return {"Decision Tree": arbol, "Random Forest": bosque, "KNN": knn}


@lru_cache(maxsize=1)
def datos():
    """Los 500 reportes sintéticos de la práctica 05 (también los usa la práctica 06)."""
    L = _libs()
    np, pd = L["np"], L["pd"]
    rng = np.random.default_rng(SEMILLA)
    n = 500
    sat = rng.uniform(75, 100, n)
    fc = rng.uniform(40, 160, n)
    gcs = rng.integers(3, 16, n)
    edad = rng.uniform(1, 95, n)
    riesgo = ((100 - sat) / 25) * 0.35 + (np.abs(fc - 85) / 75) * 0.25 + ((15 - gcs) / 12) * 0.30 + (edad / 95) * 0.10
    ruido = rng.normal(loc=0, scale=0.10, size=n)
    critica = ((riesgo + ruido) >= 0.50).astype(int)
    return pd.DataFrame({"saturacion_oxigeno": sat, "frecuencia_cardiaca": fc, "escala_glasgow": gcs, "edad": edad,
                         "es_critica": critica})


@lru_cache(maxsize=1)
def entrenar() -> dict:
    L = _libs()
    pd = L["pd"]
    df = datos()
    X, y = df[COLUMNAS], df["es_critica"]

    X_ev, X_pru, y_ev, y_pru = L["tts"](X, y, test_size=0.20, random_state=SEMILLA, stratify=y)
    X_ent, X_val, y_ent, y_val = L["tts"](X_ev, y_ev, test_size=0.25, random_state=SEMILLA, stratify=y_ev)

    def evaluar(m, Xe, ye):
        p = m.predict(Xe)
        return {"exactitud": float(L["acc"](ye, p)), "precision": float(L["prec"](ye, p, zero_division=0)),
                "recall": float(L["rec"](ye, p, zero_division=0)), "f1": float(L["f1"](ye, p, zero_division=0))}

    crear = _constructores(L)
    comparacion = []
    for nombre, c in crear.items():
        m = c().fit(X_ent, y_ent)
        comparacion.append({"algoritmo": nombre, **{k: round(v, 4) for k, v in evaluar(m, X_val, y_val).items()}})
    comparacion.sort(key=lambda r: -r["f1"])     # sort estable, como sort_values de la práctica
    elegido = comparacion[0]["algoritmo"]

    final = L["clone"](crear[elegido]())
    X_fin, y_fin = pd.concat([X_ent, X_val]), pd.concat([y_ent, y_val])
    final.fit(X_fin, y_fin)
    prueba = evaluar(final, X_pru, y_pru)
    vn, fp, fn, vp = (int(v) for v in L["cm"](y_pru, final.predict(X_pru), labels=[0, 1]).ravel())
    cv = L["cvs"](L["clone"](crear[elegido]()), X_fin, y_fin,
                  cv=L["SKF"](n_splits=5, shuffle=True, random_state=SEMILLA), scoring="f1")

    experimentos = []
    for clave, alg, param, valores in (("A", "KNN", "n_neighbors", [3, 5, 7, 9, 15]),
                                       ("B", "Random Forest", "n_estimators", [50, 100, 200, 500]),
                                       ("C", "Decision Tree", "max_depth", [2, 3, 5, 8, None])):
        filas = []
        for v in valores:
            m = crear[alg](v).fit(X_ent, y_ent)
            filas.append({"valor": "Sin límite" if v is None else str(v),
                          "exactitud_entrenamiento": round(float(L["acc"](y_ent, m.predict(X_ent))), 4),
                          **{k: round(x, 4) for k, x in evaluar(m, X_val, y_val).items()}})
        mejor = max(range(len(filas)), key=lambda k: (filas[k]["f1"], -k))
        experimentos.append({"clave": clave, "algoritmo": alg, "parametro": param, "filas": filas,
                             "mejor": filas[mejor]["valor"]})

    conteo = df["es_critica"].value_counts()
    return {
        "modelo": final,
        "reportes": len(df),
        "clases": {"no_critica": int(conteo.get(0, 0)), "critica": int(conteo.get(1, 0))},
        "conjuntos": {"entrenamiento": len(X_ent), "validacion": len(X_val), "prueba": len(X_pru)},
        "comparacion": comparacion,
        "elegido": elegido,
        "prueba": {k: round(v, 4) for k, v in prueba.items()},
        "matriz": {"vn": vn, "fp": fp, "fn": fn, "vp": vp},
        "validacion_cruzada": {"particiones": [round(float(s), 4) for s in cv],
                               "promedio": round(float(cv.mean()), 4), "desviacion": round(float(cv.std()), 4)},
        "experimentos": experimentos,
    }


def evaluacion() -> dict:
    return {k: v for k, v in entrenar().items() if k != "modelo"} | {"umbral": UMBRAL}


def validar(signos: dict) -> dict:
    out = {}
    for c in COLUMNAS:
        v = signos.get(c)
        if v is None or v == "":
            raise ValueError(f"Falta {NOMBRES[c].lower()}.")
        v = float(v)
        lo, hi = RANGOS[c]
        if not lo <= v <= hi:
            raise ValueError(f"{NOMBRES[c]} fuera de rango ({lo}-{hi}).")
        out[c] = v
    return out


def tiene_signos(em: dict) -> bool:
    return all(em.get(c) not in (None, "") for c in ("saturacion_oxigeno", "frecuencia_cardiaca", "escala_glasgow"))


def signos_de(em: dict) -> dict:
    """Signos vitales de una emergencia; la edad viene de paciente_edad (texto)."""
    try:
        edad = float(str(em.get("paciente_edad") or "").strip() or "nan")
    except ValueError:
        edad = float("nan")
    if edad != edad:      # sin edad capturada: se usa un adulto de 40 años
        edad = 40.0
    return {"saturacion_oxigeno": em.get("saturacion_oxigeno"), "frecuencia_cardiaca": em.get("frecuencia_cardiaca"),
            "escala_glasgow": em.get("escala_glasgow"), "edad": edad}


def clasificar(signos: dict) -> dict:
    L = _libs()
    s = validar(signos)
    # Si la práctica 06 ya terminó, se usa el modelo con hiperparámetros optimizados.
    from . import optimizacion
    m, algoritmo, optimizado = optimizacion.modelo_optimo(), optimizacion.descripcion_optima(), True
    if m is None:
        e = entrenar()
        m, algoritmo, optimizado = e["modelo"], e["elegido"], False
    prob = float(m.predict_proba(L["pd"].DataFrame([s])[COLUMNAS])[0][list(m.classes_).index(1)])
    critica = prob >= UMBRAL
    return {"signos": s, "probabilidad": round(prob, 3), "critica": critica, "algoritmo": algoritmo,
            "optimizado": optimizado,
            "prioridad": "CRÍTICA" if critica else "No crítica",
            "mensaje": ("Emergencia CRÍTICA: asigna ambulancia de inmediato." if critica
                        else "No crítica según el modelo: puede esperar en la cola si no hay unidades libres.")}
