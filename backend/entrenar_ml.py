# ================================================================
# EMERGEXIA · MACHINE LEARNING
# Triage: ¿la emergencia requiere ambulancia AVANZADA?
#
# Aplica al proyecto lo visto en clase:
#   Práctica 04 → entrenamiento / validación / prueba, sobreajuste y subajuste
#   Práctica 05 → comparación de Decision Tree, Random Forest y KNN
#   Actividad   → Experimentos A (KNN), B (Random Forest) y C (Decision Tree)
#
# Uso (desde la carpeta backend):
#   python entrenar_ml.py
#
# Genera en backend/ml_resultados/:
#   comparacion_algoritmos.csv / .png      matriz_confusion.png
#   ajuste_profundidad.csv / .png          experimento_A/B/C.csv
#   experimentos.png                       modelo_triage.joblib   reporte.json
#
# El modelo guardado es el que usa la API (/api/ml/predecir) y el panel
# "Triage con Machine Learning" en el formulario de Nueva emergencia.
#
# IMPORTANTE: datos sintéticos con fines educativos. No es un protocolo clínico.
# ================================================================
import json

import joblib
import matplotlib

matplotlib.use("Agg")  # guarda las gráficas sin abrir ventanas (funciona igual en WSL)
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import ConfusionMatrixDisplay, classification_report

from app.ml.datos import OBJETIVO, VARIABLES, generar_datos
from app.ml.entrenamiento import (
    CRITERIO, EXPERIMENTOS, comparar, correr_experimento, crear_arbol, diagnostico_ajuste,
    dividir, entrenar_final, evaluar_en_validacion,
)
from app.ml.prediccion import ARCHIVO_MODELO, ARCHIVO_REPORTE, CARPETA

ETIQUETAS = ["Básica", "Avanzada"]
pct = "{:.2%}".format


def titulo(texto):
    print("\n" + "=" * 50 + f"\n{texto}\n" + "=" * 50)


CARPETA.mkdir(exist_ok=True)

# ----------------------------------------------------------------
# 1. DATOS
# ----------------------------------------------------------------
df = generar_datos()
titulo("1. DATOS GENERADOS (sintéticos)")
print(df.head(10).to_string(index=False))
print("\nCantidad de emergencias:", len(df))
print("Distribución (0 = Básica, 1 = Avanzada):")
print(df[OBJETIVO].value_counts().sort_index().to_string())

d = dividir(df)
titulo("2. DISTRIBUCIÓN DE LOS CONJUNTOS (60 / 20 / 20)")
print("Entrenamiento:", len(d["X_ent"]))
print("Validación:   ", len(d["X_val"]))
print("Prueba:       ", len(d["X_prueba"]))

# ----------------------------------------------------------------
# 2. PRÁCTICA 04: profundidad del árbol vs. sobreajuste
# ----------------------------------------------------------------
titulo("3. AJUSTE SEGÚN LA PROFUNDIDAD DEL ÁRBOL (Práctica 04)")
filas_ajuste = []
for prof in [1, 2, 3, 5, 10, None]:
    m = evaluar_en_validacion(crear_arbol(prof), d)
    filas_ajuste.append({
        "profundidad": "Sin limite" if prof is None else prof,
        "entrenamiento": m["exactitud_entrenamiento"],
        "validacion": m["exactitud"],
        "diferencia": m["brecha"],
        "ajuste": diagnostico_ajuste(m["exactitud_entrenamiento"], m["exactitud"]),
    })
df_ajuste = pd.DataFrame(filas_ajuste)
print(df_ajuste.to_string(index=False, formatters={c: pct for c in ["entrenamiento", "validacion", "diferencia"]}))
df_ajuste.to_csv(CARPETA / "ajuste_profundidad.csv", index=False, encoding="utf-8")

# ----------------------------------------------------------------
# 3. PRÁCTICA 05: comparación de algoritmos
# ----------------------------------------------------------------
tabla = comparar(d)
titulo("4. COMPARACIÓN DE ALGORITMOS (conjunto de validación)")
cols = ["algoritmo", "exactitud", "precision", "recall", "f1_score", "f2_score", "exactitud_entrenamiento", "ajuste"]
print(tabla[cols].to_string(index=False, formatters={c: pct for c in cols[1:-1]}))
tabla.to_csv(CARPETA / "comparacion_algoritmos.csv", index=False, encoding="utf-8")

mejor = tabla.iloc[0]["algoritmo"]
titulo("5. MODELO SELECCIONADO")
print("Algoritmo:", mejor)
print("F2-score de validación:", pct(tabla.iloc[0][CRITERIO]))
print("Criterio: mayor F2 (prioriza no dejar sin ambulancia Avanzada a un paciente grave)")

# ----------------------------------------------------------------
# 4. Reentrenar con 80 % y evaluar UNA vez con la prueba
# ----------------------------------------------------------------
final = entrenar_final(mejor, d)
mp = final["metricas_prueba"]
titulo("6. EVALUACIÓN FINAL (conjunto de prueba)")
for k in ["exactitud", "precision", "recall", "f1_score", "f2_score"]:
    print(f"{k:<10}", pct(mp[k]))

titulo("7. REPORTE DE CLASIFICACIÓN")
print(classification_report(d["y_prueba"], final["predicciones"], labels=[0, 1],
                            target_names=ETIQUETAS, zero_division=0))

titulo("8. MATRIZ DE CONFUSIÓN")
(tn, fp), (fn, tp) = final["matriz"]
print(final["matriz"])
print(f"Verdaderos negativos (Básica bien asignada):     {tn}")
print(f"Falsos positivos (Avanzada sin necesitarla):     {fp}")
print(f"Falsos negativos (grave enviado con Básica):     {fn}   ← el error más costoso")
print(f"Verdaderos positivos (Avanzada bien asignada):   {tp}")

titulo("9. VALIDACIÓN CRUZADA ESTRATIFICADA (recall, 5 particiones)")
print("Por partición:", np.round(final["cv_recall"], 4))
print("Promedio:", pct(final["cv_recall"].mean()), "· Desviación estándar:", pct(final["cv_recall"].std()))

# ----------------------------------------------------------------
# 5. Actividad de modificación: experimentos A, B y C
# ----------------------------------------------------------------
experimentos = {}
for clave in EXPERIMENTOS:
    res = correr_experimento(clave, d)
    experimentos[clave] = res
    titulo(f"EXPERIMENTO {clave[0]} · {EXPERIMENTOS[clave][0]}")
    print(res.to_string(index=False, formatters={c: pct for c in
                                                ["exactitud_entrenamiento", "exactitud_validacion", "recall", "f2_score"]}))
    mejor_fila = res.loc[res["f2_score"].idxmax()]
    print(f"Mejor F2 con {EXPERIMENTOS[clave][0]} = {mejor_fila.iloc[0]} ({pct(mejor_fila['f2_score'])})")
    res.to_csv(CARPETA / f"experimento_{clave}.csv", index=False, encoding="utf-8")

# ----------------------------------------------------------------
# 6. Gráficas
# ----------------------------------------------------------------
# a) Comparación de métricas por algoritmo
metr = ["exactitud", "precision", "recall", "f1_score", "f2_score"]
plt.figure(figsize=(12, 6))
pos, ancho = np.arange(len(tabla)), 0.16
for i, m in enumerate(metr):
    plt.bar(pos + (i - 2) * ancho, tabla[m], width=ancho, label=m.replace("_", " ").title())
plt.xticks(pos, tabla["algoritmo"])
plt.ylim(0, 1.05); plt.ylabel("Resultado"); plt.xlabel("Algoritmo")
plt.title("Emergexia · Comparación de algoritmos de triage (validación)")
plt.legend(); plt.grid(axis="y", alpha=0.3); plt.tight_layout()
plt.savefig(CARPETA / "comparacion_algoritmos.png", dpi=200); plt.close()

# b) Entrenamiento vs validación según profundidad
x = [12 if p == "Sin limite" else p for p in df_ajuste["profundidad"]]
plt.figure(figsize=(11, 6))
plt.plot(x, df_ajuste["entrenamiento"], marker="o", linewidth=2, label="Entrenamiento")
plt.plot(x, df_ajuste["validacion"], marker="s", linewidth=2, label="Validación")
plt.xticks(x, df_ajuste["profundidad"])
plt.ylim(0, 1.05); plt.xlabel("Profundidad del árbol"); plt.ylabel("Exactitud")
plt.title("Emergexia · Sobreajuste según la profundidad del árbol")
plt.grid(True, linestyle="--", alpha=0.5); plt.legend(); plt.tight_layout()
plt.savefig(CARPETA / "ajuste_profundidad.png", dpi=200); plt.close()

# c) Matriz de confusión
ConfusionMatrixDisplay(final["matriz"], display_labels=ETIQUETAS).plot(cmap="Blues", values_format="d")
plt.title(f"Matriz de confusión · {mejor}"); plt.tight_layout()
plt.savefig(CARPETA / "matriz_confusion.png", dpi=200); plt.close()

# d) Experimentos A, B y C
fig, ejes = plt.subplots(1, 3, figsize=(16, 5))
for eje, (clave, res) in zip(ejes, experimentos.items()):
    etiquetas = [str(v) for v in res.iloc[:, 0]]
    eje.plot(etiquetas, res["exactitud_entrenamiento"], marker="o", label="Exactitud entrenamiento")
    eje.plot(etiquetas, res["exactitud_validacion"], marker="s", label="Exactitud validación")
    eje.plot(etiquetas, res["f2_score"], marker="^", label="F2 validación")
    eje.set_title(f"Experimento {clave[0]} · {EXPERIMENTOS[clave][0]}")
    eje.set_ylim(0.4, 1.02); eje.grid(alpha=0.3)
ejes[0].legend(loc="lower left", fontsize=8)
fig.suptitle("Emergexia · Actividad de modificación"); fig.tight_layout()
fig.savefig(CARPETA / "experimentos.png", dpi=200); plt.close(fig)

# ----------------------------------------------------------------
# 7. Guardar el modelo para la API y el reporte
# ----------------------------------------------------------------
joblib.dump({"modelo": final["modelo"], "algoritmo": mejor,
             "metricas_prueba": mp, "variables": VARIABLES}, ARCHIVO_MODELO)

ARCHIVO_REPORTE.write_text(json.dumps({
    "algoritmo_seleccionado": mejor,
    "criterio": CRITERIO,
    "comparacion": tabla[cols].to_dict(orient="records"),
    "metricas_prueba": mp,
    "matriz_confusion": final["matriz"].tolist(),
    "cv_recall": {"particiones": final["cv_recall"].tolist(),
                  "promedio": float(final["cv_recall"].mean()), "desviacion": float(final["cv_recall"].std())},
    "ajuste_profundidad": df_ajuste.to_dict(orient="records"),
    "experimentos": {k: v.to_dict(orient="records") for k, v in experimentos.items()},
}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

titulo("ARCHIVOS GENERADOS en backend/ml_resultados/")
for f in sorted(CARPETA.iterdir()):
    print(" ·", f.name)

titulo("CONCLUSIÓN")
print("Algoritmo seleccionado:", mejor)
print("Recall en prueba:", pct(mp["recall"]), f"· {fn} paciente(s) grave(s) no detectado(s) de {fn + tp}")
print("El mejor algoritmo depende de los datos y de la métrica: en Emergexia importa más el recall.")
print("\nPROCESO FINALIZADO.")
