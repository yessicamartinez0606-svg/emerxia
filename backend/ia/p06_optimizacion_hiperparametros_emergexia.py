# ================================================================
# PROYECTO: EMERGEXIA
# PRACTICA 06: OPTIMIZACION DE HIPERPARAMETROS
#
# Archivo:
# p06_optimizacion_hiperparametros_emergexia.py
#
# Objetivo:
# En la practica 05 comparamos Decision Tree, Random Forest y KNN
# para el TRIAJE de Emergexia (¿la emergencia es CRITICA?), pero
# cada algoritmo uso una configuracion fija elegida "a mano".
#
# Ahora probamos MUCHAS configuraciones de cada algoritmo para
# encontrar la que consigue el mejor F1-score, usando:
#
# 1. GridSearchCV:       prueba TODAS las combinaciones de una lista.
# 2. RandomizedSearchCV: prueba solo n_iter combinaciones al azar.
# 3. StratifiedKFold:    validacion cruzada de 5 particiones que
#                        conserva la proporcion de criticas.
#
# Conceptos
#
# Parametros:       valores que el algoritmo aprende al entrenar
#                   (por ejemplo, las preguntas de un arbol).
# Hiperparametros:  valores que configuramos ANTES de entrenar
#                   para controlar como aprende (max_depth, etc.).
# Optimizacion:     buscar la configuracion con mejores resultados.
# Validacion cruzada: evaluar con diferentes particiones de los datos.
#
# Que se va a optimizar
#
# Decision Tree
# - max_depth:         cuantos niveles de preguntas puede hacer.
# - min_samples_split: registros minimos de un nodo para dividirse.
#                      Ej.: con 10, un grupo de 8 reportes ya no se divide.
# - min_samples_leaf:  registros minimos en cada hoja (decision final).
# - criterion:         gini (impureza) o entropy (incertidumbre).
#                      Un grupo es "puro" si todos sus reportes son
#                      criticos (o todos no criticos).
#
# Random Forest (votacion de muchos arboles)
# - n_estimators:      cuantos arboles forman el bosque.
#                      Ej.: 75 de 100 arboles dicen "critica" -> critica.
# - max_depth, min_samples_split, min_samples_leaf: igual que el arbol,
#                      pero aplicados a cada arbol del bosque.
#
# KNN (vecinos mas cercanos)
# - n_neighbors:       cuantos reportes parecidos se consultan.
#                      Ej.: con 5 vecinos, si 4 fueron criticos -> critica.
# - weights:           uniform (todos valen igual) o distance
#                      (los mas parecidos pesan mas).
# - metric:            euclidean (linea recta) o manhattan
#                      (suma de diferencias).
#
# Problema (mismo de la practica 05):
# 0 = Emergencia NO critica (puede esperar en la cola).
# 1 = Emergencia CRITICA (ambulancia de inmediato).
#
# Variables: saturacion_oxigeno, frecuencia_cardiaca,
#            escala_glasgow, edad.
#
# IMPORTANTE:
# Los datos son sinteticos y con fines educativos. La regla que
# genera la etiqueta NO es un protocolo clinico real de triaje.
# ================================================================


# ================================================================
# 1. IMPORTAR BIBLIOTECAS
# ================================================================

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.model_selection import GridSearchCV
from sklearn.model_selection import RandomizedSearchCV
from sklearn.model_selection import StratifiedKFold

from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.neighbors import KNeighborsClassifier

from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay
)

# Distribuciones para la busqueda aleatoria.
from scipy.stats import randint

# Mostrar todas las columnas al imprimir tablas.
pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 10)


# ================================================================
# 2. CONFIGURACION GENERAL
# ================================================================

SEMILLA = 42

rng = np.random.default_rng(SEMILLA)

CANTIDAD_EMERGENCIAS = 500

print("\n==========================================")
print("EMERGEXIA")
print("OPTIMIZACION DE HIPERPARAMETROS - TRIAJE")
print("==========================================")


# ================================================================
# 3. GENERAR DATOS SINTETICOS (los mismos de la practica 05)
# ================================================================

saturacion_oxigeno = rng.uniform(75, 100, CANTIDAD_EMERGENCIAS)

frecuencia_cardiaca = rng.uniform(40, 160, CANTIDAD_EMERGENCIAS)

escala_glasgow = rng.integers(3, 16, CANTIDAD_EMERGENCIAS)

edad = rng.uniform(1, 95, CANTIDAD_EMERGENCIAS)

# Indicador sintetico de riesgo (0 a 1 aprox.).
riesgo = (
    ((100 - saturacion_oxigeno) / 25) * 0.35
    +
    (np.abs(frecuencia_cardiaca - 85) / 75) * 0.25
    +
    ((15 - escala_glasgow) / 12) * 0.30
    +
    (edad / 95) * 0.10
)

# Ruido: informacion que no viene en el reporte.
ruido = rng.normal(0, 0.10, CANTIDAD_EMERGENCIAS)

es_critica = ((riesgo + ruido) >= 0.50).astype(int)


# ================================================================
# 4. CREAR DATAFRAME
# ================================================================

df = pd.DataFrame({
    "saturacion_oxigeno": saturacion_oxigeno,
    "frecuencia_cardiaca": frecuencia_cardiaca,
    "escala_glasgow": escala_glasgow,
    "edad": edad,
    "es_critica": es_critica
})

print("\n1. DATOS GENERADOS")
print(df.head().round(2))

print("\nDistribucion de clases (0 = no critica, 1 = critica):")
print(df["es_critica"].value_counts().sort_index())


# ================================================================
# 5. SEPARAR VARIABLES
# ================================================================

COLUMNAS = [
    "saturacion_oxigeno",
    "frecuencia_cardiaca",
    "escala_glasgow",
    "edad"
]

X = df[COLUMNAS]

y = df["es_critica"]


# ================================================================
# 6. DIVIDIR DATOS EN ENTRENAMIENTO Y PRUEBA
# ================================================================

# 20 % se guarda para la evaluacion final.
# El 80 % restante se usa para optimizar con validacion cruzada
# (por eso ya no hace falta un conjunto de validacion aparte:
# la validacion cruzada cumple ese papel).

X_entrenamiento, X_prueba, y_entrenamiento, y_prueba = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=SEMILLA,
    stratify=y
)

print("\n2. DISTRIBUCION DE DATOS")
print("Entrenamiento:", len(X_entrenamiento))
print("Prueba:", len(X_prueba))


# ================================================================
# 7. CONFIGURAR VALIDACION CRUZADA
# ================================================================

validacion_cruzada = StratifiedKFold(
    n_splits=5,
    shuffle=True,
    random_state=SEMILLA
)


# ================================================================
# 8. DEFINIR LOS ALGORITMOS Y SUS HIPERPARAMETROS
# ================================================================

# ------------------------------------------------
# MODELO 1: DECISION TREE
# ------------------------------------------------

modelo_arbol = DecisionTreeClassifier(random_state=SEMILLA)

parametros_arbol = {
    "max_depth": [2, 3, 5, 8, 10, None],
    "min_samples_split": [2, 5, 10],
    "min_samples_leaf": [1, 2, 4],
    "criterion": ["gini", "entropy"]
}

# ------------------------------------------------
# MODELO 2: RANDOM FOREST
# ------------------------------------------------

modelo_bosque = RandomForestClassifier(random_state=SEMILLA, n_jobs=-1)

parametros_bosque = {
    "n_estimators": [50, 100, 200],
    "max_depth": [3, 5, 8, None],
    "min_samples_split": [2, 5, 10],
    "min_samples_leaf": [1, 2, 4]
}

# ------------------------------------------------
# MODELO 3: KNN (con escalado dentro de un Pipeline)
# ------------------------------------------------

# Sin escalar, la frecuencia cardiaca (40-160) dominaria a
# Glasgow (3-15). El escalador se ajusta solo con los datos de
# entrenamiento de cada particion (evita fuga de informacion).

modelo_knn = Pipeline([
    ("escalador", StandardScaler()),
    ("clasificador", KNeighborsClassifier())
])

# Formato de los parametros de un Pipeline: nombre_paso__parametro
parametros_knn = {
    "clasificador__n_neighbors": [3, 5, 7, 9, 11, 15],
    "clasificador__weights": ["uniform", "distance"],
    "clasificador__metric": ["euclidean", "manhattan"]
}


# ================================================================
# 9. ORGANIZAR LOS MODELOS
# ================================================================

modelos = {
    "Decision Tree": (modelo_arbol, parametros_arbol),
    "Random Forest": (modelo_bosque, parametros_bosque),
    "KNN": (modelo_knn, parametros_knn)
}


# ================================================================
# 10. EJECUTAR GRIDSEARCHCV
# ================================================================

resultados_grid = []
mejores_modelos_grid = {}

print("\n==========================================")
print("3. OPTIMIZACION CON GRIDSEARCHCV")
print("==========================================")

for nombre, (modelo, parametros) in modelos.items():

    print("\n--------------------------------------")
    print("Optimizando:", nombre)
    print("--------------------------------------")

    busqueda = GridSearchCV(
        estimator=modelo,
        param_grid=parametros,
        # En triaje usamos F1: equilibra no dejar pasar criticas
        # (recall) sin llenar la cola de falsas alarmas (precision).
        scoring="f1",
        cv=validacion_cruzada,
        n_jobs=-1,
        return_train_score=True,
        verbose=0
    )

    busqueda.fit(X_entrenamiento, y_entrenamiento)

    mejores_modelos_grid[nombre] = busqueda.best_estimator_

    print("Mejor F1-score:", f"{busqueda.best_score_:.2%}")
    print("\nMejores hiperparametros:")
    print(busqueda.best_params_)

    resultados_grid.append({
        "algoritmo": nombre,
        "mejor_f1": busqueda.best_score_,
        "hiperparametros": str(busqueda.best_params_),
        "combinaciones": len(busqueda.cv_results_["params"])
    })


# ================================================================
# 11. COMPARACION DE RESULTADOS GRIDSEARCHCV
# ================================================================

df_grid = pd.DataFrame(resultados_grid)

print("\n==========================================")
print("4. RESULTADOS GRIDSEARCHCV")
print("==========================================")

print(
    df_grid[["algoritmo", "mejor_f1", "combinaciones"]].to_string(
        index=False,
        formatters={"mejor_f1": "{:.2%}".format}
    )
)


# ================================================================
# 12. RANDOMIZEDSEARCHCV
# ================================================================

# No prueba todas las combinaciones: elige 20 al azar.
# Sirve cuando el espacio de busqueda es muy grande.

resultados_random = []
mejores_modelos_random = {}

print("\n==========================================")
print("5. OPTIMIZACION CON RANDOMIZEDSEARCHCV")
print("==========================================")

parametros_random = {

    "Decision Tree": {
        "max_depth": randint(2, 15),
        "min_samples_split": randint(2, 15),
        "min_samples_leaf": randint(1, 8),
        "criterion": ["gini", "entropy"]
    },

    "Random Forest": {
        "n_estimators": randint(50, 301),
        "max_depth": [3, 5, 8, 12, None],
        "min_samples_split": randint(2, 12),
        "min_samples_leaf": randint(1, 6)
    },

    "KNN": {
        "clasificador__n_neighbors": [3, 5, 7, 9, 11, 15, 19],
        "clasificador__weights": ["uniform", "distance"],
        "clasificador__metric": ["euclidean", "manhattan"]
    }

}

for nombre, (modelo, _) in modelos.items():

    print("\n--------------------------------------")
    print("Optimizando aleatoriamente:", nombre)
    print("--------------------------------------")

    busqueda_random = RandomizedSearchCV(
        estimator=modelo,
        param_distributions=parametros_random[nombre],
        n_iter=20,
        scoring="f1",
        cv=validacion_cruzada,
        n_jobs=-1,
        random_state=SEMILLA,
        verbose=0
    )

    busqueda_random.fit(X_entrenamiento, y_entrenamiento)

    mejores_modelos_random[nombre] = busqueda_random.best_estimator_

    print("Mejor F1-score:", f"{busqueda_random.best_score_:.2%}")
    print("\nMejores hiperparametros:")
    print(busqueda_random.best_params_)

    resultados_random.append({
        "algoritmo": nombre,
        "mejor_f1": busqueda_random.best_score_,
        "hiperparametros": str(busqueda_random.best_params_)
    })


# ================================================================
# 13. COMPARAR GRIDSEARCH Y RANDOMIZEDSEARCH
# ================================================================

df_random = pd.DataFrame(resultados_random)

print("\n==========================================")
print("6. COMPARACION DE METODOS DE OPTIMIZACION")
print("==========================================")

comparacion = pd.merge(
    df_grid[["algoritmo", "mejor_f1"]].rename(columns={"mejor_f1": "gridsearch"}),
    df_random[["algoritmo", "mejor_f1"]].rename(columns={"mejor_f1": "randomizedsearch"}),
    on="algoritmo"
)

print(
    comparacion.to_string(
        index=False,
        formatters={
            "gridsearch": "{:.2%}".format,
            "randomizedsearch": "{:.2%}".format
        }
    )
)


# ================================================================
# 14. SELECCIONAR EL MEJOR ALGORITMO
# ================================================================

mejor_indice = df_grid["mejor_f1"].idxmax()

mejor_nombre = df_grid.loc[mejor_indice, "algoritmo"]

mejor_modelo = mejores_modelos_grid[mejor_nombre]

print("\n==========================================")
print("7. MEJOR MODELO OPTIMIZADO")
print("==========================================")

print("Algoritmo:", mejor_nombre)
print("F1-score en validacion cruzada:", f"{df_grid.loc[mejor_indice, 'mejor_f1']:.2%}")
print("\nConfiguracion seleccionada:")
print(df_grid.loc[mejor_indice, "hiperparametros"])


# ================================================================
# 15. EVALUACION FINAL CON PRUEBA
# ================================================================

# El conjunto de prueba NO participo en la optimizacion.

predicciones = mejor_modelo.predict(X_prueba)

accuracy = accuracy_score(y_prueba, predicciones)
precision = precision_score(y_prueba, predicciones, zero_division=0)
recall = recall_score(y_prueba, predicciones, zero_division=0)
f1 = f1_score(y_prueba, predicciones, zero_division=0)

print("\n==========================================")
print("8. EVALUACION CON DATOS DE PRUEBA")
print("==========================================")

print("Accuracy:", f"{accuracy:.2%}")
print("Precision:", f"{precision:.2%}")
print("Recall:", f"{recall:.2%}")
print("F1-score:", f"{f1:.2%}")


# ================================================================
# 16. REPORTE DE CLASIFICACION
# ================================================================

print("\n==========================================")
print("9. REPORTE DE CLASIFICACION")
print("==========================================")

print(
    classification_report(
        y_prueba,
        predicciones,
        labels=[0, 1],
        target_names=["No critica", "Critica"],
        zero_division=0
    )
)


# ================================================================
# 17. MATRIZ DE CONFUSION
# ================================================================

matriz = confusion_matrix(y_prueba, predicciones, labels=[0, 1])

print("\n==========================================")
print("10. MATRIZ DE CONFUSION")
print("==========================================")

print(matriz)

vn, fp, fn, vp = matriz.ravel()
print("\nFalsos negativos (dijo NO critica y SI lo era):", fn)
print("En triaje es el error mas grave: la persona espera en la cola.")

visualizacion = ConfusionMatrixDisplay(
    confusion_matrix=matriz,
    display_labels=["No critica", "Critica"]
)

visualizacion.plot(cmap="Blues", values_format="d")
plt.title("Matriz de confusion - " + mejor_nombre + " optimizado")
plt.tight_layout()
plt.savefig("p06_matriz_confusion.png", dpi=300)
plt.show()


# ================================================================
# 18. GRAFICA COMPARATIVA DE OPTIMIZACION
# ================================================================

posiciones = np.arange(len(comparacion))
ancho = 0.35

plt.figure(figsize=(10, 6))
plt.bar(posiciones - ancho / 2, comparacion["gridsearch"], width=ancho, label="GridSearchCV")
plt.bar(posiciones + ancho / 2, comparacion["randomizedsearch"], width=ancho, label="RandomizedSearchCV")
plt.xticks(posiciones, comparacion["algoritmo"])
plt.ylim(0, 1.05)
plt.ylabel("F1-score (validacion cruzada)")
plt.xlabel("Algoritmo")
plt.title("Emergexia - Comparacion de metodos de optimizacion (triaje)")
plt.legend()
plt.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig("p06_comparacion_optimizacion.png", dpi=300)
plt.show()


# ================================================================
# 19. EXPORTAR RESULTADOS
# ================================================================

df_grid.to_csv("p06_resultados_gridsearch.csv", index=False, encoding="utf-8")
df_random.to_csv("p06_resultados_randomizedsearch.csv", index=False, encoding="utf-8")
comparacion.to_csv("p06_comparacion_metodos.csv", index=False, encoding="utf-8")


# ================================================================
# 20. EJEMPLO DE USO EN EMERGEXIA
# ================================================================

# Los mismos tres reportes de la practica 05, ahora con el
# modelo optimizado.

nuevos_reportes = pd.DataFrame([
    {"saturacion_oxigeno": 97, "frecuencia_cardiaca": 88,  "escala_glasgow": 15, "edad": 30},
    {"saturacion_oxigeno": 84, "frecuencia_cardiaca": 132, "escala_glasgow": 10, "edad": 71},
    {"saturacion_oxigeno": 92, "frecuencia_cardiaca": 50,  "escala_glasgow": 13, "edad": 55},
], index=["Reporte A", "Reporte B", "Reporte C"])

nuevos_reportes["prob_critica"] = mejor_modelo.predict_proba(nuevos_reportes[COLUMNAS])[:, 1]
nuevos_reportes["prioridad"] = np.where(nuevos_reportes["prob_critica"] >= 0.5, "CRITICA", "No critica")

print("\n==========================================")
print("11. EJEMPLO: COLA DE EMERGENCIAS")
print("==========================================")

print(
    nuevos_reportes.sort_values("prob_critica", ascending=False)
    .to_string(formatters={"prob_critica": "{:.0%}".format})
)


# ================================================================
# 21. CONCLUSION
# ================================================================

print("\n==========================================")
print("CONCLUSION")
print("==========================================")

print("Mejor algoritmo:", mejor_nombre)
print("F1-score final (prueba):", f"{f1:.2%}")

print("\nArchivos generados:")
print("p06_matriz_confusion.png")
print("p06_comparacion_optimizacion.png")
print("p06_resultados_gridsearch.csv")
print("p06_resultados_randomizedsearch.csv")
print("p06_comparacion_metodos.csv")

print("\nPRACTICA 06 (EMERGEXIA) FINALIZADA.")
