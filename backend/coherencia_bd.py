"""Revisa (y si se pide, corrige) la coherencia de la base de MongoDB de Emergexia.

Toma la conexión de backend/.env (MONGO_URI y MONGO_DB), igual que la API.

    python coherencia_bd.py            # solo revisa y muestra lo que encontró (no cambia nada)
    python coherencia_bd.py --aplicar  # además aplica las correcciones seguras

Qué revisa:
  1. Colecciones: que existan todas las del sistema y las de las prácticas de IA,
     con su validación e índices (app/dbschema.py).
  2. Contadores: que el contador de id de cada colección no esté por debajo del id
     más alto (si lo está, la API repetiría ids al dar de alta).
  3. Ambulancias: estatus de la versión anterior ("Disponible", "Mantenimiento"...),
     hospitales que no existen en el sistema y ambulancias "Ocupada" cuya emergencia
     ya se cerró o no existe.
  4. Emergencias y paramédicos: hospitales y ambulancias que no existen.
  5. Prácticas de IA: folios de emergencia que no existen, atenciones sin expediente,
     y servicios de Big Data con hospitales que no son los del sistema.

Qué corrige con --aplicar (nunca borra documentos):
  - Crea colecciones e índices que falten y actualiza su validación.
  - Sube los contadores al id más alto.
  - Cambia los estatus anteriores por los actuales y pone el Hospital IMSS 220 a las
    ambulancias con un hospital que no existe.
  - Libera las ambulancias "Ocupada" cuya emergencia ya está cerrada o no existe.
El resto solo se reporta, porque requiere decidir caso por caso.
"""
import argparse
import sys

from app.dbschema import COLECCIONES_IA, DEFINITIONS, ensure_schema
from app.flota import ESTADOS, ESTADOS_ANTERIORES, HOSPITAL_BASE, NOMBRES_HOSPITALES
from app.mongo import connect, get_db, safe_uri

LOTE_BIGDATA = "EMERGEXIA-50000-V1"
COLECCIONES_CON_ID = ("users", "ambulances", "emergencies", "operators", "paramedics",
                      "cargas_combustible", "historial")

hallazgos: list[str] = []
correcciones: list[str] = []


def hallazgo(texto: str) -> None:
    hallazgos.append(texto)
    print(f"  [!] {texto}")


def bien(texto: str) -> None:
    print(f"  [OK] {texto}")


def corregido(texto: str) -> None:
    correcciones.append(texto)
    print(f"  [CORREGIDO] {texto}")


def titulo(texto: str) -> None:
    print(f"\n{texto}\n" + "-" * len(texto))


# ───────────────────────── 1. Colecciones ─────────────────────────

def revisar_colecciones(db, aplicar: bool) -> None:
    titulo("1. Colecciones")
    existentes = set(db.list_collection_names())
    faltan = [c for c in DEFINITIONS if c not in existentes]
    extra = sorted(c for c in existentes - set(DEFINITIONS) - {"password_resets"} if not c.startswith("system."))
    for nombre in DEFINITIONS:
        if nombre in existentes:
            origen = "prácticas de IA" if nombre in COLECCIONES_IA else "sistema"
            bien(f"{nombre} ({origen}): {db[nombre].estimated_document_count():,} documentos")
    if faltan:
        hallazgo(f"Faltan colecciones: {', '.join(faltan)}")
    if extra:
        hallazgo(f"Colecciones que el sistema no conoce (revísalas a mano): {', '.join(extra)}")
    if aplicar:
        creadas = ensure_schema()
        corregido("Validación e índices actualizados en todas las colecciones"
                  + (f"; creadas: {', '.join(creadas)}" if creadas else ""))


# ───────────────────────── 2. Contadores ─────────────────────────

def revisar_contadores(db, aplicar: bool) -> None:
    titulo("2. Contadores de id")
    for nombre in COLECCIONES_CON_ID:
        mayor = db[nombre].find_one({"id": {"$type": "number"}}, {"id": 1}, sort=[("id", -1)])
        if not mayor:
            continue
        maximo = int(mayor["id"])
        contador = (db["counters"].find_one({"_id": nombre}) or {}).get("seq", 0)
        if contador >= maximo:
            bien(f"{nombre}: contador {contador}, id más alto {maximo}")
            continue
        hallazgo(f"{nombre}: el contador va en {contador} pero ya existe el id {maximo}")
        if aplicar:
            db["counters"].update_one({"_id": nombre}, {"$max": {"seq": maximo}}, upsert=True)
            corregido(f"{nombre}: contador subido a {maximo}")


# ───────────────────────── 3. Ambulancias ─────────────────────────

def revisar_ambulancias(db, aplicar: bool) -> None:
    titulo("3. Ambulancias")
    emergencias = {e["folio"]: e.get("estado") for e in db["emergencies"].find({}, {"folio": 1, "estado": 1})}
    problemas = 0
    for amb in db["ambulances"].find({}, {"_id": 0}):
        placa = amb.get("placa", f"id {amb.get('id')}")
        cambios = {}

        estado = amb.get("estado")
        if estado in ESTADOS_ANTERIORES:
            hallazgo(f"{placa}: estatus anterior «{estado}»")
            cambios["estado"] = ESTADOS_ANTERIORES[estado]
        elif estado not in ESTADOS:
            hallazgo(f"{placa}: estatus desconocido «{estado}» (se deja igual, revísalo)")

        if amb.get("hospital") not in NOMBRES_HOSPITALES:
            hallazgo(f"{placa}: hospital «{amb.get('hospital')}» no existe en el sistema")
            cambios["hospital"] = HOSPITAL_BASE

        folio = amb.get("emergencia_actual")
        if cambios.get("estado", estado) == "Ocupada" and (not folio or emergencias.get(folio) in (None, "Cerrada")):
            motivo = "sin emergencia" if not folio else (
                f"la emergencia {folio} ya está cerrada" if emergencias.get(folio) == "Cerrada" else f"la emergencia {folio} no existe")
            hallazgo(f"{placa}: está «Ocupada» pero {motivo}")
            cambios.update({"estado": "Libre", "emergencia_actual": None})

        if cambios:
            problemas += 1
            if aplicar:
                db["ambulances"].update_one({"placa": amb.get("placa")} if amb.get("placa") else {"id": amb.get("id")},
                                            {"$set": cambios})
                corregido(f"{placa}: {', '.join(f'{k} → {v}' for k, v in cambios.items())}")
    if not problemas:
        bien("Estatus, hospitales y emergencias de las ambulancias coherentes")


# ─────────────────── 4. Emergencias y paramédicos ───────────────────

def revisar_referencias(db) -> None:
    titulo("4. Emergencias y paramédicos")
    placas = {a.get("placa") for a in db["ambulances"].find({}, {"placa": 1})}
    problemas = 0
    for em in db["emergencies"].find({}, {"_id": 0, "folio": 1, "hospital_salida": 1, "hospital_destino": 1,
                                          "ambulancia": 1, "ambulancias": 1}):
        for campo in ("hospital_salida", "hospital_destino"):
            if em.get(campo) and em[campo] not in NOMBRES_HOSPITALES:
                problemas += 1
                hallazgo(f"Emergencia {em.get('folio')}: {campo} «{em[campo]}» no existe en el sistema")
        asignadas = set(em.get("ambulancias") or []) | ({em["ambulancia"]} if em.get("ambulancia") else set())
        for placa in sorted(p for p in asignadas if isinstance(p, str) and p not in placas):
            problemas += 1
            hallazgo(f"Emergencia {em.get('folio')}: la ambulancia {placa} ya no existe")
    for pm in db["paramedics"].find({"ambulancia": {"$nin": [None, ""]}}, {"_id": 0, "nombre": 1, "ambulancia": 1}):
        if pm["ambulancia"] not in placas:
            problemas += 1
            hallazgo(f"Paramédico {pm.get('nombre')}: la ambulancia {pm['ambulancia']} no existe")
    if not problemas:
        bien("Hospitales y ambulancias referidas existen")


# ───────────────────────── 5. Prácticas de IA ─────────────────────────

def revisar_ia(db) -> None:
    titulo("5. Colecciones de las prácticas de IA")
    folios = {e["folio"] for e in db["emergencies"].find({}, {"folio": 1})}

    for nombre in ("analisis_emergencias_ia", "atenciones_ia"):
        huerfanos = sorted({d["folio_emergencia"] for d in db[nombre].find(
            {"folio_emergencia": {"$nin": [None, ""]}}, {"folio_emergencia": 1})} - folios)
        if huerfanos:
            muestra = ", ".join(huerfanos[:8]) + (" …" if len(huerfanos) > 8 else "")
            hallazgo(f"{nombre}: {len(huerfanos)} folio(s) que no existen en emergencias ({muestra})")
        else:
            bien(f"{nombre}: todos los folios existen en emergencias")

    otros = db["analisis_emergencias_ia"].count_documents({"sistema": {"$ne": "Emergexia"}})
    if otros:
        hallazgo(f"analisis_emergencias_ia: {otros} documento(s) que no son de Emergexia (¿de SmartAcademy?)")

    expedientes = set(db["pacientes_ia"].distinct("id_paciente"))
    sin_expediente = set(db["atenciones_ia"].distinct("id_paciente")) - expedientes
    if sin_expediente:
        hallazgo(f"atenciones_ia: {len(sin_expediente)} paciente(s) sin expediente en pacientes_ia")
    elif expedientes:
        bien("atenciones_ia: todas las atenciones tienen expediente")

    servicios = db["servicios_ambulancia_masivos"]
    if not servicios.estimated_document_count():
        bien("servicios_ambulancia_masivos vacía (se llena con p20 → p21 → p22)")
        return
    lotes = servicios.distinct("id_lote")
    if lotes != [LOTE_BIGDATA]:
        hallazgo(f"servicios_ambulancia_masivos: lotes {lotes} (se espera solo {LOTE_BIGDATA})")
    ajenos = sorted(set(servicios.distinct("hospital_base")) - set(NOMBRES_HOSPITALES))
    if ajenos:
        hallazgo("servicios_ambulancia_masivos: hospitales que no son del sistema: " + ", ".join(ajenos)
                 + ". Vuelve a correr p20, p21 y p22 en backend/ia_bigdata: p22 reemplaza los 50,000 registros.")
    else:
        bien("servicios_ambulancia_masivos: hospitales iguales a los del sistema")


# ───────────────────────── Programa ─────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Revisa la coherencia de la base de Emergexia.")
    parser.add_argument("--aplicar", action="store_true", help="aplica las correcciones seguras")
    aplicar = parser.parse_args().aplicar

    print("=" * 64)
    print("EMERGEXIA · coherencia de la base de datos" + ("  (APLICANDO CORRECCIONES)" if aplicar else "  (solo revisión)"))
    print("=" * 64)
    try:
        connect()
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo conectar a MongoDB ({safe_uri()}): {exc}")
        return 2
    db = get_db()
    print(f"Base: {db.name}  ·  {safe_uri()}")

    revisar_colecciones(db, aplicar)
    revisar_contadores(db, aplicar)
    revisar_ambulancias(db, aplicar)
    revisar_referencias(db)
    revisar_ia(db)

    print("\n" + "=" * 64)
    print(f"Hallazgos: {len(hallazgos)}  ·  Correcciones aplicadas: {len(correcciones)}")
    if hallazgos and not aplicar:
        print("Para aplicar las correcciones seguras: python coherencia_bd.py --aplicar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
