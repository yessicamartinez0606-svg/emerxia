"""Prueba la búsqueda ciega de rutas con tráfico (sin abrir el sitio web ni MongoDB).

Uso (en la carpeta backend, con el entorno virtual activado):
    python probar_busqueda.py
    python probar_busqueda.py S1 IMSS          # otro origen y destino

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
    inicial, meta = (sys.argv[1], sys.argv[2]) if len(sys.argv) == 3 else ("BASE", "IMSS")
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
    revisar(all("c16" not in r["calles"] for r in res.values()), "Ninguna ruta pasa por la calle cerrada (Nezahualcóyotl)")

    # Una calle cerrada no genera sucesor: de Morelos no se puede bajar al hospital por Nezahualcóyotl.
    normal = busqueda.EspacioEstados("M3", "IMSS")
    revisar("IMSS" not in [s for s, _, _ in normal.sucesores("M3")], "La calle cerrada no es un operador válido")

    # Si se cierran todas las calles que llegan al hospital, no debe haber ruta.
    aislado = busqueda.resolver("BASE", "IMSS", {"c06": "bloqueado", "c17": "bloqueado"})
    revisar(not any(r["encontrado"] for r in aislado["resultados"]), "Sin calles abiertas al destino, no hay ruta")

    # Si se reabre Nezahualcóyotl, vuelve a ser un operador válido.
    libre = busqueda.EspacioEstados("M3", "IMSS", {"c16": "libre"})
    revisar("IMSS" in [s for s, _, _ in libre.sucesores("M3")], "Al reabrir Nezahualcóyotl, se puede avanzar de Morelos al hospital")

    print("\nTodo bien.\n" if not fallas else f"\n{fallas} regla(s) fallaron.\n")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
