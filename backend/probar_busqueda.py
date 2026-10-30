"""Prueba la búsqueda ciega de la ruta de la ambulancia.

Uso (en la carpeta backend, con el entorno virtual activado):
    python probar_busqueda.py              # sin internet: calles de ejemplo
    python probar_busqueda.py --en-vivo    # calles reales de Toluca (necesita internet)
    python probar_busqueda.py --en-vivo "Av. Independencia 100, Centro"

Sin --en-vivo se usa una cuadrícula de calles de ejemplo con el mismo formato que devuelve
OpenStreetMap, y se revisan unas reglas que siempre deben cumplirse. Con --en-vivo se
descargan las calles reales y se calcula la ruta del Hospital IMSS 220 a una dirección.
"""
import sys

from app import busqueda, red_vial

OK, BAD = "  [OK]  ", "  [X]   "


def calles_de_ejemplo():
    """Cuadrícula de 6 x 5 esquinas alrededor del IMSS 220, en formato de Overpass.

    - La fila 2 es Paseo Tollocan (vía rápida, con mucho tráfico en hora pico).
    - La columna 3 es de un solo sentido hacia el norte.
    - Entre esquinas hay nodos intermedios que solo dan forma a la calle.
    """
    lat0, lng0, paso = 19.2770, -99.6480, 0.0030
    elementos, nid = [], 1
    pos = {}

    def nodo(lat, lng):
        nonlocal nid
        elementos.append({"type": "node", "id": nid, "lat": lat, "lon": lng})
        pos[nid] = (lat, lng)
        nid += 1
        return nid - 1

    esquina = {(f, c): nodo(lat0 + f * paso, lng0 + c * paso) for f in range(5) for c in range(6)}
    wid = 1000

    def via(ids, **tags):
        nonlocal wid
        elementos.append({"type": "way", "id": wid, "nodes": ids, "tags": tags})
        wid += 1

    def con_intermedios(seq):
        out = [seq[0]]
        for a, b in zip(seq, seq[1:]):
            (la, lo), (lb, lob) = pos[a], pos[b]
            out += [nodo((la + lb) / 2, (lo + lob) / 2), b]
        return out

    for f in range(5):
        tags = {"highway": "trunk", "name": "Paseo Tollocan"} if f == 2 else {"highway": "residential", "name": f"Calle Oriente {f}"}
        via(con_intermedios([esquina[(f, c)] for c in range(6)]), **tags)
    for c in range(6):
        tags = {"highway": "secondary", "name": f"Av. Norte {c}"}
        if c == 3:
            tags["oneway"] = "yes"                     # de sur (fila 0) a norte (fila 4)
        via(con_intermedios([esquina[(f, c)] for f in range(5)]), **tags)
    # Pasillo de estacionamiento: no se debe usar.
    p = nodo(lat0 + 2.5 * paso, lng0 + 2.5 * paso)
    via([esquina[(2, 2)], p, esquina[(3, 3)]], highway="service", service="parking_aisle")
    return {"elements": elementos}, esquina, pos


def main() -> int:
    if "--en-vivo" in sys.argv:
        return en_vivo()

    fallas = 0

    def revisar(cond: bool, texto: str) -> None:
        nonlocal fallas
        print((OK if cond else BAD) + texto)
        fallas += 0 if cond else 1

    datos, esquina, pos = calles_de_ejemplo()
    red_vial.overpass = lambda consulta: datos           # sin internet
    grafo = red_vial.construir_grafo(datos)

    print("\nGrafo de esquinas")
    revisar(len(grafo.coords) == 30, f"30 esquinas (hay {len(grafo.coords)}); los nodos intermedios no son estados")
    revisar(grafo.nombre_esquina(esquina[(2, 3)]) == "Av. Norte 3 y Paseo Tollocan", "Cada esquina se nombra con sus calles")
    sube = {t.b for t in grafo.salidas[esquina[(1, 3)]]}
    revisar(esquina[(2, 3)] in sube and esquina[(0, 3)] not in sube, "Av. Norte 3 solo se recorre hacia el norte")
    revisar(all(t.highway != "service" for t in grafo.tramos), "El estacionamiento no forma parte de la red")

    o, d = pos[esquina[(0, 0)]], pos[esquina[(2, 5)]]
    origen, destino = {"lat": o[0], "lng": o[1]}, {"lat": d[0], "lng": d[1]}

    rutas = {}
    for hora, etiqueta in ((8, "hora pico"), (23, "noche")):
        sol = red_vial.calcular_ruta(origen, destino, hora)
        res = {r["algoritmo"]: r for r in sol["resultados"]}
        a, p, u = res["anchura"], res["profundidad"], res["costo_uniforme"]
        g, ae = res["greedy"], res["a_estrella"]
        print(f"\nDe la esquina 0,0 a la 2,5 en {etiqueta} ({sol['periodo_nombre']})")
        for r in sol["resultados"]:
            print(f"    {r['nombre']:<24} {r['minutos']:>5} min  {r['km']:>5} km  {r['num_tramos']:>2} tramos  {r['expandidos']:>3} esquinas revisadas")
        revisar(all(r["encontrado"] for r in res.values()), "Los cinco algoritmos encuentran ruta")
        revisar(a["num_tramos"] <= min(p["num_tramos"], u["num_tramos"]), "Anchura usa la menor cantidad de tramos")
        revisar(u["minutos"] <= min(a["minutos"], p["minutos"]) + 1e-9, "Costo uniforme encuentra la ruta más rápida")
        revisar(abs(ae["minutos"] - u["minutos"]) < 1e-9, "A* encuentra la misma ruta más rápida que costo uniforme")
        revisar(ae["expandidos"] <= u["expandidos"], "A* revisa igual o menos esquinas que costo uniforme")
        revisar(g["minutos"] >= u["minutos"] - 1e-9, "Greedy no mejora a costo uniforme (no garantiza la más rápida)")
        revisar(u["coords"][0] == [round(o[0], 6), round(o[1], 6)], "La ruta empieza en el punto de salida")
        rutas[hora] = u
    revisar(rutas[23]["minutos"] < rutas[8]["minutos"], "De noche la ruta tarda menos que en hora pico")
    print("\n    Indicaciones (costo uniforme, hora pico):")
    for i, ind in enumerate(rutas[8]["indicaciones"], 1):
        print(f"      {i}. {ind['texto']} · {ind['km']} km · {ind['minutos']} min")
    revisar(rutas[8]["indicaciones"][0]["texto"].startswith("Sal por"), "Las indicaciones empiezan con «Sal por…»")

    # Calles cerradas: si se cierran todas las que llegan al destino, no hay ruta.
    meta = esquina[(2, 5)]
    llegan = {t.way_id for t in grafo.tramos if t.b == meta}
    prob = red_vial.problema(grafo, esquina[(0, 0)], meta, 12, cerradas=llegan)
    revisar(not busqueda.buscar(prob, "costo_uniforme")["encontrado"], "Con las calles de llegada cerradas, no hay ruta")

    # Heurística admisible: h(n) nunca supera el tiempo real que falta (costo uniforme
    # desde cada esquina hasta la meta), a ninguna hora.
    print("\nHeurística")
    for hora in (8, 12, 23):
        h, vmax = red_vial.heuristica_trafico(grafo, meta, hora)
        admisible = True
        for e in grafo.coords:
            r = busqueda.buscar(red_vial.problema(grafo, e, meta, hora), "costo_uniforme")
            if r["encontrado"] and h(e) > r["minutos"] + 0.005:   # r["minutos"] viene redondeado a 2 decimales
                admisible = False
        revisar(admisible, f"A las {hora}:00 h(n) nunca sobreestima (velocidad máxima con tráfico: {vmax:.0f} km/h)")

    print("\nTodo bien.\n" if not fallas else f"\n{fallas} regla(s) fallaron.\n")
    return 1 if fallas else 0


def en_vivo() -> int:
    args = [a for a in sys.argv[1:] if a != "--en-vivo"]
    direccion = args[0] if args else "Av. Independencia, Centro, Toluca"
    print(f"\nBuscando «{direccion}»…")
    lugar = red_vial.geocodificar(direccion)
    print(f"  {lugar['texto']}  ({lugar['lat']:.5f}, {lugar['lng']:.5f})")
    print("Descargando calles de OpenStreetMap (la primera vez tarda unos segundos)…")
    h = red_vial.HOSPITAL
    sol = red_vial.calcular_ruta({"lat": h["lat"], "lng": h["lng"]}, lugar)
    print(f"\nDel {h['corto']} a la emergencia · {sol['periodo_nombre']} ({sol['hora']} h) · {sol['esquinas']} esquinas en el mapa")
    for r in sol["resultados"]:
        if r["encontrado"]:
            print(f"  {r['nombre']:<24} {r['minutos']:>5} min  {r['km']:>5} km  {r['expandidos']:>5} esquinas revisadas")
        else:
            print(f"  {r['nombre']:<24} sin ruta")
    mejor = next(r for r in sol["resultados"] if r["algoritmo"] == sol["mas_rapido"])
    print("\nIndicaciones:")
    for i, ind in enumerate(mejor["indicaciones"], 1):
        print(f"  {i}. {ind['texto']} · {ind['km']} km · {ind['minutos']} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
