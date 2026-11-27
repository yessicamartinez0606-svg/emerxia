# ==============================================================
# PROYECTO: EMERGEXIA
# ETAPA 12: GENERACION DE DATOS MASIVOS DE EMERGENCIAS
#
# Archivo:
# p20_generador_emergencias.py
#
# Objetivo:
# Generar 50,000 registros sinteticos de servicios de ambulancia
# que despues se procesan con Apache Spark y se usan para entrenar
# una red neuronal convolucional 1D con PyTorch.
#
# Estructura:
# 10,000 ambulancias x 5 tipos de emergencia = 50,000 registros.
#
# Cada registro contiene:
# - Tiempo promedio de respuesta (minutos) en 3 meses.
# - Porcentaje de disponibilidad de la ambulancia en 3 meses.
# - Hospital base (Toluca).
# - Tiempo promedio de respuesta del trimestre.
# - Tendencia del servicio (Mejora / Estable / Deterioro).
# - Resultado frente a la meta de respuesta (Cumple / No cumple).
#
# IMPORTANTE:
# Los datos son sinteticos. No representan servicios reales.
# ==============================================================


# ==============================================================
# 1. IMPORTACION DE LIBRERIAS
# ==============================================================

import numpy as np
import pandas as pd

from pathlib import Path


# ==============================================================
# 2. CONFIGURACION GENERAL
# ==============================================================

# Semilla para obtener siempre los mismos datos.
SEMILLA = 42

np.random.seed(SEMILLA)

# Cantidad de ambulancias simuladas.
TOTAL_AMBULANCIAS = 10000

# Tipos de emergencia que atiende cada ambulancia.
TIPOS_EMERGENCIA = [
    "Accidente vial",
    "Cardiovascular",
    "Trauma",
    "Respiratoria",
    "Obstetrica"
]

# Ajuste (en minutos) segun el tipo de emergencia.
# Las emergencias cardiovasculares se priorizan y llegan antes;
# las obstetricas y los accidentes viales suelen tardar mas.
AJUSTE_TIPO = {
    "Accidente vial": 1.0,
    "Cardiovascular": -1.0,
    "Trauma": 0.0,
    "Respiratoria": 0.5,
    "Obstetrica": 1.5
}

# Hospitales base de las ambulancias en Toluca.
# Los mismos hospitales que maneja el sistema (backend/app/genetico.py),
# con su numero de ambulancias como peso para repartir las 10,000 simuladas.
HOSPITALES = [
    "Hospital IMSS 220",
    "Hospital General Nicolás San Juan",
    "Cruz Roja Toluca",
    "Hospital General ISSSTE",
    "Hospital IMSS 251",
    "Cruz Roja Metepec",
    "Cruz Roja San Mateo Atenco",
    "Cruz Roja Lerma",
    "Hospital Municipal Lerma"
]

AMBULANCIAS_POR_HOSPITAL = [3, 2, 2, 1, 2, 1, 1, 1, 1]
PESOS_HOSPITAL = [n / sum(AMBULANCIAS_POR_HOSPITAL) for n in AMBULANCIAS_POR_HOSPITAL]

TOTAL_TIPOS = len(TIPOS_EMERGENCIA)

TOTAL_REGISTROS = TOTAL_AMBULANCIAS * TOTAL_TIPOS

# Limites de los tiempos de respuesta (minutos).
TIEMPO_MINIMO = 3
TIEMPO_MAXIMO = 60

# Meta simulada: tiempo promedio de respuesta de 15 minutos o menos.
META_RESPUESTA_MIN = 15

# Cambio minimo (en minutos) para considerar mejora o deterioro.
UMBRAL_TENDENCIA = 2

# Carpeta donde esta este archivo.
RUTA_BASE = Path(__file__).resolve().parent

# Carpeta de resultados.
RUTA_RESULTADOS = RUTA_BASE / "resultados_emergexia" / "datos_masivos"

RUTA_RESULTADOS.mkdir(parents=True, exist_ok=True)

ARCHIVO_CSV = RUTA_RESULTADOS / "emergexia_50000.csv"

ARCHIVO_RESUMEN = RUTA_RESULTADOS / "resumen_datos_masivos.csv"


# ==============================================================
# 3. FUNCIONES AUXILIARES
# ==============================================================

def limitar_valor(valor, minimo, maximo):
    """
    Mantiene un valor dentro de un intervalo.
    """

    return np.clip(valor, minimo, maximo)


def generar_patron():
    """
    Selecciona el patron de evolucion del servicio.

    0 = Mejora     (el tiempo de respuesta baja)
    1 = Estable
    2 = Deterioro  (el tiempo de respuesta sube)
    """

    return np.random.choice(
        [0, 1, 2],
        p=[0.40, 0.35, 0.25]
    )


def calcular_tendencia(tiempo_m1, tiempo_m2, tiempo_m3):
    """
    Determina la tendencia observada con el cambio entre
    el primer y el tercer mes.

    En tiempos de respuesta, MENOS minutos es MEJOR:

    Mejora:     el tiempo baja al menos 2 minutos.
    Deterioro:  el tiempo sube al menos 2 minutos.
    Estable:    cambios menores a 2 minutos.
    """

    diferencia = tiempo_m3 - tiempo_m1

    if diferencia <= -UMBRAL_TENDENCIA:
        return "Mejora"

    elif diferencia >= UMBRAL_TENDENCIA:
        return "Deterioro"

    else:
        return "Estable"


# ==============================================================
# 4. GENERAR UN REGISTRO
# ==============================================================

def generar_registro(id_ambulancia, hospital, tipo, tiempo_base):
    """
    Genera los datos de un tipo de emergencia para una ambulancia.

    tiempo_base:
        Tiempo de respuesta tipico de la ambulancia (minutos).
        Simula diferencias de zona, trafico y equipo.
    """

    patron = generar_patron()

    # ----------------------------------------------------------
    # 4.1 Tiempo de respuesta del primer mes
    # ----------------------------------------------------------

    tiempo_m1 = np.random.normal(
        loc=tiempo_base + AJUSTE_TIPO[tipo],
        scale=2.0
    )

    tiempo_m1 = limitar_valor(tiempo_m1, TIEMPO_MINIMO, TIEMPO_MAXIMO)

    # ----------------------------------------------------------
    # 4.2 Evolucion en los meses 2 y 3
    # ----------------------------------------------------------

    if patron == 0:

        # Mejora: el tiempo baja progresivamente.
        cambio = np.random.uniform(2.2, 4.5)

        tiempo_m2 = tiempo_m1 - cambio * 0.50
        tiempo_m3 = tiempo_m1 - cambio

    elif patron == 1:

        # Estable: cambios pequenos.
        tiempo_m2 = tiempo_m1 + np.random.uniform(-0.8, 0.8)
        tiempo_m3 = tiempo_m1 + np.random.uniform(-0.8, 0.8)

    else:

        # Deterioro: el tiempo sube progresivamente.
        cambio = np.random.uniform(2.2, 4.5)

        tiempo_m2 = tiempo_m1 + cambio * 0.50
        tiempo_m3 = tiempo_m1 + cambio

    tiempo_m2 = limitar_valor(tiempo_m2, TIEMPO_MINIMO, TIEMPO_MAXIMO)
    tiempo_m3 = limitar_valor(tiempo_m3, TIEMPO_MINIMO, TIEMPO_MAXIMO)

    # ----------------------------------------------------------
    # 4.3 Disponibilidad de la ambulancia por mes
    # ----------------------------------------------------------

    # Porcentaje del tiempo en que la ambulancia estuvo "libre"
    # (no ocupada ni en reparacion). Las ambulancias mas lentas
    # suelen tener menos disponibilidad.

    disponibilidad_base = 95 - tiempo_base * 1.2

    if patron == 0:
        disponibilidad_base += 5

    elif patron == 2:
        disponibilidad_base -= 5

    disponibilidades = limitar_valor(
        np.random.normal(disponibilidad_base, 6, size=3),
        0,
        100
    )

    # ----------------------------------------------------------
    # 4.4 Promedio, tendencia y resultado
    # ----------------------------------------------------------

    promedio_respuesta = (tiempo_m1 + tiempo_m2 + tiempo_m3) / 3

    tendencia = calcular_tendencia(tiempo_m1, tiempo_m2, tiempo_m3)

    resultado = (
        "Cumple"
        if promedio_respuesta <= META_RESPUESTA_MIN
        else "No cumple"
    )

    return {

        "id_ambulancia": id_ambulancia,

        "hospital_base": hospital,

        "tipo_emergencia": tipo,

        "tiempo_m1": round(float(tiempo_m1), 2),

        "tiempo_m2": round(float(tiempo_m2), 2),

        "tiempo_m3": round(float(tiempo_m3), 2),

        "disponibilidad_m1": round(float(disponibilidades[0]), 2),

        "disponibilidad_m2": round(float(disponibilidades[1]), 2),

        "disponibilidad_m3": round(float(disponibilidades[2]), 2),

        "promedio_respuesta": round(float(promedio_respuesta), 2),

        "tendencia": tendencia,

        "resultado": resultado
    }


# ==============================================================
# 5. PROGRAMA PRINCIPAL
# ==============================================================

def main():

    print("\n" + "=" * 65)
    print("EMERGEXIA")
    print("ETAPA 12 - GENERACION DE DATOS MASIVOS DE EMERGENCIAS")
    print("=" * 65)

    print("\nCONFIGURACION DEL PROCESO")
    print("-" * 65)
    print(f"Total de ambulancias: {TOTAL_AMBULANCIAS:,}")
    print(f"Tipos de emergencia por ambulancia: {TOTAL_TIPOS}")
    print(f"Registros esperados: {TOTAL_REGISTROS:,}")
    print(f"Meta de respuesta: {META_RESPUESTA_MIN} minutos")

    # Tiempo tipico de cada ambulancia: entre 6 y 30 minutos.
    tiempos_base = np.random.uniform(6, 30, TOTAL_AMBULANCIAS)

    # Hospital base de cada ambulancia.
    hospitales = np.random.choice(HOSPITALES, TOTAL_AMBULANCIAS, p=PESOS_HOSPITAL)

    registros = []

    print("\nGENERANDO REGISTROS...")

    for numero in range(1, TOTAL_AMBULANCIAS + 1):

        id_ambulancia = f"AMB-{numero:05d}"

        for tipo in TIPOS_EMERGENCIA:

            registros.append(
                generar_registro(
                    id_ambulancia,
                    hospitales[numero - 1],
                    tipo,
                    tiempos_base[numero - 1]
                )
            )

        if numero % 1000 == 0:
            print(f"Ambulancias procesadas: {numero:,}")

    # ----------------------------------------------------------
    # 5.1 Construir DataFrame
    # ----------------------------------------------------------

    df = pd.DataFrame(registros)

    df.insert(0, "id_registro", range(1, len(df) + 1))

    # ----------------------------------------------------------
    # 5.2 Validaciones
    # ----------------------------------------------------------

    print("\nVALIDANDO INFORMACION")
    print("-" * 65)
    print(f"Registros generados: {len(df):,}")

    assert len(df) == TOTAL_REGISTROS, (
        "ERROR: la cantidad de registros no coincide."
    )

    assert df["id_registro"].is_unique, (
        "ERROR: existen identificadores duplicados."
    )

    assert df[["tiempo_m1", "tiempo_m2", "tiempo_m3"]].apply(
        lambda c: c.between(TIEMPO_MINIMO, TIEMPO_MAXIMO).all()
    ).all(), "ERROR: tiempos fuera de rango."

    assert df[[
        "disponibilidad_m1",
        "disponibilidad_m2",
        "disponibilidad_m3"
    ]].apply(
        lambda c: c.between(0, 100).all()
    ).all(), "ERROR: disponibilidad fuera de rango."

    print("Validaciones correctas.")

    # ----------------------------------------------------------
    # 5.3 Guardar CSV
    # ----------------------------------------------------------

    df.to_csv(ARCHIVO_CSV, index=False, encoding="utf-8")

    print(f"\nArchivo generado: {ARCHIVO_CSV}")

    # ----------------------------------------------------------
    # 5.4 Resumen estadistico
    # ----------------------------------------------------------

    resumen = (
        df["tendencia"]
        .value_counts()
        .rename_axis("tendencia")
        .reset_index(name="cantidad")
    )

    resumen["porcentaje"] = (
        resumen["cantidad"] / len(df) * 100
    ).round(2)

    resumen.to_csv(ARCHIVO_RESUMEN, index=False, encoding="utf-8")

    print("\nPRIMEROS CINCO REGISTROS")
    print("-" * 65)
    print(df.head().to_string(index=False))

    print("\nDISTRIBUCION DE TENDENCIAS")
    print("-" * 65)
    print(resumen.to_string(index=False))

    print("\nCUMPLIMIENTO DE LA META DE RESPUESTA")
    print("-" * 65)
    print(df["resultado"].value_counts().to_string())

    print("\nAMBULANCIAS POR HOSPITAL")
    print("-" * 65)
    print(
        df.drop_duplicates("id_ambulancia")["hospital_base"]
        .value_counts()
        .to_string()
    )

    print("\nESTADISTICAS DE TIEMPOS DE RESPUESTA (MIN)")
    print("-" * 65)
    print(
        df[[
            "tiempo_m1",
            "tiempo_m2",
            "tiempo_m3",
            "promedio_respuesta"
        ]].describe().round(2)
    )

    print("\n" + "=" * 65)
    print("ETAPA 12 FINALIZADA CORRECTAMENTE")
    print("=" * 65)
    print(f"\nArchivo principal: {ARCHIVO_CSV}")
    print(f"Archivo resumen: {ARCHIVO_RESUMEN}")


# ==============================================================
# 6. PUNTO DE ENTRADA
# ==============================================================

if __name__ == "__main__":

    main()
