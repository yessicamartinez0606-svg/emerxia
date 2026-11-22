# ============================================================
# PROYECTO: EMERGEXIA
# PRACTICA 10 - ETAPA 3: APRENDIZAJE NO SUPERVISADO
# ALGORITMO: K-MEANS
# ARCHIVO: p12_kmeans_emergencias.py
#
# OBJETIVO:
# Identificar grupos de emergencias con caracteristicas similares.
#
# A diferencia de la etapa 2, aqui NO predecimos si la emergencia es
# critica. Buscamos patrones en los datos del paciente, por ejemplo:
#   - Emergencias de riesgo bajo.
#   - Emergencias de riesgo moderado.
#   - Emergencias de riesgo alto.
#
# K-Means no conoce estas categorias: las descubre matematicamente
# y nosotros interpretamos despues los grupos.
#
# Variables que usa K-Means:
#   edad                 Edad del paciente.
#   frecuencia_cardiaca  Latidos por minuto.
#   saturacion_oxigeno   Oxigeno en sangre (%).
#   distancia_km         Distancia al Hospital IMSS 220.
#
# NO usamos "critica" ni "id_emergencia" para entrenar.
#
# Como funciona K-Means:
#   1. Elegimos K (numero de grupos).
#   2. Se colocan K centroides iniciales.
#   3. Cada emergencia se asigna al centroide mas cercano.
#   4. Se recalcula el centro de cada grupo.
#   5. Se repite hasta que los grupos ya no cambian.
# ============================================================


# ------------------------------------------------------------
# 1. LIBRERIAS
# ------------------------------------------------------------
import os
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score


# ------------------------------------------------------------
# 2. CONFIGURACION
# ------------------------------------------------------------
DIRECTORIO_BASE = os.path.dirname(os.path.abspath(__file__))

DIRECTORIO_RESULTADOS = os.path.join(DIRECTORIO_BASE, "resultados_sistema_inteligente")
ARCHIVO_DATOS = os.path.join(DIRECTORIO_RESULTADOS, "emergexia_datos.csv")
DIRECTORIO_MODELOS = os.path.join(DIRECTORIO_RESULTADOS, "modelos")
os.makedirs(DIRECTORIO_MODELOS, exist_ok=True)

SEMILLA = 42
VALORES_K = range(2, 7)

# Mostrar todas las columnas al imprimir tablas.
pd.set_option("display.width", 200)
pd.set_option("display.max_columns", None)

CARACTERISTICAS = ["edad", "frecuencia_cardiaca", "saturacion_oxigeno", "distancia_km"]


# ------------------------------------------------------------
# 3. CARGAR Y VALIDAR LOS DATOS
# ------------------------------------------------------------
def cargar_datos():

    print("\nCARGANDO DATASET EMERGEXIA...")

    if not os.path.exists(ARCHIVO_DATOS):
        raise FileNotFoundError(f"No se encontro {ARCHIVO_DATOS}. Ejecuta primero p10_datos_emergencias.py")

    datos = pd.read_csv(ARCHIVO_DATOS)
    columnas = ["id_emergencia"] + CARACTERISTICAS

    faltantes = [c for c in columnas if c not in datos.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas: {faltantes}")

    datos[CARACTERISTICAS] = datos[CARACTERISTICAS].apply(pd.to_numeric, errors="coerce")

    if datos[columnas].isnull().any().any():
        raise ValueError("Hay valores nulos o no numericos.")

    if not np.isfinite(datos[CARACTERISTICAS].to_numpy()).all():
        raise ValueError("Hay valores infinitos.")

    print("Dataset cargado. Total de emergencias:", len(datos))
    return datos


# ------------------------------------------------------------
# 4. ESCALAR LAS CARACTERISTICAS
# ------------------------------------------------------------
def preparar_datos(datos):

    # K-Means usa distancias. Sin escalar, la frecuencia cardiaca
    # (40 a 180) pesaria mas que la distancia (0.5 a 25 km).
    X = datos[CARACTERISTICAS]

    escalador = StandardScaler()
    X_escalado = escalador.fit_transform(X)

    print("\nCaracteristicas utilizadas:", ", ".join(CARACTERISTICAS))
    print("Escalamiento completado.")

    return X_escalado, escalador


# ------------------------------------------------------------
# 5. PROBAR DIFERENTES VALORES DE K
# ------------------------------------------------------------
def evaluar_k(X_escalado):

    print("\nEVALUANDO K = 2 a 6...")

    resultados = []

    for k in VALORES_K:
        modelo = KMeans(n_clusters=k, init="k-means++", n_init=20, random_state=SEMILLA)
        etiquetas = modelo.fit_predict(X_escalado)

        resultados.append({
            "k": k,
            "inercia": modelo.inertia_,                          # que tan compactos son los grupos
            "silhouette": silhouette_score(X_escalado, etiquetas)  # que tan separados estan
        })

        print(f"K={k} | Inercia={modelo.inertia_:.2f} | Silhouette={resultados[-1]['silhouette']:.4f}")

    resultados = pd.DataFrame(resultados)
    resultados.to_csv(os.path.join(DIRECTORIO_RESULTADOS, "evaluacion_kmeans.csv"), index=False)

    return resultados


# ------------------------------------------------------------
# 6. GRAFICAS DEL CODO Y SILHOUETTE
# ------------------------------------------------------------
def graficar_evaluacion(resultados):

    fig, ejes = plt.subplots(1, 2, figsize=(12, 4))

    ejes[0].plot(resultados["k"], resultados["inercia"], marker="o")
    ejes[0].set_title("Emergexia - Metodo del codo")
    ejes[0].set_xlabel("Numero de grupos (K)")
    ejes[0].set_ylabel("Inercia")

    ejes[1].plot(resultados["k"], resultados["silhouette"], marker="o")
    ejes[1].set_title("Emergexia - Silhouette")
    ejes[1].set_xlabel("Numero de grupos (K)")
    ejes[1].set_ylabel("Silhouette")

    for eje in ejes:
        eje.set_xticks(list(VALORES_K))
        eje.grid(alpha=0.3)

    plt.tight_layout()
    archivo = os.path.join(DIRECTORIO_RESULTADOS, "grafica_codo_silhouette.png")
    plt.savefig(archivo, dpi=300)
    plt.show()

    print("\nGrafica guardada:", archivo)


# ------------------------------------------------------------
# 7. ELEGIR EL MEJOR K
# ------------------------------------------------------------
def seleccionar_k(resultados):

    mejor = resultados.loc[resultados["silhouette"].idxmax()]
    mejor_k = int(mejor["k"])

    print("\nMEJOR K:", mejor_k, "| Silhouette:", round(mejor["silhouette"], 4))
    return mejor_k


# ------------------------------------------------------------
# 8. PONER NOMBRE A LOS GRUPOS
# ------------------------------------------------------------
def nombrar_grupos(centroides):
    """
    Calcula un puntaje de riesgo para cada centroide (misma idea que
    en p10_datos_emergencias.py) y ordena los grupos de menor a mayor riesgo.
    Este puntaje solo sirve para describir los grupos.
    """
    riesgo = (
        (centroides["edad"] / 95) * 0.20 +
        (abs(centroides["frecuencia_cardiaca"] - 80) / 100) * 0.30 +
        ((100 - centroides["saturacion_oxigeno"]) / 25) * 0.35 +
        (centroides["distancia_km"] / 25) * 0.15
    )

    orden = riesgo.sort_values().index.tolist()

    if len(orden) == 2:
        nombres = ["Riesgo bajo", "Riesgo alto"]
    elif len(orden) == 3:
        nombres = ["Riesgo bajo", "Riesgo moderado", "Riesgo alto"]
    elif len(orden) == 4:
        nombres = ["Riesgo bajo", "Riesgo moderado", "Riesgo medio-alto", "Riesgo alto"]
    else:
        nombres = [f"Perfil {i + 1} (menor a mayor riesgo)" for i in range(len(orden))]

    return {int(cluster): nombre for cluster, nombre in zip(orden, nombres)}


# ------------------------------------------------------------
# 9. ENTRENAR EL MODELO FINAL Y GUARDARLO
# ------------------------------------------------------------
def entrenar_modelo(X_escalado, escalador, datos, mejor_k):

    print("\nENTRENANDO MODELO FINAL CON K =", mejor_k)

    modelo = KMeans(n_clusters=mejor_k, init="k-means++", n_init=20, random_state=SEMILLA)
    etiquetas = modelo.fit_predict(X_escalado)

    # Centroides en unidades originales (anios, lpm, %, km).
    centroides = pd.DataFrame(escalador.inverse_transform(modelo.cluster_centers_), columns=CARACTERISTICAS)

    mapa_perfiles = nombrar_grupos(centroides)
    centroides["perfil"] = [mapa_perfiles[i] for i in range(mejor_k)]

    print("\nPERFILES IDENTIFICADOS (centroides):")
    print(centroides.round(2).to_string())

    resultados = datos.copy()
    resultados["cluster"] = etiquetas
    resultados["perfil"] = [mapa_perfiles[int(c)] for c in etiquetas]

    print("\nEMERGENCIAS POR PERFIL:")
    print(resultados["perfil"].value_counts())

    # Que porcentaje de cada perfil fue critico (solo para interpretar,
    # K-Means NO uso esta columna).
    if "critica" in resultados.columns:
        print("\n% DE EMERGENCIAS CRITICAS EN CADA PERFIL:")
        print((resultados.groupby("perfil")["critica"].mean() * 100).round(1))

    resumen = resultados.groupby(["cluster", "perfil"])[CARACTERISTICAS].mean().round(2)
    print("\nRESUMEN DE PERFILES:")
    print(resumen)

    resultados.to_csv(os.path.join(DIRECTORIO_RESULTADOS, "emergencias_segmentadas.csv"), index=False)
    resumen.to_csv(os.path.join(DIRECTORIO_RESULTADOS, "resumen_perfiles.csv"))

    # Guardamos el modelo, el escalador y los nombres de los perfiles.
    paquete = {
        "modelo": modelo,
        "escalador": escalador,
        "caracteristicas": CARACTERISTICAS,
        "mapa_perfiles": mapa_perfiles,
        "numero_clusters": mejor_k,
        "semilla": SEMILLA
    }

    archivo_modelo = os.path.join(DIRECTORIO_MODELOS, "modelo_kmeans_emergexia.joblib")
    joblib.dump(paquete, archivo_modelo)

    print("\nMODELO GUARDADO EN:", archivo_modelo)
    return resultados, archivo_modelo


# ------------------------------------------------------------
# 10. VISUALIZAR LOS GRUPOS
# ------------------------------------------------------------
def visualizar_grupos(resultados):

    # Mostramos 2 de las 4 variables (las 4 si participaron en K-Means).
    plt.figure(figsize=(10, 6))

    for perfil, grupo in resultados.groupby("perfil"):
        plt.scatter(grupo["frecuencia_cardiaca"], grupo["saturacion_oxigeno"], label=perfil, alpha=0.7, s=35)

    plt.title("Emergexia - Segmentacion de emergencias")
    plt.xlabel("Frecuencia cardiaca (lpm)")
    plt.ylabel("Saturacion de oxigeno (%)")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()

    archivo = os.path.join(DIRECTORIO_RESULTADOS, "segmentacion_emergencias.png")
    plt.savefig(archivo, dpi=300)
    plt.show()

    print("Grafica guardada:", archivo)


# ------------------------------------------------------------
# 11. PROBAR EL MODELO GUARDADO CON UNA EMERGENCIA NUEVA
# ------------------------------------------------------------
def probar_modelo(archivo_modelo):

    paquete = joblib.load(archivo_modelo)

    emergencia = pd.DataFrame([{
        "edad": 72,
        "frecuencia_cardiaca": 135,
        "saturacion_oxigeno": 86.0,
        "distancia_km": 8.5
    }], columns=paquete["caracteristicas"])

    grupo = paquete["modelo"].predict(paquete["escalador"].transform(emergencia))[0]

    print("\nEMERGENCIA NUEVA:")
    print(emergencia.to_string(index=False))
    print("PERFIL ASIGNADO:", paquete["mapa_perfiles"][int(grupo)])


# ------------------------------------------------------------
# 12. PROGRAMA PRINCIPAL
# ------------------------------------------------------------
def main():

    print("\n" + "=" * 60)
    print("EMERGEXIA - ETAPA 3: APRENDIZAJE NO SUPERVISADO")
    print("=" * 60)

    datos = cargar_datos()
    X_escalado, escalador = preparar_datos(datos)
    evaluacion = evaluar_k(X_escalado)
    graficar_evaluacion(evaluacion)
    mejor_k = seleccionar_k(evaluacion)
    resultados, archivo_modelo = entrenar_modelo(X_escalado, escalador, datos, mejor_k)
    visualizar_grupos(resultados)
    probar_modelo(archivo_modelo)

    print("\n" + "=" * 60)
    print("ETAPA 3 FINALIZADA CORRECTAMENTE")
    print("=" * 60)


if __name__ == "__main__":
    main()


# ------------------------------------------------------------
# COMO INTERPRETAR LOS RESULTADOS
# ------------------------------------------------------------
# A. Metodo del codo (inercia)
#    Mide que tan cerca estan las emergencias de su centroide.
#    Siempre baja al aumentar K; buscamos donde deja de bajar mucho.
#
# B. Silhouette (de -1 a 1)
#    Cercano a 1  Grupos bien separados.
#    Cercano a 0  Grupos que se traslapan.
#    Menor a 0    Posibles asignaciones incorrectas.
#
# Elegimos el K con mayor Silhouette entre 2 y 6. Es un criterio
# matematico, no garantiza que sea la mejor division para la operacion.
#
# Los grupos se nombran de menor a mayor riesgo (2, 3 o 4 grupos).
# Con 5 o 6 grupos se usan nombres genericos ordenados por riesgo.
#
# RESULTADOS OBTENIDOS:
#   K=2 0.188 | K=3 0.190 | K=4 0.216 | K=5 0.214 | K=6 0.213
#   - El mejor K fue 4, pero todos los Silhouette son bajos (~0.2):
#     los datos de p10_datos_emergencias.py se generan de forma uniforme, sin grupos
#     naturales, asi que los perfiles se traslapan bastante.
#   - Perfiles con K=4:
#     Riesgo bajo:       jovenes (23 anios), FC 120, oxigeno 94%  -> 20% criticas
#     Riesgo moderado:   adultos mayores (73), FC normal, O2 93%  -> 34% criticas
#     Riesgo medio-alto: jovenes (29), FC normal, oxigeno 81%     -> 57% criticas
#     Riesgo alto:       adultos (63), FC 145, oxigeno 84%        -> 94% criticas
#   - La distancia es casi igual en todos (~12-13 km): no influye en los grupos.
#   - Aunque K-Means no uso la columna "critica", el perfil de riesgo alto
#     tiene 94% de emergencias criticas: los grupos si tienen sentido medico.
