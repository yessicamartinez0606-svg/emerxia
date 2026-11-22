# ============================================================
# PROYECTO: EMERGEXIA
# PRACTICA 10 - ETAPA 6: PERSISTENCIA CON MONGODB ATLAS
# ARCHIVO: p15_persistencia_mongodb_emergencias.py
#
# Objetivo:
# Leer el reporte de emergencia generado en la Etapa 5
# (p14_motor_recomendaciones_emergencias.py) y guardarlo en una coleccion
# de MongoDB Atlas, para tener el historial de analisis.
#
# Tecnologias: Python, Pandas, PyMongo, python-dotenv, MongoDB Atlas.
#
# Conexion: usa el MISMO backend/.env de la API de Emergexia:
#   MONGO_URI=mongodb+srv://usuario:contrasena@cluster0.xxxxx.mongodb.net/
#   MONGO_DB=emergexia
# Tambien acepta el formato de las practicas (MONGO_USER, MONGO_PASSWORD
# y MONGO_CLUSTER). Un .env dentro de esta carpeta tiene prioridad.
#
# Coleccion: analisis_emergencias_ia (se cambia con MONGO_COLLECTION_IA),
# separada de las emergencias reales que guarda el sistema.
# ============================================================


# ------------------------------------------------------------
# 1. LIBRERIAS
# ------------------------------------------------------------
import os
import json
import uuid
import certifi
import pandas as pd

from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError


# ------------------------------------------------------------
# 2. RUTAS Y CONFIGURACION
# ------------------------------------------------------------
RUTA_BASE = Path(__file__).resolve().parent              # backend/ia_sistema_inteligente
RUTA_REPORTE = RUTA_BASE / "resultados_sistema_inteligente" / "reporte_emergencia.csv"

# Primero el .env de esta carpeta (si existe) y luego backend/.env.
# load_dotenv no sobrescribe variables que ya se cargaron.
load_dotenv(RUTA_BASE / ".env")
load_dotenv(RUTA_BASE.parent / ".env")

MONGO_DB = os.getenv("MONGO_DB") or "emergexia"
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION_IA") or "analisis_emergencias_ia"


# ------------------------------------------------------------
# 3. ARMAR LA CADENA DE CONEXION
# ------------------------------------------------------------
def construir_uri():
    """
    1. Usa MONGO_URI (la misma variable de la API).
    2. Si no existe, la arma con MONGO_USER, MONGO_PASSWORD y MONGO_CLUSTER.
    No muestra las credenciales en pantalla.
    """
    uri = os.getenv("MONGO_URI")
    if uri:
        return uri

    usuario = os.getenv("MONGO_USER")
    password = os.getenv("MONGO_PASSWORD")
    cluster = os.getenv("MONGO_CLUSTER")

    if not usuario or not password or not cluster:
        raise ValueError(
            "Faltan variables de conexion. Configura MONGO_URI en backend/.env "
            "(o MONGO_USER, MONGO_PASSWORD y MONGO_CLUSTER)."
        )

    # quote_plus codifica caracteres especiales del usuario o contrasena.
    return (
        f"mongodb+srv://{quote_plus(usuario)}:{quote_plus(password)}"
        f"@{cluster}/?retryWrites=true&w=majority&appName=Emergexia"
    )


# ------------------------------------------------------------
# 4. CONECTAR CON MONGODB
# ------------------------------------------------------------
def conectar_mongodb():

    uri = construir_uri()

    opciones = {"serverSelectionTimeoutMS": 10000}

    # Con Atlas se usan los certificados de certifi (evita errores SSL en Windows).
    # Con un MongoDB local (sin TLS) no se agregan.
    if uri.startswith("mongodb+srv://") or "mongodb.net" in uri:
        opciones["tlsCAFile"] = certifi.where()

    cliente = MongoClient(uri, **opciones)

    # ping comprueba que la conexion funciona.
    cliente.admin.command("ping")
    print("Conexion con MongoDB establecida.")

    coleccion = cliente[MONGO_DB][MONGO_COLLECTION]
    return cliente, coleccion


# ------------------------------------------------------------
# 5. LEER EL REPORTE DE LA ETAPA 5
# ------------------------------------------------------------
def leer_reporte():

    print("\nLEYENDO REPORTE DE EMERGENCIA...")

    if not RUTA_REPORTE.exists():
        raise FileNotFoundError(f"No se encontro {RUTA_REPORTE}. Ejecuta primero p14_motor_recomendaciones_emergencias.py")

    dataframe = pd.read_csv(RUTA_REPORTE)

    if dataframe.empty:
        raise ValueError("El reporte no contiene registros.")

    print("Registros encontrados:", len(dataframe))
    return dataframe


# ------------------------------------------------------------
# 6. CONVERTIR EL REPORTE EN DOCUMENTOS
# ------------------------------------------------------------
def convertir_documentos(dataframe):
    """
    Cada fila del CSV se convierte en un documento organizado por
    secciones, para que sea facil de consultar despues.
    """

    # to_json + json.loads convierte los tipos de Pandas a tipos normales.
    registros = json.loads(dataframe.to_json(orient="records", force_ascii=False))

    documentos = []

    for r in registros:

        documento = {
            "id_analisis": str(uuid.uuid4()),
            "sistema": "Emergexia",
            "etapa": 5,
            "fecha_registro": datetime.now(timezone.utc),
            "archivo_origen": RUTA_REPORTE.name,

            # Datos capturados de la emergencia.
            "datos_paciente": {
                "edad": r["edad"],
                "frecuencia_cardiaca": r["frecuencia_cardiaca"],
                "saturacion_oxigeno": r["saturacion_oxigeno"],
                "distancia_km": r["distancia_km"]
            },
            "ambulancias_ocupadas": r["ambulancias_ocupadas"],

            # Resultado de Random Forest.
            "clasificacion": {
                "critica": bool(r["prediccion"]),
                "resultado": r["resultado"],
                "probabilidad_critica": r["probabilidad_critica"]
            },

            # Resultado de K-Means.
            "perfil_riesgo": {
                "cluster": r["cluster"],
                "perfil": r["perfil"]
            },

            # Coordenadas PCA.
            "pca": {"PC1": r["PC1"], "PC2": r["PC2"]},

            # Motor de reglas.
            "prioridad": r["prioridad"],
            "recomendaciones": r["recomendaciones"].split(" | ")
        }

        documentos.append(documento)

    return documentos


# ------------------------------------------------------------
# 7. CREAR INDICES
# ------------------------------------------------------------
def crear_indices(coleccion):
    """Los indices hacen mas rapidas las consultas."""

    coleccion.create_index("id_analisis", unique=True)   # no repetir analisis
    coleccion.create_index("fecha_registro")             # consultar por fecha
    coleccion.create_index("prioridad")                  # consultar por prioridad
    coleccion.create_index("clasificacion.critica")      # filtrar criticas

    print("Indices verificados.")


# ------------------------------------------------------------
# 8. GUARDAR LOS DOCUMENTOS
# ------------------------------------------------------------
def guardar_documentos(coleccion, documentos):

    print("\nGUARDANDO EN MONGODB ATLAS...")

    resultado = coleccion.insert_many(documentos)

    print("Documentos almacenados:", len(resultado.inserted_ids))
    return resultado.inserted_ids


# ------------------------------------------------------------
# 9. CONSULTAR EL HISTORIAL
# ------------------------------------------------------------
def consultar_historial(coleccion):

    print("\nULTIMOS 5 ANALISIS DE EMERGEXIA")
    print("-" * 55)

    registros = coleccion.find(
        {},
        {"_id": 0, "id_analisis": 1, "fecha_registro": 1, "datos_paciente": 1,
         "clasificacion": 1, "perfil_riesgo": 1, "prioridad": 1}
    ).sort("fecha_registro", -1).limit(5)

    for numero, r in enumerate(registros, start=1):
        print(f"\nANALISIS {numero}")
        print("ID:", r.get("id_analisis"))
        print("Fecha:", r.get("fecha_registro"))
        print("Paciente:", r.get("datos_paciente"))
        print("Resultado:", r["clasificacion"]["resultado"],
              f"({r['clasificacion']['probabilidad_critica'] * 100:.1f}%)")
        print("Perfil:", r["perfil_riesgo"]["perfil"])
        print("Prioridad:", r.get("prioridad"))

    # Consulta extra: cuantas emergencias criticas hay guardadas.
    total = coleccion.count_documents({})
    criticas = coleccion.count_documents({"clasificacion.critica": True})
    print(f"\nTotal de analisis guardados: {total} | Criticas: {criticas}")


# ------------------------------------------------------------
# 10. PROGRAMA PRINCIPAL
# ------------------------------------------------------------
def main():

    print("=" * 60)
    print("EMERGEXIA - ETAPA 6: PERSISTENCIA CON MONGODB ATLAS")
    print("=" * 60)

    cliente = None

    try:
        dataframe = leer_reporte()
        documentos = convertir_documentos(dataframe)
        cliente, coleccion = conectar_mongodb()
        crear_indices(coleccion)
        guardar_documentos(coleccion, documentos)
        consultar_historial(coleccion)

        print("\n" + "=" * 60)
        print("PROCESO DE PERSISTENCIA FINALIZADO")
        print("Base de datos:", MONGO_DB, "| Coleccion:", MONGO_COLLECTION)
        print("=" * 60)

    except FileNotFoundError as error:
        print("\nERROR DE ARCHIVO:", error)

    except ValueError as error:
        print("\nERROR DE CONFIGURACION:", error)

    except PyMongoError as error:
        print("\nERROR DE MONGODB:", error)

    except Exception as error:
        print("\nERROR INESPERADO:", error)

    finally:
        # Cerramos la conexion para liberar recursos.
        if cliente is not None:
            cliente.close()
            print("\nConexion con MongoDB cerrada.")


if __name__ == "__main__":
    main()
