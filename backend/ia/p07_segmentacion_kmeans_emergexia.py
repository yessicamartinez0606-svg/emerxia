# ================================================================
# PROYECTO: EMERGEXIA
# PRACTICA 07: SEGMENTACION DE SERVICIOS DE AMBULANCIA CON K-MEANS
# ARCHIVO: p07_segmentacion_kmeans_emergexia.py
#
# OBJETIVO:
# Usar K-Means para descubrir grupos de servicios de ambulancia
# con caracteristicas parecidas, utilizando agrupamiento
# (clustering), escalamiento de variables, seleccion del numero
# de grupos e interpretacion de resultados.
#
# Caso de estudio
# Emergexia ha registrado 500 servicios de ambulancia que salieron
# del Hospital IMSS 220 (Paseo Tollocan, Toluca). La central quiere
# identificar PERFILES DE SERVICIO para preparar estrategias:
#
# - Servicios de respuesta rapida (cerca, poco trafico).
# - Servicios de respuesta intermedia.
# - Servicios que requieren apoyo (lejos, trafico alto, pocas
#   ambulancias libres; conviene pedir una unidad a otro hospital).
#
# Problema: no sabemos de antemano cuantos perfiles existen.
#
# Diferencia fundamental con las practicas 04, 05 y 06:
# aqui NO hay una columna objetivo (como "llega_a_tiempo" o
# "es_critica"). K-Means es aprendizaje NO supervisado: solo
# calcula distancias y busca grupos.
#
# ¿Que es K-Means?
# - K:     numero de grupos que queremos encontrar.
# - Means: el promedio que se usa para calcular el centro de
#          cada grupo, llamado CENTROIDE.
#
# Etapas:
# 1. Inicializacion: elige K centroides iniciales.
# 2. Asignacion:     cada servicio va al centroide mas cercano.
# 3. Actualizacion:  cada centroide se recalcula con el promedio
#                    de sus servicios.
# 4. Convergencia:   se repite 2 y 3 hasta que los grupos dejan
#                    de cambiar (o se llega al limite).
#
# Ejemplo sencillo
#   Servicio   Distancia (km)   Tiempo de respuesta (min)
#      A            2                  8
#      B            3                  9
#      C           14                 30
# A y B quedarian juntos; C en otro grupo.
#
#   Concepto              Descripcion
#   Clustering            Agrupar registros parecidos.
#   K                     Numero de grupos.
#   Centroide             Centro matematico de un grupo.
#   Distancia euclidiana  Distancia entre registros y centroides.
#   WCSS / Inercia        Suma de distancias al cuadrado de cada
#                         registro a su centroide.
#   Silhouette Score      Que tan separados y compactos estan los grupos.
#
# Variables de cada servicio
#   distancia_km          Distancia del IMSS 220 al lugar (0.5 a 25)
#   nivel_trafico         0 = libre, 10 = saturado
#   tiempo_respuesta_min  Minutos desde la salida hasta la llegada
#   ambulancias_libres    Ambulancias libres en el IMSS 220 (0 a 6)
#
# ¿Por que escalar?
# El tiempo (3 a 60) y la distancia (0.5 a 25) tienen valores mas
# grandes que las ambulancias libres (0 a 6); sin escalar dominarian
# las distancias del algoritmo. StandardScaler deja cada variable
# con media 0 y desviacion estandar 1.
#
# NOTA: datos sinteticos con fines educativos.
# ================================================================


# ================================================================
# 1. IMPORTAR LAS BIBLIOTECAS
# ================================================================

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

# Mostrar todas las columnas al imprimir tablas.
pd.set_option("display.width", 140)
pd.set_option("display.max_columns", 10)


# ================================================================
# 2. CONFIGURAR LA GENERACION DE DATOS
# ================================================================

rng = np.random.default_rng(42)

# Servicios por perfil simulado. Estos perfiles SOLO sirven para
# generar datos de ejemplo; NO se entregan a K-Means.
cantidad_servicios = [180, 170, 150]

# Columnas: distancia_km, nivel_trafico, tiempo_respuesta_min,
#           ambulancias_libres

# ------------------------------------------------
# Perfil simulado 1: cerca del hospital, poco trafico
# ------------------------------------------------
perfil_rapido = np.column_stack([
    rng.normal(3.5, 1.2, cantidad_servicios[0]),
    rng.normal(3.0, 1.2, cantidad_servicios[0]),
    rng.normal(9.0, 1.8, cantidad_servicios[0]),
    rng.normal(4.0, 1.0, cantidad_servicios[0])
])

# ------------------------------------------------
# Perfil simulado 2: distancia y trafico medios
# ------------------------------------------------
perfil_intermedio = np.column_stack([
    rng.normal(8.0, 1.8, cantidad_servicios[1]),
    rng.normal(5.5, 1.3, cantidad_servicios[1]),
    rng.normal(16.0, 2.5, cantidad_servicios[1]),
    rng.normal(2.5, 1.0, cantidad_servicios[1])
])

# ------------------------------------------------
# Perfil simulado 3: lejos, trafico alto, pocas unidades
# ------------------------------------------------
perfil_apoyo = np.column_stack([
    rng.normal(13.0, 2.5, cantidad_servicios[2]),
    rng.normal(8.0, 1.2, cantidad_servicios[2]),
    rng.normal(27.0, 4.0, cantidad_servicios[2]),
    rng.normal(1.0, 0.8, cantidad_servicios[2])
])


# ================================================================
# 3. UNIFICAR Y MEZCLAR LOS REGISTROS
# ================================================================

datos = np.vstack([perfil_rapido, perfil_intermedio, perfil_apoyo])

rng.shuffle(datos)


# ================================================================
# 4. CREAR EL DATAFRAME
# ================================================================

COLUMNAS = [
    "distancia_km",
    "nivel_trafico",
    "tiempo_respuesta_min",
    "ambulancias_libres"
]

df = pd.DataFrame(datos, columns=COLUMNAS)

# 4.1 Ajustar a rangos realistas
df["distancia_km"] = df["distancia_km"].clip(0.5, 25)
df["nivel_trafico"] = df["nivel_trafico"].clip(0, 10)
df["tiempo_respuesta_min"] = df["tiempo_respuesta_min"].clip(3, 60)
# Las ambulancias son numeros enteros de 0 a 6.
df["ambulancias_libres"] = df["ambulancias_libres"].round().clip(0, 6)


# ================================================================
# 5. EXPLORAR LOS DATOS
# ================================================================

print("\n==========================================")
print("1. DATOS GENERADOS")
print("==========================================")

print(df.head(10).round(2))
print("\nCantidad de servicios:", len(df))
print("\nInformacion estadistica:")
print(df.describe().round(2))


# ================================================================
# 6. SELECCIONAR LAS VARIABLES
# ================================================================

X = df[COLUMNAS]


# ================================================================
# 7. ESCALAR LOS DATOS
# ================================================================

escalador = StandardScaler()

X_escalado = escalador.fit_transform(X)

print("\n==========================================")
print("2. DATOS ESCALADOS")
print("==========================================")

print("Media aproximada:", X_escalado.mean(axis=0).round(2))
print("Desviacion estandar aproximada:", X_escalado.std(axis=0).round(2))


# ================================================================
# 8. METODO DEL CODO
# ================================================================

valores_k = range(1, 9)

inercias = []

print("\n==========================================")
print("3. METODO DEL CODO")
print("==========================================")

for k in valores_k:

    modelo = KMeans(n_clusters=k, random_state=42, n_init=20)

    modelo.fit(X_escalado)

    inercias.append(modelo.inertia_)

    print(f"K={k} | Inercia={modelo.inertia_:.2f}")

plt.figure(figsize=(9, 5))
plt.plot(list(valores_k), inercias, marker="o", linewidth=2)
plt.title("Emergexia - Metodo del codo")
plt.xlabel("Cantidad de grupos (K)")
plt.ylabel("Inercia (WCSS)")
plt.xticks(list(valores_k))
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("p07_metodo_del_codo.png", dpi=300)
plt.show()


# ================================================================
# 9. SILHOUETTE SCORE
# ================================================================

# Cercano a 1: grupos bien separados.
# Cercano a 0: grupos que se traslapan.
# Negativo:    asignaciones posiblemente incorrectas.

resultados_silhouette = []

print("\n==========================================")
print("4. SILHOUETTE SCORE")
print("==========================================")

for k in range(2, 9):

    modelo = KMeans(n_clusters=k, random_state=42, n_init=20)

    etiquetas = modelo.fit_predict(X_escalado)

    puntuacion = silhouette_score(X_escalado, etiquetas)

    resultados_silhouette.append(puntuacion)

    print(f"K={k} | Silhouette Score={puntuacion:.4f}")

plt.figure(figsize=(9, 5))
plt.plot(list(range(2, 9)), resultados_silhouette, marker="o", linewidth=2)
plt.title("Emergexia - Evaluacion Silhouette")
plt.xlabel("Cantidad de grupos (K)")
plt.ylabel("Silhouette Score")
plt.xticks(list(range(2, 9)))
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("p07_silhouette.png", dpi=300)
plt.show()


# ================================================================
# 10. ENTRENAR EL MODELO FINAL
# ================================================================

# Usamos 3 grupos:
# - En el codo, la inercia baja mucho hasta K=3 (2000 -> 811 -> 491)
#   y despues casi se aplana (434, 385...): ahi esta el "codo".
# - El Silhouette mas alto es K=2 (0.47), pero K=3 queda muy cerca
#   (0.44) y separa los servicios intermedios de los que requieren
#   apoyo, que es justo lo que necesita la central.
# - K=4 o mas bajan el Silhouette: se parten grupos que ya eran buenos.

K_FINAL = 3

modelo_final = KMeans(n_clusters=K_FINAL, random_state=42, n_init=20)

df["cluster"] = modelo_final.fit_predict(X_escalado)


# ================================================================
# 11. INTERPRETAR LOS GRUPOS
# ================================================================

print("\n==========================================")
print("5. SERVICIOS POR GRUPO")
print("==========================================")

print(df["cluster"].value_counts().sort_index())

perfiles = df.groupby("cluster")[COLUMNAS].mean().round(2)

print("\n==========================================")
print("6. PERFIL PROMEDIO DE CADA GRUPO")
print("==========================================")

print(perfiles)

# Los numeros de cluster son arbitrarios: cluster 0 no significa
# "rapido". Ordenamos por tiempo de respuesta promedio para darles
# un nombre orientativo.

orden = perfiles["tiempo_respuesta_min"].sort_values().index.tolist()

nombres = [
    "Respuesta rapida",
    "Respuesta intermedia",
    "Requiere apoyo"
]

mapa_nombres = {cluster: nombre for cluster, nombre in zip(orden, nombres)}

df["perfil"] = df["cluster"].map(mapa_nombres)

print("\n==========================================")
print("7. INTERPRETACION DE LOS PERFILES")
print("==========================================")

print(df.head(15).round(2))


# ================================================================
# 12. VISUALIZAR LOS GRUPOS
# ================================================================

# K-Means usa las 4 variables, pero graficamos distancia contra
# tiempo de respuesta para interpretarlo facilmente.

plt.figure(figsize=(10, 6))

for cluster in sorted(df["cluster"].unique()):

    datos_cluster = df[df["cluster"] == cluster]

    plt.scatter(
        datos_cluster["distancia_km"],
        datos_cluster["tiempo_respuesta_min"],
        label=mapa_nombres[cluster],
        alpha=0.65
    )

# 12.1 Centroides en la escala original
centroides_originales = escalador.inverse_transform(modelo_final.cluster_centers_)

centroides_df = pd.DataFrame(centroides_originales, columns=COLUMNAS)

plt.scatter(
    centroides_df["distancia_km"],
    centroides_df["tiempo_respuesta_min"],
    marker="X",
    s=250,
    edgecolor="black",
    linewidth=1.5,
    label="Centroides"
)

plt.title("Emergexia - Segmentacion de servicios de ambulancia")
plt.xlabel("Distancia desde el IMSS 220 (km)")
plt.ylabel("Tiempo de respuesta (min)")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("p07_segmentacion_servicios.png", dpi=300)
plt.show()


# ================================================================
# 13. MOSTRAR LOS CENTROIDES
# ================================================================

print("\n==========================================")
print("8. CENTROIDES EN ESCALA ORIGINAL")
print("==========================================")

centroides_df["perfil"] = [mapa_nombres[c] for c in range(K_FINAL)]

print(centroides_df.round(2))


# ================================================================
# 14. EVALUAR EL MODELO FINAL
# ================================================================

silhouette_final = silhouette_score(X_escalado, df["cluster"])

print("\n==========================================")
print("9. EVALUACION FINAL")
print("==========================================")

print("Numero de grupos:", K_FINAL)
print("Inercia final:", round(modelo_final.inertia_, 2))
print("Silhouette Score:", round(silhouette_final, 4))


# ================================================================
# 15. EJEMPLO DE USO EN EMERGEXIA
# ================================================================

# Llega una emergencia nueva. Con sus datos, K-Means dice a que
# perfil se parece y la central aplica la estrategia de ese perfil.

estrategias = {
    "Respuesta rapida": "Sale la unidad del IMSS 220 de forma normal.",
    "Respuesta intermedia": "Revisar trafico y rutas alternas antes de salir.",
    "Requiere apoyo": "Pedir apoyo al hospital mas cercano y avisar al paciente.",
}

nueva = pd.DataFrame([{
    "distancia_km": 12.5,
    "nivel_trafico": 8,
    "tiempo_respuesta_min": 25,
    "ambulancias_libres": 1
}])

grupo = modelo_final.predict(escalador.transform(nueva[COLUMNAS]))[0]

print("\n==========================================")
print("10. EJEMPLO: NUEVA EMERGENCIA")
print("==========================================")

print(nueva.to_string(index=False))
print("Perfil:", mapa_nombres[grupo])
print("Estrategia:", estrategias[mapa_nombres[grupo]])


# ================================================================
# 16. EXPORTAR LOS RESULTADOS
# ================================================================

df.to_csv("p07_servicios_segmentados.csv", index=False, encoding="utf-8-sig")

perfiles.to_csv("p07_perfiles_servicio.csv", encoding="utf-8-sig")


# ================================================================
# 17. MENSAJE FINAL
# ================================================================

print("\n==========================================")
print("PRACTICA 07 (EMERGEXIA) FINALIZADA")
print("==========================================")

print("Archivos generados:")
print("1. p07_metodo_del_codo.png")
print("2. p07_silhouette.png")
print("3. p07_segmentacion_servicios.png")
print("4. p07_servicios_segmentados.csv")
print("5. p07_perfiles_servicio.csv")

print("\nLos perfiles describen patrones de los servicios;")
print("no deciden por si solos que hacer en cada emergencia.")
