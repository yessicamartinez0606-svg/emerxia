# ============================================================
# PROYECTO: EMERGEXIA
# PRACTICA 10 - ETAPA 4: REDUCCION DE DIMENSIONALIDAD
# ALGORITMO: PCA
# ARCHIVO: p13_pca_emergencias.py
#
# Hasta ahora tenemos:
#   1. 500 emergencias generadas (p10_datos_emergencias.py).
#   2. Un modelo supervisado que estima si es critica (p11).
#   3. Perfiles de riesgo descubiertos con K-Means (p12).
#
# Ahora usamos PCA para reducir las 4 variables de cada emergencia
# a 2 componentes principales y asi poder:
#   - Ver que variables explican mas variabilidad.
#   - Visualizar los perfiles de riesgo en 2 dimensiones.
#   - Revisar si los grupos de K-Means se ven separados.
#   - Guardar el modelo para usarlo despues en la interfaz.
#
# Resultados principales:
#   Varianza explicada       Cuanta informacion conserva cada componente.
#   Componentes principales  Nuevas dimensiones (PC1 y PC2).
#   Grafica PCA              Emergencias coloreadas por perfil.
# ============================================================


# ------------------------------------------------------------
# 1. LIBRERIAS
# ------------------------------------------------------------
import os
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.decomposition import PCA


# ------------------------------------------------------------
# 2. CONFIGURACION
# ------------------------------------------------------------
DIRECTORIO_BASE = os.path.dirname(os.path.abspath(__file__))

DIRECTORIO_RESULTADOS = os.path.join(DIRECTORIO_BASE, "resultados_sistema_inteligente")
DIRECTORIO_MODELOS = os.path.join(DIRECTORIO_RESULTADOS, "modelos")

ARCHIVO_DATOS = os.path.join(DIRECTORIO_RESULTADOS, "emergexia_datos.csv")
ARCHIVO_SEGMENTACION = os.path.join(DIRECTORIO_RESULTADOS, "emergencias_segmentadas.csv")
ARCHIVO_MODELO_KMEANS = os.path.join(DIRECTORIO_MODELOS, "modelo_kmeans_emergexia.joblib")

# Las mismas variables que uso K-Means.
CARACTERISTICAS = ["edad", "frecuencia_cardiaca", "saturacion_oxigeno", "distancia_km"]

NUM_COMPONENTES = 2

# Orden de los perfiles para la leyenda de la grafica.
ORDEN_PERFILES = ["Riesgo bajo", "Riesgo moderado", "Riesgo medio-alto", "Riesgo alto"]


# ------------------------------------------------------------
# 3. CARGAR DATOS, SEGMENTACION Y ESCALADOR
# ------------------------------------------------------------
def cargar_datos():

    print("\nCARGANDO INFORMACION EMERGEXIA...")

    for archivo in [ARCHIVO_DATOS, ARCHIVO_SEGMENTACION, ARCHIVO_MODELO_KMEANS]:
        if not os.path.exists(archivo):
            raise FileNotFoundError(f"No se encontro {archivo}. Ejecuta primero p10 y p12.")

    datos = pd.read_csv(ARCHIVO_DATOS)
    segmentacion = pd.read_csv(ARCHIVO_SEGMENTACION)

    # Recuperamos el escalador que se entreno en la etapa K-Means.
    escalador = joblib.load(ARCHIVO_MODELO_KMEANS)["escalador"]

    # Validar columnas.
    for columna in ["id_emergencia"] + CARACTERISTICAS:
        if columna not in datos.columns:
            raise ValueError(f"Falta la columna {columna} en los datos.")

    for columna in ["id_emergencia", "cluster", "perfil"]:
        if columna not in segmentacion.columns:
            raise ValueError(f"Falta la columna {columna} en la segmentacion.")

    # Validar identificadores.
    if datos["id_emergencia"].duplicated().any() or segmentacion["id_emergencia"].duplicated().any():
        raise ValueError("Hay identificadores de emergencia duplicados.")

    if set(datos["id_emergencia"]) != set(segmentacion["id_emergencia"]):
        raise ValueError("Las emergencias de ambos archivos no coinciden.")

    # Unimos los datos con el perfil asignado por K-Means.
    datos = datos.merge(
        segmentacion[["id_emergencia", "cluster", "perfil"]],
        on="id_emergencia", how="inner", validate="one_to_one"
    )

    datos[CARACTERISTICAS] = datos[CARACTERISTICAS].apply(pd.to_numeric, errors="coerce")

    if datos[CARACTERISTICAS + ["cluster", "perfil"]].isnull().any().any():
        raise ValueError("Hay valores nulos o no numericos.")

    if not np.isfinite(datos[CARACTERISTICAS].to_numpy()).all():
        raise ValueError("Hay valores infinitos.")

    print("Datos, segmentacion y escalador cargados.")
    print("Total de emergencias:", len(datos))

    return datos, escalador


# ------------------------------------------------------------
# 4. ESCALAR CON EL MISMO ESCALADOR DE K-MEANS
# ------------------------------------------------------------
def preparar_datos(datos, escalador):

    # IMPORTANTE: usamos transform() y NO fit_transform(),
    # porque el escalador ya fue entrenado en la etapa K-Means.
    X_escalado = escalador.transform(datos[CARACTERISTICAS])

    print("\nEscalamiento aplicado con el escalador de K-Means.")
    return X_escalado


# ------------------------------------------------------------
# 5. APLICAR PCA
# ------------------------------------------------------------
def aplicar_pca(X_escalado):

    # Reducimos de 4 dimensiones a 2.
    modelo_pca = PCA(n_components=NUM_COMPONENTES)
    componentes = modelo_pca.fit_transform(X_escalado)

    print("\nPCA aplicado.")
    print("Dimensiones originales:", X_escalado.shape[1])
    print("Dimensiones resultantes:", componentes.shape[1])

    return modelo_pca, componentes


# ------------------------------------------------------------
# 6. VARIANZA EXPLICADA
# ------------------------------------------------------------
def analizar_varianza(modelo_pca):

    varianza = modelo_pca.explained_variance_ratio_
    acumulada = np.cumsum(varianza)

    print("\nVARIANZA EXPLICADA:")
    for i, valor in enumerate(varianza):
        print(f"PC{i + 1}: {valor * 100:.2f}%")
    print(f"Total conservado: {acumulada[-1] * 100:.2f}%")

    tabla = pd.DataFrame({
        "componente": ["PC1", "PC2"],
        "varianza_explicada": varianza,
        "varianza_porcentual": varianza * 100,
        "varianza_acumulada": acumulada * 100
    })

    tabla.to_csv(os.path.join(DIRECTORIO_RESULTADOS, "varianza_explicada_pca.csv"), index=False)
    return tabla


# ------------------------------------------------------------
# 7. CARGAS: CUANTO APORTA CADA VARIABLE
# ------------------------------------------------------------
def analizar_cargas(modelo_pca):

    # Fila = componente | Columna = variable original.
    # Valores cercanos a +1 o -1 = la variable aporta mucho.
    cargas = pd.DataFrame(modelo_pca.components_, columns=CARACTERISTICAS, index=["PC1", "PC2"])

    print("\nCARGAS DE LOS COMPONENTES:")
    print(cargas.round(4))

    cargas.to_csv(os.path.join(DIRECTORIO_RESULTADOS, "cargas_componentes_pca.csv"))
    return cargas


# ------------------------------------------------------------
# 8. GUARDAR PC1 Y PC2 DE CADA EMERGENCIA
# ------------------------------------------------------------
def crear_resultados(datos, componentes):

    resultados = datos.copy()
    resultados["PC1"] = componentes[:, 0]
    resultados["PC2"] = componentes[:, 1]

    archivo = os.path.join(DIRECTORIO_RESULTADOS, "emergencias_pca.csv")
    resultados.to_csv(archivo, index=False)

    print("\nArchivo generado:", archivo)
    return resultados


# ------------------------------------------------------------
# 9. GRAFICAS
# ------------------------------------------------------------
def graficar(tabla_varianza, cargas, resultados):

    # 9.1 Varianza explicada
    plt.figure(figsize=(8, 5))
    plt.bar(tabla_varianza["componente"], tabla_varianza["varianza_porcentual"])
    plt.title("Emergexia - Varianza explicada por PCA")
    plt.xlabel("Componentes principales")
    plt.ylabel("Varianza explicada (%)")
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(DIRECTORIO_RESULTADOS, "grafica_varianza_pca.png"), dpi=300)
    plt.show()

    # 9.2 Emergencias en 2D coloreadas por perfil de riesgo
    plt.figure(figsize=(10, 7))

    perfiles = [p for p in ORDEN_PERFILES if p in resultados["perfil"].unique()]
    perfiles += [p for p in resultados["perfil"].unique() if p not in perfiles]

    for perfil in perfiles:
        grupo = resultados[resultados["perfil"] == perfil]
        plt.scatter(grupo["PC1"], grupo["PC2"], label=perfil, alpha=0.75, s=40)

    # Flechas: hacia donde "jala" cada variable original.
    for variable in CARACTERISTICAS:
        x, y = cargas.loc["PC1", variable] * 2.5, cargas.loc["PC2", variable] * 2.5
        plt.arrow(0, 0, x, y, color="black", width=0.01, head_width=0.08)
        plt.text(x * 1.12, y * 1.12, variable, fontsize=9)

    plt.axhline(0, linewidth=0.7, alpha=0.4)
    plt.axvline(0, linewidth=0.7, alpha=0.4)
    plt.title("Emergexia - Perfiles de riesgo mediante PCA")
    plt.xlabel(f"PC1 ({tabla_varianza.loc[0, 'varianza_porcentual']:.1f}%)")
    plt.ylabel(f"PC2 ({tabla_varianza.loc[1, 'varianza_porcentual']:.1f}%)")
    plt.legend(title="Perfil de riesgo")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(DIRECTORIO_RESULTADOS, "grafica_segmentacion_pca.png"), dpi=300)
    plt.show()

    print("Graficas guardadas en:", DIRECTORIO_RESULTADOS)


# ------------------------------------------------------------
# 10. GUARDAR EL MODELO PCA
# ------------------------------------------------------------
def guardar_modelo_pca(modelo_pca, escalador):

    # Guardamos PCA junto con el escalador para transformar
    # nuevas emergencias exactamente igual.
    paquete = {
        "modelo_pca": modelo_pca,
        "escalador": escalador,
        "caracteristicas": CARACTERISTICAS,
        "numero_componentes": NUM_COMPONENTES
    }

    archivo = os.path.join(DIRECTORIO_MODELOS, "modelo_pca_emergexia.joblib")
    joblib.dump(paquete, archivo)

    print("\nMODELO PCA GUARDADO EN:", archivo)
    return archivo


# ------------------------------------------------------------
# 11. PROBAR CON UNA EMERGENCIA NUEVA
# ------------------------------------------------------------
def probar_modelo(archivo):

    paquete = joblib.load(archivo)

    emergencia = pd.DataFrame([{
        "edad": 72,
        "frecuencia_cardiaca": 135,
        "saturacion_oxigeno": 86.0,
        "distancia_km": 8.5
    }], columns=paquete["caracteristicas"])

    pc = paquete["modelo_pca"].transform(paquete["escalador"].transform(emergencia))[0]

    print("\nEMERGENCIA NUEVA:")
    print(emergencia.to_string(index=False))
    print(f"Coordenadas PCA -> PC1 = {pc[0]:.3f} | PC2 = {pc[1]:.3f}")


# ------------------------------------------------------------
# 12. PROGRAMA PRINCIPAL
# ------------------------------------------------------------
def main():

    print("\n" + "=" * 60)
    print("EMERGEXIA - ETAPA 4: ANALISIS DE COMPONENTES PRINCIPALES")
    print("=" * 60)

    datos, escalador = cargar_datos()
    X_escalado = preparar_datos(datos, escalador)
    modelo_pca, componentes = aplicar_pca(X_escalado)
    tabla_varianza = analizar_varianza(modelo_pca)
    cargas = analizar_cargas(modelo_pca)
    resultados = crear_resultados(datos, componentes)
    graficar(tabla_varianza, cargas, resultados)
    archivo = guardar_modelo_pca(modelo_pca, escalador)
    probar_modelo(archivo)

    print("\n" + "=" * 60)
    print("ETAPA 4 FINALIZADA CORRECTAMENTE")
    print("=" * 60)


if __name__ == "__main__":
    main()


# ------------------------------------------------------------
# COMO INTERPRETAR LOS RESULTADOS
# ------------------------------------------------------------
# A. Varianza explicada (resultados obtenidos)
#    PC1: 26.42% | PC2: 25.29% | Total: 51.71%
#    - Las 2 componentes conservan solo la mitad de la informacion.
#    - Es normal con estos datos: en p10_datos_emergencias.py las 4 variables se
#      generan de forma independiente (no estan relacionadas entre si),
#      asi que cada una aporta ~25% y PCA no puede resumirlas en pocas.
#    - Si las variables estuvieran relacionadas (por ejemplo, mas edad
#      con menos oxigeno), PC1 y PC2 conservarian mucho mas.
#
# B. Cargas de los componentes
#    PC1: saturacion_oxigeno (0.71) y edad (0.66)
#         -> eje "edad / oxigeno": a la derecha pacientes mayores con
#            buen oxigeno; a la izquierda jovenes con oxigeno bajo.
#    PC2: frecuencia_cardiaca (0.74) y distancia_km (-0.52)
#         -> eje "corazon / distancia": arriba frecuencia cardiaca alta,
#            abajo emergencias lejanas.
#    Las flechas de la grafica muestran hacia donde jala cada variable.
#
# C. Grafica de segmentacion PCA
#    - Riesgo alto (rojo): arriba, frecuencia cardiaca alta.
#    - Riesgo moderado (naranja): a la derecha, adultos mayores con
#      buen oxigeno.
#    - Riesgo medio-alto (verde): a la izquierda, oxigeno bajo.
#    - Riesgo bajo (azul): en el centro, mezclado con los demas.
#    Los grupos se ven bastante separados aunque PCA solo conserva el 52%.
#    Que se traslapen un poco no significa que K-Means haya fallado:
#    parte de la separacion esta en la informacion que PC1 y PC2 no muestran.
