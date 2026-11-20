# ================================================================
# PROYECTO: EMERGEXIA
# PRACTICA 05: COMPARACION DE ALGORITMOS DE MACHINE LEARNING
#
# Archivo:
# p05_comparacion_algoritmos_emergexia.py
#
# Objetivo:
# Comparar tres algoritmos de clasificacion:
#
# 1. Decision Tree
# 2. Random Forest
# 3. K-Nearest Neighbors (KNN)
#
# Se utilizara un problema de clasificacion binaria:
# 0 = Emergencia NO critica (puede esperar en la cola).
# 1 = Emergencia CRITICA (se asigna ambulancia de inmediato).
#
# 1.- Decision Tree — Arbol de decision
# Construye reglas de decision a partir de los signos vitales
# reportados (por ejemplo: "si la saturacion < 88 ... critica").
#
# 2.- Random Forest — Bosque aleatorio
# Combina multiples arboles de decision para producir una prediccion.
#
# 3.- K-Nearest Neighbors (KNN)
# Clasifica una emergencia considerando las emergencias
# anteriores mas parecidas segun sus caracteristicas.
#
# Caso de estudio
# Emergexia recibe reportes de los usuarios (por mensaje o
# llamada, marcando la ubicacion). Cuando hay varias emergencias
# al mismo tiempo y pocas ambulancias libres en el IMSS 220,
# el Administrador necesita un modulo inteligente que estime
# que emergencias son CRITICAS para atenderlas primero.
#
# Para ello se utilizaran las siguientes variables:
#
# Variable              Descripcion                                Tipo
#
# saturacion_oxigeno    Saturacion de oxigeno SpO2 (%)             Numerica
# frecuencia_cardiaca   Latidos por minuto                         Numerica
# escala_glasgow        Nivel de consciencia (3 = minimo, 15 = normal)  Numerica
# edad                  Edad del paciente en años                  Numerica
# es_critica            0 = No, 1 = Si                             Objetivo
#
# Pregunta: ¿Cual de los tres algoritmos consigue predecir mejor
# si una emergencia es critica cuando trabaja con reportes
# que nunca ha visto?
#
# IMPORTANTE:
# Los datos de esta practica son sinteticos y se utilizan
# exclusivamente con fines educativos. La regla que genera
# la etiqueta NO es un protocolo clinico real de triaje.
# ================================================================


# ================================================================
# 1. IMPORTAR LAS BIBLIOTECAS
# ================================================================

import os

# NumPy permite realizar operaciones matematicas y generar datos.
import numpy as np

# Pandas permite organizar los datos en tablas.
import pandas as pd

# Matplotlib permite crear graficas.
import matplotlib.pyplot as plt

# train_test_split divide los datos en entrenamiento,
# validacion y prueba.
from sklearn.model_selection import train_test_split

# cross_val_score realiza validacion cruzada.
# StratifiedKFold conserva la proporcion de clases.
from sklearn.model_selection import cross_val_score, StratifiedKFold

# DecisionTreeClassifier implementa arboles de decision.
from sklearn.tree import DecisionTreeClassifier

# RandomForestClassifier implementa bosques aleatorios.
from sklearn.ensemble import RandomForestClassifier

# KNeighborsClassifier implementa el algoritmo KNN.
from sklearn.neighbors import KNeighborsClassifier

# StandardScaler normaliza las variables numericas.
from sklearn.preprocessing import StandardScaler

# Pipeline permite unir el escalamiento y el algoritmo.
from sklearn.pipeline import Pipeline

# clone permite crear una copia de un modelo
# conservando su configuracion.
from sklearn.base import clone

# Metricas para evaluar los modelos.
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay
)


# ================================================================
# 2. CONFIGURACION GENERAL
# ================================================================

# Fijamos una semilla para obtener resultados reproducibles.
SEMILLA = 42

# Generador de numeros aleatorios.
rng = np.random.default_rng(SEMILLA)

# Cantidad de reportes de emergencia que vamos a simular.
CANTIDAD_EMERGENCIAS = 500

# Carpeta donde se guardan graficas y tablas.
CARPETA = "resultados_p05_emergexia"
os.makedirs(CARPETA, exist_ok=True)

print("\n==========================================")
print("EMERGEXIA")
print("COMPARACION DE ALGORITMOS - TRIAJE")
print("==========================================")


# ================================================================
# 3. GENERACION DEL CONJUNTO DE DATOS
# ================================================================

# Saturacion de oxigeno: entre 75% y 100%.
saturacion_oxigeno = rng.uniform(
    75,
    100,
    CANTIDAD_EMERGENCIAS
)

# Frecuencia cardiaca: entre 40 y 160 latidos por minuto.
frecuencia_cardiaca = rng.uniform(
    40,
    160,
    CANTIDAD_EMERGENCIAS
)

# Escala de Glasgow: numero entero entre 3 y 15.
escala_glasgow = rng.integers(
    3,
    16,
    CANTIDAD_EMERGENCIAS
)

# Edad del paciente: entre 1 y 95 años.
edad = rng.uniform(
    1,
    95,
    CANTIDAD_EMERGENCIAS
)

# ------------------------------------------------
# Construimos un indicador sintetico de RIESGO.
# ------------------------------------------------

# Cada variable se convierte a una escala aproximada de 0 a 1,
# donde 1 significa "mas riesgo".
#
# - Saturacion: mientras MAS BAJA, mas riesgo.
# - Frecuencia cardiaca: el riesgo aumenta al alejarse de 85
#   (tanto si es muy baja como si es muy alta). Esta relacion
#   NO es lineal, y es interesante ver que algoritmo la capta.
# - Glasgow: mientras MAS BAJO, mas riesgo.
# - Edad: mientras mayor, un poco mas de riesgo.
#
# Ponderaciones:
# Saturacion de oxigeno: 35%
# Frecuencia cardiaca:   25%
# Escala de Glasgow:     30%
# Edad:                  10%

riesgo = (
    ((100 - saturacion_oxigeno) / 25) * 0.35
    +
    (np.abs(frecuencia_cardiaca - 85) / 75) * 0.25
    +
    ((15 - escala_glasgow) / 12) * 0.30
    +
    (edad / 95) * 0.10
)

# Agregamos ruido aleatorio para simular informacion que
# no se captura en el reporte (antecedentes, errores al
# medir, descripcion incompleta del usuario, etc.).
ruido = rng.normal(
    loc=0,
    scale=0.10,
    size=CANTIDAD_EMERGENCIAS
)

# Calculamos el riesgo final.
riesgo_final = riesgo + ruido

# Convertimos el resultado en una variable binaria.
#
# Si el riesgo es igual o superior a 0.50:
# La emergencia es critica (1).
#
# En caso contrario:
# La emergencia no es critica (0).
es_critica = (riesgo_final >= 0.50).astype(int)


# ================================================================
# 4. CONSTRUIR EL DATAFRAME
# ================================================================

df = pd.DataFrame({

    "saturacion_oxigeno": saturacion_oxigeno,

    "frecuencia_cardiaca": frecuencia_cardiaca,

    "escala_glasgow": escala_glasgow,

    "edad": edad,

    "es_critica": es_critica

})

print("\n==========================================")
print("1. DATOS GENERADOS")
print("==========================================")

# Mostramos los primeros diez registros.
print(df.head(10).round(2))

# Mostramos la cantidad de registros.
print("\nCantidad de emergencias:")
print(len(df))

# Mostramos cuantas son criticas y cuantas no.
print("\nDistribucion de resultados (0 = no critica, 1 = critica):")
print(df["es_critica"].value_counts().sort_index())


# ================================================================
# 5. SEPARAR VARIABLES PREDICTORAS Y OBJETIVO
# ================================================================

# X contiene las variables que utilizaran los algoritmos
# para realizar sus predicciones.
COLUMNAS = [
    "saturacion_oxigeno",
    "frecuencia_cardiaca",
    "escala_glasgow",
    "edad"
]

X = df[COLUMNAS]

# y contiene el resultado que queremos predecir.
y = df["es_critica"]


# ================================================================
# 6. DIVIDIR LOS DATOS
# ================================================================

# Primera division:
# 80% para entrenamiento + validacion.
# 20% para prueba.

X_entrenamiento_validacion, X_prueba, \
y_entrenamiento_validacion, y_prueba = train_test_split(

    X,
    y,

    test_size=0.20,

    random_state=SEMILLA,

    # Mantiene una proporcion similar de las clases.
    stratify=y

)

# Segunda division:
# Del 80% restante:
# 75% sera entrenamiento.
# 25% sera validacion.
#
# Resultado total:
# 60% entrenamiento.
# 20% validacion.
# 20% prueba.

X_entrenamiento, X_validacion, \
y_entrenamiento, y_validacion = train_test_split(

    X_entrenamiento_validacion,
    y_entrenamiento_validacion,

    test_size=0.25,

    random_state=SEMILLA,

    stratify=y_entrenamiento_validacion

)

print("\n==========================================")
print("2. DISTRIBUCION DE LOS CONJUNTOS")
print("==========================================")

print("Entrenamiento:", len(X_entrenamiento))
print("Validacion:", len(X_validacion))
print("Prueba:", len(X_prueba))


# ================================================================
# 7. DEFINIR LOS ALGORITMOS
# ================================================================

# Funciones que construyen cada modelo. Asi podemos reutilizarlas
# en los experimentos cambiando solo un hiperparametro.

def crear_arbol(max_depth=5):
    return DecisionTreeClassifier(

        # Limita el crecimiento del arbol.
        max_depth=max_depth,

        # Evita crear hojas con muy pocos registros.
        min_samples_leaf=4,

        # Semilla para reproducibilidad.
        random_state=SEMILLA
    )


def crear_bosque(n_estimators=200):
    return RandomForestClassifier(

        # Cantidad de arboles que formaran el bosque.
        n_estimators=n_estimators,

        # Sin limite de profundidad en cada arbol.
        max_depth=None,

        # Cantidad minima de registros por hoja.
        min_samples_leaf=2,

        # Permite utilizar todos los nucleos disponibles.
        n_jobs=-1,

        random_state=SEMILLA
    )


def crear_knn(n_neighbors=7):
    # KNN necesita datos en escalas comparables:
    # la frecuencia cardiaca (40-160) dominaria a Glasgow (3-15)
    # si no se normalizan. Por eso utilizamos Pipeline.
    #
    # Primero se normalizan los datos.
    # Despues se ejecuta KNN.
    #
    # El escalamiento se aprende durante el entrenamiento,
    # evitando utilizar informacion de validacion o prueba.
    return Pipeline([

        (
            "escalador",
            StandardScaler()
        ),

        (
            "clasificador",
            KNeighborsClassifier(

                # Cantidad de vecinos que se consultaran.
                n_neighbors=n_neighbors,

                # Los vecinos cercanos tienen mayor peso.
                weights="distance"
            )
        )

    ])


# Diccionario con los modelos base.
modelos = {

    "Decision Tree": crear_arbol(),

    "Random Forest": crear_bosque(),

    "KNN": crear_knn()

}


# ================================================================
# 8. FUNCION DE EVALUACION
# ================================================================

def evaluar(modelo, X_eval, y_eval):
    """Devuelve las cuatro metricas de un modelo ya entrenado."""

    predicciones = modelo.predict(X_eval)

    return {
        "exactitud": accuracy_score(y_eval, predicciones),
        "precision": precision_score(y_eval, predicciones, zero_division=0),
        "recall": recall_score(y_eval, predicciones, zero_division=0),
        "f1_score": f1_score(y_eval, predicciones, zero_division=0)
    }


FORMATO = {
    "exactitud": "{:.2%}".format,
    "precision": "{:.2%}".format,
    "recall": "{:.2%}".format,
    "f1_score": "{:.2%}".format
}


# ================================================================
# 9. ENTRENAMIENTO Y COMPARACION
# ================================================================

# Aqui almacenaremos los resultados de cada algoritmo.
resultados = []

# Aqui almacenaremos los modelos ya entrenados.
modelos_entrenados = {}

print("\n==========================================")
print("3. ENTRENAMIENTO DE LOS ALGORITMOS")
print("==========================================")

for nombre, modelo in modelos.items():

    print("\n--------------------------------------")
    print("Entrenando:", nombre)
    print("--------------------------------------")

    # Entrenamos el algoritmo utilizando exclusivamente
    # el conjunto de entrenamiento.
    modelo.fit(
        X_entrenamiento,
        y_entrenamiento
    )

    # Guardamos el modelo entrenado.
    modelos_entrenados[nombre] = modelo

    # Evaluamos con los datos de validacion.
    metricas_modelo = evaluar(modelo, X_validacion, y_validacion)

    resultados.append({"algoritmo": nombre, **metricas_modelo})

    print("Exactitud:", f"{metricas_modelo['exactitud']:.2%}")
    print("Precision:", f"{metricas_modelo['precision']:.2%}")
    print("Recall:", f"{metricas_modelo['recall']:.2%}")
    print("F1-score:", f"{metricas_modelo['f1_score']:.2%}")


# ================================================================
# 10. TABLA COMPARATIVA
# ================================================================

df_resultados = pd.DataFrame(resultados)

# Ordenamos los algoritmos por su F1-score.
# F1 equilibra precision y recall: en triaje nos importa
# no dejar pasar emergencias criticas (recall) sin saturar
# la cola de "falsas criticas" (precision).
df_resultados = df_resultados.sort_values(
    by="f1_score",
    ascending=False
).reset_index(drop=True)

print("\n==========================================")
print("4. COMPARACION DE ALGORITMOS (VALIDACION)")
print("==========================================")

print(df_resultados.to_string(index=False, formatters=FORMATO))


# ================================================================
# 11. SELECCIONAR EL MEJOR MODELO
# ================================================================

mejor_registro = df_resultados.iloc[0]

mejor_nombre = mejor_registro["algoritmo"]

mejor_modelo = modelos_entrenados[mejor_nombre]

print("\n==========================================")
print("5. MODELO SELECCIONADO")
print("==========================================")

print("Algoritmo:", mejor_nombre)

print(
    "F1-score de validacion:",
    f"{mejor_registro['f1_score']:.2%}"
)

print("Criterio de seleccion: mayor F1-score")


# ================================================================
# 12. REENTRENAR CON ENTRENAMIENTO + VALIDACION
# ================================================================

# Una vez seleccionado el algoritmo, aprovechamos
# los datos de entrenamiento y de validacion.
#
# El conjunto de prueba permanece separado y sin utilizar.

X_entrenamiento_final = pd.concat([X_entrenamiento, X_validacion])

y_entrenamiento_final = pd.concat([y_entrenamiento, y_validacion])

# Creamos una copia independiente del modelo seleccionado.
modelo_final = clone(modelos[mejor_nombre])

# Entrenamos el modelo final con el 80% de los datos.
modelo_final.fit(X_entrenamiento_final, y_entrenamiento_final)


# ================================================================
# 13. EVALUACION FINAL CON DATOS DE PRUEBA
# ================================================================

# El conjunto de prueba se utiliza hasta este momento.
predicciones_finales = modelo_final.predict(X_prueba)

metricas_finales = evaluar(modelo_final, X_prueba, y_prueba)

f1_final = metricas_finales["f1_score"]

print("\n==========================================")
print("6. EVALUACION FINAL (PRUEBA)")
print("==========================================")

print("Algoritmo:", mejor_nombre)
print("Exactitud:", f"{metricas_finales['exactitud']:.2%}")
print("Precision:", f"{metricas_finales['precision']:.2%}")
print("Recall:", f"{metricas_finales['recall']:.2%}")
print("F1-score:", f"{f1_final:.2%}")


# ================================================================
# 14. REPORTE DE CLASIFICACION
# ================================================================

print("\n==========================================")
print("7. REPORTE DE CLASIFICACION")
print("==========================================")

print(
    classification_report(
        y_prueba,
        predicciones_finales,
        labels=[0, 1],
        target_names=["No critica", "Critica"],
        zero_division=0
    )
)


# ================================================================
# 15. MATRIZ DE CONFUSION
# ================================================================

matriz = confusion_matrix(
    y_prueba,
    predicciones_finales,
    labels=[0, 1]
)

print("\n==========================================")
print("8. MATRIZ DE CONFUSION")
print("==========================================")

print(matriz)

vn, fp, fn, vp = matriz.ravel()

print("\nVerdaderos negativos (no critica y no lo era):", vn)
print("Falsos positivos (dijo critica y no lo era):", fp)
print("Falsos negativos (dijo NO critica y SI lo era):", fn)
print("Verdaderos positivos (critica y si lo era):", vp)

# En Emergexia el falso negativo es el error mas grave:
# una emergencia critica se quedaria esperando en la cola.


# ================================================================
# 16. VALIDACION CRUZADA DEL MODELO SELECCIONADO
# ================================================================

# Utilizamos los datos de entrenamiento y validacion.
# El conjunto de prueba sigue sin participar.

particiones = StratifiedKFold(
    n_splits=5,
    shuffle=True,
    random_state=SEMILLA
)

resultados_cv = cross_val_score(
    clone(modelos[mejor_nombre]),
    X_entrenamiento_final,
    y_entrenamiento_final,
    cv=particiones,
    scoring="f1",
    n_jobs=-1
)

print("\n==========================================")
print("9. VALIDACION CRUZADA")
print("==========================================")

print("Resultados por particion:")
print(resultados_cv)
print("Promedio F1:", f"{resultados_cv.mean():.2%}")
print("Desviacion estandar:", f"{resultados_cv.std():.2%}")


# ================================================================
# 17. GRAFICA COMPARATIVA DE METRICAS
# ================================================================

metricas = ["exactitud", "precision", "recall", "f1_score"]

plt.figure(figsize=(12, 6))

ancho = 0.22

posiciones = np.arange(len(df_resultados))

for i, metrica in enumerate(metricas):

    desplazamiento = (i - 1.5) * ancho

    plt.bar(
        posiciones + desplazamiento,
        df_resultados[metrica],
        width=ancho,
        label=metrica.replace("_", " ").title()
    )

plt.xticks(posiciones, df_resultados["algoritmo"])
plt.ylim(0, 1.05)
plt.ylabel("Resultado")
plt.xlabel("Algoritmo")
plt.title("Emergexia - Comparacion de algoritmos de triaje (validacion)")
plt.legend()
plt.grid(axis="y", alpha=0.3)
plt.tight_layout()

plt.savefig(f"{CARPETA}/p05_comparacion_algoritmos.png", dpi=300)

plt.show()


# ================================================================
# 18. GRAFICA DE LA MATRIZ DE CONFUSION
# ================================================================

visualizacion = ConfusionMatrixDisplay(
    confusion_matrix=matriz,
    display_labels=["No critica", "Critica"]
)

visualizacion.plot(cmap="Blues", values_format="d")

plt.title("Matriz de confusion - " + mejor_nombre)
plt.tight_layout()

plt.savefig(f"{CARPETA}/p05_matriz_confusion.png", dpi=300)

plt.show()


# ================================================================
# 19. EJEMPLO DE USO EN EMERGEXIA
# ================================================================

# Tres reportes que llegan al mismo tiempo. El modelo estima
# la probabilidad de que cada uno sea critico y el Administrador
# puede ordenar la cola de atencion.

nuevos_reportes = pd.DataFrame([
    {"saturacion_oxigeno": 97, "frecuencia_cardiaca": 88,  "escala_glasgow": 15, "edad": 30},
    {"saturacion_oxigeno": 84, "frecuencia_cardiaca": 132, "escala_glasgow": 10, "edad": 71},
    {"saturacion_oxigeno": 92, "frecuencia_cardiaca": 50,  "escala_glasgow": 13, "edad": 55},
], index=["Reporte A", "Reporte B", "Reporte C"])

probabilidad = modelo_final.predict_proba(nuevos_reportes)[:, 1]

nuevos_reportes["prob_critica"] = probabilidad
nuevos_reportes["prioridad"] = np.where(
    probabilidad >= 0.5, "CRITICA", "No critica"
)

print("\n==========================================")
print("10. EJEMPLO: COLA DE EMERGENCIAS")
print("==========================================")

print(
    nuevos_reportes
    .sort_values("prob_critica", ascending=False)
    .to_string(formatters={"prob_critica": "{:.0%}".format})
)


# ================================================================
# 20. GUARDAR LOS RESULTADOS
# ================================================================

df_resultados.to_csv(
    f"{CARPETA}/p05_resultados_comparacion.csv",
    index=False,
    encoding="utf-8"
)


# ================================================================
# 21. ACTIVIDAD DE MODIFICACION: EXPERIMENTOS A, B y C
# ================================================================

# En cada experimento se cambia UN solo hiperparametro,
# se entrena con el conjunto de entrenamiento y se mide
# con el de validacion (la prueba no se toca).
#
# - Experimento A: n_neighbors de KNN = 3, 5, 7, 9, 15.
# - Experimento B: n_estimators de Random Forest = 50, 100, 200, 500.
# - Experimento C: max_depth de Decision Tree = 2, 3, 5, 8, None.
#
# Tambien se registra la exactitud de entrenamiento para
# observar si hay sobreajuste (brecha entrenamiento - validacion).

experimentos = [
    ("A", "KNN", "n_neighbors", [3, 5, 7, 9, 15], crear_knn),
    ("B", "Random Forest", "n_estimators", [50, 100, 200, 500], crear_bosque),
    ("C", "Decision Tree", "max_depth", [2, 3, 5, 8, None], crear_arbol),
]

registros_experimentos = []

print("\n==========================================")
print("11. EXPERIMENTOS DE MODIFICACION")
print("==========================================")

for clave, algoritmo, parametro, valores, constructor in experimentos:

    filas = []

    for valor in valores:

        modelo_exp = constructor(valor)

        modelo_exp.fit(X_entrenamiento, y_entrenamiento)

        exactitud_entrenamiento = accuracy_score(
            y_entrenamiento,
            modelo_exp.predict(X_entrenamiento)
        )

        metricas_exp = evaluar(modelo_exp, X_validacion, y_validacion)

        fila = {
            "experimento": clave,
            "algoritmo": algoritmo,
            "parametro": parametro,
            "valor": "None" if valor is None else str(valor),
            "exactitud_entrenamiento": exactitud_entrenamiento,
            **metricas_exp
        }

        filas.append(fila)
        registros_experimentos.append(fila)

    tabla = pd.DataFrame(filas)

    print(f"\nExperimento {clave}: {algoritmo} variando {parametro}")

    print(
        tabla[
            ["valor", "exactitud_entrenamiento", "exactitud",
             "precision", "recall", "f1_score"]
        ].to_string(
            index=False,
            formatters={"exactitud_entrenamiento": "{:.2%}".format, **FORMATO}
        )
    )

    mejor_valor = tabla.loc[tabla["f1_score"].idxmax(), "valor"]

    print(f"Mejor {parametro} segun F1 de validacion: {mejor_valor}")

df_experimentos = pd.DataFrame(registros_experimentos)

df_experimentos.to_csv(
    f"{CARPETA}/p05_experimentos.csv",
    index=False,
    encoding="utf-8"
)

# Grafica: F1 de validacion en cada experimento.
figura, ejes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)

for eje, (clave, algoritmo, parametro, valores, _) in zip(ejes, experimentos):

    datos = df_experimentos[df_experimentos["experimento"] == clave]

    eje.plot(datos["valor"], datos["exactitud_entrenamiento"],
             marker="o", label="Exactitud entrenamiento")
    eje.plot(datos["valor"], datos["f1_score"],
             marker="s", label="F1 validacion")

    eje.set_title(f"Exp. {clave}: {algoritmo}")
    eje.set_xlabel(parametro)
    eje.grid(alpha=0.3)

ejes[0].set_ylabel("Resultado")
ejes[0].set_ylim(0.5, 1.02)
ejes[0].legend(loc="lower left")

plt.tight_layout()

plt.savefig(f"{CARPETA}/p05_experimentos.png", dpi=300)

plt.show()


print("\n==========================================")
print("12. ARCHIVOS GENERADOS")
print("==========================================")

print(f"{CARPETA}/p05_comparacion_algoritmos.png")
print(f"{CARPETA}/p05_matriz_confusion.png")
print(f"{CARPETA}/p05_resultados_comparacion.csv")
print(f"{CARPETA}/p05_experimentos.csv")
print(f"{CARPETA}/p05_experimentos.png")


# ================================================================
# 22. CONCLUSION DEL SISTEMA
# ================================================================

print("\n==========================================")
print("CONCLUSION")
print("==========================================")

print("El algoritmo seleccionado fue:", mejor_nombre)

print("Su F1-score final fue:", f"{f1_final:.2%}")

print(
    "\nEmergexia ha completado la comparacion"
    " de algoritmos de clasificacion para triaje."
)

print(
    "Recuerda: el mejor algoritmo depende de los datos,"
    " del problema y de la metrica que se desea optimizar."
)

print("\nPROCESO FINALIZADO.")


# ================================================================
# RESULTADOS OBTENIDOS (SEMILLA = 42)
# ================================================================
#
# Comparacion en validacion:
#
# Algoritmo        Exactitud  Precision  Recall   F1
# Random Forest     75.00%     71.43%    76.09%   73.68%
# Decision Tree     75.00%     75.61%    67.39%   71.26%
# KNN               73.00%     71.11%    69.57%   70.33%
#
# Seleccionado: Random Forest. En prueba: exactitud 77%,
# precision 76.09%, recall 74.47%, F1 75.27%.
# Validacion cruzada (F1): 79.56% ± 4.32%.
#
# Matriz de confusion (prueba):
#   [[42 11]
#    [12 35]]
# 12 emergencias criticas fueron clasificadas como NO criticas
# (falsos negativos). En un sistema real este es el error mas
# grave, porque esas personas quedarian esperando en la cola.
# Para reducirlo se podria bajar el umbral de probabilidad
# (por ejemplo, marcar critica desde 0.35 en vez de 0.50),
# aceptando mas falsas alarmas.
#
# Experimento A (KNN, n_neighbors):
#   3 -> 73.68 | 5 -> 71.74 | 7 -> 70.33 | 9 -> 73.12 | 15 -> 73.12 (F1)
#   El F1 sube y baja sin una tendencia clara (diferencias de 1-3
#   puntos con solo 100 registros de validacion). La exactitud de
#   entrenamiento es 100% en todos los casos porque weights="distance"
#   hace que cada punto de entrenamiento "se vote a si mismo";
#   por eso aqui esa cifra no sirve para medir sobreajuste.
#
# Experimento B (Random Forest, n_estimators):
#   50 -> 74.23 | 100 -> 71.58 | 200 -> 73.68 | 500 -> 74.23 (F1)
#   Agregar arboles casi no cambia el resultado: a partir de unos
#   50 arboles el bosque ya es estable. Usar 500 solo aumenta el
#   tiempo de entrenamiento sin mejorar de forma clara.
#
# Experimento C (Decision Tree, max_depth):
#   2 -> 62.37 | 3 -> 68.18 | 5 -> 71.26 | 8 -> 71.11 | None -> 71.11 (F1)
#   Es el experimento con el efecto mas claro: con profundidad 2
#   hay subajuste (el arbol no capta la relacion en forma de "U"
#   de la frecuencia cardiaca). A partir de 5 ya no mejora.
#   8 y None dan lo mismo porque min_samples_leaf=4 detiene el
#   crecimiento del arbol antes de llegar a profundidad 8.
#
# Conclusion general: con estos datos Random Forest fue el mejor,
# pero la ventaja sobre el arbol y KNN es pequeña (2-3 puntos de F1)
# y podria cambiar con otra semilla. No se debe asumir que un
# algoritmo siempre sera superior.