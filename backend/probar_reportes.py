"""Prueba las reglas de los reportes de usuarios: preguntas de sí/no, prioridad y duplicados.

Uso (en la carpeta backend, con el entorno virtual activado):
    python probar_reportes.py

No necesita MongoDB ni internet: solo prueba las funciones de app/reportes.py.
"""
import sys
from datetime import datetime, timedelta, timezone

from app import reportes
from app.routers import eventos

OK, BAD = "  [OK]  ", "  [X]   "


def main() -> int:
    fallas = 0

    def revisar(cond, texto):
        nonlocal fallas
        print((OK if cond else BAD) + texto)
        fallas += 0 if cond else 1

    print("\nPreguntas")
    claves = [p["clave"] for p in reportes.preguntas_de("Parto o embarazo")]
    revisar(claves[:3] == ["consciente", "respira", "sangrado"] and "cabeza" in claves,
            "Cada tipo trae las preguntas generales y las suyas")
    cat = reportes.catalogo()
    revisar("alarma" not in cat["generales"][0] and set(cat["tipos"]) == set(reportes.TIPOS),
            "El catálogo para la pantalla no expone las reglas internas")
    todas = [p["clave"] for ps in reportes.POR_TIPO.values() for p in ps] + [p["clave"] for p in reportes.GENERALES]
    revisar(len(todas) == len(set(todas)), "Ninguna pregunta repite su clave")

    print("\nPrioridad")
    c = reportes.calcular_prioridad("Caída o fractura", {})
    revisar(c["prioridad"] == "Media" and c["motivos"] == [] and c["respuestas"] == [],
            "Sin respuestas, la prioridad es la del tipo")
    c = reportes.calcular_prioridad("Caída o fractura", {"consciente": True, "respira": True, "cabeza_golpe": None})
    revisar(c["prioridad"] == "Media" and len(c["respuestas"]) == 2, "Respuestas tranquilizadoras o «No sé» no la cambian")
    c = reportes.calcular_prioridad("Caída o fractura", {"respira": False})
    revisar(c["prioridad"] == "Alta" and c["motivos"] == ["No respira normalmente"] and c["critica"],
            "«No respira» la vuelve Alta, con el motivo")
    c = reportes.calcular_prioridad("Quemadura", {"zona": True})
    revisar(c["prioridad"] == "Alta" and not c["critica"], "Una señal que «eleva» sube un nivel (Media → Alta)")
    c = reportes.calcular_prioridad("Quemadura", {"zona": True, "grande": True})
    revisar(c["prioridad"] == "Alta" and len(c["motivos"]) == 2, "Nunca pasa de Alta")
    c = reportes.calcular_prioridad("Caída o fractura", {"mover": False})
    revisar(c["prioridad"] == "Alta", "«No puede mover brazos o piernas» es crítica (la alarma es el «No»)")
    c = reportes.calcular_prioridad("Inventado", {"respira": True, "atrapados": True})
    revisar(c["prioridad"] == "Media" and c["motivos"] == [],
            "Un tipo desconocido cuenta como «Otro» y no usa preguntas de otros tipos")
    revisar(c["respuestas"][0] == {"pregunta": "¿Respira normalmente?", "respuesta": "Sí"},
            "Las respuestas se guardan legibles para la central")
    revisar(reportes.mayor_prioridad("Media", "Alta") == "Alta" and reportes.mayor_prioridad(None, "Baja") == "Baja",
            "Al sumar reportes se queda la prioridad más alta")

    print("\nDuplicados")
    ahora = datetime(2026, 11, 15, 18, 0, tzinfo=timezone.utc)
    hace = lambda m: (ahora - timedelta(minutes=m)).replace(tzinfo=None)   # noqa: E731  así las regresa pymongo
    choque = {"id": 1, "folio": "EMG-0001", "tipo": "Accidente de tránsito", "estado": "Asignada",
              "lat": 19.2900, "lng": -99.6500, "direccion": "Paseo Tollocan y Pino Suárez", "created_at": hace(5)}
    revisar(round(reportes.distancia_m(19.29, -99.65, 19.291, -99.65)) in range(108, 114), "La distancia entre puntos es correcta (~111 m)")
    em, d = reportes.buscar_duplicado("Accidente de tránsito", 19.2915, -99.6505, "", [choque], ahora)
    revisar(em is choque and 150 < d < 200, "Mismo tipo, a ~175 m y hace 5 min: es la misma emergencia")
    em, _ = reportes.buscar_duplicado("Accidente de tránsito", 19.2960, -99.6500, "", [choque], ahora)
    revisar(em is None, "A más de 300 m es otra emergencia")
    em, _ = reportes.buscar_duplicado("Caída o fractura", 19.2901, -99.6500, "", [choque], ahora)
    revisar(em is None, "Otro tipo en el mismo lugar es otra emergencia")
    viejo = {**choque, "created_at": hace(45)}
    revisar(reportes.buscar_duplicado("Accidente de tránsito", 19.29, -99.65, "", [viejo], ahora)[0] is None,
            "Si la primera se reportó hace más de 20 min, es otra")
    cerrada = {**choque, "estado": "Cerrada"}
    revisar(reportes.buscar_duplicado("Accidente de tránsito", 19.29, -99.65, "", [cerrada], ahora)[0] is None,
            "Una emergencia ya cerrada no recibe reportes nuevos")
    sin_punto = {**choque, "lat": None, "lng": None, "direccion": "Av. Morelos 1200, Toluca"}
    em, d = reportes.buscar_duplicado("Accidente de tránsito", None, None,
                                      "av morelos 1200 toluca (Referencias: frente al Oxxo)", [sin_punto], ahora)
    revisar(em is sin_punto and d is None, "Sin punto en el mapa se compara la dirección (sin acentos ni referencias)")
    otro = {**choque, "id": 2, "folio": "EMG-0002", "lat": 19.2903, "lng": -99.6501}
    em, _ = reportes.buscar_duplicado("Accidente de tránsito", 19.2904, -99.6501, "", [choque, otro], ahora)
    revisar(em is otro, "Si hay dos cerca, se suma a la más cercana")

    print("\nAvisos al instante (change streams)")
    em = {"id": 7, "folio": "EMG-0007", "tipo": "Quemadura", "prioridad": "Alta", "reportado_por": "rosa",
          "reportante": "Rosa", "canal": "mensaje", "num_reportes": 1, "direccion": "Centro"}
    ev = eventos.evento_de_cambio({"operationType": "insert", "fullDocument": em})
    revisar(ev["evento"] == "nueva" and ev["folio"] == "EMG-0007" and "reportado_por" not in ev,
            "Una emergencia nueva de un usuario se vuelve aviso «nueva» (sin datos internos)")
    central = {**em, "reportado_por": None}
    revisar(eventos.evento_de_cambio({"operationType": "insert", "fullDocument": central}) is None,
            "Las que registra la propia central no generan aviso")
    ev = eventos.evento_de_cambio({"operationType": "update", "fullDocument": {**em, "num_reportes": 3}})
    revisar(ev["evento"] == "otro_reporte" and ev["num_reportes"] == 3, "Cuando otra persona reporta la misma, avisa «otro_reporte»")
    revisar(eventos.evento_de_cambio({"operationType": "update", "fullDocument": None}) is None,
            "Si MongoDB no manda el documento (ya lo borraron), no truena")
    linea = eventos._sse(ev)
    revisar(linea.startswith("data: {") and linea.endswith("\n\n") and "Quemadura" in linea,
            "Cada aviso sale en formato de eventos (data: …) con acentos legibles")

    print("\nTodo bien.\n" if not fallas else f"\n{fallas} regla(s) fallaron.\n")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
