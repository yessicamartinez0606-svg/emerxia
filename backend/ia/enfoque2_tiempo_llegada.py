# ============================================================
# EMERGEXIA - FUNDAMENTOS DE INTELIGENCIA ARTIFICIAL
# ENFOQUE 2: ¿CUANTO TARDA EN LLEGAR LA AMBULANCIA?
# FORMULA FIJA VS MODELO QUE APRENDE (ARBOL DE REGRESION)
# ============================================================
#
# ¿QUE QUEREMOS RESOLVER?
# Cuando entra una emergencia, el operador quiere saber cuantos
# minutos tardara la ambulancia en llegar desde el Hospital
# IMSS 220 (Paseo Tollocan, Toluca).
#
# Comparamos dos formas de calcularlo:
#   A) FORMULA FIJA: distancia / velocidad. Siempre igual.
#   B) MODELO QUE APRENDE: revisa servicios pasados y descubre
#      solo como influyen la hora pico, la lluvia y la zona.
#
# DIFERENCIA CON LA PRACTICA 03:
# Alla el modelo respondia "si o no" (aprueba / no aprueba).
# Aqui responde con un NUMERO (minutos). A esto se le llama
# REGRESION.
#
# IMPORTANTE:
# Distancias aproximadas y tiempos inventados, solo para aprender.
# ============================================================


# ------------------------------------------------------------
# 1. BIBLIOTECAS
# ------------------------------------------------------------

import numpy as np                     # numeros aleatorios y calculos
import pandas as pd                    # tablas de datos

from sklearn.model_selection import train_test_split   # separar datos
from sklearn.tree import DecisionTreeRegressor          # el modelo
from sklearn.metrics import mean_absolute_error, r2_score


# Pequena funcion para que los titulos se vean ordenados.
def titulo(texto):
    print("\n" + "=" * 60)
    print(texto)
    print("=" * 60)


# ------------------------------------------------------------
# 2. CREAR UN HISTORIAL DE SERVICIOS (DATOS FICTICIOS)
# ------------------------------------------------------------

# Generamos 300 servicios con numeros aleatorios.
# La semilla 42 hace que siempre salgan los mismos datos.
rng = np.random.default_rng(42)
N = 300

# Zonas de destino y su distancia aproximada (km) desde el IMSS 220.
zonas = {
    "Centro Toluca": 3,
    "Metepec": 7,
    "San Pablo Autopan": 9,
    "San Mateo Atenco": 9,
    "Zinacantepec": 10,
    "Lerma": 14
}

zona = rng.choice(list(zonas.keys()), N)
distancia_km = np.array([zonas[z] for z in zona]) + rng.uniform(-1.5, 1.5, N)
distancia_km = distancia_km.clip(0.5).round(1)

hora = rng.integers(0, 24, N)                       # hora de la llamada
fin_de_semana = (rng.random(N) < 2 / 7).astype(int) # 1 = sabado o domingo
lluvia = (rng.random(N) < 0.25).astype(int)         # 1 = estaba lloviendo

# Hora pico: de 7 a 9 y de 18 a 20 h, solo entre semana.
hora_pico = (
    (((hora >= 7) & (hora <= 9)) | ((hora >= 18) & (hora <= 20)))
    & (fin_de_semana == 0)
).astype(int)

# Asi se calcula (en secreto) el tiempo "real" de cada servicio.
# El modelo NUNCA ve estas lineas: solo ve los resultados finales
# y tiene que descubrir el patron por su cuenta.
velocidad = np.full(N, 42.0)                            # km/h normal
velocidad = np.where(hora_pico == 1, 22.0, velocidad)   # trafico pesado
velocidad = np.where(lluvia == 1, velocidad * 0.75, velocidad)
velocidad = np.where(fin_de_semana == 1, velocidad * 1.10, velocidad)
velocidad = np.where(zona == "Lerma", velocidad * 0.85, velocidad)

minutos = 2 + distancia_km / velocidad * 60 + rng.normal(0, 1.5, N)
minutos = minutos.clip(3).round(1)

df = pd.DataFrame({
    "zona": zona,
    "distancia_km": distancia_km,
    "hora": hora,
    "hora_pico": hora_pico,
    "fin_de_semana": fin_de_semana,
    "lluvia": lluvia,
    "minutos_llegada": minutos
})


# ------------------------------------------------------------
# 3. CONOCER LOS DATOS
# ------------------------------------------------------------

titulo("1. HISTORIAL DE SERVICIOS DE AMBULANCIA")

print(f"Tenemos {len(df)} servicios registrados. Estos son los primeros 8:\n")

# Mostramos la tabla con nombres faciles de leer y "Si/No"
# en lugar de 1 y 0.
vista = df.head(8).copy()
for col in ["hora_pico", "fin_de_semana", "lluvia"]:
    vista[col] = vista[col].map({1: "Si", 0: "No"})
vista["hora"] = vista["hora"].astype(str) + ":00"
vista.columns = ["Zona", "Km", "Hora", "Hora pico", "Fin de semana",
                 "Lluvia", "Minutos"]
print(vista.to_string(index=False))

print("\nTiempo promedio de llegada por zona:")
promedios = df.groupby("zona")["minutos_llegada"].mean().sort_values()
for nombre_zona, prom in promedios.items():
    print(f"  {nombre_zona:20s} {prom:5.1f} min")

print("\nEfecto de las condiciones (promedio de todos los servicios):")
for col, texto in [("hora_pico", "Hora pico"), ("lluvia", "Lluvia")]:
    con = df[df[col] == 1]["minutos_llegada"].mean()
    sin = df[df[col] == 0]["minutos_llegada"].mean()
    print(f"  {texto:10s} con: {con:4.1f} min | sin: {sin:4.1f} min")


# ------------------------------------------------------------
# 4. PREPARAR LOS DATOS PARA EL MODELO
# ------------------------------------------------------------

# El modelo solo entiende numeros, no la palabra "Metepec".
# get_dummies crea una columna por zona: 1 si fue ahi, 0 si no.
df_modelo = pd.get_dummies(df, columns=["zona"], dtype=int)

X = df_modelo.drop(columns=["minutos_llegada"])   # lo que el modelo ve
y = df_modelo["minutos_llegada"]                   # lo que debe adivinar

# 70 % de los servicios para que el modelo aprenda,
# 30 % guardados para examinarlo despues.
X_entrenamiento, X_prueba, y_entrenamiento, y_prueba = train_test_split(
    X, y, test_size=0.30, random_state=42
)

titulo("2. SEPARACION DE LOS DATOS")
print(f"El modelo estudiara {len(X_entrenamiento)} servicios.")
print(f"Despues lo examinaremos con {len(X_prueba)} servicios que NUNCA vio.")
print("Asi comprobamos que aprendio y no solo memorizo.")


# ------------------------------------------------------------
# 5. METODO A: FORMULA FIJA
# ------------------------------------------------------------

# Supone que la ambulancia siempre va a 40 km/h y tarda 2 min
# en salir. No toma en cuenta trafico ni lluvia.
def estimar_con_formula(servicio):
    return 2 + servicio["distancia_km"] / 40 * 60


# ------------------------------------------------------------
# 6. METODO B: MODELO QUE APRENDE
# ------------------------------------------------------------

# Un arbol de regresion hace preguntas como
# "¿es hora pico?" o "¿son mas de 10 km?" y, al final,
# responde con el promedio de minutos de servicios parecidos.
modelo = DecisionTreeRegressor(max_depth=5, min_samples_leaf=5, random_state=42)

modelo.fit(X_entrenamiento, y_entrenamiento)   # fit() = aprender

titulo("3. ENTRENAMIENTO")
print("El modelo termino de estudiar los servicios pasados.")


# ------------------------------------------------------------
# 7. COMPARAR AMBOS METODOS
# ------------------------------------------------------------

pred_ml = modelo.predict(X_prueba)                       # predict() = estimar
pred_formula = X_prueba.apply(estimar_con_formula, axis=1)

titulo("4. ¿QUIEN SE ACERCO MAS AL TIEMPO REAL? (10 ejemplos)")

comparacion = pd.DataFrame({
    "Zona": df.loc[X_prueba.index, "zona"],
    "Real": y_prueba.round(1),
    "Formula": pred_formula.round(1),
    "Modelo": pred_ml.round(1)
})
comparacion["Mas cercano"] = np.where(
    abs(comparacion["Modelo"] - comparacion["Real"])
    < abs(comparacion["Formula"] - comparacion["Real"]),
    "Modelo", "Formula"
)
print(comparacion.head(10).to_string(index=False))
print("\n(Todos los tiempos estan en minutos)")


# ------------------------------------------------------------
# 8. CALIFICAR A CADA METODO
# ------------------------------------------------------------

# Error promedio (MAE): en promedio, ¿por cuantos minutos se equivoca?
# R2: que tan bien entiende el comportamiento (0 % = nada, 100 % = perfecto).

titulo("5. CALIFICACION DE CADA METODO")

resultados = {}
for nombre, pred in [("Formula fija", pred_formula), ("Modelo", pred_ml)]:
    error = mean_absolute_error(y_prueba, pred)
    r2 = r2_score(y_prueba, pred)
    resultados[nombre] = error
    print(f"{nombre}:")
    print(f"  - Se equivoca en promedio por {error:.1f} minutos.")
    print(f"  - Explica el {r2:.0%} de la variacion en los tiempos.\n")

mejor = min(resultados, key=resultados.get)
diferencia = abs(resultados["Formula fija"] - resultados["Modelo"])
print(f"Ganador: {mejor}. Se equivoca {diferencia:.1f} minutos menos en promedio.")


# ------------------------------------------------------------
# 9. ¿QUE APRENDIO EL MODELO?
# ------------------------------------------------------------

titulo("6. ¿EN QUE SE FIJA MAS EL MODELO?")

nombres_claros = {
    "distancia_km": "Distancia",
    "hora": "Hora exacta",
    "hora_pico": "Hora pico",
    "fin_de_semana": "Fin de semana",
    "lluvia": "Lluvia",
}
importancias = pd.Series(modelo.feature_importances_, index=X.columns)
importancias.index = [
    nombres_claros.get(c, "Zona " + c.replace("zona_", "")) for c in importancias.index
]
importancias = importancias[importancias > 0.01].sort_values(ascending=False)

for factor, peso in importancias.items():
    barra = "#" * int(peso * 40)
    print(f"  {factor:15s} {barra} {peso:.0%}")

print("\nLa formula fija solo usa la distancia. El modelo descubrio")
print("por si mismo que la hora pico y la lluvia tambien importan.")


# ------------------------------------------------------------
# 10. PROBAR CON UNA EMERGENCIA NUEVA
# ------------------------------------------------------------

# Meta de servicio (ficticia): llegar en 15 minutos o menos.
META = 15

def preparar_servicio(zona_destino, distancia, hora_llamada, finde, llueve):
    """Convierte los datos de una emergencia al formato del modelo."""
    pico = int(finde == 0 and (7 <= hora_llamada <= 9 or 18 <= hora_llamada <= 20))
    fila = {
        "distancia_km": distancia,
        "hora": hora_llamada,
        "hora_pico": pico,
        "fin_de_semana": finde,
        "lluvia": llueve
    }
    for columna in X.columns:
        if columna.startswith("zona_"):
            fila[columna] = int(columna == f"zona_{zona_destino}")
    return pd.DataFrame([fila])[X.columns]


def reportar_emergencia(zona_destino, distancia, hora_llamada, finde, llueve):
    servicio = preparar_servicio(zona_destino, distancia, hora_llamada, finde, llueve)
    t_formula = estimar_con_formula(servicio.iloc[0])
    t_modelo = modelo.predict(servicio)[0]

    print(f"Destino: {zona_destino} ({distancia} km)")
    print(f"Hora: {hora_llamada}:00 | "
          f"{'Fin de semana' if finde else 'Entre semana'} | "
          f"{'Lloviendo' if llueve else 'Sin lluvia'}")
    print(f"  Formula fija estima: {t_formula:5.1f} min")
    print(f"  Modelo estima:       {t_modelo:5.1f} min")

    if t_modelo <= META:
        print(f"  -> Segun el modelo, SI se cumple la meta de {META} min.")
    else:
        print(f"  -> ALERTA: segun el modelo NO se cumple la meta de {META} min.")
        print("     Conviene enviar la unidad disponible mas cercana.")
    print()


titulo("7. EMERGENCIAS NUEVAS")
reportar_emergencia("Lerma", 13.5, 19, 0, 1)          # hora pico y lluvia
reportar_emergencia("Metepec", 7.0, 11, 0, 0)         # dia tranquilo
reportar_emergencia("Centro Toluca", 3.0, 8, 0, 1)    # hora pico, cerca


# ------------------------------------------------------------
# 11. CONCLUSIONES
# ------------------------------------------------------------

titulo("8. CONCLUSIONES")
print("1. La formula fija es sencilla, pero falla en hora pico y con")
print("   lluvia porque supone que la velocidad siempre es la misma")
print("2. El modelo aprendio esos efectos solo con ejemplos pasados")
print("3. Clasificar = elegir una categoria. Regresion = estimar un numero")
print("4. Con datos reales del GPS de las unidades de Emergexia, el")
print("   modelo podria actualizarse cada cierto tiempo")


# ------------------------------------------------------------
# RESUMEN DE INSTRUCCIONES
# ------------------------------------------------------------
# pd.get_dummies()          Convierte texto (zona) en columnas de 0 y 1.
# train_test_split()        Separa datos para aprender y para examinar.
# DecisionTreeRegressor()   Crea un arbol que predice numeros.
# modelo.fit(X, y)          El modelo aprende de ejemplos conocidos.
# modelo.predict(X)         El modelo estima minutos para casos nuevos.
# mean_absolute_error()     Error promedio en minutos.
# r2_score()                Que tanto explica el modelo (0 a 1).
# feature_importances_      En que variables se fijo mas el modelo.