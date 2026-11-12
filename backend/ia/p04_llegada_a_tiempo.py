# ============================================================
# FUNDAMENTOS DE INTELIGENCIA ARTIFICIAL
# PRACTICA 04:
# ENTRENAMIENTO, VALIDACION Y PRUEBA
# ============================================================
#
# CASO DE ESTUDIO: EMERGEXIA
# Emergexia es un sistema de gestion medica y de emergencias.
# Las ambulancias salen del Hospital IMSS 220 (Paseo Tollocan,
# Toluca) y regresan ahi al terminar cada servicio.
#
# El Administrador necesita un modulo inteligente que estime,
# en el momento de asignar una emergencia, si la ambulancia
# LLEGARA A TIEMPO al lugar del reporte.
#
# Se considera "a tiempo" un tiempo de respuesta de
# 15 minutos o menos (umbral didactico, no normativo).
#
# OBJETIVO:
# Comprender como evaluar un modelo de Machine Learning
# y detectar problemas de sobreajuste (overfitting): el modelo
# aprende demasiado los detalles de los datos de entrenamiento,
# incluyendo ruido, y pierde capacidad para generalizar;
# y subajuste (underfitting): el modelo es demasiado sencillo y
# no logra aprender adecuadamente los patrones de los datos.
# Buen ajuste: el modelo aprende patrones utiles y mantiene un
# desempeño razonable en datos nuevos.
#
# Variable                 Descripcion
# distancia_km             Distancia del IMSS 220 al lugar de la emergencia
# nivel_trafico            Nivel de trafico en la ruta (0 = libre, 10 = saturado)
# ambulancias_libres       Ambulancias con estatus "libre" al momento del reporte
# experiencia_operador     Años de experiencia del operador asignado
# llega_a_tiempo           1 = llega en 15 min o menos, 0 = llega tarde
#
# Division de los datos
#
# 60% entrenamiento
# 20% validacion
# 20% prueba
#
# Diferencias entre los tres conjuntos
#
# Conjunto         ¿Para que sirve?
#
# Entrenamiento    Aprender patrones.
# Validacion       Ajustar parametros y elegir modelos.
# Prueba           Evaluar el desempeño final con datos no utilizados anteriormente.
#
#
# NOTA:
# Los datos generados son sinteticos y tienen fines educativos.
# No representan servicios reales de ambulancias ni pacientes.
# ============================================================


# ------------------------------------------------------------
# 1. IMPORTAR BIBLIOTECAS
# ------------------------------------------------------------

import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Herramienta para separar los conjuntos de datos.
from sklearn.model_selection import train_test_split

# Herramientas para validacion cruzada.
# StratifiedKFold conserva la proporcion de clases en cada particion.
from sklearn.model_selection import cross_val_score, StratifiedKFold

# Modelo de clasificacion.
from sklearn.tree import DecisionTreeClassifier

# Metricas de evaluacion.
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)


# ------------------------------------------------------------
# 2. CREAR CARPETA DE RESULTADOS
# ------------------------------------------------------------

# os.makedirs permite crear directorios.
# exist_ok=True evita errores si ya existe la carpeta.

CARPETA = "resultados_p04_emergexia"

os.makedirs(CARPETA, exist_ok=True)


# ------------------------------------------------------------
# 3. GENERAR DATOS SINTETICOS
# ------------------------------------------------------------

# Fijamos una semilla para reproducir los datos.
# Asi todo el equipo obtiene los mismos resultados
# al ejecutar nuevamente el programa.

SEMILLA = 42

rng = np.random.default_rng(SEMILLA)

# Definimos el numero de servicios de emergencia simulados.
cantidad_servicios = 500

# Distancia en kilometros desde el IMSS 220 hasta el reporte.
# Valores entre 0.5 km (muy cerca) y 18 km (zona metropolitana).
distancia_km = rng.uniform(
    0.5, 18, cantidad_servicios
)

# Nivel de trafico de 0 a 10.
nivel_trafico = rng.uniform(
    0, 10, cantidad_servicios
)

# Ambulancias libres en el hospital (numero entero de 0 a 6).
ambulancias_libres = rng.integers(
    0, 7, cantidad_servicios
)

# Años de experiencia del operador (0 a 15).
experiencia_operador = rng.uniform(
    0, 15, cantidad_servicios
)

# Construimos un tiempo de respuesta sintetico (en minutos).
#
# - Cada km agrega tiempo, y el trafico hace que cada km "cueste" mas.
# - Si no hay ambulancias libres, se pierde tiempo esperando
#   a que una se desocupe o llegue apoyo de otro hospital.
# - Mas ambulancias libres y mas experiencia reducen el tiempo.
#
# El ruido simula imprevistos (semaforos, clima, accesos cerrados)
# que no pueden explicarse con las variables.

ruido = rng.normal(
    0, 3.0, cantidad_servicios
)

tiempo_respuesta = (
    3                                          # tiempo de despacho
    + distancia_km * (0.9 + 0.08 * nivel_trafico)
    + np.where(ambulancias_libres == 0, 4, 0)  # sin unidades libres
    - ambulancias_libres * 0.4
    - experiencia_operador * 0.2
    + ruido
)

# Creamos la variable objetivo.
# 1 = llega a tiempo (15 min o menos).
# 0 = llega tarde.
#
# El umbral es una regla de generacion de datos ficticios,
# no un criterio oficial de tiempos de respuesta.

llega_a_tiempo = (tiempo_respuesta <= 15).astype(int)

# Construimos el DataFrame.
df = pd.DataFrame({
    "distancia_km": distancia_km,
    "nivel_trafico": nivel_trafico,
    "ambulancias_libres": ambulancias_libres,
    "experiencia_operador": experiencia_operador,
    "llega_a_tiempo": llega_a_tiempo
})

print("\n==========================================")
print("EMERGEXIA - PRACTICA 04")
print("1. DATOS GENERADOS")
print("==========================================")

print(df.head(10))

print("\nCantidad de servicios:")
print(len(df))

print("\nDistribucion de las clases (0 = tarde, 1 = a tiempo):")
print(df["llega_a_tiempo"].value_counts().sort_index())


# ------------------------------------------------------------
# 4. DEFINIR VARIABLES DE ENTRADA Y OBJETIVO
# ------------------------------------------------------------

# X contiene las caracteristicas utilizadas para aprender.

X = df[
    [
        "distancia_km",
        "nivel_trafico",
        "ambulancias_libres",
        "experiencia_operador"
    ]
]

# y contiene la clase que queremos predecir.

y = df["llega_a_tiempo"]


# ------------------------------------------------------------
# 5. SEPARAR ENTRENAMIENTO Y DATOS TEMPORALES
# ------------------------------------------------------------

# Primero reservamos el 40 % de los datos.
#
# El 60 % restante sera utilizado para entrenamiento.
# El 40 % temporal se dividira despues entre validacion
# y prueba.

X_entrenamiento, X_temporal, y_entrenamiento, y_temporal = (
    train_test_split(
        X,
        y,
        test_size=0.40,
        random_state=SEMILLA,
        stratify=y
    )
)


# ------------------------------------------------------------
# 6. DIVIDIR VALIDACION Y PRUEBA
# ------------------------------------------------------------

# Del conjunto temporal tomamos la mitad para validacion
# y la otra mitad para prueba.
#
# Resultado final:
# 60 % entrenamiento.
# 20 % validacion.
# 20 % prueba.

X_validacion, X_prueba, y_validacion, y_prueba = (
    train_test_split(
        X_temporal,
        y_temporal,
        test_size=0.50,
        random_state=SEMILLA,
        stratify=y_temporal
    )
)

print("\n==========================================")
print("2. DISTRIBUCION DE LOS CONJUNTOS")
print("==========================================")

print("Entrenamiento:", len(X_entrenamiento))
print("Validacion:", len(X_validacion))
print("Prueba:", len(X_prueba))


# ------------------------------------------------------------
# 7. ENTRENAR MODELOS CON DIFERENTES PROFUNDIDADES
# ------------------------------------------------------------

# La profundidad determina cuantas divisiones puede
# desarrollar el arbol de decisiones.
#
# Un arbol muy profundo puede aprender detalles excesivos
# (por ejemplo, memorizar servicios concretos).
# Un arbol demasiado pequeño puede no aprender suficiente
# (por ejemplo, fijarse solo en la distancia).

profundidades = [1, 2, 3, 5, 10, None]

# Lista para guardar los resultados.
resultados = []

# Guardamos los modelos para analizarlos despues.
modelos = {}

for profundidad in profundidades:

    print("\n--------------------------------------")
    print("Entrenando modelo:", profundidad)
    print("--------------------------------------")

    # Creamos el clasificador.
    modelo = DecisionTreeClassifier(
        max_depth=profundidad,
        random_state=SEMILLA
    )

    # Entrenamos utilizando exclusivamente
    # el conjunto de entrenamiento.
    modelo.fit(
        X_entrenamiento,
        y_entrenamiento
    )

    # Evaluamos el conjunto de entrenamiento.
    pred_entrenamiento = modelo.predict(
        X_entrenamiento
    )

    # Evaluamos el conjunto de validacion.
    pred_validacion = modelo.predict(
        X_validacion
    )

    # Calculamos exactitud en entrenamiento.
    exactitud_entrenamiento = accuracy_score(
        y_entrenamiento,
        pred_entrenamiento
    )

    # Calculamos exactitud en validacion.
    exactitud_validacion = accuracy_score(
        y_validacion,
        pred_validacion
    )

    # Guardamos el modelo.
    modelos[profundidad] = modelo

    # Guardamos las metricas.
    resultados.append({
        "profundidad": (
            "Sin limite"
            if profundidad is None
            else str(profundidad)
        ),

        # Valor numerico para construir las graficas.
        # Utilizamos 12 como posicion visual del modelo
        # cuya profundidad no tiene limite.
        "profundidad_grafica": (
            12
            if profundidad is None
            else profundidad
        ),

        "entrenamiento": exactitud_entrenamiento,

        "validacion": exactitud_validacion
    })


# Convertimos los resultados en una tabla.
df_resultados = pd.DataFrame(resultados)

print("\n==========================================")
print("3. COMPARACION DE MODELOS")
print("==========================================")

print(
    df_resultados[
        ["profundidad", "entrenamiento", "validacion"]
    ].to_string(
        index=False,
        formatters={
            "entrenamiento": "{:.2%}".format,
            "validacion": "{:.2%}".format
        }
    )
)


# ------------------------------------------------------------
# 8. IDENTIFICAR POSIBLES PROBLEMAS DE AJUSTE
# ------------------------------------------------------------

print("\n==========================================")
print("4. ANALISIS DE AJUSTE")
print("==========================================")

for _, fila in df_resultados.iterrows():

    diferencia = (
        fila["entrenamiento"]
        - fila["validacion"]
    )

    profundidad = fila["profundidad"]

    print("\nModelo:", profundidad)

    print(
        "Exactitud entrenamiento:",
        f"{fila['entrenamiento']:.2%}"
    )

    print(
        "Exactitud validacion:",
        f"{fila['validacion']:.2%}"
    )

    print(
        "Diferencia:",
        f"{diferencia:.2%}"
    )

    # Estas condiciones son indicadores didacticos,
    # no una prueba definitiva de sobreajuste.

    if (
        fila["entrenamiento"] < 0.70
        and fila["validacion"] < 0.70
    ):
        print("Posible subajuste.")

    elif diferencia > 0.10:
        print("Posible sobreajuste.")

    else:
        print("No se observa una brecha grande.")


# ------------------------------------------------------------
# 9. SELECCIONAR EL MODELO CON MEJOR VALIDACION
# ------------------------------------------------------------

# Buscamos el registro que obtuvo la mayor exactitud
# en el conjunto de validacion.
# (Si hay empate, idxmax devuelve el primero, es decir,
# el arbol mas sencillo.)

indice_mejor = df_resultados[
    "validacion"
].idxmax()

mejor_registro = df_resultados.loc[indice_mejor]

# Recuperamos la profundidad seleccionada directamente
# de la lista original (conserva None si no tiene limite).
profundidad_seleccionada = profundidades[indice_mejor]

# Recuperamos el modelo correspondiente.
mejor_modelo = modelos[profundidad_seleccionada]

print("\n==========================================")
print("5. MODELO SELECCIONADO")
print("==========================================")

print(
    "Profundidad seleccionada:",
    mejor_registro["profundidad"]
)

print(
    "Exactitud de validacion:",
    f"{mejor_registro['validacion']:.2%}"
)

print(
    "Configuracion interna del modelo:",
    mejor_modelo.get_params()["max_depth"]
)

# Importancia de cada variable en el arbol elegido.
# Ayuda a explicar al Administrador en que se fija el modelo.
importancias = pd.Series(
    mejor_modelo.feature_importances_,
    index=X.columns
).sort_values(ascending=False)

print("\nImportancia de las variables:")
print(importancias.to_string(float_format="{:.2%}".format))


# ------------------------------------------------------------
# 10. EVALUACION FINAL CON EL CONJUNTO DE PRUEBA
# ------------------------------------------------------------

# IMPORTANTE:
# El conjunto de prueba no se utilizo para entrenar
# ni para seleccionar la profundidad del modelo.
#
# Ahora lo utilizamos para estimar el rendimiento final.

pred_prueba = mejor_modelo.predict(X_prueba)

exactitud = accuracy_score(
    y_prueba,
    pred_prueba
)

precision = precision_score(
    y_prueba,
    pred_prueba,
    zero_division=0
)

recall = recall_score(
    y_prueba,
    pred_prueba,
    zero_division=0
)

f1 = f1_score(
    y_prueba,
    pred_prueba,
    zero_division=0
)

print("\n==========================================")
print("6. EVALUACION FINAL")
print("==========================================")

print(f"Exactitud: {exactitud:.2%}")
print(f"Precision: {precision:.2%}")
print(f"Recall: {recall:.2%}")
print(f"F1-score: {f1:.2%}")


# ------------------------------------------------------------
# 11. REPORTE DE CLASIFICACION
# ------------------------------------------------------------

print("\n==========================================")
print("7. REPORTE DE CLASIFICACION")
print("==========================================")

print(
    classification_report(
        y_prueba,
        pred_prueba,
        labels=[0, 1],
        target_names=["Llega tarde", "Llega a tiempo"],
        zero_division=0
    )
)


# ------------------------------------------------------------
# 12. MATRIZ DE CONFUSION
# ------------------------------------------------------------

matriz = confusion_matrix(
    y_prueba,
    pred_prueba,
    labels=[0, 1]
)

print("\n==========================================")
print("8. MATRIZ DE CONFUSION")
print("==========================================")

print(matriz)

vn, fp, fn, vp = matriz.ravel()

print("\nVerdaderos negativos (predijo tarde y llego tarde):", vn)
print("Falsos positivos (predijo a tiempo y llego tarde):", fp)
print("Falsos negativos (predijo tarde y llego a tiempo):", fn)
print("Verdaderos positivos (predijo a tiempo y llego a tiempo):", vp)


# ------------------------------------------------------------
# 13. VALIDACION CRUZADA
# ------------------------------------------------------------

# La validacion cruzada divide los datos de ENTRENAMIENTO
# en diferentes particiones.
#
# En cada iteracion:
# - una parte se utiliza para validar;
# - las restantes se utilizan para entrenar.
#
# No utilizamos el conjunto de prueba en este proceso.
# StratifiedKFold conserva la proporcion de clases.

modelo_cv = DecisionTreeClassifier(
    max_depth=profundidad_seleccionada,
    random_state=SEMILLA
)

particiones = StratifiedKFold(
    n_splits=5,
    shuffle=True,
    random_state=SEMILLA
)

puntuaciones_cv = cross_val_score(
    modelo_cv,
    X_entrenamiento,
    y_entrenamiento,
    cv=particiones,
    scoring="accuracy"
)

print("\n==========================================")
print("9. VALIDACION CRUZADA")
print("==========================================")

print("Resultados de cada particion:")
print(puntuaciones_cv)

print(
    "Promedio:",
    f"{puntuaciones_cv.mean():.2%}"
)

print(
    "Desviacion estandar:",
    f"{puntuaciones_cv.std():.2%}"
)


# ------------------------------------------------------------
# 14. GRAFICA: ENTRENAMIENTO VS VALIDACION
# ------------------------------------------------------------

plt.figure(figsize=(11, 6))

# Eje X: utilizamos exclusivamente valores numericos.
x = df_resultados["profundidad_grafica"]

# Graficamos el rendimiento de entrenamiento.
plt.plot(
    x,
    df_resultados["entrenamiento"],
    marker="o",
    linewidth=2,
    label="Entrenamiento"
)

# Graficamos el rendimiento de validacion.
plt.plot(
    x,
    df_resultados["validacion"],
    marker="s",
    linewidth=2,
    label="Validacion"
)

# Etiquetas personalizadas para el eje X.
etiquetas = df_resultados["profundidad"]

plt.xticks(
    x,
    etiquetas
)

plt.title(
    "Emergexia - Llegada a tiempo de ambulancias por profundidad del arbol",
    fontsize=14
)

plt.xlabel(
    "Profundidad del arbol"
)

plt.ylabel(
    "Exactitud"
)

plt.ylim(0, 1.05)

plt.grid(
    True,
    linestyle="--",
    alpha=0.5
)

plt.legend()

plt.tight_layout()

# Guardamos la grafica.
plt.savefig(
    f"{CARPETA}/comparacion_modelos.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()


# ------------------------------------------------------------
# 15. GRAFICA: MATRIZ DE CONFUSION
# ------------------------------------------------------------

plt.figure(figsize=(7, 6))

plt.imshow(matriz, cmap="Blues")

plt.title("Matriz de confusion - Llegada a tiempo")

plt.xlabel("Prediccion del modelo")

plt.ylabel("Resultado real")

plt.xticks(
    [0, 1],
    ["Llega tarde", "Llega a tiempo"]
)

plt.yticks(
    [0, 1],
    ["Llega tarde", "Llega a tiempo"]
)

# Agregamos el numero de casos dentro de cada celda.
for fila in range(2):

    for columna in range(2):

        plt.text(
            columna,
            fila,
            str(matriz[fila, columna]),
            ha="center",
            va="center",
            fontsize=14
        )

plt.colorbar()

plt.tight_layout()

plt.savefig(
    f"{CARPETA}/matriz_confusion.png",
    dpi=300
)

plt.show()


# ------------------------------------------------------------
# 16. EXPORTAR RESULTADOS
# ------------------------------------------------------------

# Guardamos la tabla comparativa en formato CSV.

df_resultados.to_csv(
    f"{CARPETA}/comparacion_modelos.csv",
    index=False
)

# Guardamos las predicciones finales.

df_predicciones = X_prueba.copy()

df_predicciones["resultado_real"] = y_prueba

df_predicciones["prediccion"] = pred_prueba

df_predicciones.to_csv(
    f"{CARPETA}/predicciones_prueba.csv",
    index=False
)


# ------------------------------------------------------------
# 17. EJEMPLO DE USO EN EMERGEXIA
# ------------------------------------------------------------

# Asi se usaria el modelo al momento de asignar una emergencia:
# el Administrador captura (o el sistema calcula) los datos
# del servicio y el modelo estima si la unidad llegara a tiempo.

nueva_emergencia = pd.DataFrame([{
    "distancia_km": 9.5,
    "nivel_trafico": 8,
    "ambulancias_libres": 1,
    "experiencia_operador": 3
}])

prediccion = mejor_modelo.predict(nueva_emergencia)[0]

print("\n==========================================")
print("10. EJEMPLO: NUEVA EMERGENCIA")
print("==========================================")

print(nueva_emergencia.to_string(index=False))

if prediccion == 1:
    print("Estimacion: la ambulancia LLEGARA A TIEMPO.")
else:
    print(
        "Estimacion: la ambulancia LLEGARA TARDE. "
        "Considerar apoyo de otro hospital."
    )


# ------------------------------------------------------------
# 18. CONCLUSIONES AUTOMATICAS
# ------------------------------------------------------------

print("\n==========================================")
print("11. CONCLUSIONES")
print("==========================================")

print(
    "El entrenamiento permite aprender patrones "
    "a partir de servicios anteriores."
)

print(
    "La validacion ayuda a seleccionar configuraciones "
    "sin utilizar los datos de prueba."
)

print(
    "La prueba permite estimar el comportamiento "
    "del modelo en servicios no utilizados anteriormente."
)

print(
    "Una diferencia grande entre entrenamiento y validacion "
    "puede indicar sobreajuste."
)

print(
    "La validacion cruzada permite estudiar la estabilidad "
    "del rendimiento en distintas particiones."
)

print(f"\nArchivos generados en la carpeta {CARPETA}.")

print("\nPRACTICA 04 (EMERGEXIA) FINALIZADA.")


# ¿Que se aprende de la comparacion?
# (Resultados obtenidos con SEMILLA = 42)
#
#   Profundidad   Entrenamiento   Validacion   Interpretacion
#
#       1             84.67%         80%       Ajuste limitado (casi solo mira la distancia)
#       2             87.67%         83%       Ajuste limitado
#       3             88.33%         84%       Buen comportamiento
#       5             95.67%         85%       Mejor resultado
#       10           100.00%         82%       Sobreajuste
#   Sin limite       100.00%         82%       Sobreajuste
#
# La profundidad 5 obtuvo el mejor resultado de validacion.
# Los arboles de profundidad 10 y sin limite memorizaron los
# servicios de entrenamiento (100%), incluyendo el ruido
# (imprevistos), y bajaron en validacion.
#
# Concepto importante: un modelo con 100% en entrenamiento
# no necesariamente es el mejor. Lo importante es que funcione
# con emergencias que nunca ha visto.
#
# Importancia de las variables (arbol de profundidad 5):
# distancia_km ~70%, experiencia_operador ~12%,
# nivel_trafico ~12%, ambulancias_libres ~6%.
# Tiene sentido: la distancia desde el IMSS 220 es el factor
# que mas pesa en el tiempo de respuesta.
#
# Interpretacion de la matriz de confusion
#
#   [[32  6]
#    [ 8 54]]
#
# Clase positiva: Llega a tiempo = 1
#
# Resultado               Cantidad   Interpretacion
# Verdaderos negativos       32      Predijo tarde y llego tarde.
# Falsos positivos            6      Predijo a tiempo, pero llego tarde.
# Falsos negativos            8      Predijo tarde, pero llego a tiempo.
# Verdaderos positivos       54      Predijo a tiempo y llego a tiempo.
#
# Precision = 90.00% y Recall = 87.10%.
#
# En Emergexia el error mas costoso es el FALSO POSITIVO:
# el sistema dice "llegara a tiempo", no se pide apoyo a otro
# hospital y la ambulancia llega tarde. Por eso conviene
# vigilar la precision (o el recall de la clase "Llega tarde",
# que fue 84%) mas que la exactitud general.
#
# La validacion cruzada (StratifiedKFold, 5 particiones,
# solo con el conjunto de entrenamiento) obtuvo:
# - Promedio: 84.67%
# - Desviacion estandar: 4.99%
#
# El promedio es muy parecido al 85% de validacion, lo que
# indica que el resultado no fue casualidad de una particion.
# La desviacion de ~5% muestra que, con solo 300 registros,
# el rendimiento puede variar segun que servicios toquen
# en cada particion.