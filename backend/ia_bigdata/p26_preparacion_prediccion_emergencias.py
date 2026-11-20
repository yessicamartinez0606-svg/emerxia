# ============================================================
# PROYECTO: EMERGEXIA
# ETAPA 18.1: PREPARACION DE DATOS PARA PREDICCION
#
# Archivo:
# p26_preparacion_prediccion_emergencias.py
#
# Objetivo:
# Preparar los datos para una CNN 1D que estime el tiempo de
# respuesta del MES 3 de cada ambulancia usando solamente:
#
# - Tiempo de respuesta del mes 1
# - Tiempo de respuesta del mes 2
# - Disponibilidad del mes 1
# - Disponibilidad del mes 2
#
# El tiempo del mes 3 es exclusivamente la variable objetivo.
# Asi el modelo sirve para ANTICIPAR que ambulancias podrian
# superar la meta de 15 minutos el siguiente mes.
# ============================================================

from pathlib import Path
import json

import numpy as np
import pandas as pd

from sklearn.model_selection import GroupShuffleSplit


# ============================================================
# 1. CONFIGURACION
# ============================================================

RUTA_BASE = Path(__file__).resolve().parent

ARCHIVO_CSV = (
    RUTA_BASE
    / "resultados_emergexia"
    / "datos_masivos"
    / "emergexia_50000.csv"
)

RUTA_SALIDA = RUTA_BASE / "resultados_emergexia" / "prediccion_cnn"

RUTA_SALIDA.mkdir(parents=True, exist_ok=True)

ARCHIVO_NPZ = RUTA_SALIDA / "emergexia_prediccion_mes3.npz"

ARCHIVO_JSON = RUTA_SALIDA / "metadatos_prediccion.json"

SEMILLA = 42

PROPORCION_ENTRENAMIENTO = 0.70

TIPOS_POR_AMBULANCIA = 5

COLUMNAS_TIEMPOS = ["tiempo_m1", "tiempo_m2", "tiempo_m3"]

COLUMNAS_DISPONIBILIDAD = [
    "disponibilidad_m1",
    "disponibilidad_m2",
    "disponibilidad_m3"
]


def titulo(texto):

    print("\n" + "=" * 65)
    print(texto)
    print("=" * 65)


def main():

    titulo("EMERGEXIA - ETAPA 18.1")

    # ========================================================
    # 2. CARGAR DATOS
    # ========================================================

    print("\nCARGANDO DATASET ORIGINAL...")

    if not ARCHIVO_CSV.exists():

        raise FileNotFoundError(
            f"No existe el archivo: {ARCHIVO_CSV}. "
            "Ejecuta primero p20_generador_emergencias.py"
        )

    datos = pd.read_csv(ARCHIVO_CSV)

    print(f"Registros encontrados: {len(datos):,}")
    print(f"Columnas encontradas: {len(datos.columns)}")

    columnas_requeridas = (
        ["id_registro", "id_ambulancia", "hospital_base", "tipo_emergencia"]
        + COLUMNAS_TIEMPOS
        + COLUMNAS_DISPONIBILIDAD
    )

    faltantes = [c for c in columnas_requeridas if c not in datos.columns]

    if faltantes:
        raise ValueError(f"Faltan columnas: {faltantes}")

    # ========================================================
    # 3. VALIDAR INTEGRIDAD
    # ========================================================

    titulo("VALIDACION DE INTEGRIDAD")

    if datos[["id_ambulancia", "tipo_emergencia"]].isnull().any().any():
        raise ValueError("Hay registros sin ambulancia o sin tipo de emergencia.")

    if datos["id_registro"].duplicated().any():
        raise ValueError("Hay identificadores de registro duplicados.")

    if datos.duplicated(subset=["id_ambulancia", "tipo_emergencia"]).any():
        raise ValueError("Hay tipos de emergencia duplicados en una ambulancia.")

    if not (
        datos.groupby("id_ambulancia")["tipo_emergencia"].nunique()
        == TIPOS_POR_AMBULANCIA
    ).all():
        raise ValueError("No todas las ambulancias tienen cinco tipos.")

    print("Identificadores: correctos")
    print("Tipos duplicados: ninguno")
    print(f"Ambulancias encontradas: {datos['id_ambulancia'].nunique():,}")

    # ========================================================
    # 4. VALIDAR VARIABLES NUMERICAS
    # ========================================================

    titulo("VALIDACION DE VARIABLES NUMERICAS")

    numericas = COLUMNAS_TIEMPOS + COLUMNAS_DISPONIBILIDAD

    for columna in numericas:
        datos[columna] = pd.to_numeric(datos[columna], errors="coerce")

    if datos[numericas].isnull().any().any():
        raise ValueError("Hay valores nulos o no numericos.")

    if not np.isfinite(datos[numericas].to_numpy()).all():
        raise ValueError("Se encontraron valores infinitos.")

    for columna in COLUMNAS_TIEMPOS:
        if not datos[columna].between(0, 60).all():
            raise ValueError(f"Tiempos fuera de rango en {columna}")

    for columna in COLUMNAS_DISPONIBILIDAD:
        if not datos[columna].between(0, 100).all():
            raise ValueError(f"Disponibilidad fuera de rango en {columna}")

    print("Tiempos: rango 0 a 60 minutos correcto")
    print("Disponibilidad: rango 0 a 100 % correcto")

    # ========================================================
    # 5. CONSTRUIR ENTRADAS Y OBJETIVO
    # ========================================================

    titulo("CONSTRUCCION DEL CONJUNTO DE PREDICCION")

    # (registros, canales, meses) = (N, 2, 2)
    # Canal 0: tiempo de respuesta.  Canal 1: disponibilidad.
    # Posicion 0: mes 1.             Posicion 1: mes 2.

    X = np.zeros((len(datos), 2, 2), dtype=np.float32)

    X[:, 0, 0] = datos["tiempo_m1"].to_numpy()
    X[:, 0, 1] = datos["tiempo_m2"].to_numpy()
    X[:, 1, 0] = datos["disponibilidad_m1"].to_numpy()
    X[:, 1, 1] = datos["disponibilidad_m2"].to_numpy()

    y = datos["tiempo_m3"].to_numpy(dtype=np.float32)

    grupos = datos["id_ambulancia"].to_numpy()

    tipos = datos["tipo_emergencia"].to_numpy()

    hospitales = datos["hospital_base"].to_numpy()

    print(f"Entradas X: {X.shape}")
    print(f"Objetivo y: {y.shape}")
    print("\nEntradas: tiempo mes 1, tiempo mes 2, disponibilidad mes 1 y mes 2")
    print("Objetivo: tiempo de respuesta del mes 3")
    print("\nIMPORTANTE: ni el tiempo ni la disponibilidad del mes 3 forman parte de X.")

    # ========================================================
    # 6. SEPARAR POR AMBULANCIA
    # ========================================================

    titulo("SEPARACION DE ENTRENAMIENTO, VALIDACION Y PRUEBA")

    separador_1 = GroupShuffleSplit(
        n_splits=1,
        test_size=1 - PROPORCION_ENTRENAMIENTO,
        random_state=SEMILLA
    )

    indices_train, indices_temp = next(separador_1.split(X, y, groups=grupos))

    separador_2 = GroupShuffleSplit(
        n_splits=1,
        test_size=0.50,
        random_state=SEMILLA
    )

    val_rel, test_rel = next(
        separador_2.split(indices_temp, y[indices_temp], groups=grupos[indices_temp])
    )

    indices_val = indices_temp[val_rel]

    indices_test = indices_temp[test_rel]

    ids_train = set(grupos[indices_train])
    ids_val = set(grupos[indices_val])
    ids_test = set(grupos[indices_test])

    assert ids_train.isdisjoint(ids_val)
    assert ids_train.isdisjoint(ids_test)
    assert ids_val.isdisjoint(ids_test)

    print("SEPARACION POR AMBULANCIA CORRECTA")
    print(f"Ambulancias entrenamiento: {len(ids_train):,}")
    print(f"Ambulancias validacion:    {len(ids_val):,}")
    print(f"Ambulancias prueba:        {len(ids_test):,}")
    print(f"\nRegistros: {len(indices_train):,} / {len(indices_val):,} / {len(indices_test):,}")

    # ========================================================
    # 7. NORMALIZAR CON ESTADISTICAS DE ENTRENAMIENTO
    # ========================================================

    titulo("NORMALIZACION DE VARIABLES")

    X_train_raw = X[indices_train]

    media = X_train_raw.mean(axis=(0, 2), keepdims=True)

    desviacion = X_train_raw.std(axis=(0, 2), keepdims=True)

    desviacion = np.where(desviacion == 0, 1.0, desviacion)

    def normalizar(indices):
        return ((X[indices] - media) / desviacion).astype(np.float32)

    X_train = normalizar(indices_train)
    X_val = normalizar(indices_val)
    X_test = normalizar(indices_test)

    print(f"Media tiempos: {media[0, 0, 0]:.4f}")
    print(f"Desviacion tiempos: {desviacion[0, 0, 0]:.4f}")
    print(f"Media disponibilidad: {media[0, 1, 0]:.4f}")
    print(f"Desviacion disponibilidad: {desviacion[0, 1, 0]:.4f}")

    for arreglo in (X_train, X_val, X_test):
        assert arreglo.shape[1:] == (2, 2)
        assert np.isfinite(arreglo).all()

    # ========================================================
    # 8. ESTADISTICAS DEL OBJETIVO
    # ========================================================

    titulo("ANALISIS DEL TIEMPO DE RESPUESTA DEL MES 3")

    print(f"Promedio entrenamiento: {y[indices_train].mean():.4f} min")
    print(f"Promedio validacion:    {y[indices_val].mean():.4f} min")
    print(f"Promedio prueba:        {y[indices_test].mean():.4f} min")
    print(f"Minimo: {y.min():.2f}  Maximo: {y.max():.2f}  Desv.: {y.std():.4f}")

    # ========================================================
    # 9. GUARDAR
    # ========================================================

    titulo("GUARDANDO DATOS PARA PYTORCH")

    # Los identificadores se guardan como texto para auditar
    # las predicciones; NO son entradas del modelo.
    np.savez_compressed(
        ARCHIVO_NPZ,
        X_train=X_train,
        y_train=y[indices_train],
        X_val=X_val,
        y_val=y[indices_val],
        X_test=X_test,
        y_test=y[indices_test],
        ids_train=grupos[indices_train].astype(str),
        ids_val=grupos[indices_val].astype(str),
        ids_test=grupos[indices_test].astype(str),
        tipos_test=tipos[indices_test].astype(str),
        hospitales_test=hospitales[indices_test].astype(str),
        media_entrenamiento=media,
        desviacion_entrenamiento=desviacion
    )

    metadatos = {
        "proyecto": "Emergexia",
        "etapa": 18.1,
        "tipo_problema": "Regresion",
        "objetivo": "Prediccion del tiempo de respuesta del mes 3 (minutos)",
        "total_registros": int(len(datos)),
        "total_ambulancias": int(datos["id_ambulancia"].nunique()),
        "variables_entrada": [
            "tiempo_m1",
            "tiempo_m2",
            "disponibilidad_m1",
            "disponibilidad_m2"
        ],
        "variable_objetivo": "tiempo_m3",
        "variables_excluidas": [
            "tiempo_m3 como entrada",
            "disponibilidad_m3",
            "promedio_respuesta",
            "tendencia",
            "resultado",
            "id_ambulancia",
            "hospital_base",
            "tipo_emergencia"
        ],
        "forma_entrada": [2, 2],
        "separacion": {
            "entrenamiento": 0.70,
            "validacion": 0.15,
            "prueba": 0.15,
            "metodo": "GroupShuffleSplit",
            "grupo": "id_ambulancia"
        },
        "semilla": SEMILLA,
        "normalizacion": {
            "metodo": "Z-score",
            "calculada_con": "Solo entrenamiento",
            "media": media.tolist(),
            "desviacion": desviacion.tolist()
        },
        "advertencia": (
            "Datos sinteticos. Los resultados son una validacion "
            "experimental, no evidencia con servicios reales."
        )
    }

    with open(ARCHIVO_JSON, "w", encoding="utf-8") as archivo:
        json.dump(metadatos, archivo, indent=4, ensure_ascii=False)

    print(f"Archivo NPZ: {ARCHIVO_NPZ}")
    print(f"Metadatos:   {ARCHIVO_JSON}")

    titulo("ETAPA 18.1 FINALIZADA")

    print("Entrada de la CNN: (2 canales, 2 meses)")
    print("Objetivo: tiempo de respuesta del mes 3")
    print("No se detecto fuga de informacion por ambulancia.")


if __name__ == "__main__":

    main()
