# ============================================================
# PROYECTO: EMERGEXIA
# PRACTICA 10 - ETAPA 5: MOTOR INTELIGENTE DE RECOMENDACIONES
# ARCHIVO: p14_motor_recomendaciones_emergencias.py
#
# Ya tenemos los tres modelos guardados (.joblib):
#   Modelo          Resultado
#   Random Forest   Estima si la emergencia es critica (p11)
#   K-Means         Perfil de riesgo: bajo, moderado, medio-alto, alto (p12)
#   PCA             Reduce las 4 variables a 2 componentes (p13)
#
# Nota: PCA conserva solo ~52% de la variabilidad. Sirve para ubicar
# la emergencia en la grafica, pero las decisiones se toman con las
# 4 variables originales.
#
# Objetivo:
# Capturar una emergencia, analizarla con los tres modelos y generar
# recomendaciones para el Administrador (prioridad, ambulancia, apoyo).
# ============================================================


# ------------------------------------------------------------
# 1. LIBRERIAS
# ------------------------------------------------------------
import os
import joblib
import numpy as np
import pandas as pd


# ------------------------------------------------------------
# 2. CONFIGURACION
# ------------------------------------------------------------
DIRECTORIO_BASE = os.path.dirname(os.path.abspath(__file__))

DIRECTORIO_RESULTADOS = os.path.join(DIRECTORIO_BASE, "resultados_sistema_inteligente")
DIRECTORIO_MODELOS = os.path.join(DIRECTORIO_RESULTADOS, "modelos")

ARCHIVO_RANDOM_FOREST = os.path.join(DIRECTORIO_MODELOS, "modelo_emergexia.joblib")
ARCHIVO_KMEANS = os.path.join(DIRECTORIO_MODELOS, "modelo_kmeans_emergexia.joblib")
ARCHIVO_PCA = os.path.join(DIRECTORIO_MODELOS, "modelo_pca_emergexia.joblib")

CARACTERISTICAS = ["edad", "frecuencia_cardiaca", "saturacion_oxigeno", "distancia_km"]

# Regla del proyecto: si hay mas de 3 ambulancias ocupadas,
# se pide apoyo a otros hospitales.
LIMITE_AMBULANCIAS_OCUPADAS = 3


# ------------------------------------------------------------
# 3. CARGAR LOS TRES MODELOS
# ------------------------------------------------------------
def cargar_modelos():

    print("\nCARGANDO MODELOS...")

    for archivo in [ARCHIVO_RANDOM_FOREST, ARCHIVO_KMEANS, ARCHIVO_PCA]:
        if not os.path.exists(archivo):
            raise FileNotFoundError(f"No se encontro {archivo}. Ejecuta primero p11, p12 y p13.")

    supervisado = joblib.load(ARCHIVO_RANDOM_FOREST)
    kmeans = joblib.load(ARCHIVO_KMEANS)
    pca = joblib.load(ARCHIVO_PCA)

    print("Random Forest, K-Means y PCA cargados.")

    return {
        "supervisado": supervisado["modelo"],
        "kmeans": kmeans["modelo"],
        "escalador_kmeans": kmeans["escalador"],
        "mapa_perfiles": kmeans["mapa_perfiles"],
        "pca": pca["modelo_pca"],
        "escalador_pca": pca["escalador"]
    }


# ------------------------------------------------------------
# 4. CAPTURAR LA EMERGENCIA
# ------------------------------------------------------------
def pedir_numero(mensaje, minimo, maximo):
    """Pide un numero y valida que este dentro del rango."""
    valor = float(input(mensaje))

    if not np.isfinite(valor) or not minimo <= valor <= maximo:
        raise ValueError(f"El valor debe estar entre {minimo} y {maximo}.")

    return valor


def capturar_emergencia():

    print("\nDATOS DE LA EMERGENCIA")
    print("-" * 45)

    emergencia = pd.DataFrame([{
        "edad": pedir_numero("Edad del paciente (0-110): ", 0, 110),
        "frecuencia_cardiaca": pedir_numero("Frecuencia cardiaca (20-250 lpm): ", 20, 250),
        "saturacion_oxigeno": pedir_numero("Saturacion de oxigeno (50-100 %): ", 50, 100),
        "distancia_km": pedir_numero("Distancia al Hospital IMSS 220 (0-100 km): ", 0, 100)
    }], columns=CARACTERISTICAS)

    ocupadas = int(pedir_numero("Ambulancias ocupadas en este momento (0-20): ", 0, 20))

    return emergencia, ocupadas


# ------------------------------------------------------------
# 5. PREDICCION SUPERVISADA: ES CRITICA?
# ------------------------------------------------------------
def predecir_criticidad(emergencia, modelo):

    prediccion = int(modelo.predict(emergencia)[0])

    # Relacionamos cada probabilidad con su clase.
    probabilidades = dict(zip(modelo.classes_, modelo.predict_proba(emergencia)[0]))

    resultado = "EMERGENCIA CRITICA" if prediccion == 1 else "EMERGENCIA NO CRITICA"

    print("\nAPRENDIZAJE SUPERVISADO (Random Forest)")
    print("Resultado:", resultado)
    print(f"Probabilidad de ser critica: {probabilidades.get(1, 0) * 100:.2f}%")

    return {
        "prediccion": prediccion,
        "resultado": resultado,
        "probabilidad_critica": float(probabilidades.get(1, 0)),
        "probabilidad_no_critica": float(probabilidades.get(0, 0))
    }


# ------------------------------------------------------------
# 6. PERFIL DE RIESGO CON K-MEANS
# ------------------------------------------------------------
def identificar_perfil(emergencia, modelo, escalador, mapa_perfiles):

    # Usamos el escalador que se entreno con K-Means (solo transform).
    cluster = int(modelo.predict(escalador.transform(emergencia))[0])
    perfil = mapa_perfiles[cluster]

    print("\nAPRENDIZAJE NO SUPERVISADO (K-Means)")
    print("Cluster:", cluster, "| Perfil:", perfil)

    return {"cluster": cluster, "perfil": perfil}


# ------------------------------------------------------------
# 7. UBICACION EN PCA
# ------------------------------------------------------------
def proyectar_pca(emergencia, modelo_pca, escalador):

    pc = modelo_pca.transform(escalador.transform(emergencia))[0]

    print("\nPCA")
    print(f"PC1 = {pc[0]:.4f} | PC2 = {pc[1]:.4f}")

    return {"PC1": float(pc[0]), "PC2": float(pc[1])}


# ------------------------------------------------------------
# 8. MOTOR DE REGLAS
# ------------------------------------------------------------
def generar_recomendaciones(emergencia, prediccion, perfil, ocupadas):

    edad = emergencia["edad"].iloc[0]
    fc = emergencia["frecuencia_cardiaca"].iloc[0]
    oxigeno = emergencia["saturacion_oxigeno"].iloc[0]
    distancia = emergencia["distancia_km"].iloc[0]

    recomendaciones = []

    # ---------- REGLA 1: PRIORIDAD (modelo + perfil) ----------
    if prediccion["prediccion"] == 1 and perfil["perfil"] == "Riesgo alto":
        prioridad = "PRIORIDAD 1 - INMEDIATA"
        recomendaciones.append("Asignar de inmediato la ambulancia libre mas cercana.")
    elif prediccion["prediccion"] == 1:
        prioridad = "PRIORIDAD 2 - URGENTE"
        recomendaciones.append("Asignar ambulancia lo antes posible y dar seguimiento.")
    else:
        prioridad = "PRIORIDAD 3 - NO URGENTE"
        recomendaciones.append("Atender segun disponibilidad de ambulancias.")

    # ---------- REGLA 2: SATURACION DE OXIGENO ----------
    if oxigeno < 90:
        recomendaciones.append("Oxigeno bajo: enviar ambulancia con oxigeno suplementario listo.")
    elif oxigeno < 94:
        recomendaciones.append("Oxigeno ligeramente bajo: vigilar la saturacion durante el traslado.")
    else:
        recomendaciones.append("Saturacion de oxigeno en rango aceptable.")

    # ---------- REGLA 3: FRECUENCIA CARDIACA ----------
    if fc > 120 or fc < 50:
        recomendaciones.append("Frecuencia cardiaca anormal: enviar unidad con monitor cardiaco.")
    elif fc > 100 or fc < 60:
        recomendaciones.append("Frecuencia cardiaca fuera de lo normal: monitorear en el traslado.")
    else:
        recomendaciones.append("Frecuencia cardiaca en rango normal.")

    # ---------- REGLA 4: EDAD ----------
    if edad >= 65:
        recomendaciones.append("Paciente adulto mayor: avisar al hospital para preparar su recepcion.")
    elif edad < 12:
        recomendaciones.append("Paciente pediatrico: confirmar que la unidad lleve equipo pediatrico.")

    # ---------- REGLA 5: DISTANCIA ----------
    if distancia > 15:
        recomendaciones.append("Emergencia lejana: verificar que la ambulancia tenga gasolina suficiente.")
    elif distancia > 8:
        recomendaciones.append("Distancia media: elegir la ruta con menos trafico.")
    else:
        recomendaciones.append("Emergencia cercana al Hospital IMSS 220.")

    # ---------- REGLA 6: DISPONIBILIDAD DE AMBULANCIAS ----------
    if ocupadas > LIMITE_AMBULANCIAS_OCUPADAS:
        recomendaciones.append(
            f"Hay {ocupadas} ambulancias ocupadas (mas de {LIMITE_AMBULANCIAS_OCUPADAS}): "
            "solicitar apoyo a otros hospitales."
        )

    # ---------- REGLA 7: PERFIL K-MEANS ----------
    recomendaciones.append(f"Perfil identificado por K-Means: {perfil['perfil']}.")

    print("\nMOTOR DE RECOMENDACIONES")
    print("Prioridad:", prioridad)
    for i, texto in enumerate(recomendaciones, start=1):
        print(f"{i}. {texto}")

    return prioridad, recomendaciones


# ------------------------------------------------------------
# 9. GENERAR Y GUARDAR EL REPORTE
# ------------------------------------------------------------
def generar_reporte(emergencia, ocupadas, prediccion, perfil, pca, prioridad, recomendaciones):

    reporte = {
        **{c: float(emergencia[c].iloc[0]) for c in CARACTERISTICAS},
        "ambulancias_ocupadas": ocupadas,
        "prediccion": prediccion["prediccion"],
        "resultado": prediccion["resultado"],
        "probabilidad_critica": prediccion["probabilidad_critica"],
        "probabilidad_no_critica": prediccion["probabilidad_no_critica"],
        "cluster": perfil["cluster"],
        "perfil": perfil["perfil"],
        "PC1": pca["PC1"],
        "PC2": pca["PC2"],
        "prioridad": prioridad,
        "recomendaciones": " | ".join(recomendaciones)
    }

    archivo = os.path.join(DIRECTORIO_RESULTADOS, "reporte_emergencia.csv")
    pd.DataFrame([reporte]).to_csv(archivo, index=False, encoding="utf-8")

    print("\nReporte exportado:", archivo)
    return reporte


# ------------------------------------------------------------
# 10. MOSTRAR EL RESULTADO FINAL
# ------------------------------------------------------------
def mostrar_resultado(reporte):

    print("\n" + "=" * 60)
    print("REPORTE INTELIGENTE EMERGEXIA")
    print("=" * 60)

    print("\nResultado del modelo:", reporte["resultado"])
    print(f"Probabilidad de ser critica: {reporte['probabilidad_critica'] * 100:.2f}%")
    print("Perfil de riesgo:", reporte["perfil"])
    print(f"PCA: PC1 = {reporte['PC1']:.4f} | PC2 = {reporte['PC2']:.4f}")
    print("\n>>>", reporte["prioridad"], "<<<")

    print("\nRECOMENDACIONES:")
    for i, texto in enumerate(reporte["recomendaciones"].split(" | "), start=1):
        print(f"{i}. {texto}")

    print("\n" + "=" * 60)
    print("IMPORTANTE: los resultados son estimaciones de apoyo para el")
    print("Administrador. No sustituyen la valoracion del personal medico.")
    print("=" * 60)


# ------------------------------------------------------------
# 11. PROGRAMA PRINCIPAL
# ------------------------------------------------------------
def main():

    print("\n" + "=" * 60)
    print("EMERGEXIA - ETAPA 5: MOTOR DE RECOMENDACIONES")
    print("=" * 60)

    modelos = cargar_modelos()
    emergencia, ocupadas = capturar_emergencia()

    prediccion = predecir_criticidad(emergencia, modelos["supervisado"])
    perfil = identificar_perfil(emergencia, modelos["kmeans"], modelos["escalador_kmeans"], modelos["mapa_perfiles"])
    pca = proyectar_pca(emergencia, modelos["pca"], modelos["escalador_pca"])

    prioridad, recomendaciones = generar_recomendaciones(emergencia, prediccion, perfil, ocupadas)

    reporte = generar_reporte(emergencia, ocupadas, prediccion, perfil, pca, prioridad, recomendaciones)
    mostrar_resultado(reporte)


if __name__ == "__main__":
    main()
