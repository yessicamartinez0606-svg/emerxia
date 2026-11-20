# ==============================================================
# PROYECTO: EMERGEXIA
# ETAPA 14: PERSISTENCIA MASIVA CON SPARK Y MONGODB ATLAS
#
# Archivo:
# p22_atlas_emergencias.py
#
# Objetivo:
# Guardar en MongoDB Atlas los 50,000 registros de servicios
# de ambulancia procesados con Apache Spark.
#
# ORIGEN:
# resultados_emergexia/spark_procesado
#
# DESTINO:
# Base de datos: MONGO_DB de backend/.env (por defecto emergexia)
# Coleccion: servicios_ambulancia_masivos
#
# CARACTERISTICAS:
# - Lectura de Parquet.
# - Insercion masiva por lotes, una conexion por particion.
# - ReplaceOne + upsert: se puede repetir sin duplicar.
# - Indices de busqueda.
# - Validacion final.
#
# IMPORTANTE:
# Se usa una coleccion independiente para no mezclar los
# datos sinteticos con las emergencias reales del sistema.
# ==============================================================


# ==============================================================
# 1. IMPORTACION DE LIBRERIAS
# ==============================================================

import os
import sys

from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote_plus

import certifi

from dotenv import load_dotenv

from pymongo import MongoClient, ReplaceOne
from pymongo.errors import ServerSelectionTimeoutError

from pyspark.sql import SparkSession


# ==============================================================
# 2. CONFIGURACION
# ==============================================================

RUTA_BASE = Path(__file__).resolve().parent

# Se usa el mismo archivo de configuracion del sistema: backend/.env
# (si existe un .env dentro de ia_bigdata, ese tiene prioridad).
# load_dotenv no sobrescribe variables que ya se cargaron.
load_dotenv(RUTA_BASE / ".env")
load_dotenv(RUTA_BASE.parent / ".env")

RUTA_PARQUET = RUTA_BASE / "resultados_emergexia" / "spark_procesado"

NOMBRE_COLECCION = "servicios_ambulancia_masivos"

# Identificador fijo del lote: si se ejecuta otra vez,
# los registros se actualizan en lugar de duplicarse.
LOTE_ID = "EMERGEXIA-50000-V1"

TAMANO_LOTE = 500

NUM_PARTICIONES = 8

TOTAL_ESPERADO = 50000

AMBULANCIAS_ESPERADAS = 10000


# ==============================================================
# 3. CONSTRUIR URI
# ==============================================================

def construir_uri():

    """
    1. Usa MONGO_URI, la misma variable que usa la API de Emergexia
       (backend/.env).
    2. Si no existe, arma la URI con MONGO_USER, MONGO_PASSWORD y
       MONGO_CLUSTER (formato de las practicas de SmartAcademy).
    """

    uri = os.getenv("MONGO_URI")

    if uri:
        return uri

    usuario = os.getenv("MONGO_USER")
    password = os.getenv("MONGO_PASSWORD")
    cluster = os.getenv("MONGO_CLUSTER")

    if not usuario or not password or not cluster:

        raise ValueError(
            "Faltan variables de conexion. Configura MONGO_URI en "
            "backend/.env (o MONGO_USER, MONGO_PASSWORD y MONGO_CLUSTER)."
        )

    return (
        f"mongodb+srv://{quote_plus(usuario)}:{quote_plus(password)}"
        f"@{cluster}/"
        "?retryWrites=true&w=majority&appName=Emergexia"
    )


def es_atlas(uri):

    return uri.startswith("mongodb+srv://") or "mongodb.net" in uri


def crear_cliente(uri):

    """
    Con Atlas se usan los certificados de certifi.
    Con un MongoDB local (sin TLS) no se agregan.
    """

    opciones = {
        "serverSelectionTimeoutMS": 30000,
        "retryWrites": True
    }

    if es_atlas(uri):
        opciones["tlsCAFile"] = certifi.where()

    return MongoClient(uri, **opciones)


def obtener_base_datos():

    """
    Misma base que usa la API: MONGO_DB (por defecto "emergexia").
    """

    return os.getenv("MONGO_DB") or "emergexia"


def preparar_spark_local():

    """
    Igual que backend/app/spark.py: Spark usa el mismo Python
    que ejecuta el script y se queda en 127.0.0.1 (evita fallos
    en Windows/WSL por VPN o varias tarjetas de red).
    """

    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")


# ==============================================================
# 4. CONECTAR CON MONGODB ATLAS
# ==============================================================

def conectar_mongodb():

    print("\n1. CONECTANDO CON MONGODB ATLAS")
    print("-" * 65)

    uri = construir_uri()

    nombre_db = obtener_base_datos()

    cliente = crear_cliente(uri)

    try:

        cliente.admin.command("ping")

    except ServerSelectionTimeoutError as error:

        cliente.close()

        raise RuntimeError(
            "No se pudo conectar a MongoDB. Si usas Atlas, revisa en "
            "Network Access que tu IP este permitida, que el cluster no "
            "este en pausa y tu conexion a internet. "
            "Se puede volver a ejecutar: no duplica registros."
        ) from error

    print("Conexion establecida correctamente.")
    print(f"Base de datos: {nombre_db}")
    print(f"Coleccion: {NOMBRE_COLECCION}")

    coleccion = cliente[nombre_db][NOMBRE_COLECCION]

    # Lote + registro debe ser unico.
    coleccion.create_index(
        [("id_lote", 1), ("id_registro", 1)],
        unique=True,
        name="indice_lote_registro_unico"
    )

    coleccion.create_index("id_ambulancia", name="indice_ambulancia")

    coleccion.create_index("hospital_base", name="indice_hospital")

    coleccion.create_index("tipo_emergencia", name="indice_tipo")

    print("Indices verificados correctamente.")

    return cliente, nombre_db, coleccion, uri


# ==============================================================
# 5. CREAR SESION SPARK
# ==============================================================

def crear_sesion_spark():

    preparar_spark_local()

    spark = (
        SparkSession.builder
        .appName("EMERGEXIA_SPARK_MONGODB")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", str(NUM_PARTICIONES))
        .config("spark.ui.enabled", "false")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    return spark


# ==============================================================
# 6. INSERTAR UNA PARTICION
# ==============================================================

def insertar_particion(filas, uri, nombre_db, nombre_coleccion, lote_id):

    """
    Cada particion de Spark abre su propia conexion
    (un MongoClient no se comparte entre procesos)
    y escribe por lotes con bulk_write.
    """

    cliente = crear_cliente(uri)

    try:

        coleccion = cliente[nombre_db][nombre_coleccion]

        operaciones = []

        fecha_carga = datetime.now(timezone.utc)

        for fila in filas:

            documento = fila.asDict(recursive=True)

            documento["id_lote"] = lote_id
            documento["sistema"] = "Emergexia"
            documento["etapa"] = 14
            documento["datos_sinteticos"] = True
            documento["fecha_carga"] = fecha_carga

            operaciones.append(
                ReplaceOne(
                    {
                        "id_lote": lote_id,
                        "id_registro": documento["id_registro"]
                    },
                    documento,
                    upsert=True
                )
            )

            if len(operaciones) >= TAMANO_LOTE:

                coleccion.bulk_write(operaciones, ordered=False)

                operaciones.clear()

        if operaciones:

            coleccion.bulk_write(operaciones, ordered=False)

    finally:

        cliente.close()


# ==============================================================
# 7. LEER PARQUET
# ==============================================================

def cargar_parquet(spark):

    print("\n2. LEYENDO ARCHIVOS PARQUET")
    print("-" * 65)

    if not RUTA_PARQUET.exists():

        raise FileNotFoundError(
            f"No existe el directorio: {RUTA_PARQUET}. "
            "Ejecuta primero p21_spark_emergencias.py"
        )

    df = spark.read.parquet(str(RUTA_PARQUET))

    total = df.count()

    print(f"Registros leidos: {total:,}")

    if total != TOTAL_ESPERADO:

        raise ValueError(
            f"Se esperaban {TOTAL_ESPERADO} registros "
            f"y se encontraron {total}."
        )

    print("Archivos Parquet validados.")

    return df


# ==============================================================
# 8. CARGA MASIVA
# ==============================================================

def ejecutar_carga(df, uri, nombre_db):

    print("\n3. INICIANDO CARGA MASIVA")
    print("-" * 65)

    df_distribuido = df.repartition(NUM_PARTICIONES)

    print("Particiones de escritura:", df_distribuido.rdd.getNumPartitions())
    print("Tamano del lote de escritura:", TAMANO_LOTE)
    print("Identificador de lote:", LOTE_ID)

    # No se usa collect(): cada particion escribe sus registros.
    df_distribuido.foreachPartition(
        lambda filas: insertar_particion(
            filas,
            uri,
            nombre_db,
            NOMBRE_COLECCION,
            LOTE_ID
        )
    )

    print("Proceso de escritura terminado.")


# ==============================================================
# 9. VALIDAR PERSISTENCIA
# ==============================================================

def validar_persistencia(coleccion):

    print("\n4. VALIDANDO PERSISTENCIA")
    print("-" * 65)

    filtro = {"id_lote": LOTE_ID}

    total = coleccion.count_documents(filtro)

    print(f"Documentos encontrados en Atlas: {total:,}")
    print(f"Documentos esperados: {TOTAL_ESPERADO:,}")

    if total != TOTAL_ESPERADO:

        raise ValueError(
            "La cantidad de documentos en Atlas no coincide. "
            "Puedes volver a ejecutar el script: no duplica registros."
        )

    tipos = coleccion.distinct("tipo_emergencia", filtro)

    print(f"Tipos de emergencia almacenados: {len(tipos)}")

    hospitales = coleccion.distinct("hospital_base", filtro)

    print(f"Hospitales almacenados: {len(hospitales)}")

    ambulancias = coleccion.distinct("id_ambulancia", filtro)

    print(f"Ambulancias almacenadas: {len(ambulancias):,}")

    if len(ambulancias) != AMBULANCIAS_ESPERADAS:
        raise ValueError("La cantidad de ambulancias no coincide.")

    ejemplo = coleccion.find_one(
        filtro,
        {
            "_id": 0,
            "id_registro": 1,
            "id_ambulancia": 1,
            "hospital_base": 1,
            "tipo_emergencia": 1,
            "promedio_respuesta": 1,
            "tendencia": 1,
            "resultado": 1,
            "id_lote": 1
        }
    )

    print("\nDOCUMENTO DE EJEMPLO")
    print("-" * 65)
    print(ejemplo)

    print("\nVALIDACION COMPLETADA.")

    return total


# ==============================================================
# 10. PROGRAMA PRINCIPAL
# ==============================================================

def main():

    print("\n" + "=" * 65)
    print("EMERGEXIA")
    print("ETAPA 14 - PERSISTENCIA MASIVA EN MONGODB ATLAS")
    print("=" * 65)

    spark = None

    cliente = None

    try:

        cliente, nombre_db, coleccion, uri = conectar_mongodb()

        spark = crear_sesion_spark()

        print("\nSESION SPARK INICIADA")
        print("Version:", spark.version)

        df = cargar_parquet(spark)

        ejecutar_carga(df, uri, nombre_db)

        total = validar_persistencia(coleccion)

        print("\n" + "=" * 65)
        print("ETAPA 14 FINALIZADA CORRECTAMENTE")
        print("=" * 65)
        print(f"Registros almacenados: {total:,}")
        print(f"Base de datos: {nombre_db}")
        print(f"Coleccion: {NOMBRE_COLECCION}")

    except Exception as error:

        print("\nERROR DURANTE LA PERSISTENCIA")
        print("-" * 65)
        print(type(error).__name__, ":", error)

        raise

    finally:

        if spark is not None:

            spark.stop()

            print("\nSESION SPARK CERRADA")

        if cliente is not None:

            cliente.close()

            print("CONEXION MONGODB CERRADA")


if __name__ == "__main__":

    main()
