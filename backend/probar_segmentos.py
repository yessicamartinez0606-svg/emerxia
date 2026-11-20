"""Prueba las prácticas 08 (confiabilidad de los tipos de servicio) y 09 (PCA).

Uso (en la carpeta backend, con el entorno virtual activado):
    python probar_segmentos.py

No necesita MongoDB ni internet: solo prueba app/segmentacion.py.
"""
import sys

from app import segmentacion as s

OK, BAD = "  [OK]  ", "  [X]   "


def main() -> int:
    fallas = 0

    def revisar(cond, texto):
        nonlocal fallas
        print((OK if cond else BAD) + texto)
        fallas += 0 if cond else 1

    print("\nPráctica 08: confiabilidad")
    c = s.confiabilidad()
    revisar([i["inicializacion"] for i in c["inicializaciones"]] == ["k-means++", "random"], "Compara k-means++ y random")
    revisar([e["escalador"] for e in c["escaladores"]] == ["StandardScaler", "MinMaxScaler"], "Compara los dos escaladores")
    revisar(all(len(e["perfiles"]) == 3 for e in c["escaladores"]), "Cada escalador da los 3 perfiles")
    est = c["estabilidad"]
    revisar(len(est["pares"]) == 15 and len(est["matriz"]) == 6, "6 semillas → 15 comparaciones y matriz 6×6")
    revisar(all(est["matriz"][i][i] == 1.0 for i in range(6)), "La diagonal de la matriz ARI es 1")
    revisar(0.9 <= est["ari_promedio"] <= 1.0, f"Los tipos son estables (ARI promedio {est['ari_promedio']})")
    a = c["atipicos"]
    revisar(a["total"] == 25 and a["porcentaje"] == 5.0, "Percentil 95 → 5 % de servicios poco comunes")
    revisar(sum(a["por_perfil"].values()) == a["total"], "Los poco comunes se reparten entre los tipos")
    revisar(all(x["distancia"] > a["umbral"] for x in a["ejemplos"]), "Los ejemplos superan el umbral")

    print("\nPráctica 09: PCA")
    m = s.mapa_pca()
    acum = [v["acumulada"] for v in m["varianza"]]
    revisar(len(acum) == 4 and abs(acum[-1] - 1) < 1e-3, "4 componentes conservan el 100 %")
    revisar(acum == sorted(acum), "La varianza acumulada crece")
    revisar(m["componentes_necesarias"] == next(i + 1 for i, v in enumerate(acum) if v >= 0.85),
            f"Componentes para el 85 %: {m['componentes_necesarias']}")
    mse = [r["mse"] for r in m["reconstruccion"]]
    revisar(mse == sorted(mse, reverse=True) and mse[-1] < 1e-9, "El error de reconstrucción baja hasta 0")
    revisar(len(m["puntos"]) == 500 and len(m["centros"]) == 3, "500 servicios y 3 centros en el mapa")

    print("\nEmergencia nueva")
    normal = s.clasificar(12.5, 7.5, 25, 1)
    raro = s.clasificar(25, 0, 3, 6)
    revisar(normal["perfil"] == "Requiere apoyo" and not normal["poco_comun"], "Un servicio típico no se marca")
    revisar(raro["poco_comun"], "Lejos, sin tráfico y en 3 min: poco común")
    revisar({"pc1", "pc2"} <= set(normal), "Trae su lugar en el mapa (PC1, PC2)")

    print(f"\n{'Todo bien' if not fallas else f'{fallas} falla(s)'}")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
