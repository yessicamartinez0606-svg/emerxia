# ============================================================
# PROYECTO: EMERGEXIA
# ETAPA 15 - PREPARACION DE DATOS PARA CNN 1D
#
# Archivo:
# p23_preparacion_cnn_emergencias.py
#
# Objetivo:
# 1. Leer los 50,000 registros procesados con Spark.
# 2. Tomar la evolucion mensual de cada ambulancia.
# 3. Convertir los registros en tensores para una CNN 1D.
# 4. Codificar las tres tendencias del servicio.
# 5. Dividir los datos por ambulancia.
# 6. Normalizar usando solo entrenamiento.
# 7. Guardar los conjuntos para el entrenamiento.
#
# IMPORTANTE:
# En esta etapa no se entrena la red neuronal.
# ============================================================


# ============================================================
# 1. IMPORTACION DE LIBRERIAS
# ============================================================

import os
import sys

from pathlib import Path
import json

import numpy as np

from pyspark.sql import SparkSession

from sklearn.model_selection import GroupShuffleSplit

import torch


# ============================================================
# 2. CONFIGURACION
# ============================================================

RUTA_BASE = Path(__file__).resolve().parent

RUTA_PARQUET = RUTA_BASE / "resultados_emergexia" / "spark_procesado"

RUTA_SALIDA = RUTA_BASE / "resultados_emergexia" / "cnn"

RUTA_SALIDA.mkdir(parents=True, exist_ok=True)

SEMILLA = 42

REGISTROS_ESPERADOS = 50000

TIPOS_POR_AMBULANCIA = 5

# Clases que aprendera la CNN.
MAPA_ETIQUETAS = {
    "Deterioro": 0,
    "Estable": 1,
    "Mejora": 2
}

COLUMNAS_TIEMPOS = [
    "tiempo_m1",
    "tiempo_m2",
    "tiempo_m3"
]

COLUMNAS_DISPONIBILIDAD = [
    "disponibilidad_m1",
    "disponibilidad_m2",
    "disponibilidad_m3"
]

COLUMNAS_NECESARIAS = (
    ["id_registro", "id_ambulancia"]
    + COLUMNAS_TIEMPOS
    + COLUMNAS_DISPONIBILIDAD
    + ["tendencia"]
)


# ============================================================
# 3. SESION SPARK
# ============================================================

def crear_sesion_spark():

    # Spark usa el mismo Python que ejecuta el script y se queda
    # en 127.0.0.1 (igual que backend/app/spark.py).
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")

    spark = (
        SparkSession.builder
        .appName("Emergexia_Preparacion_CNN")
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("ERROR")

    return spark


# ============================================================
# 4. LEER DATOS
# ============================================================

def cargar_datos(spark):

    print("\n1. LEYENDO DATOS PARQUET")
    print("-" * 60)

    if not RUTA_PARQUET.exists():

        raise FileNotFoundError(
            f"No existe el directorio: {RUTA_PARQUET}. "
            "Ejecuta primero p21_spark_emergencias.py"
        )

    datos_spark = spark.read.parquet(str(RUTA_PARQUET))

    faltantes = set(COLUMNAS_NECESARIAS) - set(datos_spark.columns)

    if faltantes:
        raise ValueError(f"Faltan columnas necesarias: {faltantes}")

    datos_spark = datos_spark.select(*COLUMNAS_NECESARIAS)

    total = datos_spark.count()

    print(f"Registros encontrados: {total:,}")

    if total != REGISTROS_ESPERADOS:

        raise ValueError(
            f"Esperados: {REGISTROS_ESPERADOS:,}; encontrados: {total:,}"
        )

    # 50,000 registros caben bien en memoria con Pandas.
    datos = datos_spark.toPandas()

    # Ordenar para que el resultado sea reproducible
    # (Spark puede devolver las filas en otro orden).
    datos = datos.sort_values("id_registro").reset_index(drop=True)

    print("Archivos Parquet leidos correctamente.")

    return datos


# ============================================================
# 5. VALIDAR CALIDAD
# ============================================================

def validar_datos(datos):

    print("\n2. VALIDANDO CALIDAD DE LOS DATOS")
    print("-" * 60)

    nulos = int(datos[COLUMNAS_NECESARIAS].isnull().sum().sum())

    print(f"Valores nulos: {nulos}")

    if nulos > 0:
        raise ValueError("Se encontraron valores nulos.")

    duplicados = int(datos["id_registro"].duplicated().sum())

    print(f"Identificadores duplicados: {duplicados}")

    if duplicados > 0:
        raise ValueError("Existen identificadores duplicados.")

    tiempos = datos[COLUMNAS_TIEMPOS].to_numpy(dtype=np.float64)

    if not np.isfinite(tiempos).all():
        raise ValueError("Hay tiempos no numericos o infinitos.")

    if (tiempos < 0).any() or (tiempos > 60).any():
        raise ValueError("Hay tiempos fuera del rango 0-60 minutos.")

    disponibilidad = datos[COLUMNAS_DISPONIBILIDAD].to_numpy(dtype=np.float64)

    if not np.isfinite(disponibilidad).all():
        raise ValueError("Hay disponibilidades no numericas o infinitas.")

    if (disponibilidad < 0).any() or (disponibilidad > 100).any():
        raise ValueError("Hay disponibilidad fuera del rango 0-100.")

    tendencias = set(datos["tendencia"].unique())

    if tendencias != set(MAPA_ETIQUETAS):

        raise ValueError(
            f"Las categorias de tendencia no coinciden: {tendencias}"
        )

    registros_por_ambulancia = datos.groupby("id_ambulancia")["id_registro"].count()

    incorrectas = int((registros_por_ambulancia != TIPOS_POR_AMBULANCIA).sum())

    print(
        "Ambulancias con cinco registros: "
        f"{len(registros_por_ambulancia) - incorrectas:,}"
    )

    if incorrectas > 0:
        raise ValueError("Hay ambulancias sin exactamente cinco registros.")

    print("Validacion de datos completada.")


# ============================================================
# 6. CONSTRUIR TENSORES
# ============================================================

def construir_tensores(datos):

    """
    Cada registro tendra:

        Canal 0: tiempo de respuesta (min).
        Canal 1: disponibilidad (%).

    Tres posiciones temporales: mes 1, mes 2, mes 3.

        X = [50000, 2, 3]
        y = [50000]
    """

    print("\n3. CONSTRUYENDO TENSORES")
    print("-" * 60)

    tiempos = datos[COLUMNAS_TIEMPOS].to_numpy(dtype=np.float32)

    disponibilidad = datos[COLUMNAS_DISPONIBILIDAD].to_numpy(dtype=np.float32)

    X = np.stack([tiempos, disponibilidad], axis=1)

    y = datos["tendencia"].map(MAPA_ETIQUETAS).to_numpy(dtype=np.int64)

    # Se usa para separar sin mezclar la misma ambulancia
    # entre entrenamiento y prueba.
    grupos = datos["id_ambulancia"].astype(str).to_numpy()

    print(f"Forma de X: {X.shape}")
    print(f"Forma de y: {y.shape}")
    print("\nEjemplo de un registro:")
    print(X[0])
    print("\nEtiqueta numerica:", y[0])

    if X.shape != (REGISTROS_ESPERADOS, 2, 3):
        raise ValueError(f"Forma inesperada para X: {X.shape}")

    if y.shape != (REGISTROS_ESPERADOS,):
        raise ValueError(f"Forma inesperada para y: {y.shape}")

    print("\nTensores construidos correctamente.")

    return X, y, grupos


# ============================================================
# 7. DIVIDIR POR AMBULANCIA
# ============================================================

def dividir_datos(X, y, grupos):

    """
    70% entrenamiento, 15% validacion y 15% prueba.

    Se divide por ambulancia: una misma ambulancia no puede
    estar en entrenamiento y en prueba al mismo tiempo.
    """

    print("\n4. DIVIDIENDO LOS CONJUNTOS")
    print("-" * 60)

    separador_1 = GroupShuffleSplit(
        n_splits=1,
        test_size=0.15,
        random_state=SEMILLA
    )

    indices_train_val, indices_test = next(
        separador_1.split(X, y, groups=grupos)
    )

    separador_2 = GroupShuffleSplit(
        n_splits=1,
        test_size=0.1764705882,
        random_state=SEMILLA
    )

    indices_train_rel, indices_val_rel = next(
        separador_2.split(
            X[indices_train_val],
            y[indices_train_val],
            groups=grupos[indices_train_val]
        )
    )

    indices_train = indices_train_val[indices_train_rel]

    indices_val = indices_train_val[indices_val_rel]

    conjuntos = {}

    for nombre, indices in [
        ("train", indices_train),
        ("val", indices_val),
        ("test", indices_test)
    ]:

        conjuntos[nombre] = (X[indices], y[indices], grupos[indices])

    ids_train = set(conjuntos["train"][2])
    ids_val = set(conjuntos["val"][2])
    ids_test = set(conjuntos["test"][2])

    if ids_train & ids_val or ids_train & ids_test or ids_val & ids_test:
        raise ValueError("Hay ambulancias compartidas entre conjuntos.")

    print(f"Entrenamiento: {len(indices_train):,} registros ({len(ids_train):,} ambulancias)")
    print(f"Validacion:    {len(indices_val):,} registros ({len(ids_val):,} ambulancias)")
    print(f"Prueba:        {len(indices_test):,} registros ({len(ids_test):,} ambulancias)")
    print("Separacion por ambulancia verificada.")

    return conjuntos


# ============================================================
# 8. NORMALIZAR
# ============================================================

def normalizar_datos(X_train, X_val, X_test):

    """
    Media y desviacion por canal calculadas SOLO con
    entrenamiento, y aplicadas a los tres conjuntos.
    Esto evita fuga de informacion.
    """

    print("\n5. NORMALIZANDO LOS DATOS")
    print("-" * 60)

    datos_train = X_train.transpose(0, 2, 1).reshape(-1, 2)

    medias = datos_train.mean(axis=0)

    desviaciones = datos_train.std(axis=0)

    desviaciones = np.where(desviaciones == 0, 1.0, desviaciones)

    def aplicar(X):
        return (
            (X - medias[None, :, None]) / desviaciones[None, :, None]
        ).astype(np.float32)

    print(f"Media tiempos de respuesta: {medias[0]:.4f}")
    print(f"Desviacion tiempos de respuesta: {desviaciones[0]:.4f}")
    print(f"Media disponibilidad: {medias[1]:.4f}")
    print(f"Desviacion disponibilidad: {desviaciones[1]:.4f}")
    print("Normalizacion completada.")

    return aplicar(X_train), aplicar(X_val), aplicar(X_test), medias, desviaciones


# ============================================================
# 9. DISTRIBUCION DE CLASES
# ============================================================

def validar_clases(y_train, y_val, y_test):

    print("\n6. DISTRIBUCION DE CLASES")
    print("-" * 60)

    for nombre, y in [
        ("ENTRENAMIENTO", y_train),
        ("VALIDACION", y_val),
        ("PRUEBA", y_test)
    ]:

        print(f"\n{nombre}")

        for etiqueta, codigo in MAPA_ETIQUETAS.items():

            cantidad = int(np.sum(y == codigo))

            print(
                f"{etiqueta:10}: {cantidad:6,} registros "
                f"({cantidad / len(y) * 100:.2f}%)"
            )

        if set(np.unique(y).tolist()) != set(MAPA_ETIQUETAS.values()):
            raise ValueError(f"Faltan categorias en {nombre}.")

    print("\nLas tres clases estan presentes en los conjuntos.")


# ============================================================
# 10. GUARDAR
# ============================================================

def guardar_datos(conjuntos, medias, desviaciones):

    print("\n7. GUARDANDO LOS RESULTADOS")
    print("-" * 60)

    ruta_datos = RUTA_SALIDA / "emergexia_datos_cnn.npz"

    ruta_metadatos = RUTA_SALIDA / "metadatos_cnn.json"

    np.savez_compressed(
        ruta_datos,
        X_train=conjuntos["train"][0],
        y_train=conjuntos["train"][1],
        grupos_train=conjuntos["train"][2],
        X_val=conjuntos["val"][0],
        y_val=conjuntos["val"][1],
        grupos_val=conjuntos["val"][2],
        X_test=conjuntos["test"][0],
        y_test=conjuntos["test"][1],
        grupos_test=conjuntos["test"][2]
    )

    metadatos = {
        "proyecto": "Emergexia",
        "etapa": 15,
        "total_registros": REGISTROS_ESPERADOS,
        "forma_entrada": [2, 3],
        "canales": ["tiempo_respuesta_min", "disponibilidad_pct"],
        "momentos_temporales": ["mes1", "mes2", "mes3"],
        "mapa_etiquetas": MAPA_ETIQUETAS,
        "media_normalizacion": medias.tolist(),
        "desviacion_normalizacion": desviaciones.tolist(),
        "semilla": SEMILLA,
        "separacion": {
            "entrenamiento": 0.70,
            "validacion": 0.15,
            "prueba": 0.15,
            "metodo": "GroupShuffleSplit por ambulancia"
        },
        "framework": "PyTorch",
        "version_pytorch": torch.__version__,
        "cuda_disponible": torch.cuda.is_available()
    }

    with open(ruta_metadatos, "w", encoding="utf-8") as archivo:
        json.dump(metadatos, archivo, indent=4, ensure_ascii=False)

    print(f"Datos guardados: {ruta_datos}")
    print(f"Metadatos guardados: {ruta_metadatos}")


# ============================================================
# 11. VERIFICAR PYTORCH
# ============================================================

def verificar_pytorch():

    print("\n8. VERIFICANDO PYTORCH")
    print("-" * 60)
    print(f"Version PyTorch: {torch.__version__}")
    print(f"CUDA disponible: {torch.cuda.is_available()}")

    if torch.cuda.is_available():
        print(f"GPU detectada: {torch.cuda.get_device_name(0)}")
    else:
        print("Se utilizara CPU cuando se entrene el modelo.")


# ============================================================
# 12. PROCESO PRINCIPAL
# ============================================================

def main():

    print("=" * 65)
    print("EMERGEXIA")
    print("ETAPA 15 - PREPARACION DE DATOS PARA CNN 1D")
    print("=" * 65)

    spark = None

    try:

        spark = crear_sesion_spark()

        print("\nSESION SPARK INICIADA")

        datos = cargar_datos(spark)

        validar_datos(datos)

        X, y, grupos = construir_tensores(datos)

        conjuntos = dividir_datos(X, y, grupos)

        X_train, X_val, X_test, medias, desviaciones = normalizar_datos(
            conjuntos["train"][0],
            conjuntos["val"][0],
            conjuntos["test"][0]
        )

        conjuntos["train"] = (X_train,) + conjuntos["train"][1:]
        conjuntos["val"] = (X_val,) + conjuntos["val"][1:]
        conjuntos["test"] = (X_test,) + conjuntos["test"][1:]

        validar_clases(
            conjuntos["train"][1],
            conjuntos["val"][1],
            conjuntos["test"][1]
        )

        guardar_datos(conjuntos, medias, desviaciones)

        verificar_pytorch()

        print("\n" + "=" * 65)
        print("ETAPA 15 FINALIZADA CORRECTAMENTE")
        print("Los datos estan preparados para la CNN 1D.")
        print("=" * 65)

    except Exception as error:

        print("\nERROR EN LA ETAPA 15")
        print(f"Detalle: {error}")

        raise

    finally:

        if spark is not None:

            spark.stop()

            print("\nSESION SPARK CERRADA")


if __name__ == "__main__":

    main()
