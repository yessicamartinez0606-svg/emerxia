"""Prueba la asignación automática de ambulancias al registrar una emergencia.

Uso (en la carpeta backend, con el entorno virtual activado):
    python probar_asignacion_automatica.py

No necesita MongoDB ni internet: usa la base de datos en memoria de probar_perfiles.py.
"""
import sys

from app import repository
from app.routers import flota as flota_api, modules, portal
from app.schemas import EmergencyIn, EventoEmergenciaIn, ReporteUsuarioIn
from probar_perfiles import BAD, OK, Base


def main() -> int:
    fallas = 0

    def revisar(cond, texto):
        nonlocal fallas
        print((OK if cond else BAD) + texto)
        fallas += 0 if cond else 1

    db = Base()
    repository.get_db = lambda: db
    for m in (portal, flota_api, modules):
        for f in ("list_rows", "insert_row", "update_row"):
            if hasattr(m, f):
                setattr(m, f, getattr(repository, f))
    flota_api._ubicacion = lambda em: None

    ops = ["Mariana Torres", "Ricardo Paredes", "Elena Cruz", "Pablo Núñez"]
    for i, n in enumerate(ops, 1):
        db["operators"].insert_one({"id": i, "nombre": n, "turno": "Matutino", "estado": "En línea"})
    flota = [("AMB-101", "Hospital IMSS 220", "Mariana Torres", 80), ("AMB-102", "Hospital IMSS 220", "Ricardo Paredes", 70),
             ("CRT-201", "Cruz Roja Toluca", "Elena Cruz", 90), ("CRT-202", "Cruz Roja Toluca", "Pablo Núñez", 10)]
    for i, (placa, hosp, cond, gas) in enumerate(flota, 1):
        db["ambulances"].insert_one({"id": i, "placa": placa, "tipo": "Avanzada", "hospital": hosp, "conductor": cond,
                                     "estado": "Libre", "tanque_litros": 80, "rendimiento_km_l": 6,
                                     "combustible_pct": gas, "kilometraje": 1000})
    db["counters"].insert_one({"_id": "ambulances", "seq": 4})
    db["counters"].insert_one({"_id": "operators", "seq": 4})

    crear = next(r for r in modules.routers if r.prefix == "/api/emergencias").routes
    crear = next(r.endpoint for r in crear if "POST" in r.methods)

    def emergencia(**k):
        datos = {"paciente_nombre": "Paciente", "direccion": "Av. Hidalgo 1, Toluca", "descripcion": "Caída", **k}
        return crear(EmergencyIn(**datos))

    def amb(placa):
        return next(a for a in db["ambulances"].docs if a["placa"] == placa)

    def em(eid):
        return next(e for e in db["emergencies"].docs if e["id"] == eid)

    print("\nAl guardar una emergencia")
    e1 = emergencia()
    revisar(e1["asignacion"]["asignadas"] == ["AMB-101"], "Se le asigna sola una ambulancia del IMSS 220")
    revisar(em(e1["id"])["estado"] == "Asignada" and em(e1["id"])["operador"] == "Mariana Torres",
            "Queda Asignada y su operador es quien maneja la ambulancia")
    revisar(amb("AMB-101")["estado"] == "Ocupada", "La ambulancia queda Ocupada")

    e2 = emergencia(ambulancias_requeridas=2, prioridad="Alta")
    revisar(e2["asignacion"]["asignadas"] == ["AMB-102", "CRT-201"] and e2["asignacion"]["usa_otros_hospitales"],
            "Si no alcanzan las del IMSS 220, pide las de otro hospital")
    revisar(amb("CRT-202")["estado"] == "Libre", "No manda una ambulancia sin gasolina suficiente")

    e3 = emergencia(prioridad="Baja")
    e4 = emergencia(prioridad="Alta")
    revisar(e3["asignacion"]["faltan"] == 1 and "en espera" in e3["asignacion"]["mensaje"],
            "Sin ambulancias libres, la emergencia queda en espera")
    revisar(em(e3["id"])["estado"] == "Pendiente", "…y sigue Pendiente")
    avisos = [h for h in db["historial"].docs if h["tipo"] == "aviso" and "no hay ambulancias" in h["detalle"]]
    revisar(len(avisos) == 2, "Queda un aviso en el historial por cada emergencia en espera")

    print("\nCuando se libera una ambulancia")
    flota_api.evento(e1["id"], EventoEmergenciaIn(tipo="cierre", km_recorridos=4), "admin")
    revisar(em(e4["id"])["ambulancias"] == ["AMB-101"], "Al cerrar una emergencia, su ambulancia va sola a la de prioridad Alta")
    revisar(not em(e3["id"]).get("ambulancias"), "La de prioridad Baja sigue esperando")

    flota_api.cargar_combustible(4, flota_api.CargaCombustibleIn(operador="Pablo Núñez", litros=40), "admin")
    revisar(em(e3["id"])["ambulancias"] == ["CRT-202"], "Al cargar gasolina, la ambulancia se asigna sola a la que esperaba")

    print("\nReportada por un usuario")
    flota_api.evento(e2["id"], EventoEmergenciaIn(tipo="cierre", km_recorridos=6), "admin")
    r = portal.reportar(ReporteUsuarioIn(tipo="Accidente", descripcion="Choque", direccion="Paseo Tollocan 620, Toluca",
                                         canal="mensaje", personas=1), {"username": "ana", "full_name": "Ana", "telefono": ""})
    nueva = max(db["emergencies"].docs, key=lambda e: e["id"])
    revisar(nueva.get("ambulancias") and nueva["estado"] == "Asignada", "El reporte de un usuario también sale solo")
    revisar(r["estado"] == "Asignada", "…y el usuario ve que ya tiene ambulancia")

    print("\nReintentar a mano")
    e5 = emergencia(ambulancias_requeridas=3)
    faltaban = e5["asignacion"]["faltan"]
    r = flota_api.reintentar_asignacion(e5["id"], "admin")
    revisar(r["automatica"] and r["faltan"] <= faltaban, "El botón de reintentar vuelve a buscar sin error")

    print("\n" + ("Todo bien." if not fallas else f"{fallas} prueba(s) fallaron."))
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
