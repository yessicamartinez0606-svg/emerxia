# ============================================================
# PROYECTO: EMERGEXIA
# ETAPA 17: COMPARACION DE MODELOS DE IA
#
# Archivo:
# p25_comparacion_modelos_emergencias.py
#
# Modelos:
# 1. CNN 1D        - PyTorch (resultados de la etapa 16)
# 2. Random Forest - Scikit-learn (se entrena aqui)
#
# Objetivo:
# Comparar ambos modelos con exactamente los mismos conjuntos
# de entrenamiento, validacion y prueba para clasificar la
# tendencia del servicio de ambulancias.
# ============================================================

from pathlib import Path
import json
import time

import joblib
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # guarda graficas sin abrir ventanas
import matplotlib.pyplot as plt

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)


# ============================================================
# 1. CONFIGURACION
# ============================================================

RUTA_BASE = Path(__file__).resolve().parent

RUTA_DATOS = RUTA_BASE / "resultados_emergexia" / "cnn"

RUTA_SALIDA = RUTA_BASE / "resultados_emergexia" / "comparacion"

RUTA_SALIDA.mkdir(parents=True, exist_ok=True)

ARCHIVO_DATOS = RUTA_DATOS / "emergexia_datos_cnn.npz"

ARCHIVO_METRICAS_CNN = RUTA_DATOS / "metricas_cnn.json"

ARCHIVO_MODELO_RF = RUTA_SALIDA / "modelo_random_forest.joblib"

NOMBRES_CLASES = ["Deterioro", "Estable", "Mejora"]

# Orden de las 6 caracteristicas al aplanar (N, 2, 3) -> (N, 6).
NOMBRES_CARACTERISTICAS = [
    "tiempo_m1",
    "tiempo_m2",
    "tiempo_m3",
    "disponibilidad_m1",
    "disponibilidad_m2",
    "disponibilidad_m3"
]

RANDOM_STATE = 42


def titulo(texto):

    print("\n" + "=" * 65)
    print(texto)
    print("=" * 65)


def main():

    titulo("EMERGEXIA\nETAPA 17 - COMPARACION CNN 1D VS RANDOM FOREST")

    # ========================================================
    # 2. CARGAR DATOS
    # ========================================================

    print("\nCARGANDO LOS DATOS...")

    if not ARCHIVO_DATOS.exists():

        raise FileNotFoundError(
            f"No se encontro: {ARCHIVO_DATOS}. "
            "Ejecuta primero p23_preparacion_cnn_emergencias.py"
        )

    datos = np.load(ARCHIVO_DATOS, allow_pickle=False)

    X_train, X_val, X_test = datos["X_train"], datos["X_val"], datos["X_test"]

    y_train, y_val, y_test = datos["y_train"], datos["y_val"], datos["y_test"]

    print(f"Entrenamiento: {X_train.shape}")
    print(f"Validacion:    {X_val.shape}")
    print(f"Prueba:        {X_test.shape}")

    # ========================================================
    # 3. TRANSFORMAR PARA RANDOM FOREST
    # ========================================================

    # La CNN usa (registros, canales, meses) = (N, 2, 3).
    # Random Forest necesita una tabla (N, 6).

    X_train_rf = X_train.reshape(X_train.shape[0], -1)
    X_val_rf = X_val.reshape(X_val.shape[0], -1)
    X_test_rf = X_test.reshape(X_test.shape[0], -1)

    print("\nCaracteristicas utilizadas:")

    for numero, nombre in enumerate(NOMBRES_CARACTERISTICAS, start=1):
        print(f"{numero}. {nombre}")

    assert X_train_rf.shape[1] == 6
    assert len(X_train_rf) == len(y_train)
    assert len(X_val_rf) == len(y_val)
    assert len(X_test_rf) == len(y_test)

    for y in (y_train, y_val, y_test):
        assert set(np.unique(y)) == {0, 1, 2}

    print("Validaciones correctas.")

    # ========================================================
    # 4. ENTRENAR RANDOM FOREST
    # ========================================================

    print("\nENTRENANDO RANDOM FOREST (300 arboles)...")

    modelo_rf = RandomForestClassifier(
        n_estimators=300,
        random_state=RANDOM_STATE,
        n_jobs=-1
    )

    inicio = time.perf_counter()

    modelo_rf.fit(X_train_rf, y_train)

    tiempo_entrenamiento_rf = time.perf_counter() - inicio

    print(f"Tiempo de entrenamiento: {tiempo_entrenamiento_rf:.4f} s")

    # Validacion.
    pred_val = modelo_rf.predict(X_val_rf)

    print(f"Accuracy validacion: {accuracy_score(y_val, pred_val):.4f}")
    print(f"F1 Macro validacion: {f1_score(y_val, pred_val, average='macro'):.4f}")

    # ========================================================
    # 5. EVALUAR CON PRUEBA
    # ========================================================

    inicio = time.perf_counter()

    pred_test = modelo_rf.predict(X_test_rf)

    tiempo_prediccion_rf = time.perf_counter() - inicio

    accuracy_rf = accuracy_score(y_test, pred_test)
    precision_rf = precision_score(y_test, pred_test, average="macro", zero_division=0)
    recall_rf = recall_score(y_test, pred_test, average="macro", zero_division=0)
    f1_rf = f1_score(y_test, pred_test, average="macro", zero_division=0)

    titulo("RESULTADOS RANDOM FOREST")

    print(f"Accuracy:  {accuracy_rf:.4f}")
    print(f"Precision: {precision_rf:.4f}")
    print(f"Recall:    {recall_rf:.4f}")
    print(f"F1 Score:  {f1_rf:.4f}")

    print("\nMATRIZ DE CONFUSION (filas = real, columnas = predicho)")

    print(pd.DataFrame(
        confusion_matrix(y_test, pred_test, labels=[0, 1, 2]),
        index=NOMBRES_CLASES,
        columns=NOMBRES_CLASES
    ))

    print("\nREPORTE DE CLASIFICACION")

    print(classification_report(
        y_test,
        pred_test,
        labels=[0, 1, 2],
        target_names=NOMBRES_CLASES,
        zero_division=0
    ))

    # Importancia de cada variable: que meses y que canal
    # pesan mas para decidir la tendencia.
    importancias = pd.DataFrame({
        "caracteristica": NOMBRES_CARACTERISTICAS,
        "importancia": modelo_rf.feature_importances_
    }).sort_values("importancia", ascending=False)

    print("IMPORTANCIA DE LAS VARIABLES")

    print(importancias.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    importancias.to_csv(
        RUTA_SALIDA / "importancia_variables_rf.csv",
        index=False
    )

    # ========================================================
    # 6. METRICAS DE LA CNN
    # ========================================================

    if not ARCHIVO_METRICAS_CNN.exists():

        raise FileNotFoundError(
            "No se encontro metricas_cnn.json. "
            "Ejecuta primero p24_entrenamiento_cnn_emergencias.py"
        )

    with open(ARCHIVO_METRICAS_CNN, "r", encoding="utf-8") as archivo:
        metricas_cnn = json.load(archivo)["metricas_prueba"]

    accuracy_cnn = float(metricas_cnn["accuracy"])
    precision_cnn = float(metricas_cnn["precision_macro"])
    recall_cnn = float(metricas_cnn["recall_macro"])
    f1_cnn = float(metricas_cnn["f1_macro"])

    # ========================================================
    # 7. TABLA COMPARATIVA
    # ========================================================

    comparacion = pd.DataFrame({
        "Modelo": ["CNN 1D", "Random Forest"],
        "Accuracy": [accuracy_cnn, accuracy_rf],
        "Precision Macro": [precision_cnn, precision_rf],
        "Recall Macro": [recall_cnn, recall_rf],
        "F1 Macro": [f1_cnn, f1_rf]
    })

    titulo("RESULTADOS COMPARATIVOS")

    print(comparacion.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    archivo_csv = RUTA_SALIDA / "comparacion_cnn_randomforest.csv"

    comparacion.to_csv(archivo_csv, index=False, encoding="utf-8")

    archivo_json = RUTA_SALIDA / "metricas_comparacion.json"

    with open(archivo_json, "w", encoding="utf-8") as archivo:
        json.dump(
            {
                "proyecto": "Emergexia",
                "etapa": 17,
                "modelos": {
                    "CNN_1D": {
                        "accuracy": accuracy_cnn,
                        "precision_macro": precision_cnn,
                        "recall_macro": recall_cnn,
                        "f1_macro": f1_cnn
                    },
                    "Random_Forest": {
                        "accuracy": accuracy_rf,
                        "precision_macro": precision_rf,
                        "recall_macro": recall_rf,
                        "f1_macro": f1_rf,
                        "tiempo_entrenamiento_segundos": tiempo_entrenamiento_rf,
                        "tiempo_prediccion_segundos": tiempo_prediccion_rf
                    }
                },
                "observacion": (
                    "Ambos modelos usan los mismos conjuntos. La tendencia "
                    "se deriva de los tiempos de respuesta que tambien son "
                    "entradas del modelo."
                )
            },
            archivo,
            indent=4,
            ensure_ascii=False
        )

    # ========================================================
    # 8. GRAFICA
    # ========================================================

    metricas = ["Accuracy", "Precision Macro", "Recall Macro", "F1 Macro"]

    posiciones = np.arange(len(metricas))

    ancho = 0.35

    fig, ax = plt.subplots(figsize=(11, 6))

    ax.bar(posiciones - ancho / 2, comparacion.iloc[0, 1:].astype(float).values, ancho, label="CNN 1D")

    ax.bar(posiciones + ancho / 2, comparacion.iloc[1, 1:].astype(float).values, ancho, label="Random Forest")

    ax.set_title("Emergexia: CNN 1D vs Random Forest (tendencia del servicio)")
    ax.set_ylabel("Valor de la metrica")
    ax.set_xticks(posiciones)
    ax.set_xticklabels(metricas)
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()

    archivo_grafica = RUTA_SALIDA / "comparacion_modelos.png"

    plt.savefig(archivo_grafica, dpi=300)

    plt.close()

    # ========================================================
    # 9. GUARDAR MODELO RF
    # ========================================================

    joblib.dump(modelo_rf, ARCHIVO_MODELO_RF)

    print("\nARCHIVOS GENERADOS")

    for ruta in [archivo_csv, archivo_json, archivo_grafica, ARCHIVO_MODELO_RF]:
        print(ruta)

    # ========================================================
    # 10. CONCLUSION
    # ========================================================

    titulo("CONCLUSION DE LA COMPARACION")

    if accuracy_cnn > accuracy_rf:
        print("CNN 1D obtuvo mayor accuracy.")
    elif accuracy_rf > accuracy_cnn:
        print("Random Forest obtuvo mayor accuracy.")
    else:
        print("Ambos modelos obtuvieron el mismo accuracy.")

    if f1_cnn > f1_rf:
        print("CNN 1D obtuvo mayor F1 Macro.")
    elif f1_rf > f1_cnn:
        print("Random Forest obtuvo mayor F1 Macro.")
    else:
        print("Ambos modelos obtuvieron el mismo F1 Macro.")

    print("\nIMPORTANTE:")
    print("La tendencia se calcula con los mismos tiempos de respuesta")
    print("que recibe el modelo, por eso las metricas salen altas.")
    print("Esto no demuestra capacidad de anticipar el desempeno futuro;")
    print("para eso esta la etapa 18 (p26 y p27).")

    titulo("ETAPA 17 FINALIZADA")


if __name__ == "__main__":

    main()
