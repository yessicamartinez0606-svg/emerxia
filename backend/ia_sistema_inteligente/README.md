# Emergexia · Sistema inteligente de emergencias (Prácticas 10 a 19)

Adaptación a Emergexia de las prácticas p10–p19 de Fundamentos de IA
(originalmente con el caso SmartAcademy). En lugar de **estudiantes y su
aprobación**, se analizan **emergencias y su prioridad** para apoyar al
Administrador al asignar ambulancias desde el Hospital IMSS 220 (Toluca).

| SmartAcademy (original) | Emergexia (esta carpeta) |
|---|---|
| Horas de estudio, asistencia, actividades, participación | Edad, frecuencia cardiaca, saturación de oxígeno, distancia al IMSS 220 |
| Aprueba (1) / No aprueba (0) | Crítica (1) / No crítica (0) |
| Perfiles académicos (K-Means) | Perfiles de riesgo: bajo, moderado, medio-alto y alto |
| Recomendaciones académicas | Prioridad (1, 2 o 3), equipo de la ambulancia, gasolina y apoyo de otros hospitales |
| Colección de reportes de estudiantes | Colección `analisis_emergencias_ia` en MongoDB |
| Expediente del estudiante y materias (p19) | Expediente del paciente y tomas de signos vitales |

> Los datos son **sintéticos** (semilla 42). No representan pacientes reales y
> las recomendaciones no sustituyen la valoración del personal médico.

## Archivos

| Script | Etapa | Qué hace | Genera |
|---|---|---|---|
| `p10_datos_emergencias.py` | 1 | Genera 500 emergencias con la variable `critica` | `emergexia_datos.csv` |
| `p11_modelo_supervisado_emergencias.py` | 2 | Compara Decision Tree y Random Forest; guarda el mejor | `modelo_emergexia.joblib` |
| `p12_kmeans_emergencias.py` | 3 | K-Means (K de 2 a 6) y perfiles de riesgo | `modelo_kmeans_emergexia.joblib` |
| `p13_pca_emergencias.py` | 4 | Reduce las 4 variables a PC1 y PC2 | `modelo_pca_emergexia.joblib` |
| `p14_motor_recomendaciones_emergencias.py` | 5 | Captura una emergencia, usa los 3 modelos y aplica reglas | `reporte_emergencia.csv` |
| `p15_persistencia_mongodb_emergencias.py` | 6 | Guarda el reporte en MongoDB y muestra el historial | Documento en Atlas |
| `p16_analisis_estadistico_emergencias.py` | 7 | Consultas con `find()` y `aggregate()`: críticas, perfiles, prioridades | 5 reportes CSV |
| `p17_dashboard_emergencias.py` | 8 | Dashboard web (Streamlit + Plotly) con filtros | Página en el navegador |
| `p18_evaluacion_emergencias.py` | 9 | App web: evalúa una emergencia, la guarda e historial por folio | Documento en Atlas |
| `p19_registro_atencion_emergencias.py` | 11 | Expediente del paciente, atención y tomas de signos vitales + IA | 3 colecciones en Atlas |

## Instalación

```bash
cd backend/ia_sistema_inteligente
pip install -r requirements-ia.txt
```

## Orden de ejecución

Desde `backend/ia_sistema_inteligente` (o desde cualquier carpeta: las rutas se
calculan a partir de la ubicación de cada archivo):

```bash
python p10_datos_emergencias.py
python p11_modelo_supervisado_emergencias.py
python p12_kmeans_emergencias.py
python p13_pca_emergencias.py
python p14_motor_recomendaciones_emergencias.py   # pide los datos por teclado
python p15_persistencia_mongodb_emergencias.py
python p16_analisis_estadistico_emergencias.py
streamlit run p17_dashboard_emergencias.py          # dashboard
streamlit run p18_evaluacion_emergencias.py         # evaluar emergencias
streamlit run p19_registro_atencion_emergencias.py  # registro integral
```

Cada script necesita lo que generaron los anteriores. p17, p18 y p19 son páginas web: se abren
con `streamlit run` (no con `python`) en <http://localhost:8501>. p18 y p19 reutilizan las
funciones de p14 y los modelos de p11–p13; no entrenan nada nuevo.

## Conexión a MongoDB (p15 a p19)

Todas usan **el mismo `backend/.env` de la API**: `MONGO_URI` y `MONGO_DB`.
También acepta `MONGO_USER`, `MONGO_PASSWORD` y `MONGO_CLUSTER` (formato de las prácticas).
Si existe un `.env` dentro de esta carpeta, ese tiene prioridad.

Colecciones (separadas de las colecciones reales del sistema):

| Colección | La llenan | La leen | Contenido |
|---|---|---|---|
| `analisis_emergencias_ia` (`MONGO_COLLECTION_IA`) | p15, p18, p19 | p16, p17 | Un análisis de IA por documento (datos, clasificación, perfil, PCA, prioridad, recomendaciones) |
| `pacientes_ia` | p19 | p19 | Expediente permanente de cada paciente (uno por `id_paciente`) |
| `atenciones_ia` | p19 | p19 | Cada atención: servicio (ambulancia, operador) y tomas de signos vitales |

Todas las consultas filtran `"sistema": "Emergexia"`, así que la colección de análisis
se puede compartir con otras prácticas sin mezclar resultados.

## Reglas del motor (p14)

| Regla | Condición | Recomendación |
|---|---|---|
| Prioridad | Crítica + perfil Riesgo alto / solo crítica / no crítica | Prioridad 1 (inmediata) / 2 (urgente) / 3 (no urgente) |
| Oxígeno | SpO2 < 90 % | Enviar ambulancia con oxígeno suplementario listo |
| Corazón | FC > 120 o < 50 lpm | Enviar unidad con monitor cardiaco |
| Edad | ≥ 65 años / < 12 años | Avisar al hospital / confirmar equipo pediátrico |
| Distancia | > 15 km | Verificar que la ambulancia tenga gasolina suficiente |
| Disponibilidad | Más de 3 ambulancias ocupadas | Solicitar apoyo a otros hospitales |

## Resultados

Los archivos de p10–p16 se guardan en `resultados_sistema_inteligente/` (no se sube a GitHub):

```
resultados_sistema_inteligente/
├── emergexia_datos.csv            500 emergencias               (p10)
├── comparacion_modelos.csv/.png   Decision Tree vs Random Forest (p11)
├── evaluacion_kmeans.csv          Inercia y Silhouette por K     (p12)
├── emergencias_segmentadas.csv    Perfil de cada emergencia      (p12)
├── emergencias_pca.csv            PC1 y PC2 de cada emergencia   (p13)
├── reporte_emergencia.csv         Último análisis del motor      (p14)
├── analisis_*.csv, estadisticas_*.csv  Reportes de las consultas (p16)
├── *.png                          Gráficas de codo, Silhouette, segmentación y PCA
└── modelos/                       Los tres modelos .joblib
```

## Interpretación

- **p11**: Random Forest gana (F1 ≈ 0.89, recall ≈ 92 %). Se elige por F1 y se
  revisan los falsos negativos: no detectar una emergencia crítica es el peor error.
- **p12**: el mejor K es 4, con Silhouette bajo (≈ 0.22) porque los datos se generan
  uniformes, sin grupos naturales. Aun así el perfil *Riesgo alto* tiene 94 % de
  emergencias críticas, aunque K-Means nunca vio esa columna.
- **p13**: PC1 + PC2 conservan ≈ 52 % de la variabilidad (las 4 variables son
  independientes). Sirve para visualizar, no para tomar decisiones.
