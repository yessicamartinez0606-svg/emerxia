# Emergexia · Big Data y Deep Learning (Prácticas 20 a 27)

Adaptación a Emergexia de las prácticas p20–p27 de Fundamentos de IA
(originalmente con el caso SmartAcademy). En lugar de **estudiantes y
calificaciones**, se trabaja con **ambulancias y tiempos de respuesta**
de los hospitales de Toluca.

| SmartAcademy (original) | Emergexia (esta carpeta) |
|---|---|
| 10,000 estudiantes × 5 materias | 10,000 ambulancias × 5 tipos de emergencia |
| Calificación de los parciales 1, 2 y 3 | Tiempo de respuesta (min) en los meses 1, 2 y 3 |
| Asistencia por parcial (%) | Disponibilidad de la ambulancia por mes (%) |
| Tendencia: Favorable / Estable / Descendente | Tendencia: Mejora / Estable / Deterioro |
| Resultado: Aprobado (promedio ≥ 7) | Resultado: Cumple (promedio ≤ 15 min) |
| Predecir la calificación del parcial 3 | Predecir el tiempo del mes 3 y lanzar **ALERTA** si pasará de 15 min |

> Los datos son **sintéticos** (generados con semilla 42). No representan servicios reales.

## Archivos

| Script | Etapa | Qué hace | Necesita |
|---|---|---|---|
| `p20_generador_emergencias.py` | 12 | Genera 50,000 registros (CSV) | numpy, pandas |
| `p21_spark_emergencias.py` | 13 | Valida y procesa con Spark; guarda Parquet | PySpark + Java |
| `p22_atlas_emergencias.py` | 14 | Sube los 50,000 registros a MongoDB | PySpark + Java + pymongo |
| `p23_preparacion_cnn_emergencias.py` | 15 | Convierte a tensores `[N, 2, 3]` y divide por ambulancia | PySpark + Java + PyTorch |
| `p24_entrenamiento_cnn_emergencias.py` | 16 | Entrena la CNN 1D que clasifica la tendencia | PyTorch |
| `p25_comparacion_modelos_emergencias.py` | 17 | Compara CNN 1D contra Random Forest | scikit-learn |
| `p26_preparacion_prediccion_emergencias.py` | 18.1 | Prepara datos para predecir el mes 3 (solo usa meses 1 y 2) | scikit-learn |
| `p27_prediccion_cnn_emergencias.py` | 18.2 | CNN de regresión + alertas de la meta de 15 min | PyTorch |

## Instalación (WSL / Ubuntu, recomendado)

Spark en Windows necesita Hadoop/winutils para guardar Parquet; en WSL funciona directo.

```bash
sudo apt install -y openjdk-17-jdk          # Java para Spark (una sola vez)
cd backend/ia_bigdata
python3 -m venv ~/emergexia-ia-venv
source ~/emergexia-ia-venv/bin/activate
pip install -r requirements-ia.txt
pip install torch --index-url https://download.pytorch.org/whl/cpu   # PyTorch (CPU)
```

Si tienes GPU NVIDIA, instala PyTorch con CUDA (`pip install torch`) y p24/p27 la usarán solas.

## Conexión a MongoDB (solo p22)

p22 usa **el mismo `backend/.env` de la API**: `MONGO_URI` y `MONGO_DB`.
También acepta `MONGO_USER`, `MONGO_PASSWORD` y `MONGO_CLUSTER` (formato de las prácticas).

Los datos se guardan en la colección **`servicios_ambulancia_masivos`**, separada de las
emergencias reales del sistema. Se puede volver a ejecutar sin duplicar registros (upsert).

## Orden de ejecución

Desde `backend/ia_bigdata`, con el entorno activado:

```bash
python p20_generador_emergencias.py
python p21_spark_emergencias.py
python p22_atlas_emergencias.py
python p23_preparacion_cnn_emergencias.py
python p24_entrenamiento_cnn_emergencias.py
python p25_comparacion_modelos_emergencias.py
python p26_preparacion_prediccion_emergencias.py
python p27_prediccion_cnn_emergencias.py
```

p26 y p27 solo dependen de p20, así que se pueden correr sin Spark.

## Resultados

Todo se guarda en `resultados_emergexia/` (no se sube a GitHub porque pesa varios MB):

```
resultados_emergexia/
├── datos_masivos/     CSV de 50,000 registros y resumen        (p20)
├── spark_procesado/   Parquet particionado por tipo            (p21)
├── resumen_spark/     Resumen por hospital y tipo              (p21)
├── cnn/               Tensores, modelo .pth, métricas, matriz  (p23, p24)
├── comparacion/       Tabla, gráfica e importancia de variables (p25)
└── prediccion_cnn/    Modelo de regresión, curvas, predicciones con ALERTA (p26, p27)
```

## Verlas dentro del sistema

Los resultados aparecen en **Asistente de despacho → Big Data y predicción** (solo personal de la
central). Después de correr las prácticas:

```bash
python exportar_resumen_sistema.py
```

Ese script junta lo que haya en `resultados_emergexia/` en un archivo pequeño,
`backend/app/datos_ia/bigdata_resumen.json`, que la API sirve en `GET /api/ia/bigdata`.
**Ese archivo sí se sube a GitHub**, así el panel funciona también en Render (donde no hay Spark
ni PyTorch). Las prácticas que no se hayan corrido aparecen como «Pendiente».

## Interpretación

- **p24 y p25** obtienen métricas cercanas a 100 % porque la tendencia se calcula con los
  mismos tiempos que recibe el modelo. Sirve para practicar CNN 1D, no para anticipar.
- **p27** sí predice: con los meses 1 y 2 estima el mes 3 y marca `ALERTA` cuando la
  ambulancia probablemente superará los 15 minutos. Se compara contra un modelo base
  que siempre predice el promedio.
