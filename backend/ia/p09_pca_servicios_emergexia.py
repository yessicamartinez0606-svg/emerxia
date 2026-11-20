# ================================================================
# PROYECTO: EMERGEXIA
# PRACTICA 09: REDUCCION DE DIMENSIONALIDAD MEDIANTE PCA
#              (Analisis de Componentes Principales)
# ARCHIVO: p09_pca_servicios_emergexia.py
#
# Cada servicio de ambulancia tiene cuatro variables:
#   distancia_km          Distancia desde el IMSS 220
#   nivel_trafico         0 = libre, 10 = saturado
#   tiempo_respuesta_min  Minutos de la salida a la llegada
#   ambulancias_libres    Ambulancias libres en el IMSS 220
#
# Cuatro variables no caben en una grafica normal. PCA las
# transforma en componentes principales:
# - PC1: concentra la mayor variabilidad posible.
# - PC2: la mayor variabilidad restante, sin correlacion con PC1.
# Asi cada servicio se dibuja con dos coordenadas (PC1, PC2) y se
# ve como se separan los perfiles de la practica 07.
#
# Conceptos:
# - Varianza explicada: % de la variabilidad que representa cada PC.
# - Varianza acumulada: suma de las primeras componentes.
# - Cargas (loadings): cuanto aporta cada variable a cada PC.
# - Reconstruccion: aproximacion de los datos con menos PCs (MSE).
#
# PCA busca conservar la varianza, NO separar los clusters: si en
# 2D se ven grupos mezclados, no significa que K-Means fallo.
#
# En el sistema: app/segmentacion.py -> mapa_pca() y el "Mapa de
# servicios" del Asistente de despacho, donde tambien se marca la
# emergencia abierta.
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

from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import mean_squared_error

from p08_analisis_avanzado_segmentos_emergexia import generar_servicios


# ================================================================
# 2. CONFIGURACION GENERAL
# ================================================================

SEMILLA = 42
NUM_CLUSTERS = 3
VARIANZA_OBJETIVO = 0.85    # referencia de trabajo, no regla obligatoria
CARPETA_RESULTADOS = "resultados_p09"

os.makedirs(CARPETA_RESULTADOS, exist_ok=True)

VARIABLES = [
    "distancia_km",
    "nivel_trafico",
    "tiempo_respuesta_min",
    "ambulancias_libres"
]
COMPONENTES = ["PC1", "PC2", "PC3", "PC4"]


# ================================================================
# 3. CARGAR LOS DATOS
# ================================================================

def cargar_datos():
    """Usa el CSV de la P07 (sus clusters solo colorean las graficas;
    PCA no los usa). Si no existe, genera los mismos servicios."""
    ruta = "p07_servicios_segmentados.csv"
    if os.path.exists(ruta):
        df = pd.read_csv(ruta)
        faltantes = [c for c in VARIABLES if c not in df.columns]
        if faltantes:
            raise ValueError("Faltan las variables: " + str(faltantes))
        if "id_servicio" not in df.columns:
            df.insert(0, "id_servicio", [f"SRV-{i:04d}" for i in range(1, len(df) + 1)])
    else:
        print("\nNo se encontro el CSV de P07. Se generan los mismos servicios.")
        df = generar_servicios()
    print("\nServicios cargados:", len(df))
    return df


# ================================================================
# 4. PREPARAR Y ESTANDARIZAR
# ================================================================

def preparar_datos(df):
    X = df[VARIABLES].apply(pd.to_numeric, errors="coerce")
    return X.fillna(X.median()).to_numpy(dtype=float)


def estandarizar(X):
    """PCA es sensible a la escala: sin estandarizar, el tiempo (3 a 60)
    dominaria sobre las ambulancias libres (0 a 6)."""
    escalador = StandardScaler()
    X_esc = escalador.fit_transform(X)
    print("\n" + "=" * 60)
    print("ESTANDARIZACION")
    print("=" * 60)
    print("Media:", np.round(X_esc.mean(axis=0), 4))
    print("Desviacion estandar:", np.round(X_esc.std(axis=0), 4))
    return X_esc, escalador


def obtener_clusters(df, X_esc):
    """Usa los clusters de la P07 si existen; si no, entrena K-Means."""
    if "cluster" in df.columns:
        print("\nSe usan los clusters de la practica 07.")
        return df["cluster"].to_numpy().astype(int)
    print("\nSe generan los perfiles con K-Means.")
    return KMeans(n_clusters=NUM_CLUSTERS, n_init=20, random_state=SEMILLA).fit_predict(X_esc)


# ================================================================
# 5. ENTRENAR PCA
# ================================================================

def entrenar_pca(X_esc):
    pca = PCA(n_components=4)
    datos = pca.fit_transform(X_esc)
    acumulada = np.cumsum(pca.explained_variance_ratio_)
    print("\n" + "=" * 60)
    print("RESULTADOS DE PCA")
    print("=" * 60)
    print("Varianza explicada (%):", np.round(pca.explained_variance_ratio_ * 100, 2))
    print("Varianza acumulada (%):", np.round(acumulada * 100, 2))
    return pca, datos, acumulada


def tabla_varianza(pca):
    v = pca.explained_variance_ratio_
    a = np.cumsum(v)
    df = pd.DataFrame({"componente": COMPONENTES, "varianza_explicada": v, "porcentaje_explicado": v * 100,
                       "varianza_acumulada": a, "porcentaje_acumulado": a * 100})
    print("\n" + df.round(4).to_string(index=False))
    df.to_csv(f"{CARPETA_RESULTADOS}/p09_varianza_explicada.csv", index=False)
    return df


# ================================================================
# 6. CARGAS DE LAS COMPONENTES
# ================================================================

def analizar_cargas(pca):
    """Fila = componente, columna = variable original. El signo dice
    la direccion; la magnitud, cuanto aporta."""
    cargas = pd.DataFrame(pca.components_, columns=VARIABLES, index=COMPONENTES)
    print("\n" + "=" * 60)
    print("CARGAS DE LAS COMPONENTES")
    print("=" * 60)
    print(cargas.round(4))
    cargas.to_csv(f"{CARPETA_RESULTADOS}/p09_cargas_componentes.csv")

    plt.figure(figsize=(10, 5))
    plt.imshow(cargas.values, aspect="auto", cmap="coolwarm", vmin=-1, vmax=1)
    plt.colorbar(label="Carga de componente")
    plt.xticks(range(len(VARIABLES)), VARIABLES, rotation=25, ha="right")
    plt.yticks(range(4), COMPONENTES)
    plt.title("Cargas de las componentes principales")
    plt.tight_layout()
    plt.savefig(f"{CARPETA_RESULTADOS}/p09_cargas_componentes.png", dpi=300)
    plt.close()
    return cargas


# ================================================================
# 7. CUANTAS COMPONENTES HACEN FALTA
# ================================================================

def determinar_componentes(pca):
    acumulada = np.cumsum(pca.explained_variance_ratio_)
    cantidad = int(np.argmax(acumulada >= VARIANZA_OBJETIVO) + 1)
    if acumulada[-1] < VARIANZA_OBJETIVO:
        cantidad = len(acumulada)
    print("\n" + "=" * 60)
    print("SELECCION DE COMPONENTES")
    print("=" * 60)
    print(f"Objetivo: {VARIANZA_OBJETIVO * 100:.2f} %")
    print("Componentes necesarias:", cantidad)
    print("Varianza conservada:", round(acumulada[cantidad - 1] * 100, 2), "%")
    return cantidad


# ================================================================
# 8. GRAFICAS
# ================================================================

def graficar_varianza(df_v):
    plt.figure(figsize=(8, 5))
    plt.plot(df_v["componente"], df_v["porcentaje_explicado"], marker="o")
    plt.title("Grafica de sedimentacion PCA")
    plt.xlabel("Componentes principales")
    plt.ylabel("Varianza explicada (%)")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{CARPETA_RESULTADOS}/p09_sedimentacion.png", dpi=300)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.plot(df_v["componente"], df_v["porcentaje_acumulado"], marker="o")
    plt.axhline(y=VARIANZA_OBJETIVO * 100, linestyle="--", label="Objetivo de varianza")
    plt.title("Varianza acumulada PCA")
    plt.xlabel("Componentes principales")
    plt.ylabel("Varianza acumulada (%)")
    plt.ylim(0, 105)
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{CARPETA_RESULTADOS}/p09_varianza_acumulada.png", dpi=300)
    plt.close()


def visualizar_2d(datos, et):
    plt.figure(figsize=(10, 7))
    sc = plt.scatter(datos[:, 0], datos[:, 1], c=et, cmap="viridis", alpha=0.75, s=45)
    plt.title("Emergexia - Servicios en PCA 2D")
    plt.xlabel("Componente principal 1 (PC1)")
    plt.ylabel("Componente principal 2 (PC2)")
    plt.colorbar(sc, label="Perfil K-Means")
    plt.grid(alpha=0.2)
    plt.tight_layout()
    plt.savefig(f"{CARPETA_RESULTADOS}/p09_pca_2d.png", dpi=300)
    plt.close()


def visualizar_3d(datos, et):
    fig = plt.figure(figsize=(10, 7))
    eje = fig.add_subplot(111, projection="3d")
    sc = eje.scatter(datos[:, 0], datos[:, 1], datos[:, 2], c=et, cmap="viridis", alpha=0.75, s=35)
    eje.set_title("Emergexia - Servicios en PCA 3D")
    eje.set_xlabel("PC1")
    eje.set_ylabel("PC2")
    eje.set_zlabel("PC3")
    fig.colorbar(sc, ax=eje, label="Perfil K-Means", shrink=0.7)
    plt.tight_layout()
    plt.savefig(f"{CARPETA_RESULTADOS}/p09_pca_3d.png", dpi=300)
    plt.close()


# ================================================================
# 9. ERROR DE RECONSTRUCCION
# ================================================================

def evaluar_reconstruccion(X_esc, datos, pca, n):
    """Reconstruye con las primeras n componentes y mide el MSE."""
    rec = datos[:, :n] @ pca.components_[:n, :] + pca.mean_
    error = mean_squared_error(X_esc, rec)
    print("\n" + "=" * 60)
    print("RECONSTRUCCION")
    print("=" * 60)
    print("Componentes usadas:", n)
    print("Error cuadratico medio:", round(error, 6))
    return rec, error


# ================================================================
# 10. EXPORTAR
# ================================================================

def exportar(df, datos, et, rec, escalador):
    coords = pd.DataFrame({"id_servicio": df["id_servicio"], "cluster": et,
                           **{c: datos[:, i] for i, c in enumerate(COMPONENTES)}})
    coords.to_csv(f"{CARPETA_RESULTADOS}/p09_coordenadas_pca.csv", index=False)

    reconstruidos = pd.DataFrame(escalador.inverse_transform(rec), columns=VARIABLES)
    reconstruidos.insert(0, "id_servicio", df["id_servicio"].to_numpy())
    reconstruidos.to_csv(f"{CARPETA_RESULTADOS}/p09_datos_reconstruidos.csv", index=False)
    print("\nCoordenadas y datos reconstruidos exportados.")


# ================================================================
# 11. FUNCION PRINCIPAL
# ================================================================

def main():
    print("\n" + "=" * 65)
    print("EMERGEXIA - PRACTICA 09")
    print("REDUCCION DE DIMENSIONALIDAD MEDIANTE PCA")
    print("=" * 65)

    df = cargar_datos()
    X_esc, escalador = estandarizar(preparar_datos(df))
    et = obtener_clusters(df, X_esc)
    pca, datos, acumulada = entrenar_pca(X_esc)
    df_v = tabla_varianza(pca)
    analizar_cargas(pca)
    n = determinar_componentes(pca)
    graficar_varianza(df_v)
    visualizar_2d(datos, et)
    visualizar_3d(datos, et)
    rec, error = evaluar_reconstruccion(X_esc, datos, pca, n)
    exportar(df, datos, et, rec, escalador)

    print("\n" + "=" * 65)
    print("RESUMEN FINAL DE LA PRACTICA 09")
    print("=" * 65)
    print("Servicios analizados:", len(df))
    print("Variables originales:", len(VARIABLES))
    print("Varianza de PC1:", round(pca.explained_variance_ratio_[0] * 100, 2), "%")
    print("Varianza acumulada PC1 y PC2:", round(acumulada[1] * 100, 2), "%")
    print("Componentes seleccionadas:", n)
    print("Error de reconstruccion:", round(error, 6))
    print("Archivos generados en:", CARPETA_RESULTADOS)


if __name__ == "__main__":
    main()
