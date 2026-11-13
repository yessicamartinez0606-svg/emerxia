"""Prueba la flota: estatus, gasolina, varias ambulancias de varios hospitales e historial.

Uso (en la carpeta backend, con el entorno virtual activado):
    python probar_flota.py

No necesita MongoDB ni internet: usa una base de datos de ejemplo en memoria con la misma
forma que las colecciones reales, y llama directo a las funciones de la API.
"""
import sys
from copy import deepcopy

from fastapi import HTTPException

from app import flota
from app.routers import flota as api

OK, BAD = "  [OK]  ", "  [X]   "


class BaseEnMemoria:
    def __init__(self, datos: dict[str, list[dict]]):
        self.datos = {k: [dict(r) for r in v] for k, v in datos.items()}

    def list_rows(self, nombre):
        return deepcopy(sorted(self.datos.setdefault(nombre, []), key=lambda r: r.get("id", 0)))

    def insert_row(self, nombre, data):
        filas = self.datos.setdefault(nombre, [])
        doc = {"id": max((r["id"] for r in filas), default=0) + 1, **data, "created_at": flota.ahora()}
        if nombre == "emergencies":
            doc["folio"] = f"EMG-{doc['id']:04d}"
        filas.append(doc)
        return dict(doc)

    def update_row(self, nombre, row_id, cambios):
        for r in self.datos.get(nombre, []):
            if r["id"] == row_id:
                r.update(cambios)
                return dict(r)
        return None


def ejemplo() -> BaseEnMemoria:
    amb = lambda i, placa, hosp, cond, estado="Libre", pct=80, tipo="Avanzada": {  # noqa: E731
        "id": i, "placa": placa, "tipo": tipo, "hospital": hosp, "conductor": cond, "estado": estado,
        "tanque_litros": 80, "rendimiento_km_l": 6, "combustible_pct": pct, "kilometraje": 10000}
    return BaseEnMemoria({
        "ambulances": [
            amb(1, "AMB-101", "Hospital IMSS 220", "Mariana Torres"),
            amb(2, "AMB-102", "Hospital IMSS 220", "Ricardo Paredes", tipo="Básica"),
            amb(3, "AMB-103", "Hospital IMSS 220", "Daniela Ibarra"),
            amb(4, "AMB-104", "Hospital IMSS 220", "Jorge Salinas", estado="En reparación"),
            amb(5, "CRT-201", "Cruz Roja Toluca", "Elena Cruz"),
            amb(6, "CRT-202", "Cruz Roja Toluca", "Pablo Núñez", pct=15),
            amb(7, "NSJ-301", "Hospital General Nicolás San Juan", "Marcos Herrera"),
            amb(8, "MET-401", "Hospital IMSS 251", "Lucía Gómez"),
            {"id": 9, "placa": "VIEJA-1", "tipo": "Básica", "conductor": "", "estado": "Disponible"},   # versión anterior
        ],
        "operators": [{"id": i, "nombre": n, "turno": "Matutino", "estado": "En línea", "celular": "7220000000"}
                      for i, n in enumerate(["Mariana Torres", "Ricardo Paredes", "Daniela Ibarra", "Jorge Salinas",
                                             "Elena Cruz", "Pablo Núñez", "Marcos Herrera", "Lucía Gómez", "Ana Ruiz"], 1)],
        "emergencies": [{"id": 1, "folio": "EMG-0001", "paciente_nombre": "Juan Pérez", "direccion": "Av. Independencia 300, Toluca",
                         "descripcion": "Choque múltiple", "prioridad": "Alta", "estado": "Pendiente", "ambulancias_requeridas": 5,
                         "operador": "Mariana Torres"}],
        "historial": [], "cargas_combustible": [], "verificaciones": [],
    })


def main() -> int:
    fallas = 0

    def revisar(cond: bool, texto: str) -> None:
        nonlocal fallas
        print((OK if cond else BAD) + texto)
        fallas += 0 if cond else 1

    def error(fn, *a, **k) -> str:
        try:
            fn(*a, **k)
        except (HTTPException, ValueError) as exc:
            return getattr(exc, "detail", None) or str(exc)
        return ""

    db = ejemplo()
    api.list_rows, api.insert_row, api.update_row = db.list_rows, db.insert_row, db.update_row
    toluca_centro = {"lat": 19.2925, "lng": -99.6569}
    api._ubicacion = lambda em: toluca_centro          # sin internet

    print("\nEstatus y hospitales")
    vieja = flota.normalizar(db.list_rows("ambulances")[-1])
    revisar(vieja["estado"] == "Libre" and vieja["hospital"] == "Hospital IMSS 220",
            "Una ambulancia de la versión anterior (Disponible, sin hospital) queda Libre en el IMSS 220")
    hs = {h["nombre"]: h for h in api.hospitales()["hospitales"]}
    revisar(len(hs["Hospital IMSS 220"]["ambulancias"]) == 5, "El IMSS 220 tiene 5 ambulancias registradas")
    revisar(hs["Hospital IMSS 220"]["conteo"]["En reparación"] == 1, "Se cuentan las que están en reparación")
    revisar(hs["Cruz Roja Toluca"]["listas"] == 1, "CRT-202 no cuenta como lista: tiene 15 % de gasolina")

    print("\nMás de tres ambulancias")
    plan = api.asignar(1, api.AsignarIn(), "admin")["plan"]
    print("    " + plan["resumen"])
    base = plan["por_hospital"][0]
    revisar(base["hospital"] == "Hospital IMSS 220" and len(base["aporta"]) == 3,
            "Primero salen las 3 listas del IMSS 220 (AMB-104 en reparación, VIEJA-1 sin conductor)")
    revisar(plan["usa_otros_hospitales"] and len(plan["elegidas"]) == 5, "Las otras 2 se piden a otros hospitales")
    revisar(plan["por_hospital"][1]["hospital"] == "Cruz Roja Toluca", "El segundo hospital es el más cercano a la emergencia")
    revisar("CRT-202" not in [a["placa"] for a in plan["elegidas"]], "No se manda una ambulancia con gasolina baja")
    revisar(db.list_rows("ambulances")[0]["estado"] == "Libre", "Sin confirmar, no se cambia nada")

    r = api.asignar(1, api.AsignarIn(confirmar=True), "admin")
    ocupadas = [a["placa"] for a in db.list_rows("ambulances") if a["estado"] == "Ocupada"]
    revisar(len(r["asignadas"]) == 5 and len(ocupadas) == 5, "Al confirmar, las 5 quedan Ocupadas y ligadas a la emergencia")
    em = db.list_rows("emergencies")[0]
    revisar(em["estado"] == "Asignada" and em["ambulancia"].count(",") == 4, "La emergencia queda Asignada con sus 5 placas")
    revisar(len([h for h in db.list_rows("historial") if h["tipo"] == "asignacion"]) == 5, "Cada asignación queda en el historial")
    msg = error(api.cambiar_ambulancia, 1, api.AmbulanciaPatch(estado="En reparación"), "admin")
    revisar("EMG-0001" in msg, "No se puede mandar a reparación una ambulancia que está en una emergencia")

    print("\nSalida, cierre y gasolina")
    api.evento(1, api.EventoEmergenciaIn(tipo="salida"), "admin")
    api.evento(1, api.EventoEmergenciaIn(tipo="llegada"), "admin")
    api.evento(1, api.EventoEmergenciaIn(tipo="traslado", hospital_destino="Hospital IMSS 220"), "admin")
    rep = api.evento(1, api.EventoEmergenciaIn(tipo="cierre", km_recorridos=12, observaciones="3 lesionados, 1 grave"), "admin")
    a1 = db.list_rows("ambulances")[0]
    revisar(a1["estado"] == "Libre" and a1["emergencia_actual"] is None, "Al cerrar, las ambulancias regresan Libres")
    revisar(a1["combustible_pct"] == 77.5 and a1["kilometraje"] == 10012, "12 km con 6 km/L gastan 2 L: 80 % → 77.5 %")
    revisar(rep["emergencia"]["estado"] == "Cerrada" and rep["emergencia"]["litros_consumidos"] == 10,
            "El reporte muestra la emergencia cerrada y 10 L gastados entre las 5")
    revisar(all(a["conductor_info"] for a in rep["ambulancias"]), "El reporte trae al conductor de cada ambulancia")
    tipos = [f["tipo"] for f in rep["linea_tiempo"]]
    revisar(tipos.index("asignacion") < tipos.index("salida") < tipos.index("llegada") < tipos.index("traslado") < tipos.index("liberacion"),
            "La línea de tiempo va en orden: asignación, salida, llegada, traslado, regreso")

    print("\nCargas de gasolina por el conductor")
    msg = error(api.cargar_combustible, 6, api.CargaCombustibleIn(operador="Ana Ruiz", litros=20), "admin")
    revisar("Pablo Núñez" in msg, "Solo el conductor de la ambulancia puede registrar su gasolina")
    msg = error(api.cargar_combustible, 6, api.CargaCombustibleIn(operador="Pablo Núñez", litros=90), "admin")
    revisar("No caben" in msg, "No se aceptan más litros de los que caben en el tanque")
    ficha = api.cargar_combustible(6, api.CargaCombustibleIn(operador="Pablo Núñez", litros=40, costo=980, kilometraje=10050,
                                                             verificado_facial=True), "admin")
    revisar(ficha["ambulancia"]["combustible_pct"] == 65 and not ficha["ambulancia"]["combustible_bajo"],
            "40 L en un tanque de 80 L: 15 % → 65 %, ya puede salir")
    revisar(ficha["cargas"][0]["verificado_facial"] and ficha["gasto_total"] == 980, "La carga queda registrada con su costo y Face ID")
    msg = error(api.cargar_combustible, 6, api.CargaCombustibleIn(operador="Pablo Núñez", litros=5, kilometraje=9000), "admin")
    revisar("kilometraje" in msg, "El kilometraje no puede ir hacia atrás")

    print("\nConductores")
    msg = error(api.cambiar_ambulancia, 2, api.AmbulanciaPatch(conductor="Elena Cruz"), "admin")
    revisar("CRT-201" in msg, "Un operador no puede conducir dos ambulancias")
    api.cambiar_ambulancia(9, api.AmbulanciaPatch(conductor="Ana Ruiz", estado="En reparación", motivo="Frenos"), "admin")
    h = api.historial(ambulancia="VIEJA-1", limite=50)["items"]
    revisar({x["tipo"] for x in h} == {"estado", "conductor"} and "Frenos" in " ".join(x["detalle"] for x in h),
            "Cambiar estatus y conductor queda en el historial con el motivo")

    print("\nTodo bien.\n" if not fallas else f"\n{fallas} regla(s) fallaron.\n")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
