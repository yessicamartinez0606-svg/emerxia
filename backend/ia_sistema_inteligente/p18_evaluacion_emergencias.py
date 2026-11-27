# ============================================================
# PROYECTO: EMERGEXIA
# PRACTICA 10 - ETAPA 9: EVALUACION Y REGISTRO DE EMERGENCIAS
# ARCHIVO: p18_evaluacion_emergencias.py
#
# OBJETIVO:
# Integrar los modelos de las etapas anteriores en una aplicacion
# web con Streamlit, para que el Administrador capture una emergencia
# y obtenga al instante su prioridad y recomendaciones.
#
# FUNCIONALIDADES:
# 1. Capturar los datos de la emergencia (folio, paciente, distancia,
#    ambulancias ocupadas).
# 2. Estimar si es critica con Random Forest.
# 3. Identificar su perfil de riesgo con K-Means.
# 4. Ubicarla en el mapa PCA.
# 5. Generar prioridad y recomendaciones (motor de reglas de p14).
# 6. Guardar la evaluacion en MongoDB.
# 7. Consultar el historial de un folio (por ejemplo, cuando se
#    revalua al paciente durante el traslado).
#
# IMPORTANTE:
# No se entrenan modelos nuevos: se reutilizan los de p11, p12 y p13
# a traves de las funciones de p14 (motor de recomendaciones).
#
# Ejecutar (desde esta carpeta):
#   streamlit run p18_evaluacion_emergencias.py
#
# Los documentos tienen la misma estructura que p15, asi que tambien
# aparecen en p16 (estadisticas) y en p17 (dashboard).
# ============================================================


# ============================================================
# 1. LIBRERIAS
# ============================================================
import os
import sys
import uuid
import importlib

from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote_plus

import certifi
import pandas as pd
import plotly.express as px
import streamlit as st

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError


# ============================================================
# 2. IMPORTAR EL MOTOR DE RECOMENDACIONES (p14)
# ============================================================
RUTA_BASE = Path(__file__).resolve().parent

# p14 esta en la misma carpeta que este archivo.
if str(RUTA_BASE) not in sys.path:
    sys.path.insert(0, str(RUTA_BASE))

# Nombres con los que puede estar guardado el archivo de p14.
NOMBRES_P14 = [
    "p14_motor_recomendaciones_emergencias",   # nombre en el repositorio
    "p14emergexia",                            # nombre en la carpeta de practicas
    "p14motor_recomendaciones"
]


def importar_motor():
    for nombre in NOMBRES_P14:
        if (RUTA_BASE / f"{nombre}.py").exists():
            return importlib.import_module(nombre)
    raise FileNotFoundError(
        "No se encontro el archivo de p14 en esta carpeta. Nombres buscados: "
        + ", ".join(n + ".py" for n in NOMBRES_P14)
    )


# ============================================================
# 3. CONFIGURACION
# ============================================================
# Primero el .env de esta carpeta (si existe) y luego backend/.env.
load_dotenv(RUTA_BASE / ".env")
load_dotenv(RUTA_BASE.parent / ".env")

MONGO_DB = os.getenv("MONGO_DB") or "emergexia"
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION_IA") or "analisis_emergencias_ia"

COLORES_PERFIL = {
    "Riesgo bajo": "#2E7D32",
    "Riesgo moderado": "#F9A825",
    "Riesgo medio-alto": "#EF6C00",
    "Riesgo alto": "#C62828"
}


# ============================================================
# 4. INTERFAZ
# ============================================================
st.set_page_config(page_title="Emergexia - Evaluacion", page_icon="🚑", layout="wide")

st.title("🚑 EMERGEXIA")
st.subheader("Evaluacion inteligente de emergencias")
st.markdown(
    """
    Esta aplicacion integra tres tecnicas de inteligencia artificial:

    - **Random Forest:** estima si la emergencia es critica.
    - **K-Means:** identifica el perfil de riesgo del paciente.
    - **PCA:** ubica la emergencia en un mapa de dos dimensiones.

    Despues, el motor de reglas asigna la **prioridad** y las **recomendaciones**
    para la ambulancia que sale del Hospital IMSS 220 (Toluca).
    """
)
st.divider()


# ============================================================
# 5. CARGAR LOS MODELOS (una sola vez)
# ============================================================
@st.cache_resource
def cargar_modelos():
    """No entrena nada: carga los .joblib de p11, p12 y p13 con la funcion de p14."""
    motor = importar_motor()
    return motor, motor.cargar_modelos()


try:
    motor, modelos = cargar_modelos()
except FileNotFoundError as error:
    st.error("No se encontraron los modelos o el archivo de p14. Ejecuta primero p10 a p13.")
    st.exception(error)
    st.stop()
except Exception as error:
    st.error("No fue posible cargar los modelos.")
    st.exception(error)
    st.stop()

st.success("Los modelos de Machine Learning se cargaron correctamente.")


# ============================================================
# 6. CONEXION A MONGODB (igual que p15, p16 y p17)
# ============================================================
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


@st.cache_resource
def obtener_coleccion():
    """Se conecta una sola vez y reutiliza la conexion."""

    uri = construir_uri()
    opciones = {"serverSelectionTimeoutMS": 10000}

    if uri.startswith("mongodb+srv://") or "mongodb.net" in uri:
        opciones["tlsCAFile"] = certifi.where()

    cliente = MongoClient(uri, **opciones)
    cliente.admin.command("ping")

    coleccion = cliente[MONGO_DB][MONGO_COLLECTION]

    # id_analisis es unico; un folio puede tener varias evaluaciones.
    coleccion.create_index("id_analisis", unique=True)
    coleccion.create_index("folio_emergencia")
    coleccion.create_index("fecha_registro")

    return coleccion


# ============================================================
# 7. CAPTURA DE LA EMERGENCIA
# ============================================================
st.header("1. Datos de la emergencia")
st.info("Usa el mismo folio para revaluar al paciente y consultar su historial.")

with st.form("formulario_emergencia"):

    folio = st.text_input("Folio de la emergencia", placeholder="Ejemplo: EMG-0001")

    col1, col2 = st.columns(2)

    with col1:
        edad = st.number_input("Edad del paciente (anios)", min_value=0, max_value=110, value=45, step=1)
        frecuencia_cardiaca = st.number_input("Frecuencia cardiaca (lpm)", min_value=20, max_value=250,
                                              value=90, step=1)
        saturacion_oxigeno = st.number_input("Saturacion de oxigeno (%)", min_value=50.0, max_value=100.0,
                                             value=95.0, step=0.5)

    with col2:
        distancia_km = st.number_input("Distancia al Hospital IMSS 220 (km)", min_value=0.0, max_value=100.0,
                                       value=8.0, step=0.5)
        ambulancias_ocupadas = st.number_input("Ambulancias ocupadas en este momento", min_value=0,
                                               max_value=20, value=1, step=1)

    enviar = st.form_submit_button("Evaluar emergencia y guardar", use_container_width=True)


# ============================================================
# 8. PROCESAR LA EVALUACION
# ============================================================
if enviar:

    if not folio.strip():
        st.error("Escribe el folio de la emergencia.")
        st.stop()

    folio = folio.strip().upper()

    # Mismo orden de columnas con el que se entrenaron los modelos.
    emergencia = pd.DataFrame([{
        "edad": float(edad),
        "frecuencia_cardiaca": float(frecuencia_cardiaca),
        "saturacion_oxigeno": float(saturacion_oxigeno),
        "distancia_km": float(distancia_km)
    }])

    try:
        prediccion = motor.predecir_criticidad(emergencia, modelos["supervisado"])
        perfil = motor.identificar_perfil(emergencia, modelos["kmeans"],
                                          modelos["escalador_kmeans"], modelos["mapa_perfiles"])
        pca = motor.proyectar_pca(emergencia, modelos["pca"], modelos["escalador_pca"])
        prioridad, recomendaciones = motor.generar_recomendaciones(
            emergencia, prediccion, perfil, int(ambulancias_ocupadas))

    except Exception as error:
        st.error("Ocurrio un problema durante el analisis.")
        st.exception(error)
        st.stop()

    st.divider()
    st.header("2. Resultado del analisis")

    # ---------- Prioridad (lo primero que necesita el Administrador) ----------
    if prioridad.startswith("PRIORIDAD 1"):
        st.error(f"### {prioridad}")
    elif prioridad.startswith("PRIORIDAD 2"):
        st.warning(f"### {prioridad}")
    else:
        st.success(f"### {prioridad}")

    # ---------- Random Forest y K-Means ----------
    col1, col2, col3 = st.columns(3)
    col1.metric("Probabilidad de ser critica", f"{prediccion['probabilidad_critica'] * 100:.1f}%")
    col2.metric("Clasificacion", prediccion["resultado"].replace("EMERGENCIA ", ""))
    col3.metric("Perfil de riesgo (K-Means)", perfil["perfil"])

    st.caption("Las probabilidades son estimaciones del modelo y no sustituyen la valoracion "
               "del personal medico.")

    # ---------- Recomendaciones ----------
    st.subheader("Recomendaciones")
    for numero, texto in enumerate(recomendaciones, start=1):
        st.write(f"**{numero}.** {texto}")

    # ---------- PCA ----------
    st.subheader("Ubicacion en el mapa PCA")

    col1, col2 = st.columns([1, 2])
    col1.metric("PC1", f"{pca['PC1']:.4f}")
    col1.metric("PC2", f"{pca['PC2']:.4f}")
    col1.metric("Cluster", perfil["cluster"])

    # Si existe el archivo de p13, dibujamos la emergencia junto a las 500 de entrenamiento.
    carpetas = [RUTA_BASE / "resultados_sistema_inteligente", RUTA_BASE / "resultados_p10"]
    archivo_pca = next((c / "emergencias_pca.csv" for c in carpetas if (c / "emergencias_pca.csv").exists()), None)

    if archivo_pca is not None:
        referencia = pd.read_csv(archivo_pca)
        figura = px.scatter(referencia, x="PC1", y="PC2", color="perfil", opacity=0.35,
                            color_discrete_map=COLORES_PERFIL,
                            labels={"perfil": "Perfil"})
        figura.add_scatter(x=[pca["PC1"]], y=[pca["PC2"]], mode="markers+text",
                           marker=dict(size=20, color="white", symbol="star",
                                       line=dict(width=2, color="black")),
                           text=[folio], textposition="top center", name="Esta emergencia")
        figura.update_layout(height=420, margin=dict(t=20))
        col2.plotly_chart(figura, use_container_width=True)
    else:
        col2.info("Ejecuta p13 para ver la emergencia junto a las 500 de referencia.")

    # ========================================================
    # 9. GUARDAR EN MONGODB (misma estructura que p15)
    # ========================================================
    id_analisis = str(uuid.uuid4())

    documento = {
        "id_analisis": id_analisis,
        "folio_emergencia": folio,
        "sistema": "Emergexia",
        "etapa": 9,
        "fecha_registro": datetime.now(timezone.utc),
        "archivo_origen": "p18_evaluacion_emergencias.py",
        "datos_paciente": {
            "edad": float(edad),
            "frecuencia_cardiaca": float(frecuencia_cardiaca),
            "saturacion_oxigeno": float(saturacion_oxigeno),
            "distancia_km": float(distancia_km)
        },
        "ambulancias_ocupadas": int(ambulancias_ocupadas),
        "clasificacion": {
            "critica": bool(prediccion["prediccion"]),
            "resultado": prediccion["resultado"],
            "probabilidad_critica": float(prediccion["probabilidad_critica"])
        },
        "perfil_riesgo": {"cluster": int(perfil["cluster"]), "perfil": perfil["perfil"]},
        "pca": {"PC1": float(pca["PC1"]), "PC2": float(pca["PC2"])},
        "prioridad": prioridad,
        "recomendaciones": recomendaciones     # se guarda como lista, no como texto
    }

    try:
        with st.spinner("Guardando en MongoDB..."):
            obtener_coleccion().insert_one(documento)

        st.success("La evaluacion se guardo correctamente en MongoDB.")
        st.write("**Folio:**", folio, " | **Evaluacion:**", id_analisis)
        st.write("**Base de datos:**", MONGO_DB, " | **Coleccion:**", MONGO_COLLECTION)

    except ValueError as error:
        st.error(f"Error de configuracion: {error}")
    except PyMongoError as error:
        st.error("No fue posible guardar la evaluacion en MongoDB.")
        st.exception(error)
    except Exception as error:
        st.error("Ocurrio un error inesperado al guardar.")
        st.exception(error)


# ============================================================
# 10. HISTORIAL DE UN FOLIO
# ============================================================
st.divider()
st.header("3. Historial de evaluaciones de una emergencia")
st.write("Muestra todas las evaluaciones guardadas con el mismo folio, de la mas reciente a la mas antigua.")

folio_consulta = st.text_input("Folio a consultar", key="folio_consulta", placeholder="Ejemplo: EMG-0001")

if st.button("Consultar historial", use_container_width=True):

    if not folio_consulta.strip():
        st.warning("Escribe el folio de la emergencia.")

    else:
        try:
            registros = list(
                obtener_coleccion().find(
                    {"sistema": "Emergexia", "folio_emergencia": folio_consulta.strip().upper()},
                    {"_id": 0}
                ).sort("fecha_registro", -1)
            )

            if not registros:
                st.info("No hay evaluaciones guardadas con ese folio.")

            else:
                st.success(f"Se encontraron {len(registros)} evaluaciones.")

                historial = pd.DataFrame([{
                    "Fecha": r.get("fecha_registro"),
                    "Edad": r["datos_paciente"]["edad"],
                    "Frecuencia cardiaca": r["datos_paciente"]["frecuencia_cardiaca"],
                    "Oxigeno (%)": r["datos_paciente"]["saturacion_oxigeno"],
                    "Distancia (km)": r["datos_paciente"]["distancia_km"],
                    "Resultado": r["clasificacion"]["resultado"],
                    "Prob. critica (%)": round(r["clasificacion"]["probabilidad_critica"] * 100, 1),
                    "Perfil": r["perfil_riesgo"]["perfil"],
                    "Prioridad": r.get("prioridad"),
                    "ID analisis": r.get("id_analisis")
                } for r in registros])

                st.dataframe(historial, use_container_width=True, hide_index=True)

                # Con 2 o mas evaluaciones se ve como cambio el paciente.
                if len(historial) >= 2:
                    evolucion = historial.sort_values("Fecha")
                    figura = px.line(evolucion, x="Fecha", y=["Oxigeno (%)", "Prob. critica (%)"],
                                     markers=True, title="Evolucion del paciente",
                                     labels={"value": "Valor", "variable": ""})
                    st.plotly_chart(figura, use_container_width=True)

        except ValueError as error:
            st.error(f"Error de configuracion: {error}")
        except PyMongoError as error:
            st.error("No fue posible consultar MongoDB.")
            st.exception(error)
        except Exception as error:
            st.error("Ocurrio un error al consultar el historial.")
            st.exception(error)


# ============================================================
# 11. PIE DE PAGINA
# ============================================================
st.divider()
st.caption("EMERGEXIA | Evaluacion de emergencias con Machine Learning. "
           "Los resultados apoyan al Administrador y no sustituyen la valoracion medica.")
