# ============================================================
# PROYECTO: EMERGEXIA
# PRACTICA 10 - ETAPA 8: DASHBOARD DE EMERGENCIAS INTELIGENTE
# ARCHIVO: p17_dashboard_emergencias.py
#
# Objetivo:
# Dashboard web para que el Administrador consulte y visualice los
# analisis de emergencias guardados en MongoDB por p15.
#
# Tecnologias: Python, Streamlit, Pandas, Plotly, PyMongo, MongoDB Atlas.
#
# Ejecutar (desde esta carpeta):
#   streamlit run p17_dashboard_emergencias.py
#
# Conexion: el mismo backend/.env que p15 y p16 (MONGO_URI y MONGO_DB,
# o MONGO_USER, MONGO_PASSWORD y MONGO_CLUSTER).
# Coleccion: analisis_emergencias_ia (se cambia con MONGO_COLLECTION_IA).
# ============================================================


# ------------------------------------------------------------
# 1. LIBRERIAS
# ------------------------------------------------------------
import os
import certifi
import pandas as pd
import plotly.express as px
import streamlit as st

from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError


# ------------------------------------------------------------
# 2. CONFIGURAR LA PAGINA (debe ir antes que cualquier otro elemento)
# ------------------------------------------------------------
st.set_page_config(
    page_title="Emergexia | Dashboard",
    page_icon="🚑",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ------------------------------------------------------------
# 3. CONFIGURACION
# ------------------------------------------------------------
RUTA_BASE = Path(__file__).resolve().parent

# Primero el .env de esta carpeta (si existe) y luego backend/.env.
load_dotenv(RUTA_BASE / ".env")
load_dotenv(RUTA_BASE.parent / ".env")

MONGO_DB = os.getenv("MONGO_DB") or "emergexia"
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION_IA") or "analisis_emergencias_ia"

LIMITE_AMBULANCIAS_OCUPADAS = 3

# Orden y colores fijos para que todas las graficas coincidan.
ORDEN_PERFILES = ["Riesgo bajo", "Riesgo moderado", "Riesgo medio-alto", "Riesgo alto"]
COLORES_PERFIL = {
    "Riesgo bajo": "#2E7D32",
    "Riesgo moderado": "#F9A825",
    "Riesgo medio-alto": "#EF6C00",
    "Riesgo alto": "#C62828"
}
COLORES_RESULTADO = {"EMERGENCIA CRITICA": "#C62828", "EMERGENCIA NO CRITICA": "#2E7D32"}


# ------------------------------------------------------------
# 4. CONEXION A MONGODB (igual que p15 y p16)
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


@st.cache_resource
def obtener_cliente():
    """cache_resource reutiliza la misma conexion en cada recarga de la pagina."""

    uri = construir_uri()
    opciones = {"serverSelectionTimeoutMS": 15000}

    if uri.startswith("mongodb+srv://") or "mongodb.net" in uri:
        opciones["tlsCAFile"] = certifi.where()

    cliente = MongoClient(uri, **opciones)
    cliente.admin.command("ping")
    return cliente


# ------------------------------------------------------------
# 5. CARGAR LOS ANALISIS
# ------------------------------------------------------------
def documentos_a_tabla(documentos):
    """Convierte los documentos anidados de p15 en una tabla (una fila por analisis)."""

    filas = []

    for d in documentos:
        paciente = d.get("datos_paciente", {})
        clasificacion = d.get("clasificacion", {})
        perfil = d.get("perfil_riesgo", {})
        pca = d.get("pca", {})

        filas.append({
            "id_analisis": d.get("id_analisis"),
            "fecha_registro": d.get("fecha_registro"),
            "edad": paciente.get("edad"),
            "frecuencia_cardiaca": paciente.get("frecuencia_cardiaca"),
            "saturacion_oxigeno": paciente.get("saturacion_oxigeno"),
            "distancia_km": paciente.get("distancia_km"),
            "ambulancias_ocupadas": d.get("ambulancias_ocupadas"),
            "critica": clasificacion.get("critica"),
            "resultado": clasificacion.get("resultado"),
            "probabilidad_critica": clasificacion.get("probabilidad_critica"),
            "cluster": perfil.get("cluster"),
            "perfil": perfil.get("perfil"),
            "PC1": pca.get("PC1"),
            "PC2": pca.get("PC2"),
            "prioridad": d.get("prioridad"),
            "recomendaciones": d.get("recomendaciones", [])
        })

    tabla = pd.DataFrame(filas)

    if tabla.empty:
        return tabla

    numericas = ["edad", "frecuencia_cardiaca", "saturacion_oxigeno", "distancia_km",
                 "ambulancias_ocupadas", "probabilidad_critica", "cluster", "PC1", "PC2"]
    tabla[numericas] = tabla[numericas].apply(pd.to_numeric, errors="coerce")
    tabla["fecha_registro"] = pd.to_datetime(tabla["fecha_registro"], errors="coerce", utc=True)
    tabla["critica"] = tabla["critica"].fillna(False).astype(bool)
    tabla["pidio_apoyo"] = tabla["ambulancias_ocupadas"] > LIMITE_AMBULANCIAS_OCUPADAS

    return tabla


@st.cache_data(ttl=60)
def cargar_datos():
    """ttl=60: los datos se guardan en cache 60 segundos."""

    coleccion = obtener_cliente()[MONGO_DB][MONGO_COLLECTION]
    documentos = list(coleccion.find({"sistema": "Emergexia"}, {"_id": 0}).sort("fecha_registro", -1))
    return documentos_a_tabla(documentos)


# ------------------------------------------------------------
# 6. FILTROS (barra lateral)
# ------------------------------------------------------------
def aplicar_filtros(tabla):

    st.sidebar.header("Filtros de consulta")

    perfiles = [p for p in ORDEN_PERFILES if p in tabla["perfil"].unique()]
    perfiles += sorted(set(tabla["perfil"].dropna()) - set(perfiles))
    prioridades = sorted(tabla["prioridad"].dropna().unique())
    resultados = sorted(tabla["resultado"].dropna().unique())

    sel_perfiles = st.sidebar.multiselect("Perfil de riesgo", perfiles, default=perfiles)
    sel_prioridades = st.sidebar.multiselect("Prioridad", prioridades, default=prioridades)
    sel_resultados = st.sidebar.multiselect("Resultado", resultados, default=resultados)

    return tabla[
        tabla["perfil"].isin(sel_perfiles)
        & tabla["prioridad"].isin(sel_prioridades)
        & tabla["resultado"].isin(sel_resultados)
    ]


# ------------------------------------------------------------
# 7. SECCIONES DEL DASHBOARD
# ------------------------------------------------------------
def mostrar_encabezado():

    st.title("🚑 EMERGEXIA")
    st.subheader("Dashboard de emergencias inteligente")
    st.markdown(
        "Consulta de los analisis generados con Random Forest, K-Means y PCA, "
        "guardados en MongoDB. Ambulancias con base en el Hospital IMSS 220 (Toluca)."
    )
    st.divider()


def mostrar_indicadores(tabla):

    st.subheader("1. Indicadores generales")

    total = len(tabla)
    criticas = int(tabla["critica"].sum())
    prioridad_1 = int(tabla["prioridad"].str.startswith("PRIORIDAD 1").sum())
    apoyo = int(tabla["pidio_apoyo"].sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de analisis", total)
    c2.metric("Emergencias criticas", criticas, f"{criticas / total * 100:.1f}% del total", delta_color="inverse")
    c3.metric("Prioridad 1 (inmediata)", prioridad_1)
    c4.metric("Solicitudes de apoyo a otros hospitales", apoyo)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Probabilidad promedio de ser critica", f"{tabla['probabilidad_critica'].mean() * 100:.1f}%")
    c6.metric("Saturacion de oxigeno promedio", f"{tabla['saturacion_oxigeno'].mean():.1f}%")
    c7.metric("Frecuencia cardiaca promedio", f"{tabla['frecuencia_cardiaca'].mean():.0f} lpm")
    c8.metric("Distancia promedio al IMSS 220", f"{tabla['distancia_km'].mean():.1f} km")


def mostrar_resultados(tabla):

    st.subheader("2. Criticas vs no criticas")

    conteo = tabla["resultado"].value_counts().reset_index()
    conteo.columns = ["resultado", "cantidad"]

    figura = px.pie(conteo, names="resultado", values="cantidad", hole=0.45,
                    color="resultado", color_discrete_map=COLORES_RESULTADO,
                    title="Clasificacion de Random Forest")
    figura.update_traces(textposition="inside", textinfo="percent+value")
    st.plotly_chart(figura, use_container_width=True)


def mostrar_perfiles(tabla):

    st.subheader("3. Perfiles de riesgo (K-Means)")

    conteo = tabla.groupby("perfil").size().reset_index(name="cantidad")

    figura = px.bar(conteo, x="perfil", y="cantidad", text="cantidad",
                    color="perfil", color_discrete_map=COLORES_PERFIL,
                    category_orders={"perfil": ORDEN_PERFILES},
                    title="Analisis por perfil de riesgo",
                    labels={"perfil": "Perfil", "cantidad": "Analisis"})
    figura.update_traces(textposition="outside")
    figura.update_layout(showlegend=False)
    st.plotly_chart(figura, use_container_width=True)


def mostrar_prioridades(tabla):

    st.subheader("4. Emergencias por prioridad")

    conteo = tabla.groupby(["prioridad", "resultado"]).size().reset_index(name="cantidad")

    figura = px.bar(conteo, x="prioridad", y="cantidad", color="resultado", text="cantidad",
                    color_discrete_map=COLORES_RESULTADO,
                    category_orders={"prioridad": sorted(tabla["prioridad"].dropna().unique())},
                    title="Prioridad asignada por el motor de reglas",
                    labels={"prioridad": "Prioridad", "cantidad": "Emergencias", "resultado": "Resultado"})
    st.plotly_chart(figura, use_container_width=True)


def mostrar_signos_por_perfil(tabla):

    st.subheader("5. Signos vitales promedio por perfil")

    variables = {
        "edad": "Edad (anios)",
        "frecuencia_cardiaca": "Frecuencia cardiaca (lpm)",
        "saturacion_oxigeno": "Saturacion de oxigeno (%)",
        "distancia_km": "Distancia (km)"
    }

    # Cada variable tiene su propia grafica porque sus escalas son distintas.
    promedios = tabla.groupby("perfil")[list(variables)].mean().reset_index()
    promedios = promedios.melt(id_vars="perfil", var_name="variable", value_name="promedio")
    promedios["variable"] = promedios["variable"].map(variables)

    figura = px.bar(promedios, x="perfil", y="promedio", color="perfil", text_auto=".1f",
                    facet_col="variable", facet_col_wrap=4,
                    color_discrete_map=COLORES_PERFIL,
                    category_orders={"perfil": ORDEN_PERFILES},
                    labels={"perfil": "", "promedio": "Promedio"})
    figura.update_yaxes(matches=None, showticklabels=True)
    figura.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    figura.update_layout(showlegend=False, height=420)
    st.plotly_chart(figura, use_container_width=True)


def mostrar_pca(tabla):

    st.subheader("6. Mapa de emergencias (PCA)")

    datos = tabla.dropna(subset=["PC1", "PC2"])

    if datos.empty:
        st.info("No hay coordenadas PCA disponibles.")
        return

    figura = px.scatter(datos, x="PC1", y="PC2", color="perfil", symbol="resultado",
                        color_discrete_map=COLORES_PERFIL,
                        category_orders={"perfil": ORDEN_PERFILES},
                        hover_data=["edad", "frecuencia_cardiaca", "saturacion_oxigeno",
                                    "distancia_km", "prioridad"],
                        title="Emergencias en dos componentes principales",
                        labels={"PC1": "Componente principal 1", "PC2": "Componente principal 2",
                                "perfil": "Perfil", "resultado": "Resultado"})
    figura.update_traces(marker=dict(size=11))
    st.plotly_chart(figura, use_container_width=True)

    st.caption(
        "PC1 y PC2 conservan cerca del 52% de la variabilidad de las 4 variables "
        "(p13). La grafica es exploratoria: las decisiones usan las variables originales."
    )


def mostrar_ultimo_analisis(tabla):

    st.subheader("7. Ultimo analisis y sus recomendaciones")

    ultimo = tabla.sort_values("fecha_registro", ascending=False).iloc[0]

    c1, c2, c3 = st.columns(3)
    c1.metric("Prioridad", ultimo["prioridad"])
    c2.metric("Resultado", ultimo["resultado"], f"{ultimo['probabilidad_critica'] * 100:.1f}% critica",
              delta_color="off")
    c3.metric("Perfil de riesgo", ultimo["perfil"])

    st.write(
        f"Paciente de **{ultimo['edad']:.0f} anios** · FC **{ultimo['frecuencia_cardiaca']:.0f} lpm** · "
        f"SpO2 **{ultimo['saturacion_oxigeno']:.1f}%** · a **{ultimo['distancia_km']:.1f} km** del IMSS 220 · "
        f"**{ultimo['ambulancias_ocupadas']:.0f}** ambulancias ocupadas"
    )

    for numero, texto in enumerate(ultimo["recomendaciones"], start=1):
        st.markdown(f"{numero}. {texto}")


def mostrar_historial(tabla):

    st.subheader("8. Historial de analisis")

    columnas = ["fecha_registro", "edad", "frecuencia_cardiaca", "saturacion_oxigeno", "distancia_km",
                "ambulancias_ocupadas", "resultado", "probabilidad_critica", "perfil", "prioridad",
                "id_analisis"]

    historial = tabla[columnas].copy()

    # Probabilidad de 0 a 100 para mostrarla como barra de porcentaje.
    historial["probabilidad_critica"] = (historial["probabilidad_critica"] * 100).round(1)

    st.dataframe(
        historial,
        use_container_width=True,
        hide_index=True,
        column_config={
            "fecha_registro": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
            "probabilidad_critica": st.column_config.ProgressColumn(
                "Prob. critica", min_value=0, max_value=100, format="%.1f%%"),
        }
    )

    csv = historial.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Descargar historial CSV", data=csv,
                       file_name="emergexia_historial.csv", mime="text/csv")


# ------------------------------------------------------------
# 8. APLICACION PRINCIPAL
# ------------------------------------------------------------
def main():

    mostrar_encabezado()

    if st.sidebar.button("Actualizar informacion"):
        cargar_datos.clear()
        st.rerun()

    try:
        tabla = cargar_datos()

        if tabla.empty:
            st.warning("Todavia no hay analisis guardados en MongoDB.")
            st.info("Ejecuta primero p14_motor_recomendaciones_emergencias.py y "
                    "p15_persistencia_mongodb_emergencias.py.")
            return

        st.sidebar.success("Conexion con MongoDB activa")
        st.sidebar.write("Base de datos:", MONGO_DB)
        st.sidebar.write("Coleccion:", MONGO_COLLECTION)

        filtrada = aplicar_filtros(tabla)
        st.sidebar.write("Analisis encontrados:", len(filtrada))

        if filtrada.empty:
            st.warning("No hay analisis para los filtros seleccionados.")
            return

        mostrar_indicadores(filtrada)
        st.divider()

        c1, c2 = st.columns(2)
        with c1:
            mostrar_resultados(filtrada)
        with c2:
            mostrar_perfiles(filtrada)
        st.divider()

        mostrar_prioridades(filtrada)
        st.divider()

        mostrar_signos_por_perfil(filtrada)
        st.divider()

        mostrar_pca(filtrada)
        st.divider()

        mostrar_ultimo_analisis(filtrada)
        st.divider()

        mostrar_historial(filtrada)
        st.divider()

        st.info(
            "Las predicciones y prioridades son estimaciones de modelos entrenados con datos "
            "sinteticos. Apoyan al Administrador, pero no sustituyen la valoracion del personal medico."
        )

    except ValueError as error:
        st.error(f"Error de configuracion: {error}")

    except PyMongoError as error:
        st.error("No fue posible consultar MongoDB.")
        st.code(str(error))

    except Exception as error:
        st.error("Se produjo un error inesperado.")
        st.code(str(error))


if __name__ == "__main__":
    main()
