"""Prueba la búsqueda ciega de rutas con tráfico (sin abrir el sitio web ni MongoDB).

Uso (en la carpeta backend, con el entorno virtual activado):
    python probar_busqueda.py
    python probar_busqueda.py BASE HN          # otro origen y destino

Imprime, para cada algoritmo, la ruta encontrada, los minutos estimados y cuántos estados
expandió. Al final revisa unas reglas que siempre deben cumplirse.
"""
import sys

from app import busqueda

OK, BAD = "  [OK]  ", "  [X]   "


def mostrar(r: dict) -> None:
    print(f"\n{r['nombre']}")
    if not r["encontrado"]:
        print("    No hay ruta: el destino quedó aislado por el tráfico.")
        return
    print("    Ruta:      " + " → ".join(r["ruta"]))
    print(f"    Calles:    {r['num_calles']}   Distancia: {r['distancia_km']} km   Tiempo: {r['minutos']} min")
    print(f"    Expandidos: {r['expandidos']}   Generados: {r['generados']}   Frontera máx.: {r['frontera_max']}")


def main() -> int:
    inicial, meta = (sys.argv[1], sys.argv[2]) if len(sys.argv) == 3 else ("BASE", "HS")
    nombres = {n.id: n.nombre for n in busqueda.NODOS}
    print(f"\nDe {nombres[inicial]} ({inicial}) a {nombres[meta]} ({meta}), tráfico por defecto")
    sol = busqueda.resolver(inicial, meta)
    for r in sol["resultados"]:
        mostrar(r)

    fallas = 0

    def revisar(cond: bool, texto: str) -> None:
        nonlocal fallas
        print((OK if cond else BAD) + texto)
        fallas += 0 if cond else 1

    print("\nReglas:")
    res = {r["algoritmo"]: r for r in sol["resultados"]}
    a, p, u = res["anchura"], res["profundidad"], res["costo_uniforme"]
    revisar(all(r["encontrado"] for r in res.values()), "Los tres algoritmos encuentran ruta")
    revisar(a["num_calles"] <= min(p["num_calles"], u["num_calles"]), "Anchura usa la menor cantidad de calles")
    revisar(u["minutos"] <= min(a["minutos"], p["minutos"]), "Costo uniforme encuentra la ruta más rápida")
    revisar(all("c07" not in r["calles"] for r in res.values()), "Ninguna ruta pasa por la calle bloqueada (Reforma)")

    # Sentido de las calles: R5 → HS es de un solo sentido, así que de HS no se puede subir a R5.
    inverso = busqueda.EspacioEstados("HS", "BASE")
    revisar("R5" not in [s for s, _, _ in inverso.sucesores("HS")], "Se respeta el sentido de Bucareli (solo hacia el sur)")

    # Si se bloquean todas las calles que llegan al hospital, no debe haber ruta.
    aislado = busqueda.resolver("BASE", "HS", {"c12": "bloqueado", "c22": "bloqueado"})
    revisar(not any(r["encontrado"] for r in aislado["resultados"]), "Sin calles abiertas al destino, no hay ruta")

    # Si se libera la marcha, Reforma vuelve a ser un operador válido.
    libre = busqueda.EspacioEstados("R3", "R4", {"c07": "libre"})
    revisar("R4" in [s for s, _, _ in libre.sucesores("R3")], "Al liberar Reforma, se puede avanzar de R3 a R4")

    print("\nTodo bien.\n" if not fallas else f"\n{fallas} regla(s) fallaron.\n")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
