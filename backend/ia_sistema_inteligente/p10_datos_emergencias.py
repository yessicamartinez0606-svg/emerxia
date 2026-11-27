# ============================================================
# PROYECTO: EMERGEXIA
# Sistema de gestion medica y de emergencias
# PRACTICA 10 - SISTEMA INTELIGENTE
# ARCHIVO: p10_datos_emergencias.py
#
# OBJETIVO:
# Desarrollar un sistema inteligente que analice la informacion de
# cada emergencia reportada para estimar su prioridad, identificar
# perfiles de pacientes y dar recomendaciones al Administrador.
#
# El sistema integrara:
# 1. ML supervisado: clasificacion para estimar si la emergencia es critica.
# 2. ML no supervisado: K-Means para identificar perfiles de emergencia.
# 3. Reduccion de dimensionalidad: PCA para visualizar los patrones.
# 4. Sistema basado en reglas: recomendaciones (prioridad, ambulancia, apoyo).
# 5. Interfaz grafica: captura y resultados con Python y Tkinter.
# 6. Base de datos: almacenamiento de emergencias y resultados.
#
# Datos que recibe el sistema por cada emergencia:
#   Variable              Descripcion
#   edad                  Edad del paciente (anios)
#   frecuencia_cardiaca   Latidos por minuto
#   saturacion_oxigeno    Porcentaje de oxigeno en sangre (SpO2)
#   distancia_km          Distancia del lugar al Hospital IMSS 220 (Toluca)
#   critica               Variable objetivo: 1 = critica, 0 = no critica
#
# En este archivo solo GENERAMOS los datos. Los demas analisis se
# haran en los siguientes archivos de la practica.
# ============================================================


# ------------------------------------------------------------
# 1. LIBRERIAS
# ------------------------------------------------------------
import numpy as np
import pandas as pd
from pathlib import Path


# ------------------------------------------------------------
# 2. CONFIGURACION
# ------------------------------------------------------------
SEMILLA = 42
TOTAL_EMERGENCIAS = 500

# La carpeta se crea JUNTO A ESTE ARCHIVO, sin importar desde
# donde se ejecute el programa (asi la encuentran p11, p12, p13...).
RUTA_RESULTADOS = Path(__file__).resolve().parent / "resultados_sistema_inteligente"
RUTA_RESULTADOS.mkdir(parents=True, exist_ok=True)


# ------------------------------------------------------------
# 3. GENERAR LAS EMERGENCIAS
# ------------------------------------------------------------
def generar_datos_emergencias():
    """
    Genera emergencias simuladas (datos sinteticos, solo para practicar).
    """

    np.random.seed(SEMILLA)

    edad = np.random.uniform(1, 95, TOTAL_EMERGENCIAS)
    frecuencia_cardiaca = np.random.uniform(40, 180, TOTAL_EMERGENCIAS)
    saturacion_oxigeno = np.random.uniform(75, 100, TOTAL_EMERGENCIAS)
    distancia_km = np.random.uniform(0.5, 25, TOTAL_EMERGENCIAS)

    # --------------------------------------------------------
    # 3.1 Convertir cada variable a un riesgo de 0 a 100
    # --------------------------------------------------------
    # Mas edad = mas riesgo.
    riesgo_edad = (edad / 95) * 100

    # Lo normal son ~80 lpm. Mientras mas se aleje, mas riesgo.
    riesgo_corazon = np.clip(np.abs(frecuencia_cardiaca - 80) / 100 * 100, 0, 100)

    # Lo normal es 100%. Mientras mas baje, mas riesgo.
    riesgo_oxigeno = (100 - saturacion_oxigeno) / 25 * 100

    # Mas lejos del hospital = mas tiempo de traslado = mas riesgo.
    riesgo_distancia = (distancia_km / 25) * 100

    # --------------------------------------------------------
    # 3.2 Puntuacion de gravedad (ponderada)
    # --------------------------------------------------------
    gravedad = (
        riesgo_edad * 0.20 +
        riesgo_corazon * 0.30 +
        riesgo_oxigeno * 0.35 +
        riesgo_distancia * 0.15
    )

    # Ruido para simular casos reales que no siguen la regla exacta.
    ruido = np.random.normal(0, 4, TOTAL_EMERGENCIAS)

    # 1 = Critica | 0 = No critica
    critica = ((gravedad + ruido) >= 45).astype(int)

    # --------------------------------------------------------
    # 3.3 Crear la tabla
    # --------------------------------------------------------
    datos = pd.DataFrame({
        "edad": edad.round(0).astype(int),
        "frecuencia_cardiaca": frecuencia_cardiaca.round(0).astype(int),
        "saturacion_oxigeno": saturacion_oxigeno.round(1),
        "distancia_km": distancia_km.round(2),
        "critica": critica
    })

    # Identificador de cada emergencia.
    datos.insert(0, "id_emergencia", [f"EMG-{i:04d}" for i in range(1, TOTAL_EMERGENCIAS + 1)])

    return datos


# ------------------------------------------------------------
# 4. PROGRAMA PRINCIPAL
# ------------------------------------------------------------
def main():

    print("\n" + "=" * 60)
    print("EMERGEXIA - GENERACION DE DATOS")
    print("=" * 60)

    datos = generar_datos_emergencias()

    print("\nPRIMERAS 10 EMERGENCIAS:")
    print(datos.head(10))

    print("\nDIMENSIONES DEL DATASET:")
    print(datos.shape)

    print("\nTIPOS DE DATOS:")
    print(datos.dtypes)

    print("\nVALORES NULOS:")
    print(datos.isnull().sum())

    print("\nDISTRIBUCION (1 = Critica, 0 = No critica):")
    print(datos["critica"].value_counts())

    print("\nPORCENTAJES:")
    print(datos["critica"].value_counts(normalize=True).mul(100).round(2))

    archivo = RUTA_RESULTADOS / "emergexia_datos.csv"
    datos.to_csv(archivo, index=False, encoding="utf-8")

    print("\nARCHIVO GENERADO:")
    print(archivo)

    print("\nPROCESO FINALIZADO CORRECTAMENTE.")


if __name__ == "__main__":
    main()
