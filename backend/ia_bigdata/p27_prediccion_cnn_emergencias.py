# ============================================================
# PROYECTO: EMERGEXIA
# ETAPA 18.2: ENTRENAMIENTO DE CNN 1D PARA REGRESION
#
# Archivo:
# p27_prediccion_cnn_emergencias.py
#
# Objetivo:
# Predecir el tiempo de respuesta del mes 3 de cada ambulancia
# usando solamente los datos de los meses 1 y 2, y marcar una
# ALERTA cuando la prediccion supere la meta de 15 minutos.
#
# Framework: PyTorch
# Problema: Regresion
# ============================================================

from pathlib import Path
import json
import time
import copy

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import torch
import torch.nn as nn

from torch.utils.data import Dataset, DataLoader

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    accuracy_score,
    precision_score,
    recall_score
)


# ============================================================
# 1. CONFIGURACION
# ============================================================

RUTA_BASE = Path(__file__).resolve().parent

RUTA_DATOS = RUTA_BASE / "resultados_emergexia" / "prediccion_cnn"

RUTA_SALIDA = RUTA_DATOS

RUTA_SALIDA.mkdir(parents=True, exist_ok=True)

ARCHIVO_DATOS = RUTA_DATOS / "emergexia_prediccion_mes3.npz"

SEMILLA = 42

BATCH_SIZE = 256

MAX_EPOCAS = 60

LEARNING_RATE = 0.001

PACIENCIA = 10

META_RESPUESTA_MIN = 15

TIEMPO_MAXIMO = 60


# ============================================================
# 2. DATASET
# ============================================================

class DatasetEmergencias(Dataset):

    """
    Cada muestra: 2 canales (tiempo, disponibilidad) x 2 meses.
    Objetivo: tiempo de respuesta del mes 3.
    """

    def __init__(self, X, y):

        self.X = torch.tensor(X, dtype=torch.float32)

        self.y = torch.tensor(y, dtype=torch.float32)

    def __len__(self):

        return len(self.X)

    def __getitem__(self, indice):

        return self.X[indice], self.y[indice]


# ============================================================
# 3. ARQUITECTURA
# ============================================================

class CNNRegresionEmergencias(nn.Module):

    """
    Entrada: (lote, 2 canales, 2 meses)
    Salida:  un tiempo estimado (minutos) por registro.
    """

    def __init__(self):

        super().__init__()

        self.conv1 = nn.Conv1d(2, 16, kernel_size=2, padding=1)

        self.bn1 = nn.BatchNorm1d(16)

        self.conv2 = nn.Conv1d(16, 32, kernel_size=2)

        self.bn2 = nn.BatchNorm1d(32)

        self.relu = nn.ReLU()

        self.pool = nn.AdaptiveAvgPool1d(1)

        self.dropout = nn.Dropout(0.20)

        # Una sola neurona: regresion.
        self.fc = nn.Linear(32, 1)

    def forward(self, x):

        x = self.relu(self.bn1(self.conv1(x)))

        x = self.relu(self.bn2(self.conv2(x)))

        x = self.pool(x)

        x = torch.flatten(x, start_dim=1)

        x = self.dropout(x)

        return self.fc(x).squeeze(1)


# ============================================================
# 4. FUNCIONES DE ENTRENAMIENTO
# ============================================================

def recorrer_epoca(modelo, loader, funcion_perdida, dispositivo, optimizador=None):

    """
    Si recibe optimizador, entrena; si no, solo evalua.
    Devuelve la perdida promedio (MSE).
    """

    entrenando = optimizador is not None

    modelo.train() if entrenando else modelo.eval()

    perdida_acumulada = 0.0

    total = 0

    with torch.set_grad_enabled(entrenando):

        for entradas, objetivos in loader:

            entradas = entradas.to(dispositivo)

            objetivos = objetivos.to(dispositivo)

            if entrenando:
                optimizador.zero_grad()

            perdida = funcion_perdida(modelo(entradas), objetivos)

            if entrenando:
                perdida.backward()
                optimizador.step()

            perdida_acumulada += perdida.item() * len(entradas)

            total += len(entradas)

    return perdida_acumulada / total


def obtener_predicciones(modelo, loader, dispositivo):

    modelo.eval()

    predicciones, reales = [], []

    with torch.no_grad():

        for entradas, objetivos in loader:

            predicciones.extend(modelo(entradas.to(dispositivo)).cpu().numpy())

            reales.extend(objetivos.numpy())

    return np.asarray(predicciones), np.asarray(reales)


# ============================================================
# 5. PROGRAMA PRINCIPAL
# ============================================================

def main():

    torch.manual_seed(SEMILLA)

    np.random.seed(SEMILLA)

    if torch.cuda.is_available():

        torch.cuda.manual_seed_all(SEMILLA)

        dispositivo = torch.device("cuda")

    else:

        dispositivo = torch.device("cpu")

    print("=" * 65)
    print("EMERGEXIA")
    print("ETAPA 18.2 - CNN 1D PARA PREDECIR EL TIEMPO DE RESPUESTA")
    print("=" * 65)
    print("\nDispositivo de entrenamiento:", dispositivo)

    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))

    # --------------------------------------------------------
    # 5.1 Cargar datos
    # --------------------------------------------------------

    if not ARCHIVO_DATOS.exists():

        raise FileNotFoundError(
            f"No existe el archivo: {ARCHIVO_DATOS}. "
            "Ejecuta primero p26_preparacion_prediccion_emergencias.py"
        )

    datos = np.load(ARCHIVO_DATOS, allow_pickle=False)

    X_train, y_train = datos["X_train"], datos["y_train"]
    X_val, y_val = datos["X_val"], datos["y_val"]
    X_test, y_test = datos["X_test"], datos["y_test"]

    for X, y in [(X_train, y_train), (X_val, y_val), (X_test, y_test)]:
        assert X.shape[1:] == (2, 2)
        assert len(X) == len(y)
        assert np.isfinite(X).all() and np.isfinite(y).all()

    print("\nDATOS CARGADOS")
    print("Entrenamiento:", X_train.shape)
    print("Validacion:", X_val.shape)
    print("Prueba:", X_test.shape)

    usar_pin = torch.cuda.is_available()

    loader_train = DataLoader(
        DatasetEmergencias(X_train, y_train),
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=0,
        pin_memory=usar_pin,
        drop_last=True  # BatchNorm falla con un lote de 1 registro
    )

    loader_val = DataLoader(
        DatasetEmergencias(X_val, y_val),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
        pin_memory=usar_pin
    )

    loader_test = DataLoader(
        DatasetEmergencias(X_test, y_test),
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0,
        pin_memory=usar_pin
    )

    # --------------------------------------------------------
    # 5.2 Modelo
    # --------------------------------------------------------

    modelo = CNNRegresionEmergencias().to(dispositivo)

    total_parametros = sum(
        p.numel() for p in modelo.parameters() if p.requires_grad
    )

    print("\nARQUITECTURA:")
    print(modelo)
    print("Parametros entrenables:", total_parametros)

    funcion_perdida = nn.MSELoss()

    optimizador = torch.optim.Adam(modelo.parameters(), lr=LEARNING_RATE)

    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizador,
        mode="min",
        factor=0.5,
        patience=4
    )

    # --------------------------------------------------------
    # 5.3 Entrenamiento con Early Stopping
    # --------------------------------------------------------

    print("\nINICIANDO ENTRENAMIENTO...")

    historial = []

    mejor_perdida = float("inf")

    mejor_epoca = 0

    mejores_pesos = None

    epocas_sin_mejora = 0

    inicio = time.perf_counter()

    for epoca in range(1, MAX_EPOCAS + 1):

        perdida_train = recorrer_epoca(
            modelo, loader_train, funcion_perdida, dispositivo, optimizador
        )

        perdida_val = recorrer_epoca(
            modelo, loader_val, funcion_perdida, dispositivo
        )

        scheduler.step(perdida_val)

        tasa = optimizador.param_groups[0]["lr"]

        historial.append({
            "epoca": epoca,
            "perdida_train": perdida_train,
            "perdida_val": perdida_val,
            "learning_rate": tasa
        })

        print(
            f"Epoca {epoca:02d}/{MAX_EPOCAS} | "
            f"Train: {perdida_train:.5f} | "
            f"Val: {perdida_val:.5f} | "
            f"LR: {tasa:.6f}"
        )

        if perdida_val < mejor_perdida:

            mejor_perdida = perdida_val

            mejor_epoca = epoca

            mejores_pesos = copy.deepcopy(modelo.state_dict())

            epocas_sin_mejora = 0

        else:

            epocas_sin_mejora += 1

        if epocas_sin_mejora >= PACIENCIA:

            print("\nEARLY STOPPING ACTIVADO")

            break

    tiempo_entrenamiento = time.perf_counter() - inicio

    if mejores_pesos is None:
        raise RuntimeError("No se encontraron pesos validos.")

    modelo.load_state_dict(mejores_pesos)

    print(f"\nMejor epoca: {mejor_epoca}")
    print(f"Mejor perdida validacion (MSE): {mejor_perdida:.6f}")
    print(f"Tiempo de entrenamiento: {tiempo_entrenamiento:.2f} s")

    # --------------------------------------------------------
    # 5.4 Evaluacion con prueba
    # --------------------------------------------------------

    inicio = time.perf_counter()

    predicciones, reales = obtener_predicciones(modelo, loader_test, dispositivo)

    tiempo_inferencia = time.perf_counter() - inicio

    # Un tiempo de respuesta no puede ser negativo ni pasar de 60.
    predicciones = np.clip(predicciones, 0, TIEMPO_MAXIMO)

    mae = mean_absolute_error(reales, predicciones)
    mse = mean_squared_error(reales, predicciones)
    rmse = np.sqrt(mse)
    r2 = r2_score(reales, predicciones)

    print("\nRESULTADOS DE LA CNN 1D")
    print(f"MAE:  {mae:.4f} min")
    print(f"MSE:  {mse:.4f}")
    print(f"RMSE: {rmse:.4f} min")
    print(f"R2:   {r2:.4f}")

    # Modelo base: siempre predice el promedio de entrenamiento.
    base = np.full(len(y_test), y_train.mean())

    mae_base = mean_absolute_error(y_test, base)
    rmse_base = np.sqrt(mean_squared_error(y_test, base))

    print("\nMODELO BASE (predice siempre el promedio)")
    print(f"MAE base:  {mae_base:.4f} min")
    print(f"RMSE base: {rmse_base:.4f} min")

    # --------------------------------------------------------
    # 5.5 Alertas de la meta de 15 minutos
    # --------------------------------------------------------

    # Se trata la prediccion como un sistema de alerta:
    # positivo = la ambulancia superara la meta el mes 3.

    alerta_real = reales > META_RESPUESTA_MIN

    alerta_predicha = predicciones > META_RESPUESTA_MIN

    exactitud_alerta = accuracy_score(alerta_real, alerta_predicha)
    precision_alerta = precision_score(alerta_real, alerta_predicha, zero_division=0)
    recall_alerta = recall_score(alerta_real, alerta_predicha, zero_division=0)

    print(f"\nALERTA: TIEMPO MES 3 > {META_RESPUESTA_MIN} MIN")
    print(f"Exactitud de la alerta: {exactitud_alerta:.4f}")
    print(f"Precision de la alerta: {precision_alerta:.4f}")
    print(f"Recall de la alerta:    {recall_alerta:.4f}")

    # --------------------------------------------------------
    # 5.6 Guardar modelo, historial y metricas
    # --------------------------------------------------------

    archivo_modelo = RUTA_SALIDA / "emergexia_cnn_regresion.pth"

    torch.save(
        {
            "model_state_dict": modelo.state_dict(),
            "arquitectura": "CNNRegresionEmergencias",
            "canales": 2,
            "meses_entrada": 2,
            "variable_objetivo": "tiempo_m3",
            "media_entrenamiento": datos["media_entrenamiento"].tolist(),
            "desviacion_entrenamiento": datos["desviacion_entrenamiento"].tolist(),
            "meta_respuesta_min": META_RESPUESTA_MIN,
            "mejor_epoca": mejor_epoca,
            "mejor_perdida_validacion": mejor_perdida,
            "parametros_entrenables": total_parametros
        },
        archivo_modelo
    )

    df_historial = pd.DataFrame(historial)

    archivo_historial = RUTA_SALIDA / "historial_entrenamiento_regresion.csv"

    df_historial.to_csv(archivo_historial, index=False)

    archivo_metricas = RUTA_SALIDA / "metricas_prediccion_cnn.json"

    with open(archivo_metricas, "w", encoding="utf-8") as archivo:
        json.dump(
            {
                "proyecto": "Emergexia",
                "etapa": 18.2,
                "tipo_problema": "Regresion",
                "mejor_epoca": int(mejor_epoca),
                "mejor_perdida_validacion": float(mejor_perdida),
                "metricas_prueba": {
                    "MAE": float(mae),
                    "MSE": float(mse),
                    "RMSE": float(rmse),
                    "R2": float(r2)
                },
                "modelo_base": {
                    "MAE": float(mae_base),
                    "RMSE": float(rmse_base)
                },
                "alerta_meta": {
                    "umbral_minutos": META_RESPUESTA_MIN,
                    "exactitud": float(exactitud_alerta),
                    "precision": float(precision_alerta),
                    "recall": float(recall_alerta)
                },
                "tiempos": {
                    "entrenamiento_segundos": float(tiempo_entrenamiento),
                    "inferencia_segundos": float(tiempo_inferencia)
                },
                "advertencia": (
                    "Datos sinteticos. Los resultados no representan "
                    "una validacion con servicios reales."
                )
            },
            archivo,
            indent=4,
            ensure_ascii=False
        )

    # --------------------------------------------------------
    # 5.7 Graficas
    # --------------------------------------------------------

    plt.figure(figsize=(10, 5))
    plt.plot(df_historial["epoca"], df_historial["perdida_train"], label="Entrenamiento")
    plt.plot(df_historial["epoca"], df_historial["perdida_val"], label="Validacion")
    plt.xlabel("Epoca")
    plt.ylabel("MSE")
    plt.title("Emergexia - Perdida de entrenamiento")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()

    archivo_curva = RUTA_SALIDA / "curva_entrenamiento_regresion.png"

    plt.savefig(archivo_curva, dpi=300)
    plt.close()

    limite = float(max(reales.max(), predicciones.max())) + 2

    plt.figure(figsize=(8, 7))
    plt.scatter(reales, predicciones, alpha=0.25)
    plt.plot([0, limite], [0, limite], linestyle="--", label="Prediccion perfecta")
    plt.axvline(META_RESPUESTA_MIN, color="red", alpha=0.4, label="Meta 15 min")
    plt.axhline(META_RESPUESTA_MIN, color="red", alpha=0.4)
    plt.xlabel("Tiempo real mes 3 (min)")
    plt.ylabel("Tiempo predicho mes 3 (min)")
    plt.title("Emergexia - Real vs Predicho")
    plt.xlim(0, limite)
    plt.ylim(0, limite)
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()

    archivo_dispersion = RUTA_SALIDA / "predicciones_real_vs_predicho.png"

    plt.savefig(archivo_dispersion, dpi=300)
    plt.close()

    # --------------------------------------------------------
    # 5.8 Predicciones de prueba con alerta
    # --------------------------------------------------------

    df_predicciones = pd.DataFrame({
        "id_ambulancia": datos["ids_test"],
        "hospital_base": datos["hospitales_test"],
        "tipo_emergencia": datos["tipos_test"],
        "tiempo_real_m3": reales.round(2),
        "tiempo_predicho_m3": predicciones.round(2),
        "error_absoluto": np.abs(reales - predicciones).round(2),
        "alerta_meta_15min": np.where(alerta_predicha, "ALERTA", "OK")
    })

    archivo_predicciones = RUTA_SALIDA / "predicciones_prueba_cnn.csv"

    df_predicciones.to_csv(archivo_predicciones, index=False)

    print("\nALERTAS PREDICHAS POR HOSPITAL (CONJUNTO DE PRUEBA)")

    print(
        df_predicciones.groupby("hospital_base")["alerta_meta_15min"]
        .apply(lambda s: (s == "ALERTA").mean() * 100)
        .round(2)
        .rename("porcentaje_alertas")
        .sort_values(ascending=False)
        .to_string()
    )

    # --------------------------------------------------------
    # 5.9 Resumen
    # --------------------------------------------------------

    print("\n" + "=" * 65)
    print("ETAPA 18.2 FINALIZADA")
    print("=" * 65)
    print(f"MAE CNN:  {mae:.4f} min  |  MAE base: {mae_base:.4f} min")
    print(f"R2:       {r2:.4f}")

    print("\nARCHIVOS GENERADOS:")

    for ruta in [
        archivo_modelo,
        archivo_historial,
        archivo_metricas,
        archivo_curva,
        archivo_dispersion,
        archivo_predicciones
    ]:
        print(ruta)

    print("\nNO SE UTILIZO EL TIEMPO DEL MES 3 COMO ENTRADA.")
    print("=" * 65)


if __name__ == "__main__":

    main()
