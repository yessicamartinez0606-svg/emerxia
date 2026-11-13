"""Prueba las ambulancias con vehículos reales (app/vehiculos.py).

Uso (en la carpeta backend, con el entorno virtual activado):
    python probar_vehiculos.py            # con internet consulta la API vPIC de verdad
    python probar_vehiculos.py --sin-red  # simula la API (sin internet)

Usa la base de datos en memoria de probar_perfiles.py: no toca MongoDB.
"""
import sys

from app import repository, vehiculos
from app.routers import flota as flota_api
from probar_perfiles import BAD, OK, Base

# Respuesta con el formato real de GetModelsForMakeYear (vpic.nhtsa.dot.gov).
RESPUESTA = {
    "ford": ["Transit", "Transit Connect", "E-350", "F-150", "Ranger"],
    "mercedes-benz": ["Sprinter", "Metris", "GLE-Class"],
    "chevrolet": ["Express", "Silverado", "Tahoe"],
    "ram": ["ProMaster", "ProMaster City", "1500"],
}


def simular_api(marca, anio):
    return [{"Make_ID": 1, "Make_Name": marca.upper(), "Model_ID": 1000 + i, "Model_Name": m}
            for i, m in enumerate(RESPUESTA[marca])]


def main() -> int:
    fallas = 0

    def revisar(cond, texto):
        nonlocal fallas
        print((OK if cond else BAD) + texto)
        fallas += 0 if cond else 1

    real = "--sin-red" not in sys.argv
    if not real:
        vehiculos._pedir = simular_api
    vehiculos._archivo = lambda marca, anio: None        # sin copias en disco durante la prueba

    print("\nModelos de la API")
    r = vehiculos.modelos_ambulancia("Ford", 2022)
    print(f"        fuente: {r['fuente']} · {r['total_modelos_marca']} modelos de Ford en 2022")
    nombres = [m["modelo"] for m in r["modelos"]]
    revisar(any("Transit" in n for n in nombres) and not any("Connect" in n for n in nombres),
            "Ford 2022: aparece la Transit y no la Transit Connect (no sirve de ambulancia)")
    revisar(all(m["tanque_litros"] == 94.6 for m in r["modelos"]), "Cada modelo trae el tanque de su ficha técnica (94.6 L)")
    rr = vehiculos.modelos_ambulancia("RAM", 2021)
    revisar(rr["modelos"] and all("City" not in m["modelo"] for m in rr["modelos"]), "RAM: ProMaster sí, ProMaster City no")
    try:
        vehiculos.modelos_ambulancia("Tesla", 2022)
        revisar(False, "Una marca que no es chasis de ambulancia se rechaza")
    except ValueError:
        revisar(True, "Una marca que no es chasis de ambulancia se rechaza")

    print("\nFlota del sistema")
    db = Base()
    repository.get_db = lambda: db
    for f in ("list_rows", "insert_row", "update_row"):
        setattr(flota_api, f, getattr(repository, f))
    flota_api._ubicacion = lambda em: None
    for i, n in enumerate(["Mariana Torres", "Ricardo Paredes", "Elena Cruz", "Lucía Gómez", "Pablo Núñez"], 1):
        db["operators"].insert_one({"id": i, "nombre": n, "turno": "Matutino", "estado": "En línea"})
    db["ambulances"].insert_one({"id": 1, "placa": "AMB-101", "tipo": "Avanzada", "hospital": "Hospital IMSS 220",
                                 "conductor": "Mariana Torres", "estado": "Libre", "combustible_pct": 80, "kilometraje": 48210})
    db["counters"].insert_one({"_id": "ambulances", "seq": 1})

    res = flota_api.importar_flota_real("admin")
    print("        " + res["mensaje"])
    ambs = db["ambulances"].docs
    vieja = next(a for a in ambs if a["placa"] == "AMB-101")
    revisar(vieja.get("marca") and vieja["kilometraje"] == 48210 and vieja["conductor"] == "Mariana Torres",
            "La ambulancia que ya existía recibe marca y modelo reales y conserva su placa, kilometraje y conductor")
    from app.genetico import HOSPITALES
    por_h = {h["nombre"]: sum(1 for a in ambs if a["hospital"] == h["nombre"]) for h in HOSPITALES}
    revisar(all(por_h[h["nombre"]] >= h["ambulancias"] for h in HOSPITALES),
            f"Cada hospital tiene sus ambulancias ({len(ambs)} en total)")
    revisar(all(a.get("marca") in vehiculos.MARCAS and a.get("modelo") and a.get("anio") for a in ambs),
            "Todas tienen marca, modelo y año")
    revisar(len({a["placa"] for a in ambs}) == len(ambs), "No se repiten placas")
    con = [a for a in ambs if a.get("conductor")]
    revisar(len({a["conductor"] for a in con}) == len(con), "Cada operador maneja una sola ambulancia")
    revisar(all(a["kilometraje"] > 0 for a in ambs), "Kilometraje según los años de uso")
    res2 = flota_api.importar_flota_real("admin")
    revisar(not res2["creadas"] and res2["actualizadas"] == 0, "Si se vuelve a correr no duplica nada")
    ejemplo = next(a for a in ambs if a["placa"] != "AMB-101")
    print(f"        ejemplo: {ejemplo['placa']} · {ejemplo['marca']} {ejemplo['modelo']} {ejemplo['anio']} · "
          f"{ejemplo['motor']} · tanque {ejemplo['tanque_litros']} L · {ejemplo['hospital']} · {ejemplo['fuente_vehiculo']}")

    print("\n" + ("Todo bien." if not fallas else f"{fallas} prueba(s) fallaron."))
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
