# ============================================================
# EMERGEXIA
# exportar_resumen_sistema.py
#
# Junta los resultados de las practicas 20 a 27 en un solo archivo
# pequeno (backend/app/datos_ia/bigdata_resumen.json) que la API lee
# para mostrarlos en Asistente de despacho -> "Big Data y prediccion".
#
# Los resultados completos (CSV de 50,000 registros, Parquet, modelos
# .pth) pesan varios MB y no se suben a GitHub; este resumen si se sube,
# asi el panel funciona tambien en Render, donde no hay Spark ni PyTorch.
#
# Uso (despues de correr p20 ... p27, o solo las que tengas):
#     python exportar_resumen_sistema.py
#
# Cada practica que todavia no se ha corrido queda como "pendiente".
# ============================================================

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

RUTA_BASE = Path(__file__).resolve().parent
RESULTADOS = RUTA_BASE / "resultados_emergexia"
SALIDA = RUTA_BASE.parent / "app" / "datos_ia" / "bigdata_resumen.json"

META_MIN = 15

PRACTICAS = {
    "p20": "Generar 50,000 registros de servicios",
    "p21": "Validar y procesar con Spark (Parquet)",
    "p22": "Carga masiva a MongoDB Atlas",
    "p23": "Preparar tensores para la CNN 1D",
    "p24": "Entrenar la CNN 1D (tendencia)",
    "p25": "Comparar CNN 1D contra Random Forest",
    "p26": "Preparar datos para predecir el mes 3",
    "p27": "CNN de regresion y alertas de 15 min",
}


def leer_json(ruta):
    if not ruta.exists():
        return None
    with open(ruta, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def r(valor, dec=2):
    return None if valor is None else round(float(valor), dec)


# ------------------------------------------------------------
# p20: datos masivos (se resumen con pandas a partir del CSV)
# ------------------------------------------------------------

def resumen_datos():
    ruta = RESULTADOS / "datos_masivos" / "emergexia_50000.csv"
    if not ruta.exists():
        return None
    df = pd.read_csv(ruta)
    df["disponibilidad_promedio"] = df[["disponibilidad_m1", "disponibilidad_m2", "disponibilidad_m3"]].mean(axis=1)
    df["cumple"] = (df["resultado"] == "Cumple").astype(float)

    def agrupar(col):
        g = df.groupby(col).agg(
            registros=("id_registro", "count"),
            ambulancias=("id_ambulancia", "nunique"),
            tiempo_promedio=("promedio_respuesta", "mean"),
            disponibilidad=("disponibilidad_promedio", "mean"),
            cumple_meta=("cumple", "mean"),
        ).reset_index().sort_values("tiempo_promedio")
        return [
            {
                "nombre": f[col],
                "registros": int(f["registros"]),
                "ambulancias": int(f["ambulancias"]),
                "tiempo_promedio": r(f["tiempo_promedio"]),
                "disponibilidad": r(f["disponibilidad"], 1),
                "cumple_meta": r(f["cumple_meta"], 4),
            }
            for _, f in g.iterrows()
        ]

    return {
        "registros": int(len(df)),
        "ambulancias": int(df["id_ambulancia"].nunique()),
        "por_hospital": agrupar("hospital_base"),
        "por_tipo": agrupar("tipo_emergencia"),
        "tendencias": {k: int(v) for k, v in df["tendencia"].value_counts().items()},
        "cumple_meta": r(df["cumple"].mean(), 4),
        "tiempo_por_mes": [r(df["tiempo_m1"].mean()), r(df["tiempo_m2"].mean()), r(df["tiempo_m3"].mean())],
    }


# ------------------------------------------------------------
# p21 / p22 / p23
# ------------------------------------------------------------

def estado_spark():
    parquet = RESULTADOS / "spark_procesado"
    if not parquet.exists():
        return None
    particiones = sorted(p.name.replace("tipo_emergencia=", "") for p in parquet.iterdir() if p.is_dir())
    archivos = list(parquet.rglob("*.parquet"))
    return {
        "particiones": particiones,
        "archivos_parquet": len(archivos),
        "megabytes": r(sum(a.stat().st_size for a in archivos) / 1_048_576, 1),
    }


def estado_mongo():
    """Cuenta los documentos de servicios_ambulancia_masivos si hay conexion."""
    try:
        from dotenv import load_dotenv
        from pymongo import MongoClient
        import os

        load_dotenv(RUTA_BASE / ".env")
        load_dotenv(RUTA_BASE.parent / ".env")
        uri = os.getenv("MONGO_URI")
        if not uri:
            return None
        cliente = MongoClient(uri, serverSelectionTimeoutMS=5000)
        bd = cliente[os.getenv("MONGO_DB", "emergexia")]
        total = bd["servicios_ambulancia_masivos"].estimated_document_count()
        cliente.close()
        return {"coleccion": "servicios_ambulancia_masivos", "documentos": int(total)} if total else None
    except Exception as error:  # noqa: BLE001
        print(f"  (p22) No se pudo consultar MongoDB: {error}")
        return None


def estado_tensores():
    meta = leer_json(RESULTADOS / "cnn" / "metadatos_cnn.json")
    if not meta:
        return None
    return {"forma_entrada": meta.get("forma_entrada"), "canales": meta.get("canales"),
            "separacion": meta.get("separacion"), "etiquetas": meta.get("mapa_etiquetas")}


# ------------------------------------------------------------
# p24 / p25: clasificacion de la tendencia
# ------------------------------------------------------------

def resumen_cnn():
    metricas = leer_json(RESULTADOS / "cnn" / "metricas_cnn.json")
    if not metricas:
        return None
    salida = {"mejor_epoca": metricas.get("mejor_epoca"),
              "metricas": {k: r(v, 4) for k, v in metricas["metricas_prueba"].items()}}
    ruta_matriz = RESULTADOS / "cnn" / "matriz_confusion_cnn.csv"
    if ruta_matriz.exists():
        m = pd.read_csv(ruta_matriz, index_col=0)
        salida["matriz"] = {"clases": list(m.columns), "valores": m.values.astype(int).tolist()}
    return salida


def resumen_comparacion():
    comp = leer_json(RESULTADOS / "comparacion" / "metricas_comparacion.json")
    if not comp:
        return None
    modelos = []
    for clave, nombre in (("CNN_1D", "CNN 1D"), ("Random_Forest", "Random Forest")):
        m = comp["modelos"].get(clave)
        if m:
            modelos.append({"modelo": nombre, **{k: r(v, 4) for k, v in m.items()}})
    salida = {"modelos": modelos}
    ruta_imp = RESULTADOS / "comparacion" / "importancia_variables_rf.csv"
    if ruta_imp.exists():
        imp = pd.read_csv(ruta_imp)
        col_var, col_val = imp.columns[0], imp.columns[-1]
        salida["importancia_rf"] = [{"variable": str(f[col_var]), "importancia": r(f[col_val], 4)}
                                    for _, f in imp.head(8).iterrows()]
    return salida


# ------------------------------------------------------------
# p26 / p27: prediccion del mes 3 y alertas
# ------------------------------------------------------------

def estado_preparacion_prediccion():
    meta = leer_json(RESULTADOS / "prediccion_cnn" / "metadatos_prediccion.json")
    if not meta:
        return None
    return {"variables_entrada": meta.get("variables_entrada"), "variable_objetivo": meta.get("variable_objetivo"),
            "separacion": meta.get("separacion")}


def resumen_prediccion():
    metricas = leer_json(RESULTADOS / "prediccion_cnn" / "metricas_prediccion_cnn.json")
    if not metricas:
        return None
    salida = {
        "mejor_epoca": metricas.get("mejor_epoca"),
        "metricas": {k: r(v, 4) for k, v in metricas["metricas_prueba"].items()},
        "modelo_base": {k: r(v, 4) for k, v in metricas["modelo_base"].items()},
        "alerta": {k: (r(v, 4) if k != "umbral_minutos" else v) for k, v in metricas["alerta_meta"].items()},
    }
    ruta = RESULTADOS / "prediccion_cnn" / "predicciones_prueba_cnn.csv"
    if ruta.exists():
        df = pd.read_csv(ruta)
        df["es_alerta"] = df["alerta_meta_15min"] == "ALERTA"
        df["real_tarde"] = df["tiempo_real_m3"] > META_MIN

        def por(col):
            g = df.groupby(col).agg(servicios=("es_alerta", "size"), alertas=("es_alerta", "sum"),
                                    predicho=("tiempo_predicho_m3", "mean"), real=("tiempo_real_m3", "mean"))
            g = g.reset_index().sort_values("alertas", ascending=False)
            return [{"nombre": f[col], "servicios": int(f["servicios"]), "alertas": int(f["alertas"]),
                     "porcentaje": r(f["alertas"] / f["servicios"], 4),
                     "predicho": r(f["predicho"]), "real": r(f["real"])} for _, f in g.iterrows()]

        top = df[df["es_alerta"]].sort_values("tiempo_predicho_m3", ascending=False).head(12)
        muestra = df.sample(n=min(400, len(df)), random_state=42)
        salida.update({
            "servicios_prueba": int(len(df)),
            "alertas_total": int(df["es_alerta"].sum()),
            "por_hospital": por("hospital_base"),
            "por_tipo": por("tipo_emergencia"),
            "mas_urgentes": [
                {"ambulancia": f["id_ambulancia"], "hospital": f["hospital_base"], "tipo": f["tipo_emergencia"],
                 "predicho": r(f["tiempo_predicho_m3"]), "real": r(f["tiempo_real_m3"])}
                for _, f in top.iterrows()
            ],
            "dispersion": [[r(a, 1), r(b, 1)] for a, b in zip(muestra["tiempo_real_m3"], muestra["tiempo_predicho_m3"])],
        })
    return salida


# ------------------------------------------------------------
# Proceso principal
# ------------------------------------------------------------

def main():
    print("=" * 65)
    print("EMERGEXIA - Resumen de las practicas 20 a 27 para el sistema")
    print("=" * 65)

    secciones = {
        "p20": resumen_datos(),
        "p21": estado_spark(),
        "p22": estado_mongo(),
        "p23": estado_tensores(),
        "p24": resumen_cnn(),
        "p25": resumen_comparacion(),
        "p26": estado_preparacion_prediccion(),
        "p27": resumen_prediccion(),
    }

    practicas = []
    for clave, titulo in PRACTICAS.items():
        listo = secciones[clave] is not None
        practicas.append({"clave": clave, "titulo": titulo, "listo": listo})
        print(f"  {clave}  {'OK       ' if listo else 'pendiente'}  {titulo}")

    resumen = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "meta_minutos": META_MIN,
        "practicas": practicas,
        "datos": secciones["p20"],
        "spark": secciones["p21"],
        "mongo": secciones["p22"],
        "tensores": secciones["p23"],
        "cnn": secciones["p24"],
        "comparacion": secciones["p25"],
        "preparacion_prediccion": secciones["p26"],
        "prediccion": secciones["p27"],
        "advertencia": "Datos sinteticos con fines educativos; no son servicios reales.",
    }

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8") as archivo:
        json.dump(resumen, archivo, ensure_ascii=False, indent=1)

    print(f"\nResumen guardado en: {SALIDA}  ({SALIDA.stat().st_size / 1024:.1f} KB)")
    print("Sube ese archivo a GitHub para que el panel lo muestre en el sistema.")


if __name__ == "__main__":
    main()
