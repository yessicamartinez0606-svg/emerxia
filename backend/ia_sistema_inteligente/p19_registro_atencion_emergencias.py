# ============================================================
# PROYECTO: EMERGEXIA
# PRACTICA 10 - ETAPA 11: REGISTRO INTEGRAL DE ATENCION
# ARCHIVO: p19_registro_atencion_emergencias.py
#
# OBJETIVO:
# Registrar el expediente del paciente, la atencion de cada
# emergencia (ambulancia, operador, tomas de signos vitales) y el
# resultado de inteligencia artificial.
#
# COLECCIONES (separadas de las del sistema real):
#   1. pacientes_ia      Expediente permanente del paciente.
#   2. atenciones_ia     Cada atencion: servicio y tomas de signos vitales.
#   3. MONGO_COLLECTION_IA (por defecto analisis_emergencias_ia)
#                        Analisis de IA, con la misma estructura de p15,
#                        para que aparezca en p16 y en el dashboard p17.
#
# MODELOS REUTILIZADOS: Random Forest, K-Means y PCA (via p14).
# IMPORTANTE: no se entrenan modelos nuevos.
#
# Ejecutar (en la carpeta donde estan p14 y los modelos):
#   streamlit run p19_registro_atencion_emergencias.py
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
import streamlit as st

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import PyMongoError


# ============================================================
# 2. IMPORTAR EL MOTOR DE IA (p14)
# ============================================================
RUTA_BASE = Path(__file__).resolve().parent

if str(RUTA_BASE) not in sys.path:
    sys.path.insert(0, str(RUTA_BASE))

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
load_dotenv(RUTA_BASE / ".env")
load_dotenv(RUTA_BASE.parent / ".env")

MONGO_DB = os.getenv("MONGO_DB") or "emergexia"
MONGO_COLLECTION_IA = os.getenv("MONGO_COLLECTION_IA") or "analisis_emergencias_ia"

COLECCION_PACIENTES = "pacientes_ia"
COLECCION_ATENCIONES = "atenciones_ia"

TIPOS_EMERGENCIA = ["Cardiaca", "Respiratoria", "Traumatismo / accidente", "Neurologica",
                    "Obstetrica", "Intoxicacion", "Otra"]

HOSPITALES_DESTINO = ["Hospital IMSS 220 (Paseo Tollocan)", "Otro hospital de apoyo"]


# ============================================================
# 4. INTERFAZ
# ============================================================
st.set_page_config(page_title="Emergexia - Registro de atencion", page_icon="🚑", layout="wide")

st.title("🚑 EMERGEXIA")
st.subheader("Etapa 11 - Registro integral de atencion")
st.markdown(
    """
    Registro que integra:

    - Expediente permanente del paciente.
    - Datos del servicio: folio, tipo de emergencia, ambulancia y operador.
    - Tomas de signos vitales durante la atencion.
    - Resumen de la atencion (peores signos registrados).
    - Analisis con inteligencia artificial: prioridad y recomendaciones.
    """
)
st.divider()


# ============================================================
# 5. CARGAR MODELOS (sin entrenar)
# ============================================================
@st.cache_resource
def cargar_modelos():
    motor = importar_motor()
    return motor, motor.cargar_modelos()


try:
    motor, modelos = cargar_modelos()
    st.success("Modelos de inteligencia artificial cargados.")
except Exception as error:
    st.error("No fue posible cargar los modelos. Ejecuta p10 a p13 en esta carpeta.")
    st.exception(error)
    st.stop()


# ============================================================
# 6. CONEXION A MONGODB
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
def obtener_colecciones():
    """Se conecta una sola vez, crea los indices y devuelve las 3 colecciones."""

    uri = construir_uri()
    opciones = {"serverSelectionTimeoutMS": 15000}

    if uri.startswith("mongodb+srv://") or "mongodb.net" in uri:
        opciones["tlsCAFile"] = certifi.where()

    cliente = MongoClient(uri, **opciones)
    cliente.admin.command("ping")

    base = cliente[MONGO_DB]
    pacientes = base[COLECCION_PACIENTES]
    atenciones = base[COLECCION_ATENCIONES]
    analisis = base[MONGO_COLLECTION_IA]

    pacientes.create_index("id_paciente", unique=True)          # un expediente por paciente
    atenciones.create_index("id_atencion", unique=True)
    atenciones.create_index([("id_paciente", 1), ("fecha_registro", -1)])
    atenciones.create_index("folio_emergencia")
    analisis.create_index("id_analisis", unique=True)

    return pacientes, atenciones, analisis


# ============================================================
# 7. VALIDAR Y RESUMIR LAS TOMAS DE SIGNOS VITALES
# ============================================================
RANGOS = {
    "frecuencia_cardiaca": (20, 250, "La frecuencia cardiaca debe estar entre 20 y 250 lpm."),
    "saturacion_oxigeno": (50, 100, "La saturacion de oxigeno debe estar entre 50 y 100 %."),
    "presion_sistolica": (40, 260, "La presion sistolica debe estar entre 40 y 260 mmHg."),
    "temperatura": (30, 43, "La temperatura debe estar entre 30 y 43 °C.")
}


def procesar_tomas(tabla):
    """
    Valida la tabla de tomas y agrega una columna de alertas por toma.
    Cada fila es una medicion (en el lugar, durante el traslado, al llegar).
    """
    tomas = tabla.copy()

    tomas["momento"] = tomas["momento"].fillna("").astype(str).str.strip()
    tomas = tomas[tomas["momento"] != ""].copy()

    if tomas.empty:
        raise ValueError("Registra al menos una toma de signos vitales.")

    for columna in RANGOS:
        tomas[columna] = pd.to_numeric(tomas[columna], errors="coerce")

    if tomas[list(RANGOS)].isna().any().any():
        raise ValueError("Completa todos los signos vitales de cada toma.")

    for columna, (minimo, maximo, mensaje) in RANGOS.items():
        if not tomas[columna].between(minimo, maximo).all():
            raise ValueError(mensaje)

    tomas["responsable"] = tomas["responsable"].fillna("").astype(str).str.strip()

    # Alertas de cada toma (mismos umbrales que el motor de reglas de p14).
    def alertas(fila):
        lista = []
        if fila["saturacion_oxigeno"] < 90:
            lista.append("Oxigeno bajo")
        if fila["frecuencia_cardiaca"] > 120 or fila["frecuencia_cardiaca"] < 50:
            lista.append("FC anormal")
        if fila["presion_sistolica"] < 90:
            lista.append("Hipotension")
        if fila["temperatura"] >= 38:
            lista.append("Fiebre")
        return ", ".join(lista) if lista else "Sin alertas"

    tomas["alertas"] = tomas.apply(alertas, axis=1)

    return tomas


def resumir_tomas(tomas):
    """
    Para los modelos usamos los PEORES signos de la atencion
    (como en SmartAcademy se usaba la asistencia general calculada).
    """
    # La FC "peor" es la que mas se aleja de 80 lpm (puede ser alta o baja).
    fc_peor = tomas.loc[(tomas["frecuencia_cardiaca"] - 80).abs().idxmax(), "frecuencia_cardiaca"]

    return {
        "total_tomas": int(len(tomas)),
        "saturacion_minima": float(tomas["saturacion_oxigeno"].min()),
        "frecuencia_peor": float(fc_peor),
        "frecuencia_promedio": round(float(tomas["frecuencia_cardiaca"].mean()), 1),
        "presion_minima": float(tomas["presion_sistolica"].min()),
        "temperatura_maxima": float(tomas["temperatura"].max()),
        "tomas_con_alerta": int((tomas["alertas"] != "Sin alertas").sum())
    }


def tomas_a_documentos(tomas):
    return [{
        "momento": fila["momento"],
        "responsable": fila["responsable"],
        "signos": {
            "frecuencia_cardiaca": float(fila["frecuencia_cardiaca"]),
            "saturacion_oxigeno": float(fila["saturacion_oxigeno"]),
            "presion_sistolica": float(fila["presion_sistolica"]),
            "temperatura": float(fila["temperatura"])
        },
        "alertas": fila["alertas"]
    } for _, fila in tomas.iterrows()]


# ============================================================
# 8. REGISTRAR O ACTUALIZAR EL EXPEDIENTE
# ============================================================
def guardar_paciente(coleccion, id_paciente, nombre, edad, sexo, tipo_sangre, alergias, telefono_contacto):
    """
    Si el paciente existe, actualiza sus datos; si no, crea su expediente.
    No borra atenciones anteriores.
    """
    ahora = datetime.now(timezone.utc)

    coleccion.update_one(
        {"id_paciente": id_paciente},
        {
            "$set": {
                "nombre_completo": nombre,
                "edad": int(edad),
                "sexo": sexo,
                "tipo_sangre": tipo_sangre,
                "alergias": alergias,
                "telefono_contacto": telefono_contacto,
                "fecha_actualizacion": ahora
            },
            "$setOnInsert": {"id_paciente": id_paciente, "fecha_creacion": ahora}
        },
        upsert=True
    )


# ============================================================
# 9. FORMULARIO
# ============================================================
st.header("1. Expediente del paciente")

with st.form("formulario_atencion", clear_on_submit=False):

    col1, col2, col3 = st.columns(3)

    with col1:
        id_paciente = st.text_input("ID permanente del paciente", placeholder="Ejemplo: PAC-0001")
        nombre = st.text_input("Nombre completo")
        edad = st.number_input("Edad (anios)", min_value=0, max_value=110, value=45, step=1)

    with col2:
        sexo = st.selectbox("Sexo", ["Femenino", "Masculino", "Otro / no especificado"])
        tipo_sangre = st.selectbox("Tipo de sangre",
                                   ["Desconocido", "O+", "O-", "A+", "A-", "B+", "B-", "AB+", "AB-"])

    with col3:
        alergias = st.text_input("Alergias conocidas", placeholder="Ninguna")
        telefono_contacto = st.text_input("Telefono de un familiar o contacto")

    st.divider()
    st.header("2. Datos del servicio")

    col1, col2, col3 = st.columns(3)

    with col1:
        folio = st.text_input("Folio de la emergencia", placeholder="Ejemplo: EMG-0001")
        tipo_emergencia = st.selectbox("Tipo de emergencia", TIPOS_EMERGENCIA)

    with col2:
        ambulancia = st.text_input("Ambulancia (placa o numero)", placeholder="Ejemplo: AMB-03")
        operador = st.text_input("Operador que conduce")

    with col3:
        distancia_km = st.number_input("Distancia al Hospital IMSS 220 (km)", min_value=0.0,
                                       max_value=100.0, value=8.0, step=0.5)
        ambulancias_ocupadas = st.number_input("Ambulancias ocupadas en este momento", min_value=0,
                                               max_value=20, value=1, step=1)
        hospital_destino = st.selectbox("Hospital destino", HOSPITALES_DESTINO)

    st.divider()
    st.header("3. Tomas de signos vitales")
    st.write("Agrega una fila por cada medicion (en el lugar, en el traslado, al llegar). "
             "Para la IA se usan los peores valores de la atencion.")

    tabla_inicial = pd.DataFrame({
        "momento": ["En el lugar"],
        "responsable": [""],
        "frecuencia_cardiaca": [90],
        "saturacion_oxigeno": [95.0],
        "presion_sistolica": [120],
        "temperatura": [36.5]
    })

    tabla_tomas = st.data_editor(
        tabla_inicial,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_config={
            "momento": st.column_config.SelectboxColumn(
                "Momento", options=["En el lugar", "Durante el traslado", "Al llegar al hospital"],
                required=True),
            "responsable": st.column_config.TextColumn("Paramedico responsable"),
            "frecuencia_cardiaca": st.column_config.NumberColumn("FC (lpm)", min_value=20, max_value=250, step=1),
            "saturacion_oxigeno": st.column_config.NumberColumn("SpO2 (%)", min_value=50.0, max_value=100.0,
                                                                step=0.5, format="%.1f"),
            "presion_sistolica": st.column_config.NumberColumn("Presion sistolica (mmHg)", min_value=40,
                                                               max_value=260, step=1),
            "temperatura": st.column_config.NumberColumn("Temperatura (°C)", min_value=30.0, max_value=43.0,
                                                         step=0.1, format="%.1f")
        }
    )

    enviar = st.form_submit_button("Guardar expediente y evaluar la atencion", use_container_width=True)


# ============================================================
# 10. PROCESAR EL REGISTRO
# ============================================================
if enviar:

    # ---------- Validar datos generales ----------
    obligatorios = {
        "El ID del paciente": id_paciente,
        "El nombre del paciente": nombre,
        "El folio de la emergencia": folio,
        "La ambulancia": ambulancia,
        "El operador": operador
    }

    for campo, valor in obligatorios.items():
        if not valor.strip():
            st.error(f"{campo} es obligatorio.")
            st.stop()

    id_paciente = id_paciente.strip().upper()
    folio = folio.strip().upper()

    # ---------- Procesar tomas ----------
    try:
        tomas = procesar_tomas(tabla_tomas)
        resumen = resumir_tomas(tomas)
        documentos_tomas = tomas_a_documentos(tomas)
    except ValueError as error:
        st.error(str(error))
        st.stop()

    # ---------- Datos para los modelos (mismo orden del entrenamiento) ----------
    emergencia = pd.DataFrame([{
        "edad": float(edad),
        "frecuencia_cardiaca": resumen["frecuencia_peor"],
        "saturacion_oxigeno": resumen["saturacion_minima"],
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
        st.error("No fue posible ejecutar los modelos.")
        st.exception(error)
        st.stop()

    # Recomendaciones extra a partir de signos que los modelos no usan.
    if resumen["presion_minima"] < 90:
        recomendaciones.append("Presion sistolica baja: vigilar al paciente y avisar al hospital destino.")
    if resumen["temperatura_maxima"] >= 38:
        recomendaciones.append("Fiebre registrada: informarlo al recibir al paciente.")

    # ---------- Resumen de la atencion ----------
    st.divider()
    st.header("4. Resumen de la atencion")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tomas registradas", resumen["total_tomas"])
    c2.metric("SpO2 minima", f"{resumen['saturacion_minima']:.1f}%")
    c3.metric("FC mas alterada", f"{resumen['frecuencia_peor']:.0f} lpm")
    c4.metric("Tomas con alerta", resumen["tomas_con_alerta"])

    st.dataframe(tomas, use_container_width=True, hide_index=True)

    # ---------- Resultado de IA ----------
    st.header("5. Analisis de inteligencia artificial")

    if prioridad.startswith("PRIORIDAD 1"):
        st.error(f"### {prioridad}")
    elif prioridad.startswith("PRIORIDAD 2"):
        st.warning(f"### {prioridad}")
    else:
        st.success(f"### {prioridad}")

    c1, c2, c3 = st.columns(3)
    c1.metric("Probabilidad de ser critica", f"{prediccion['probabilidad_critica'] * 100:.1f}%")
    c2.metric("Clasificacion", prediccion["resultado"].replace("EMERGENCIA ", ""))
    c3.metric("Perfil de riesgo (K-Means)", perfil["perfil"])

    st.write(f"**Componentes PCA:** PC1 = {pca['PC1']:.4f} | PC2 = {pca['PC2']:.4f}")

    st.subheader("Recomendaciones")
    for numero, texto in enumerate(recomendaciones, start=1):
        st.write(f"{numero}. {texto}")

    # ---------- Documentos ----------
    id_atencion = str(uuid.uuid4())
    id_analisis = str(uuid.uuid4())
    fecha_actual = datetime.now(timezone.utc)

    documento_atencion = {
        "id_atencion": id_atencion,
        "id_paciente": id_paciente,
        "folio_emergencia": folio,
        "sistema": "Emergexia",
        "fecha_registro": fecha_actual,
        "servicio": {
            "tipo_emergencia": tipo_emergencia,
            "ambulancia": ambulancia.strip(),
            "operador": operador.strip(),
            "hospital_base": "Hospital IMSS 220 (Paseo Tollocan)",
            "hospital_destino": hospital_destino,
            "distancia_km": float(distancia_km),
            "ambulancias_ocupadas": int(ambulancias_ocupadas)
        },
        "tomas_signos": documentos_tomas,
        "resumen_atencion": resumen,
        "id_analisis": id_analisis
    }

    # Misma estructura que p15: asi aparece en p16 y en el dashboard p17.
    documento_ia = {
        "id_analisis": id_analisis,
        "id_atencion": id_atencion,
        "id_paciente": id_paciente,
        "folio_emergencia": folio,
        "sistema": "Emergexia",
        "etapa": 11,
        "fecha_registro": fecha_actual,
        "archivo_origen": "p19_registro_atencion_emergencias.py",
        "datos_paciente": {
            "edad": float(edad),
            "frecuencia_cardiaca": resumen["frecuencia_peor"],
            "saturacion_oxigeno": resumen["saturacion_minima"],
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
        "recomendaciones": recomendaciones
    }

    # ---------- Guardar en las 3 colecciones ----------
    try:
        with st.spinner("Guardando expediente, atencion y analisis en MongoDB..."):
            pacientes, atenciones, analisis = obtener_colecciones()

            guardar_paciente(pacientes, id_paciente, nombre.strip(), edad, sexo, tipo_sangre,
                             alergias.strip() or "Ninguna", telefono_contacto.strip())
            atenciones.insert_one(documento_atencion)
            analisis.insert_one(documento_ia)

        st.success("Se guardaron el expediente, la atencion y el analisis de IA.")
        st.write(f"**Paciente:** {id_paciente} | **Folio:** {folio}")
        st.write(f"**ID de atencion:** {id_atencion} | **ID de analisis:** {id_analisis}")
        st.info("Las atenciones anteriores del paciente se conservaron; se agrego una nueva.")

    except ValueError as error:
        st.error(f"Error de configuracion: {error}")
    except PyMongoError as error:
        st.error("Ocurrio un problema al guardar en MongoDB.")
        st.exception(error)
        st.warning("Las escrituras en varias colecciones no forman una transaccion: si hubo un error, "
                   "revisa las colecciones antes de repetir el registro.")
    except Exception as error:
        st.error("Ocurrio un error inesperado.")
        st.exception(error)


# ============================================================
# 11. CONSULTAR EXPEDIENTE E HISTORIAL DE ATENCIONES
# ============================================================
st.divider()
st.header("6. Consulta del expediente del paciente")

id_consulta = st.text_input("ID del paciente", key="consulta_expediente", placeholder="Ejemplo: PAC-0001")

if st.button("Consultar expediente", use_container_width=True):

    if not id_consulta.strip():
        st.warning("Escribe el ID del paciente.")

    else:
        try:
            pacientes, atenciones, analisis = obtener_colecciones()
            identificador = id_consulta.strip().upper()

            expediente = pacientes.find_one({"id_paciente": identificador}, {"_id": 0})

            if expediente is None:
                st.warning("No existe un expediente con ese ID.")

            else:
                st.success("Expediente localizado.")

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Paciente", expediente.get("nombre_completo", ""))
                c2.metric("Edad", expediente.get("edad", ""))
                c3.metric("Tipo de sangre", expediente.get("tipo_sangre", ""))
                c4.metric("Alergias", expediente.get("alergias", ""))
                st.write("**Contacto:**", expediente.get("telefono_contacto") or "Sin registrar")

                lista = list(atenciones.find({"id_paciente": identificador}, {"_id": 0})
                             .sort("fecha_registro", -1))

                st.subheader(f"Historial de atenciones ({len(lista)})")

                for numero, atencion in enumerate(lista, start=1):

                    servicio = atencion.get("servicio", {})
                    ia = analisis.find_one({"id_analisis": atencion.get("id_analisis")}, {"_id": 0}) or {}

                    titulo = (f"{numero}. {atencion.get('folio_emergencia')} | "
                              f"{servicio.get('tipo_emergencia')} | {ia.get('prioridad', 'Sin analisis')}")

                    with st.expander(titulo):
                        st.write(f"**Fecha:** {atencion.get('fecha_registro')}")
                        st.write(f"**Ambulancia:** {servicio.get('ambulancia')} | "
                                 f"**Operador:** {servicio.get('operador')} | "
                                 f"**Destino:** {servicio.get('hospital_destino')} | "
                                 f"**Distancia:** {servicio.get('distancia_km')} km")

                        filas = [{"Momento": t["momento"], "Responsable": t["responsable"], **t["signos"],
                                  "Alertas": t["alertas"]} for t in atencion.get("tomas_signos", [])]
                        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

                        if ia:
                            st.write(f"**Resultado IA:** {ia['clasificacion']['resultado']} "
                                     f"({ia['clasificacion']['probabilidad_critica'] * 100:.1f}%) | "
                                     f"**Perfil:** {ia['perfil_riesgo']['perfil']}")
                            for i, texto in enumerate(ia.get("recomendaciones", []), start=1):
                                st.write(f"{i}. {texto}")

        except ValueError as error:
            st.error(f"Error de configuracion: {error}")
        except PyMongoError as error:
            st.error("No fue posible consultar MongoDB.")
            st.exception(error)
        except Exception as error:
            st.error("Ocurrio un error durante la consulta.")
            st.exception(error)


# ============================================================
# 12. PIE DE PAGINA
# ============================================================
st.divider()
st.caption("EMERGEXIA | Registro integral de atencion con Machine Learning y MongoDB. "
           "Datos de practica: no sustituye el expediente clinico oficial.")
