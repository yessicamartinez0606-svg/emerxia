# ============================================================
# PROYECTO: EMERGEXIA
# PRACTICA 10 - ETAPA 7: CONSULTAS INTELIGENTES Y ANALISIS ESTADISTICO
# ARCHIVO: p16_analisis_estadistico_emergencias.py
#
# Objetivo:
# Consultar los analisis de emergencias guardados en MongoDB por
# p15_persistencia_mongodb_emergencias.py y generar estadisticas
# para el Administrador: cuantas emergencias son criticas, como se
# reparten por perfil de riesgo y prioridad, y cuando hizo falta
# pedir apoyo a otros hospitales.
#
# Operaciones:
#   Operacion  Tecnica MongoDB   Proposito
#       1      find()            Consultar todos los analisis
#       2      $match            Filtrar las emergencias criticas
#       3      $group            Agrupar por perfil de riesgo (K-Means)
#       4      $group            Contar emergencias por prioridad
#       5      $group + $cond    Estadisticas generales
#       6      $sort + $limit    Las 5 emergencias con mayor probabilidad de ser criticas
#
# Operadores del framework de agregacion:
#   $match    Filtrar documentos        Emergencias criticas
#   $group    Agrupar documentos        Por perfil o por prioridad
#   $sum      Sumar / contar            Total de analisis
#   $avg      Promedios                 Edad, oxigeno, distancia...
#   $cond     Evaluar condiciones       Contar criticas o solicitudes de apoyo
#   $project  Seleccionar campos        Armar los reportes
#   $sort     Ordenar                   Por probabilidad de ser critica
#   $limit    Limitar resultados        Solo 5 registros
#
# Reportes que genera (en resultados_sistema_inteligente/):
#   analisis_historico.csv       Todos los analisis guardados
#   analisis_criticos.csv        Solo las emergencias criticas
#   estadisticas_perfiles.csv    Promedios por perfil de riesgo
#   estadisticas_prioridad.csv   Cantidad por prioridad
#   estadisticas_generales.csv   Resumen global
#
# Conexion: el mismo backend/.env que p15 (MONGO_URI y MONGO_DB, o
# MONGO_USER, MONGO_PASSWORD y MONGO_CLUSTER).
# Coleccion: analisis_emergencias_ia (se cambia con MONGO_COLLECTION_IA).
# ============================================================


# ------------------------------------------------------------
# 1. LIBRERIAS
# ------------------------------------------------------------
import os
import certifi
import pandas as pd

from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError


# ------------------------------------------------------------
# 2. RUTAS Y CONFIGURACION
# ------------------------------------------------------------
RUTA_BASE = Path(__file__).resolve().parent
RUTA_RESULTADOS = RUTA_BASE / "resultados_sistema_inteligente"
RUTA_RESULTADOS.mkdir(parents=True, exist_ok=True)

# Primero el .env de esta carpeta (si existe) y luego backend/.env.
load_dotenv(RUTA_BASE / ".env")
load_dotenv(RUTA_BASE.parent / ".env")

MONGO_DB = os.getenv("MONGO_DB") or "emergexia"
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION_IA") or "analisis_emergencias_ia"

# Solo analizamos los documentos de este sistema.
FILTRO_SISTEMA = {"sistema": "Emergexia"}

# Regla del proyecto: con mas de 3 ambulancias ocupadas se pide apoyo.
LIMITE_AMBULANCIAS_OCUPADAS = 3


# ------------------------------------------------------------
# 3. CONECTAR CON MONGODB (igual que p15)
# ------------------------------------------------------------
def construir_uri():

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

    return (
        f"mongodb+srv://{quote_plus(usuario)}:{quote_plus(password)}"
        f"@{cluster}/?retryWrites=true&w=majority&appName=Emergexia"
    )


def conectar_mongodb():

    uri = construir_uri()
    opciones = {"serverSelectionTimeoutMS": 15000}

    if uri.startswith("mongodb+srv://") or "mongodb.net" in uri:
        opciones["tlsCAFile"] = certifi.where()

    cliente = MongoClient(uri, **opciones)
    cliente.admin.command("ping")

    print("Conexion con MongoDB establecida.")
    return cliente, cliente[MONGO_DB][MONGO_COLLECTION]


# ------------------------------------------------------------
# 4. OPERACION 1: CONSULTAR TODOS LOS ANALISIS (find)
# ------------------------------------------------------------
def consultar_todos(coleccion):

    print("\n1. CONSULTA GENERAL DE ANALISIS")
    print("-" * 60)

    # find(filtro, campos) y ordenamos del mas reciente al mas antiguo.
    registros = list(
        coleccion.find(
            FILTRO_SISTEMA,
            {"_id": 0, "id_analisis": 1, "fecha_registro": 1, "datos_paciente": 1,
             "ambulancias_ocupadas": 1, "clasificacion": 1, "perfil_riesgo": 1, "prioridad": 1}
        ).sort("fecha_registro", -1)
    )

    print("Total de analisis encontrados:", len(registros))

    for numero, r in enumerate(registros, start=1):
        paciente = r.get("datos_paciente", {})
        print(f"\nANALISIS {numero} | {r.get('fecha_registro')}")
        print(f"  Paciente: {paciente.get('edad')} anios | FC {paciente.get('frecuencia_cardiaca')} lpm | "
              f"SpO2 {paciente.get('saturacion_oxigeno')}% | {paciente.get('distancia_km')} km")
        print("  Resultado:", r.get("clasificacion", {}).get("resultado"))
        print("  Perfil:", r.get("perfil_riesgo", {}).get("perfil"))
        print("  Prioridad:", r.get("prioridad"))

    return registros


# ------------------------------------------------------------
# 5. OPERACION 2: EMERGENCIAS CRITICAS ($match)
# ------------------------------------------------------------
def consultar_criticas(coleccion):

    print("\n2. EMERGENCIAS CRITICAS")
    print("-" * 60)

    pipeline = [
        # Etapa 1: solo las clasificadas como criticas.
        {"$match": {**FILTRO_SISTEMA, "clasificacion.critica": True}},

        # Etapa 2: aplanar los campos que necesitamos.
        {"$project": {
            "_id": 0,
            "id_analisis": 1,
            "edad": "$datos_paciente.edad",
            "frecuencia_cardiaca": "$datos_paciente.frecuencia_cardiaca",
            "saturacion_oxigeno": "$datos_paciente.saturacion_oxigeno",
            "distancia_km": "$datos_paciente.distancia_km",
            "probabilidad_critica": "$clasificacion.probabilidad_critica",
            "perfil": "$perfil_riesgo.perfil",
            "prioridad": 1
        }},

        # Etapa 3: primero las de mayor probabilidad.
        {"$sort": {"probabilidad_critica": -1}}
    ]

    resultados = list(coleccion.aggregate(pipeline))

    print("Emergencias criticas:", len(resultados))

    for r in resultados:
        print(f"\n  {r.get('prioridad')} | probabilidad {r.get('probabilidad_critica', 0) * 100:.1f}%")
        print(f"  Edad {r.get('edad')} | SpO2 {r.get('saturacion_oxigeno')}% | Perfil: {r.get('perfil')}")

    return resultados


# ------------------------------------------------------------
# 6. OPERACION 3: AGRUPAR POR PERFIL DE RIESGO ($group)
# ------------------------------------------------------------
def analizar_perfiles(coleccion):

    print("\n3. DISTRIBUCION POR PERFIL DE RIESGO")
    print("-" * 60)

    pipeline = [
        {"$match": FILTRO_SISTEMA},

        {"$group": {
            "_id": "$perfil_riesgo.perfil",
            "total_analisis": {"$sum": 1},
            "total_criticas": {"$sum": {"$cond": [{"$eq": ["$clasificacion.critica", True]}, 1, 0]}},
            "promedio_edad": {"$avg": "$datos_paciente.edad"},
            "promedio_frecuencia": {"$avg": "$datos_paciente.frecuencia_cardiaca"},
            "promedio_oxigeno": {"$avg": "$datos_paciente.saturacion_oxigeno"},
            "promedio_distancia": {"$avg": "$datos_paciente.distancia_km"},
            "promedio_probabilidad": {"$avg": "$clasificacion.probabilidad_critica"}
        }},

        {"$sort": {"total_analisis": -1}}
    ]

    resultados = list(coleccion.aggregate(pipeline))

    for p in resultados:
        print(f"\nPerfil: {p['_id']}")
        print(f"  Analisis: {p['total_analisis']} | Criticas: {p['total_criticas']}")
        print(f"  Promedios -> edad {p['promedio_edad'] or 0:.1f} | FC {p['promedio_frecuencia'] or 0:.1f} | "
              f"SpO2 {p['promedio_oxigeno'] or 0:.1f}% | distancia {p['promedio_distancia'] or 0:.1f} km")
        print(f"  Probabilidad promedio de ser critica: {(p['promedio_probabilidad'] or 0) * 100:.1f}%")

    return resultados


# ------------------------------------------------------------
# 7. OPERACION 4: CONTAR POR PRIORIDAD ($group)
# ------------------------------------------------------------
def analizar_prioridades(coleccion):

    print("\n4. EMERGENCIAS POR PRIORIDAD")
    print("-" * 60)

    pipeline = [
        {"$match": FILTRO_SISTEMA},
        {"$group": {
            "_id": "$prioridad",
            "total": {"$sum": 1},
            "promedio_distancia": {"$avg": "$datos_paciente.distancia_km"}
        }},
        # "PRIORIDAD 1..." queda antes que "PRIORIDAD 2..." al ordenar el texto.
        {"$sort": {"_id": 1}}
    ]

    resultados = list(coleccion.aggregate(pipeline))

    for p in resultados:
        print(f"{p['_id']}: {p['total']} | distancia promedio {p['promedio_distancia'] or 0:.1f} km")

    return resultados


# ------------------------------------------------------------
# 8. OPERACION 5: ESTADISTICAS GENERALES ($group + $cond)
# ------------------------------------------------------------
def generar_estadisticas(coleccion):

    print("\n5. ESTADISTICAS GENERALES")
    print("-" * 60)

    pipeline = [
        {"$match": FILTRO_SISTEMA},
        {"$group": {
            "_id": None,
            "total_analisis": {"$sum": 1},
            "promedio_edad": {"$avg": "$datos_paciente.edad"},
            "promedio_frecuencia": {"$avg": "$datos_paciente.frecuencia_cardiaca"},
            "promedio_oxigeno": {"$avg": "$datos_paciente.saturacion_oxigeno"},
            "promedio_distancia": {"$avg": "$datos_paciente.distancia_km"},
            "promedio_probabilidad_critica": {"$avg": "$clasificacion.probabilidad_critica"},

            # $cond: si se cumple la condicion suma 1, si no suma 0.
            "total_criticas": {"$sum": {"$cond": [{"$eq": ["$clasificacion.critica", True]}, 1, 0]}},
            "total_no_criticas": {"$sum": {"$cond": [{"$eq": ["$clasificacion.critica", False]}, 1, 0]}},
            "total_solicitudes_apoyo": {"$sum": {"$cond": [
                {"$gt": ["$ambulancias_ocupadas", LIMITE_AMBULANCIAS_OCUPADAS]}, 1, 0
            ]}}
        }},
        {"$project": {"_id": 0}}
    ]

    resultados = list(coleccion.aggregate(pipeline))

    if not resultados:
        print("No existen registros para analizar.")
        return None

    e = resultados[0]

    print("Total de analisis:", e["total_analisis"])
    print(f"Emergencias criticas: {e['total_criticas']} | No criticas: {e['total_no_criticas']}")
    print(f"Porcentaje critico: {e['total_criticas'] / e['total_analisis'] * 100:.1f}%")
    print(f"Promedio de edad: {e['promedio_edad'] or 0:.1f} anios")
    print(f"Promedio de frecuencia cardiaca: {e['promedio_frecuencia'] or 0:.1f} lpm")
    print(f"Promedio de saturacion de oxigeno: {e['promedio_oxigeno'] or 0:.1f}%")
    print(f"Promedio de distancia al IMSS 220: {e['promedio_distancia'] or 0:.1f} km")
    print(f"Probabilidad promedio de ser critica: {(e['promedio_probabilidad_critica'] or 0) * 100:.1f}%")
    print(f"Veces que se pidio apoyo a otros hospitales: {e['total_solicitudes_apoyo']}")

    return e


# ------------------------------------------------------------
# 9. OPERACION 6: LAS 5 EMERGENCIAS MAS GRAVES ($sort + $limit)
# ------------------------------------------------------------
def consultar_mas_graves(coleccion):

    print("\n6. LAS 5 EMERGENCIAS CON MAYOR PROBABILIDAD DE SER CRITICAS")
    print("-" * 60)

    pipeline = [
        {"$match": FILTRO_SISTEMA},
        {"$project": {
            "_id": 0,
            "edad": "$datos_paciente.edad",
            "saturacion_oxigeno": "$datos_paciente.saturacion_oxigeno",
            "frecuencia_cardiaca": "$datos_paciente.frecuencia_cardiaca",
            "probabilidad_critica": "$clasificacion.probabilidad_critica",
            "perfil": "$perfil_riesgo.perfil",
            "prioridad": 1
        }},
        {"$sort": {"probabilidad_critica": -1}},
        {"$limit": 5}
    ]

    resultados = list(coleccion.aggregate(pipeline))

    for numero, r in enumerate(resultados, start=1):
        print(f"\nPOSICION {numero}: {r.get('probabilidad_critica', 0) * 100:.1f}% | {r.get('prioridad')}")
        print(f"  Edad {r.get('edad')} | FC {r.get('frecuencia_cardiaca')} | "
              f"SpO2 {r.get('saturacion_oxigeno')}% | Perfil: {r.get('perfil')}")

    return resultados


# ------------------------------------------------------------
# 10. EXPORTAR LOS REPORTES A CSV
# ------------------------------------------------------------
def exportar_reportes(registros, criticas, perfiles, prioridades, estadisticas):

    print("\n7. EXPORTACION DE REPORTES")
    print("-" * 60)

    def guardar(datos, nombre, renombrar=None):
        if not datos:
            return
        df = pd.DataFrame(datos)
        if renombrar:
            df = df.rename(columns=renombrar)
        # Redondeamos solo las columnas numericas (no las fechas).
        numericas = df.select_dtypes("number").columns
        df[numericas] = df[numericas].round(4)
        ruta = RUTA_RESULTADOS / nombre
        df.to_csv(ruta, index=False, encoding="utf-8-sig")
        print("Reporte generado:", ruta)

    # Historial: aplanamos cada documento en una fila.
    historial = [{
        "id_analisis": r.get("id_analisis"),
        "fecha_registro": r.get("fecha_registro"),
        **r.get("datos_paciente", {}),
        "ambulancias_ocupadas": r.get("ambulancias_ocupadas"),
        "critica": r.get("clasificacion", {}).get("critica"),
        "resultado": r.get("clasificacion", {}).get("resultado"),
        "probabilidad_critica": r.get("clasificacion", {}).get("probabilidad_critica"),
        "cluster": r.get("perfil_riesgo", {}).get("cluster"),
        "perfil": r.get("perfil_riesgo", {}).get("perfil"),
        "prioridad": r.get("prioridad")
    } for r in registros]

    guardar(historial, "analisis_historico.csv")
    guardar(criticas, "analisis_criticos.csv")
    guardar(perfiles, "estadisticas_perfiles.csv", {"_id": "perfil"})
    guardar(prioridades, "estadisticas_prioridad.csv", {"_id": "prioridad"})
    guardar([estadisticas] if estadisticas else [], "estadisticas_generales.csv")


# ------------------------------------------------------------
# 11. PROGRAMA PRINCIPAL
# ------------------------------------------------------------
def main():

    print("=" * 60)
    print("EMERGEXIA - ETAPA 7: CONSULTAS Y ANALISIS ESTADISTICO")
    print("=" * 60)

    cliente = None

    try:
        cliente, coleccion = conectar_mongodb()

        registros = consultar_todos(coleccion)

        if not registros:
            print("\nNo hay analisis guardados. Ejecuta primero p14 y p15.")
            return

        criticas = consultar_criticas(coleccion)
        perfiles = analizar_perfiles(coleccion)
        prioridades = analizar_prioridades(coleccion)
        estadisticas = generar_estadisticas(coleccion)
        consultar_mas_graves(coleccion)

        exportar_reportes(registros, criticas, perfiles, prioridades, estadisticas)

        print("\n" + "=" * 60)
        print("ANALISIS ESTADISTICO FINALIZADO")
        print("Base de datos:", MONGO_DB, "| Coleccion:", MONGO_COLLECTION)
        print("=" * 60)

    except ValueError as error:
        print("\nERROR DE CONFIGURACION:", error)

    except PyMongoError as error:
        print("\nERROR DE MONGODB:", error)

    except Exception as error:
        print("\nERROR INESPERADO:", error)

    finally:
        if cliente is not None:
            cliente.close()
            print("\nConexion con MongoDB cerrada.")


if __name__ == "__main__":
    main()
