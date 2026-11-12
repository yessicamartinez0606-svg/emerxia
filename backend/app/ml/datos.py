"""Conjunto de datos sintético para el triage de Emergexia.

Pregunta que responde el modelo:
    ¿Esta emergencia requiere una ambulancia AVANZADA (1) o basta con una BÁSICA (0)?

Se conecta con la lógica proposicional (app/logica.py):  M = u ∧ (p → v)
la regla exige ambulancia Avanzada (v) cuando la prioridad es Alta (p). El modelo de ML
sugiere esa necesidad a partir de los signos vitales, antes de que el despachador decida.

Variable              Descripción                                   Tipo
edad                  Edad del paciente (años)                      Numérica
frecuencia_cardiaca   Latidos por minuto                            Numérica
saturacion_oxigeno    SpO2 (%)                                      Numérica
presion_sistolica     mmHg                                          Numérica
glasgow               Escala de coma de Glasgow (3 a 15)            Numérica
dolor_toracico        1 = sí, 0 = no                                Numérica (binaria)
requiere_avanzada     1 = Avanzada, 0 = Básica                      Objetivo

IMPORTANTE: los datos son SINTÉTICOS y con fines educativos. No son criterios clínicos
reales ni deben usarse para decidir la atención de un paciente.
"""
import numpy as np
import pandas as pd

SEMILLA = 42

VARIABLES = [
    "edad",
    "frecuencia_cardiaca",
    "saturacion_oxigeno",
    "presion_sistolica",
    "glasgow",
    "dolor_toracico",
]
OBJETIVO = "requiere_avanzada"


def generar_datos(cantidad: int = 1000, semilla: int = SEMILLA) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)

    # Signos vitales: la mayoría en rangos normales y una parte alterados.
    edad = rng.uniform(1, 95, cantidad)
    frecuencia = np.clip(rng.normal(90, 22, cantidad), 35, 190)
    saturacion = np.clip(rng.normal(94, 4.5, cantidad), 70, 100)
    presion = np.clip(rng.normal(120, 25, cantidad), 60, 210)
    glasgow = np.clip(np.round(rng.normal(13.5, 2.5, cantidad)), 3, 15)
    dolor_toracico = (rng.uniform(0, 1, cantidad) < 0.2).astype(int)

    # Indicador sintético de gravedad (0 = estable). Cada término se lleva a escala ~0-1.
    gravedad = (
        0.20 * np.clip((edad - 60) / 35, 0, 1)                  # edad avanzada
        + 0.20 * np.clip(np.abs(frecuencia - 80) / 60, 0, 1)    # taquicardia o bradicardia
        + 0.25 * np.clip((95 - saturacion) / 15, 0, 1)          # hipoxemia
        + 0.15 * np.clip(np.abs(presion - 120) / 60, 0, 1)      # hipo o hipertensión
        + 0.30 * (15 - glasgow) / 12                            # alteración de la conciencia
        + 0.15 * dolor_toracico                                 # posible evento cardiaco
    )

    # Ruido: variaciones que los signos vitales no explican por completo.
    gravedad_final = gravedad + rng.normal(0, 0.06, cantidad)

    # Umbral de generación (regla ficticia, no un protocolo médico).
    requiere_avanzada = (gravedad_final >= 0.32).astype(int)

    return pd.DataFrame({
        "edad": edad.round(0),
        "frecuencia_cardiaca": frecuencia.round(0),
        "saturacion_oxigeno": saturacion.round(1),
        "presion_sistolica": presion.round(0),
        "glasgow": glasgow.astype(int),
        "dolor_toracico": dolor_toracico,
        OBJETIVO: requiere_avanzada,
    })
