# ============================================================
# PROYECTO: EMERGEXIA
# PRACTICA 10 - ETAPA 2
# ARCHIVO: p11_modelo_supervisado_emergencias.py
#
# OBJETIVO:
# 1. Separar caracteristicas (X) y variable objetivo (y).
# 2. Dividir los datos en entrenamiento y prueba.
# 3. Entrenar Decision Tree y Random Forest.
# 4. Comparar sus metricas.
# 5. Elegir el mejor modelo.
# 6. Guardarlo con Joblib.
# 7. Recuperarlo para clasificar nuevas emergencias.
#
# Problema: predecir si una emergencia es critica.
#   1 = Critica | 0 = No critica
#
# En emergencias, el Recall de la clase "Critica" es muy importante:
# no detectar una emergencia critica es el error mas peligroso.
# ============================================================


# ------------------------------------------------------------
# 1. LIBRERIAS
# ------------------------------------------------------------
import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
from pathlib import Path

from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report
)


# ------------------------------------------------------------
# 2. CONFIGURACION
# ------------------------------------------------------------
# Carpeta donde esta este archivo (no depende de desde donde se ejecute).
RUTA_BASE = Path(__file__).resolve().parent
ARCHIVO_DATOS = RUTA_BASE / "resultados_sistema_inteligente" / "emergexia_datos.csv"
RUTA_MODELOS = RUTA_BASE / "resultados_sistema_inteligente" / "modelos"
RUTA_MODELOS.mkdir(parents=True, exist_ok=True)

CARACTERISTICAS = ["edad", "frecuencia_cardiaca", "saturacion_oxigeno", "distancia_km"]
VARIABLE_OBJETIVO = "critica"
ETIQUETAS = ["No critica", "Critica"]
SEMILLA = 42


# ------------------------------------------------------------
# 3. CARGAR Y VALIDAR LOS DATOS
# ------------------------------------------------------------
def cargar_datos():

    print("\nCARGANDO DATASET EMERGEXIA...")

    if not ARCHIVO_DATOS.exists():
        raise FileNotFoundError(f"No se encontro {ARCHIVO_DATOS}. Ejecuta primero p10_datos_emergencias.py")

    datos = pd.read_csv(ARCHIVO_DATOS)
    columnas = CARACTERISTICAS + [VARIABLE_OBJETIVO]

    faltantes = [c for c in columnas if c not in datos.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas: {faltantes}")

    if datos[columnas].isnull().any().any():
        raise ValueError("Existen valores nulos.")

    if not np.isfinite(datos[columnas].to_numpy(dtype=float)).all():
        raise ValueError("Hay valores no numericos o infinitos.")

    if set(datos[VARIABLE_OBJETIVO].unique()) != {0, 1}:
        raise ValueError("La variable critica debe tener los valores 0 y 1.")

    print("Dataset cargado. Total de emergencias:", len(datos))
    return datos


# ------------------------------------------------------------
# 4. SEPARAR X e y, Y DIVIDIR LOS DATOS
# ------------------------------------------------------------
def preparar_datos(datos):

    X = datos[CARACTERISTICAS]
    y = datos[VARIABLE_OBJETIVO]

    print("\nCARACTERISTICAS:")
    print(X.head())
    print("\nCriticas / No criticas:")
    print(y.value_counts())

    # 80% entrenamiento y 20% prueba.
    # stratify=y conserva la proporcion de criticas y no criticas.
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=SEMILLA, stratify=y
    )

    print("\nEntrenamiento:", len(X_train), "| Prueba:", len(X_test))
    return X_train, X_test, y_train, y_test


# ------------------------------------------------------------
# 5. ENTRENAR Y EVALUAR LOS MODELOS
# ------------------------------------------------------------
def entrenar_y_evaluar(X_train, X_test, y_train, y_test):

    modelos = {
        # Un solo arbol de decisiones.
        "Decision Tree": DecisionTreeClassifier(
            max_depth=5, min_samples_split=10, min_samples_leaf=5, random_state=SEMILLA
        ),
        # 200 arboles que votan.
        "Random Forest": RandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_split=5, min_samples_leaf=2,
            random_state=SEMILLA, n_jobs=-1
        )
    }

    resultados = {}

    for nombre, modelo in modelos.items():

        print("\n" + "=" * 60)
        print("ENTRENANDO:", nombre)
        print("=" * 60)

        modelo.fit(X_train, y_train)
        pred = modelo.predict(X_test)

        resultados[nombre] = {
            "Accuracy": accuracy_score(y_test, pred),
            "Precision": precision_score(y_test, pred, zero_division=0),
            "Recall": recall_score(y_test, pred, zero_division=0),
            "F1-score": f1_score(y_test, pred, zero_division=0)
        }

        for metrica, valor in resultados[nombre].items():
            print(f"{metrica:10}: {valor:.4f}")

        print("\nREPORTE DE CLASIFICACION:")
        print(classification_report(y_test, pred, labels=[0, 1], target_names=ETIQUETAS, zero_division=0))

        matriz = confusion_matrix(y_test, pred, labels=[0, 1])
        print("MATRIZ DE CONFUSION:")
        print(matriz)
        print("Criticas NO detectadas (falsos negativos):", matriz[1, 0])

    return resultados, modelos


# ------------------------------------------------------------
# 6. COMPARAR Y GRAFICAR
# ------------------------------------------------------------
def comparar_modelos(resultados):

    tabla = pd.DataFrame(resultados).T.sort_values("F1-score", ascending=False)

    print("\n" + "=" * 60)
    print("COMPARACION DE ALGORITMOS")
    print("=" * 60)
    print(tabla.round(4))

    tabla.to_csv(RUTA_BASE / "resultados_sistema_inteligente" / "comparacion_modelos.csv", encoding="utf-8")

    tabla.plot(kind="bar", figsize=(10, 6))
    plt.title("Emergexia - Comparacion de modelos")
    plt.xlabel("Algoritmo")
    plt.ylabel("Valor de la metrica")
    plt.ylim(0, 1.05)
    plt.xticks(rotation=0)
    plt.legend(title="Metricas", loc="lower right")
    plt.tight_layout()
    plt.savefig(RUTA_BASE / "resultados_sistema_inteligente" / "comparacion_modelos.png", dpi=300)
    plt.close()

    return tabla


# ------------------------------------------------------------
# 7. GUARDAR EL MEJOR MODELO
# ------------------------------------------------------------
def guardar_mejor_modelo(tabla, modelos):

    mejor_nombre = tabla.index[0]   # el de mayor F1-score

    # Guardamos el modelo junto con la informacion para usarlo despues.
    paquete = {
        "modelo": modelos[mejor_nombre],
        "nombre_modelo": mejor_nombre,
        "caracteristicas": CARACTERISTICAS,
        "variable_objetivo": VARIABLE_OBJETIVO,
        "semilla": SEMILLA
    }

    archivo = RUTA_MODELOS / "modelo_emergexia.joblib"
    joblib.dump(paquete, archivo)

    print("\nMEJOR MODELO:", mejor_nombre)
    print("GUARDADO EN:", archivo)
    return archivo


# ------------------------------------------------------------
# 8. RECUPERAR EL MODELO Y CLASIFICAR UNA EMERGENCIA NUEVA
# ------------------------------------------------------------
def probar_modelo_guardado(archivo):

    print("\n" + "=" * 60)
    print("PRUEBA DEL MODELO GUARDADO")
    print("=" * 60)

    paquete = joblib.load(archivo)
    modelo = paquete["modelo"]

    # Emergencia reportada por un usuario desde la app.
    emergencia = pd.DataFrame([{
        "edad": 72,
        "frecuencia_cardiaca": 135,
        "saturacion_oxigeno": 86.0,
        "distancia_km": 8.5
    }], columns=paquete["caracteristicas"])

    prediccion = modelo.predict(emergencia)[0]
    probabilidades = modelo.predict_proba(emergencia)[0]

    print("\nDATOS DE LA EMERGENCIA:")
    print(emergencia.to_string(index=False))

    print("\nRESULTADO:", "EMERGENCIA CRITICA" if prediccion == 1 else "EMERGENCIA NO CRITICA")
    print(f"Probabilidad no critica: {probabilidades[0] * 100:.2f}%")
    print(f"Probabilidad critica:    {probabilidades[1] * 100:.2f}%")
    print("Modelo utilizado:", paquete["nombre_modelo"])


# ------------------------------------------------------------
# 9. PROGRAMA PRINCIPAL
# ------------------------------------------------------------
def main():

    print("\n" + "=" * 60)
    print("EMERGEXIA - ETAPA 2: APRENDIZAJE SUPERVISADO")
    print("=" * 60)

    datos = cargar_datos()
    X_train, X_test, y_train, y_test = preparar_datos(datos)
    resultados, modelos = entrenar_y_evaluar(X_train, X_test, y_train, y_test)
    tabla = comparar_modelos(resultados)
    archivo = guardar_mejor_modelo(tabla, modelos)
    probar_modelo_guardado(archivo)

    print("\n" + "=" * 60)
    print("ETAPA 2 FINALIZADA CORRECTAMENTE")
    print("=" * 60)


if __name__ == "__main__":
    main()
