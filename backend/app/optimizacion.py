"""Optimización de hiperparámetros del TRIAJE — Práctica 06 dentro del sistema.

Es backend/ia/p06_optimizacion_hiperparametros_emergexia.py: con los mismos 500 reportes de
la práctica 05, GridSearchCV y RandomizedSearchCV (validación cruzada estratificada de 5
particiones, métrica F1) buscan la mejor configuración de Árbol de decisión, Bosque aleatorio
y KNN. El mejor modelo se califica con el 20 % de prueba, que es el MISMO de la práctica 05,
así que se puede comparar directamente.

En el sistema:
    - La búsqueda tarda alrededor de un minuto, así que se hace en segundo plano al arrancar
      la API y el resultado se guarda en DATA_DIR/ia/ (la siguiente vez carga al instante).
    - Mientras termina, el triaje usa el modelo de la práctica 05; cuando termina, usa el
      modelo optimizado (app/triaje.py → clasificar).
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

log = logging.getLogger("emergexia.ia")

SEMILLA = 42
VERSION = 1          # súbelo si cambian los datos o las rejillas, para no usar un resultado viejo

REJILLAS = {
    "Decision Tree": {"max_depth": [2, 3, 5, 8, 10, None], "min_samples_split": [2, 5, 10],
                      "min_samples_leaf": [1, 2, 4], "criterion": ["gini", "entropy"]},
    "Random Forest": {"n_estimators": [50, 100, 200], "max_depth": [3, 5, 8, None],
                      "min_samples_split": [2, 5, 10], "min_samples_leaf": [1, 2, 4]},
    "KNN": {"clasificador__n_neighbors": [3, 5, 7, 9, 11, 15], "clasificador__weights": ["uniform", "distance"],
            "clasificador__metric": ["euclidean", "manhattan"]},
}

_lock = threading.Lock()
_estado: dict = {"estado": "pendiente", "inicio": None, "fin": None, "error": None, "resultado": None, "modelo": None}


def _archivo() -> Path:
    import sklearn
    from .config import settings
    d = Path(settings.data_dir) / "ia"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"p06_triaje_v{VERSION}_sklearn{sklearn.__version__}.joblib"


def _limpiar(params: dict) -> dict:
    """Parámetros legibles: sin el prefijo del Pipeline y con None → "Sin límite"."""
    return {k.replace("clasificador__", ""): ("Sin límite" if v is None else v) for k, v in sorted(params.items())}


def _buscar() -> tuple[dict, object]:
    from scipy.stats import randint
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
    from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, StratifiedKFold, train_test_split
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeClassifier

    from . import triaje

    df = triaje.datos()        # mismos 500 reportes de la práctica 05
    X, y = df[triaje.COLUMNAS], df["es_critica"]
    X_ent, X_pru, y_ent, y_pru = train_test_split(X, y, test_size=0.20, random_state=SEMILLA, stratify=y)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMILLA)

    modelos = {
        "Decision Tree": DecisionTreeClassifier(random_state=SEMILLA),
        "Random Forest": RandomForestClassifier(random_state=SEMILLA, n_jobs=-1),
        "KNN": Pipeline([("escalador", StandardScaler()), ("clasificador", KNeighborsClassifier())]),
    }
    aleatorio = {
        "Decision Tree": {"max_depth": randint(2, 15), "min_samples_split": randint(2, 15),
                          "min_samples_leaf": randint(1, 8), "criterion": ["gini", "entropy"]},
        "Random Forest": {"n_estimators": randint(50, 301), "max_depth": [3, 5, 8, 12, None],
                          "min_samples_split": randint(2, 12), "min_samples_leaf": randint(1, 6)},
        "KNN": {"clasificador__n_neighbors": [3, 5, 7, 9, 11, 15, 19], "clasificador__weights": ["uniform", "distance"],
                "clasificador__metric": ["euclidean", "manhattan"]},
    }

    grid, random_, mejores = [], [], {}
    for nombre, modelo in modelos.items():
        t = time.time()
        g = GridSearchCV(modelo, REJILLAS[nombre], scoring="f1", cv=cv, n_jobs=-1, return_train_score=True).fit(X_ent, y_ent)
        seg_grid = time.time() - t
        mejores[nombre] = g.best_estimator_
        # Las 5 mejores combinaciones de la rejilla, con su F1 de entrenamiento y de validación.
        res = g.cv_results_
        top = sorted(range(len(res["params"])), key=lambda i: res["rank_test_score"][i])[:5]
        grid.append({"algoritmo": nombre, "mejor_f1": round(float(g.best_score_), 4),
                     "hiperparametros": _limpiar(g.best_params_), "combinaciones": len(res["params"]),
                     "entrenamientos": len(res["params"]) * cv.get_n_splits(), "segundos": round(seg_grid, 1),
                     "top": [{"hiperparametros": _limpiar(res["params"][i]),
                              "f1_validacion": round(float(res["mean_test_score"][i]), 4),
                              "f1_entrenamiento": round(float(res["mean_train_score"][i]), 4)} for i in top]})
        t = time.time()
        r = RandomizedSearchCV(modelo, aleatorio[nombre], n_iter=20, scoring="f1", cv=cv, n_jobs=-1,
                               random_state=SEMILLA).fit(X_ent, y_ent)
        random_.append({"algoritmo": nombre, "mejor_f1": round(float(r.best_score_), 4),
                        "hiperparametros": _limpiar(r.best_params_), "combinaciones": 20,
                        "segundos": round(time.time() - t, 1)})

    i = max(range(len(grid)), key=lambda k: (grid[k]["mejor_f1"], -k))      # idxmax: el primero en empate
    elegido = grid[i]["algoritmo"]
    mejor = mejores[elegido]
    pred = mejor.predict(X_pru)
    vn, fp, fn, vp = (int(v) for v in confusion_matrix(y_pru, pred, labels=[0, 1]).ravel())
    prueba = {"exactitud": accuracy_score(y_pru, pred), "precision": precision_score(y_pru, pred, zero_division=0),
              "recall": recall_score(y_pru, pred, zero_division=0), "f1": f1_score(y_pru, pred, zero_division=0)}

    p05 = triaje.entrenar()
    resultado = {
        "version": VERSION,
        "conjuntos": {"entrenamiento": len(X_ent), "prueba": len(X_pru)},
        "grid": grid,
        "random": random_,
        "elegido": elegido,
        "hiperparametros": grid[i]["hiperparametros"],
        "f1_validacion_cruzada": grid[i]["mejor_f1"],
        "prueba": {k: round(float(v), 4) for k, v in prueba.items()},
        "matriz": {"vn": vn, "fp": fp, "fn": fn, "vp": vp},
        # La práctica 05 usó el mismo 20 % de prueba: comparación directa.
        "antes": {"algoritmo": p05["elegido"], "prueba": p05["prueba"], "matriz": p05["matriz"]},
    }
    return resultado, mejor


def _correr() -> None:
    try:
        try:
            import joblib
            guardado = joblib.load(_archivo())
            if guardado.get("resultado", {}).get("version") == VERSION:
                with _lock:
                    _estado.update(estado="listo", resultado=guardado["resultado"], modelo=guardado["modelo"],
                                   fin=time.time(), error=None)
                return
        except Exception:  # noqa: BLE001  (no hay resultado guardado: se calcula)
            pass
        log.info("Optimizando hiperparámetros del triaje (práctica 06)…")
        resultado, modelo = _buscar()
        with _lock:
            _estado.update(estado="listo", resultado=resultado, modelo=modelo, fin=time.time(), error=None)
        log.info("Optimización lista: %s (F1 prueba %.2f)", resultado["elegido"], resultado["prueba"]["f1"])
        try:
            import joblib
            joblib.dump({"resultado": resultado, "modelo": modelo}, _archivo())
        except Exception:  # noqa: BLE001  (guardar es opcional)
            pass
    except Exception as exc:  # noqa: BLE001
        log.exception("Falló la optimización de hiperparámetros")
        with _lock:
            _estado.update(estado="error", error=f"{exc.__class__.__name__}: {exc}", fin=time.time())


def iniciar(esperar: bool = False) -> dict:
    """Arranca la búsqueda si no está corriendo ni lista. esperar=True la hace aquí mismo."""
    with _lock:
        if _estado["estado"] in ("entrenando", "listo"):
            return estado()
        _estado.update(estado="entrenando", inicio=time.time(), error=None)
    if esperar:
        _correr()
    else:
        threading.Thread(target=_correr, daemon=True, name="p06-optimizacion").start()
    return estado()


def estado() -> dict:
    e = _estado
    out = {"estado": e["estado"], "error": e["error"]}
    if e["estado"] == "entrenando" and e["inicio"]:
        out["segundos"] = round(time.time() - e["inicio"])
    if e["resultado"]:
        out.update(e["resultado"])
    return out


def modelo_optimo():
    """El modelo optimizado si ya está listo; si no, None."""
    return _estado["modelo"] if _estado["estado"] == "listo" else None


def descripcion_optima() -> str | None:
    r = _estado["resultado"] if _estado["estado"] == "listo" else None
    return r["elegido"] if r else None
