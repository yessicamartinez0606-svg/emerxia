# ================================================================
# PROYECTO: EMERGEXIA
# PRACTICA 08: ANALISIS AVANZADO Y OPTIMIZACION DE LOS PERFILES
#              DE SERVICIO (K-MEANS)
# ARCHIVO: p08_analisis_avanzado_segmentos_emergexia.py
#
# Continua directamente la practica 07. Ahi K-Means encontro tres
# perfiles de servicio de ambulancia: respuesta rapida, respuesta
# intermedia y requiere apoyo. Ahora investigamos que tan
# CONFIABLES son esos perfiles.
#
# OBJETIVOS:
# 1. Comparar las inicializaciones k-means++ y random.
# 2. Comparar StandardScaler y MinMaxScaler.
# 3. Evaluar la estabilidad con el Adjusted Rand Index (ARI).
# 4. Detectar servicios atipicos (poco comunes para su perfil).
# 5. Analizar centroides y distancias.
# 6. Exportar los resultados (para guardarlos despues en MongoDB).
#
# Caso: la central quiere saber si un servicio que cae en
# "requiere apoyo" sigue cayendo en un grupo parecido cuando se
# cambia la inicializacion o la semilla. Tambien quiere detectar
# servicios muy alejados del centro de su perfil: conviene
# revisarlos con mas cuidado, aunque una distancia grande NO
# demuestra por si sola que haya un problema.
#
# En el sistema: app/segmentacion.py -> confiabilidad() y la
# pantalla "Tipo de servicio" del Asistente de despacho. Una
# emergencia nueva que quede mas lejos que el percentil 95 se
# marca como "poco comun".
#
# NOTA: datos sinteticos con fines educativos.
# ================================================================


# ================================================================
# 1. IMPORTAR LAS BIBLIOTECAS
# ================================================================

import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.metrics import silhouette_score, silhouette_samples, adjusted_rand_score


# ================================================================
# 2. CONFIGURACION GENERAL
# ================================================================

NUM_CLUSTERS = 3            # perfiles encontrados en la practica 07
SEMILLA = 42
NUM_INICIALIZACIONES = 20
PERCENTIL_ATIPICOS = 95     # por encima de este percentil = atipico
CARPETA_RESULTADOS = "resultados_p08"

os.makedirs(CARPETA_RESULTADOS, exist_ok=True)


# ================================================================
# 3. VARIABLES (las mismas de la practica 07)
# ================================================================

VARIABLES = [
    "distancia_km",
    "nivel_trafico",
    "tiempo_respuesta_min",
    "ambulancias_libres"
]

NOMBRES = ["Respuesta rapida", "Respuesta intermedia", "Requiere apoyo"]


# ================================================================
# 4. GENERAR LOS DATOS SI NO EXISTE EL CSV DE LA PRACTICA 07
# ================================================================

def generar_servicios():
    """500 servicios con tres perfiles simulados (K-Means no los ve)."""
    rng = np.random.default_rng(42)
    n = [180, 170, 150]

    rapido = np.column_stack([rng.normal(3.5, 1.2, n[0]), rng.normal(3.0, 1.2, n[0]),
                              rng.normal(9.0, 1.8, n[0]), rng.normal(4.0, 1.0, n[0])])
    intermedio = np.column_stack([rng.normal(8.0, 1.8, n[1]), rng.normal(5.5, 1.3, n[1]),
                                  rng.normal(16.0, 2.5, n[1]), rng.normal(2.5, 1.0, n[1])])
    apoyo = np.column_stack([rng.normal(13.0, 2.5, n[2]), rng.normal(8.0, 1.2, n[2]),
                             rng.normal(27.0, 4.0, n[2]), rng.normal(1.0, 0.8, n[2])])

    datos = np.vstack([rapido, intermedio, apoyo])
    rng.shuffle(datos)

    df = pd.DataFrame(datos, columns=VARIABLES)
    df["distancia_km"] = df["distancia_km"].clip(0.5, 25)
    df["nivel_trafico"] = df["nivel_trafico"].clip(0, 10)
    df["tiempo_respuesta_min"] = df["tiempo_respuesta_min"].clip(3, 60)
    df["ambulancias_libres"] = df["ambulancias_libres"].round().clip(0, 6)
    df.insert(0, "id_servicio", [f"SRV-{i:04d}" for i in range(1, len(df) + 1)])
    return df


# ================================================================
# 5. CARGAR LOS DATOS DE LA PRACTICA 07
# ================================================================

def cargar_datos():
    """Usa p07_servicios_segmentados.csv si existe (sin sus etiquetas)."""
    ruta = "p07_servicios_segmentados.csv"
    if not os.path.exists(ruta):
        print("\nNo se encontro el CSV de P07. Se generan datos equivalentes.")
        return generar_servicios()

    print("\nArchivo de P07 encontrado. Cargando servicios...")
    df = pd.read_csv(ruta)
    faltantes = [c for c in VARIABLES if c not in df.columns]
    if faltantes:
        raise ValueError("El archivo de P07 no contiene: " + str(faltantes))
    # No se reutilizan las etiquetas: K-Means las vuelve a calcular.
    df = df.drop(columns=["cluster", "perfil"], errors="ignore")
    if "id_servicio" not in df.columns:
        df.insert(0, "id_servicio", [f"SRV-{i:04d}" for i in range(1, len(df) + 1)])
    return df


# ================================================================
# 6. PREPARAR LOS DATOS
# ================================================================

def preparar_datos(df):
    print("\n" + "=" * 60)
    print("PREPARACION DE DATOS")
    print("=" * 60)
    print("Servicios:", len(df))
    print("\nValores faltantes por variable:")
    print(df[VARIABLES].isnull().sum())

    for c in VARIABLES:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df[VARIABLES] = df[VARIABLES].fillna(df[VARIABLES].median())
    return df, df[VARIABLES].to_numpy()


def kmeans(init="k-means++", semilla=SEMILLA):
    return KMeans(n_clusters=NUM_CLUSTERS, init=init, n_init=NUM_INICIALIZACIONES, random_state=semilla)


def barras(nombres, valores, titulo, xlabel, archivo):
    plt.figure(figsize=(8, 5))
    plt.bar(nombres, valores)
    plt.title(titulo)
    plt.xlabel(xlabel)
    plt.ylabel("Silhouette Score")
    plt.tight_layout()
    plt.savefig(f"{CARPETA_RESULTADOS}/{archivo}", dpi=300)
    plt.close()


# ================================================================
# 7. COMPARAR INICIALIZACIONES
# ================================================================

def comparar_inicializaciones(X):
    """k-means++ elige centroides iniciales separados; random, al azar.
    Se mantienen el escalador, K y n_init para comparar de forma justa."""
    print("\n" + "=" * 60)
    print("COMPARACION DE INICIALIZACIONES")
    print("=" * 60)

    X_esc = StandardScaler().fit_transform(X)
    filas = []
    for init in ["k-means++", "random"]:
        modelo = kmeans(init)
        et = modelo.fit_predict(X_esc)
        sil = silhouette_score(X_esc, et)
        filas.append({"inicializacion": init, "inercia": modelo.inertia_, "silhouette": sil})
        print(f"\n{init}: inercia {modelo.inertia_:.4f} · silhouette {sil:.4f}")

    res = pd.DataFrame(filas)
    res.to_csv(f"{CARPETA_RESULTADOS}/p08_inicializaciones.csv", index=False)
    barras(res["inicializacion"], res["silhouette"], "Comparacion de inicializaciones K-Means",
           "Metodo de inicializacion", "p08_inicializaciones.png")
    return res, X_esc


# ================================================================
# 8. COMPARAR ESCALADORES
# ================================================================

def comparar_escaladores(X):
    """StandardScaler: media 0 y desviacion 1. MinMaxScaler: de 0 a 1.
    La inercia NO se compara entre escalas distintas: se compara el
    Silhouette y los perfiles resultantes."""
    print("\n" + "=" * 60)
    print("COMPARACION DE ESCALADORES")
    print("=" * 60)

    filas, etiquetas = [], {}
    for nombre, esc in {"StandardScaler": StandardScaler(), "MinMaxScaler": MinMaxScaler()}.items():
        Xt = esc.fit_transform(X)
        modelo = kmeans()
        et = modelo.fit_predict(Xt)
        etiquetas[nombre] = et
        sil = silhouette_score(Xt, et)
        filas.append({"escalador": nombre, "inercia": modelo.inertia_, "silhouette": sil})
        print(f"\n{nombre}: inercia {modelo.inertia_:.4f} · silhouette {sil:.4f}")
        perfiles = pd.DataFrame(X, columns=VARIABLES).groupby(et).mean().sort_values("tiempo_respuesta_min")
        print(perfiles.round(2))

    ari = adjusted_rand_score(etiquetas["StandardScaler"], etiquetas["MinMaxScaler"])
    print(f"\nCoincidencia entre los dos escaladores (ARI): {ari:.4f}")

    res = pd.DataFrame(filas)
    res.to_csv(f"{CARPETA_RESULTADOS}/p08_comparacion_escaladores.csv", index=False)
    barras(res["escalador"], res["silhouette"], "Comparacion de escaladores", "Escalador", "p08_escaladores.png")
    return res


# ================================================================
# 9. ESTABILIDAD CON ADJUSTED RAND INDEX
# ================================================================

def analizar_estabilidad(X_esc):
    """ARI = 1: misma agrupacion. Cerca de 0: como al azar. Puede ser
    negativo. Sirve aunque los numeros de cluster cambien de orden."""
    print("\n" + "=" * 60)
    print("ANALISIS DE ESTABILIDAD")
    print("=" * 60)

    semillas = [10, 20, 30, 40, 50, 42]
    particiones = {s: kmeans(semilla=s).fit_predict(X_esc) for s in semillas}

    filas = []
    for i, a in enumerate(semillas):
        for b in semillas[i + 1:]:
            filas.append({"semilla_a": a, "semilla_b": b, "ARI": adjusted_rand_score(particiones[a], particiones[b])})
    df_ari = pd.DataFrame(filas)
    print(df_ari.round(4).to_string(index=False))
    print("\nARI promedio:", round(df_ari["ARI"].mean(), 4))
    df_ari.to_csv(f"{CARPETA_RESULTADOS}/p08_estabilidad_ari.csv", index=False)

    matriz = np.eye(len(semillas))
    for _, f in df_ari.iterrows():
        i, j = semillas.index(int(f["semilla_a"])), semillas.index(int(f["semilla_b"]))
        matriz[i, j] = matriz[j, i] = f["ARI"]

    plt.figure(figsize=(8, 6))
    img = plt.imshow(matriz, vmin=0, vmax=1, cmap="viridis")
    plt.colorbar(img, label="Adjusted Rand Index")
    plt.xticks(range(len(semillas)), semillas)
    plt.yticks(range(len(semillas)), semillas)
    plt.title("Estabilidad de K-Means mediante ARI")
    plt.xlabel("Semilla")
    plt.ylabel("Semilla")
    for i in range(len(semillas)):
        for j in range(len(semillas)):
            plt.text(j, i, f"{matriz[i, j]:.2f}", ha="center", va="center", color="white")
    plt.tight_layout()
    plt.savefig(f"{CARPETA_RESULTADOS}/p08_matriz_estabilidad.png", dpi=300)
    plt.close()
    return df_ari


# ================================================================
# 10. MODELO FINAL
# ================================================================

def entrenar_modelo_final(X):
    """StandardScaler + K-Means con K = 3 (la eleccion de la P07)."""
    escalador = StandardScaler()
    X_esc = escalador.fit_transform(X)
    modelo = kmeans()
    et = modelo.fit_predict(X_esc)
    return modelo, escalador, X_esc, et, silhouette_samples(X_esc, et)


# ================================================================
# 11. CENTROIDES Y PERFILES
# ================================================================

def analizar_centroides(df, modelo, escalador, et):
    """inverse_transform regresa los centroides a km, minutos, etc."""
    print("\n" + "=" * 60)
    print("ANALISIS DE CENTROIDES")
    print("=" * 60)

    centroides = pd.DataFrame(escalador.inverse_transform(modelo.cluster_centers_), columns=VARIABLES)
    centroides.insert(0, "cluster", range(NUM_CLUSTERS))
    print(centroides.round(2).to_string(index=False))

    perfiles = df[VARIABLES].assign(cluster=et).groupby("cluster")[VARIABLES].mean().reset_index()
    print("\nPerfiles promedio:")
    print(perfiles.round(2).to_string(index=False))

    centroides.to_csv(f"{CARPETA_RESULTADOS}/p08_centroides.csv", index=False)
    perfiles.to_csv(f"{CARPETA_RESULTADOS}/p08_perfiles.csv", index=False)
    return centroides


# ================================================================
# 12. SERVICIOS ATIPICOS
# ================================================================

def detectar_atipicos(df, X_esc, modelo, et, sil):
    """Distancia euclidiana de cada servicio al centroide de su perfil.
    Por encima del percentil 95 = candidato a revision. Es una regla
    exploratoria, no una prueba estadistica definitiva."""
    print("\n" + "=" * 60)
    print("SERVICIOS POCO COMUNES (POSIBLES ATIPICOS)")
    print("=" * 60)

    distancias = np.linalg.norm(X_esc - modelo.cluster_centers_[et], axis=1)
    umbral = np.percentile(distancias, PERCENTIL_ATIPICOS)

    df_at = df.copy()
    df_at["cluster"] = et
    df_at["distancia_centroide"] = distancias
    df_at["silhouette_individual"] = sil
    df_at["posible_atipico"] = distancias > umbral
    candidatos = df_at[df_at["posible_atipico"]].copy()

    print(f"Umbral (percentil {PERCENTIL_ATIPICOS}): {umbral:.4f}")
    print("Candidatos:", len(candidatos), f"({len(candidatos) / len(df_at) * 100:.2f} %)")
    print(candidatos[["id_servicio", "cluster", "distancia_centroide", "silhouette_individual"]]
          .head(10).round(4).to_string(index=False))

    df_at.to_csv(f"{CARPETA_RESULTADOS}/p08_analisis_distancias.csv", index=False)
    candidatos.to_csv(f"{CARPETA_RESULTADOS}/p08_posibles_atipicos.csv", index=False)

    plt.figure(figsize=(10, 5))
    plt.scatter(range(len(distancias)), distancias, s=12)
    plt.axhline(y=umbral, linestyle="--", label=f"Umbral P{PERCENTIL_ATIPICOS}")
    plt.title("Distancia de cada servicio al centro de su perfil")
    plt.xlabel("Servicio")
    plt.ylabel("Distancia euclidiana")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{CARPETA_RESULTADOS}/p08_distancias_atipicos.png", dpi=300)
    plt.close()
    return candidatos, umbral


# ================================================================
# 13. VISUALIZAR LOS PERFILES
# ================================================================

def visualizar_segmentos(df, et):
    """Proyeccion de dos variables; K-Means uso las cuatro."""
    plt.figure(figsize=(10, 6))
    sc = plt.scatter(df["distancia_km"], df["tiempo_respuesta_min"], c=et, cmap="viridis", alpha=0.75)
    plt.title("Perfiles de servicio de Emergexia")
    plt.xlabel("Distancia desde el IMSS 220 (km)")
    plt.ylabel("Tiempo de respuesta (min)")
    plt.colorbar(sc, label="Cluster")
    plt.tight_layout()
    plt.savefig(f"{CARPETA_RESULTADOS}/p08_segmentacion_final.png", dpi=300)
    plt.close()


# ================================================================
# 14. REPORTE INTEGRAL
# ================================================================

def exportar_reporte(df, et, sil, centroides, candidatos):
    reporte = df.copy()
    reporte["cluster"] = et
    reporte["silhouette_individual"] = sil
    reporte["posible_atipico"] = reporte["id_servicio"].isin(set(candidatos["id_servicio"]))
    # Nombre del perfil: centroides ordenados por tiempo de respuesta.
    orden = centroides.sort_values("tiempo_respuesta_min")["cluster"].tolist()
    reporte["perfil"] = reporte["cluster"].map({c: NOMBRES[i] for i, c in enumerate(orden)})
    reporte.to_csv(f"{CARPETA_RESULTADOS}/p08_reporte_integral.csv", index=False)
    print("\nReporte integral exportado.")


# ================================================================
# 15. FUNCION PRINCIPAL
# ================================================================

def main():
    print("\n" + "=" * 60)
    print("EMERGEXIA - PRACTICA 08")
    print("ANALISIS AVANZADO DE LOS PERFILES DE SERVICIO")
    print("=" * 60)

    df, X = preparar_datos(cargar_datos())
    _, X_std = comparar_inicializaciones(X)
    comparar_escaladores(X)
    analizar_estabilidad(X_std)
    modelo, escalador, X_esc, et, sil = entrenar_modelo_final(X)
    centroides = analizar_centroides(df, modelo, escalador, et)
    candidatos, _ = detectar_atipicos(df, X_esc, modelo, et, sil)
    visualizar_segmentos(df, et)
    exportar_reporte(df, et, sil, centroides, candidatos)

    print("\n" + "=" * 60)
    print("RESUMEN FINAL DE LA PRACTICA 08")
    print("=" * 60)
    print("Servicios analizados:", len(df))
    print("Clusters:", NUM_CLUSTERS)
    print("Silhouette final:", round(silhouette_score(X_esc, et), 4))
    print("Posibles atipicos:", len(candidatos), f"({len(candidatos) / len(df) * 100:.2f} %)")
    print("Archivos generados en:", CARPETA_RESULTADOS)
    print("\nUn servicio atipico no es un error: solo conviene revisarlo con mas cuidado.")


if __name__ == "__main__":
    main()
