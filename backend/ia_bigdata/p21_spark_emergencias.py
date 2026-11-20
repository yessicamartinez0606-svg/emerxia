# ==============================================================
# PROYECTO: EMERGEXIA
# ETAPA 13: PROCESAMIENTO MASIVO CON APACHE SPARK
#
# Archivo:
# p21_spark_emergencias.py
#
# Objetivo:
# Leer y procesar los 50,000 registros de servicios de ambulancia
# con PySpark.
#
# Operaciones:
# 1. Lectura del CSV con esquema definido.
# 2. Validacion de datos.
# 3. Deteccion de duplicados.
# 4. Transformacion de variables.
# 5. Estadisticas distribuidas (por tipo y por hospital).
# 6. Exportacion a formato Parquet.
#
# IMPORTANTE:
# Este modulo no modifica MongoDB Atlas.
# ==============================================================


# ==============================================================
# 1. IMPORTACION DE LIBRERIAS
# ==============================================================

import os
import sys

from pathlib import Path

from pyspark.sql import SparkSession

from pyspark.sql.types import (
    StructType,
    StructField,
    LongType,
    StringType,
    DoubleType
)

from pyspark.sql.functions import (
    col,
    avg,
    count,
    countDistinct,
    round,
    when,
    lit
)


# ==============================================================
# 2. CONFIGURACION
# ==============================================================

RUTA_BASE = Path(__file__).resolve().parent

RUTA_RESULTADOS = RUTA_BASE / "resultados_emergexia"

RUTA_CSV = RUTA_RESULTADOS / "datos_masivos" / "emergexia_50000.csv"

RUTA_PARQUET = RUTA_RESULTADOS / "spark_procesado"

RUTA_RESUMEN = RUTA_RESULTADOS / "resumen_spark"

TOTAL_ESPERADO = 50000

TOTAL_TIPOS = 5

TIEMPO_MAXIMO = 60

UMBRAL_TENDENCIA = 2

NUM_PARTICIONES = 8


# ==============================================================
# 3. ESQUEMA DE DATOS
# ==============================================================

# Definir los tipos evita que Spark los adivine y ayuda
# a detectar errores de formato en el CSV.

ESQUEMA = StructType([

    StructField("id_registro", LongType(), False),

    StructField("id_ambulancia", StringType(), False),

    StructField("hospital_base", StringType(), False),

    StructField("tipo_emergencia", StringType(), False),

    StructField("tiempo_m1", DoubleType(), False),

    StructField("tiempo_m2", DoubleType(), False),

    StructField("tiempo_m3", DoubleType(), False),

    StructField("disponibilidad_m1", DoubleType(), False),

    StructField("disponibilidad_m2", DoubleType(), False),

    StructField("disponibilidad_m3", DoubleType(), False),

    StructField("promedio_respuesta", DoubleType(), False),

    StructField("tendencia", StringType(), False),

    StructField("resultado", StringType(), False)

])


# ==============================================================
# 4. CREAR SESION DE SPARK
# ==============================================================

def crear_sesion_spark():

    """
    local[*] usa todos los nucleos del equipo.
    Se simula el procesamiento distribuido de forma local.
    """

    # Spark usa el mismo Python que ejecuta el script y se queda
    # en 127.0.0.1 (igual que backend/app/spark.py).
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")

    spark = (
        SparkSession.builder
        .appName("EMERGEXIA_CARGA_MASIVA")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", str(NUM_PARTICIONES))
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    return spark


# ==============================================================
# 5. LEER CSV
# ==============================================================

def cargar_datos(spark):

    print("\n1. LEYENDO ARCHIVO CSV")
    print("-" * 65)

    if not RUTA_CSV.exists():

        raise FileNotFoundError(
            f"No se encontro el archivo: {RUTA_CSV}. "
            "Ejecuta primero p20_generador_emergencias.py"
        )

    df = (
        spark.read
        .format("csv")
        .option("header", "true")
        .option("encoding", "UTF-8")
        .option("mode", "FAILFAST")
        .schema(ESQUEMA)
        .load(str(RUTA_CSV))
    )

    print("Archivo leido correctamente.")

    df.printSchema()

    return df


# ==============================================================
# 6. FUNCION AUXILIAR: CONDICION "FUERA DE RANGO"
# ==============================================================

def condicion_fuera_de_rango(columnas, minimo, maximo):

    """
    Construye una condicion que es verdadera si alguna
    de las columnas esta fuera del intervalo indicado.
    """

    condicion = None

    for nombre in columnas:

        actual = (col(nombre) < minimo) | (col(nombre) > maximo)

        condicion = actual if condicion is None else (condicion | actual)

    return condicion


# ==============================================================
# 7. VALIDACION
# ==============================================================

def validar_datos(df):

    print("\n2. VALIDANDO INFORMACION")
    print("-" * 65)

    # 7.1 Cantidad de registros.
    total = df.count()

    print(f"Registros encontrados: {total:,}")

    if total != TOTAL_ESPERADO:
        raise ValueError("La cantidad de registros no coincide.")

    # 7.2 Identificadores unicos.
    duplicados = total - df.select("id_registro").distinct().count()

    print(f"Registros duplicados: {duplicados}")

    if duplicados > 0:
        raise ValueError("Se encontraron identificadores duplicados.")

    # 7.3 Valores nulos.
    condicion_nulos = None

    for nombre in df.columns:

        actual = col(nombre).isNull()

        condicion_nulos = (
            actual if condicion_nulos is None
            else (condicion_nulos | actual)
        )

    nulos = df.filter(condicion_nulos).count()

    print(f"Registros con valores nulos: {nulos}")

    if nulos > 0:
        raise ValueError("Se encontraron registros con valores nulos.")

    # 7.4 Tiempos de respuesta entre 0 y 60 minutos.
    tiempos_invalidos = df.filter(
        condicion_fuera_de_rango(
            ["tiempo_m1", "tiempo_m2", "tiempo_m3", "promedio_respuesta"],
            0,
            TIEMPO_MAXIMO
        )
    ).count()

    print(f"Registros con tiempos invalidos: {tiempos_invalidos}")

    if tiempos_invalidos > 0:
        raise ValueError("Existen tiempos fuera del rango 0-60 minutos.")

    # 7.5 Disponibilidad entre 0 y 100 %.
    disponibilidad_invalida = df.filter(
        condicion_fuera_de_rango(
            ["disponibilidad_m1", "disponibilidad_m2", "disponibilidad_m3"],
            0,
            100
        )
    ).count()

    print(f"Registros con disponibilidad invalida: {disponibilidad_invalida}")

    if disponibilidad_invalida > 0:
        raise ValueError("Existe disponibilidad fuera del rango 0-100.")

    # 7.6 Cinco tipos de emergencia por ambulancia.
    ambulancias_incorrectas = (
        df.groupBy("id_ambulancia")
        .agg(countDistinct("tipo_emergencia").alias("total_tipos"))
        .filter(col("total_tipos") != TOTAL_TIPOS)
        .count()
    )

    print(
        "Ambulancias sin los cinco tipos de emergencia: "
        f"{ambulancias_incorrectas}"
    )

    if ambulancias_incorrectas > 0:
        raise ValueError(
            "Existen ambulancias con una cantidad incorrecta "
            "de tipos de emergencia."
        )

    # 7.7 Cada ambulancia pertenece a un solo hospital.
    ambulancias_multihospital = (
        df.groupBy("id_ambulancia")
        .agg(countDistinct("hospital_base").alias("hospitales"))
        .filter(col("hospitales") > 1)
        .count()
    )

    print(
        "Ambulancias con mas de un hospital base: "
        f"{ambulancias_multihospital}"
    )

    if ambulancias_multihospital > 0:
        raise ValueError("Hay ambulancias con mas de un hospital base.")

    print("\nVALIDACION COMPLETADA CORRECTAMENTE.")

    return total


# ==============================================================
# 8. TRANSFORMACION
# ==============================================================

def transformar_datos(df):

    """
    Nuevas columnas:
    - disponibilidad_promedio
    - variacion_tiempo (mes 3 - mes 1)
    - tendencia_recalculada
    """

    print("\n3. TRANSFORMANDO DATOS")
    print("-" * 65)

    df = df.withColumn(
        "disponibilidad_promedio",
        round(
            (
                col("disponibilidad_m1")
                + col("disponibilidad_m2")
                + col("disponibilidad_m3")
            ) / 3,
            2
        )
    )

    df = df.withColumn(
        "variacion_tiempo",
        round(col("tiempo_m3") - col("tiempo_m1"), 2)
    )

    # Menos minutos = mejor servicio.
    df = df.withColumn(
        "tendencia_recalculada",
        when(col("variacion_tiempo") <= -UMBRAL_TENDENCIA, lit("Mejora"))
        .when(col("variacion_tiempo") >= UMBRAL_TENDENCIA, lit("Deterioro"))
        .otherwise(lit("Estable"))
    )

    print("Nuevas variables calculadas.")

    return df


# ==============================================================
# 9. ANALISIS ESTADISTICO DISTRIBUIDO
# ==============================================================

def analizar_datos(df):

    print("\n4. ANALISIS ESTADISTICO CON SPARK")
    print("-" * 65)

    print("\nTIEMPO PROMEDIO GENERAL DE RESPUESTA (MIN)")

    df.select(
        round(avg("promedio_respuesta"), 2).alias("promedio_general")
    ).show()

    print("\nTIEMPO PROMEDIO POR TIPO DE EMERGENCIA")

    (
        df.groupBy("tipo_emergencia")
        .agg(
            round(avg("promedio_respuesta"), 2).alias("tiempo_promedio"),
            count("*").alias("total_registros")
        )
        .orderBy("tiempo_promedio")
        .show(truncate=False)
    )

    print("\nDESEMPENO POR HOSPITAL BASE")

    (
        df.groupBy("hospital_base")
        .agg(
            countDistinct("id_ambulancia").alias("ambulancias"),
            round(avg("promedio_respuesta"), 2).alias("tiempo_promedio"),
            round(avg("disponibilidad_promedio"), 2).alias("disponibilidad"),
            round(
                avg(when(col("resultado") == "Cumple", 1).otherwise(0)) * 100,
                2
            ).alias("porcentaje_cumple_meta")
        )
        .orderBy("tiempo_promedio")
        .show(truncate=False)
    )

    print("\nDISTRIBUCION DE TENDENCIAS")

    df.groupBy("tendencia").agg(count("*").alias("cantidad")) \
        .orderBy("tendencia").show()

    print("\nCUMPLIMIENTO DE LA META DE RESPUESTA")

    df.groupBy("resultado").agg(count("*").alias("cantidad")).show()

    print("\nCOMPROBACION DE ETIQUETAS")

    diferencias = df.filter(
        col("tendencia") != col("tendencia_recalculada")
    ).count()

    print(
        "Diferencias entre tendencia original y recalculada: "
        f"{diferencias}"
    )

    # Pueden aparecer pocas diferencias en casos muy cercanos
    # al umbral, porque la etiqueta original se calculo antes
    # de redondear a dos decimales.


# ==============================================================
# 10. GUARDAR PARQUET Y RESUMEN
# ==============================================================

def guardar_resultados(df):

    print("\n5. GUARDANDO RESULTADOS")
    print("-" * 65)

    # Se particiona por tipo de emergencia para consultas
    # posteriores por esta variable.
    (
        df.repartition(NUM_PARTICIONES, "tipo_emergencia")
        .write
        .mode("overwrite")
        .partitionBy("tipo_emergencia")
        .parquet(str(RUTA_PARQUET))
    )

    print(f"Datos Parquet guardados en: {RUTA_PARQUET}")

    resumen = (
        df.groupBy("hospital_base", "tipo_emergencia")
        .agg(
            count("*").alias("registros"),
            round(avg("promedio_respuesta"), 2).alias("tiempo_promedio"),
            round(avg("disponibilidad_promedio"), 2).alias(
                "disponibilidad_promedio"
            )
        )
        .orderBy("hospital_base", "tipo_emergencia")
    )

    (
        resumen.coalesce(1)
        .write
        .mode("overwrite")
        .option("header", "true")
        .csv(str(RUTA_RESUMEN))
    )

    print(f"Resumen guardado en: {RUTA_RESUMEN}")


# ==============================================================
# 11. PROGRAMA PRINCIPAL
# ==============================================================

def main():

    print("\n" + "=" * 65)
    print("EMERGEXIA")
    print("ETAPA 13 - PROCESAMIENTO MASIVO CON APACHE SPARK")
    print("=" * 65)

    spark = None

    try:

        spark = crear_sesion_spark()

        print("\nSESION SPARK INICIADA")
        print("Version de Spark:", spark.version)

        df = cargar_datos(spark)

        print("\nParticiones iniciales:", df.rdd.getNumPartitions())

        validar_datos(df)

        df = transformar_datos(df)

        df = df.repartition(NUM_PARTICIONES)

        print("\nParticiones de trabajo:", df.rdd.getNumPartitions())

        analizar_datos(df)

        guardar_resultados(df)

        print("\n" + "=" * 65)
        print("ETAPA 13 FINALIZADA CORRECTAMENTE")
        print("=" * 65)

    except Exception as error:

        print("\nERROR DURANTE EL PROCESAMIENTO")
        print("-" * 65)
        print(type(error).__name__, ":", error)

        raise

    finally:

        if spark is not None:

            spark.stop()

            print("\nSESION SPARK CERRADA")


if __name__ == "__main__":

    main()
