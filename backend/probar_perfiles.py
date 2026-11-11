"""Prueba los perfiles: Operador con Face ID, Usuario que reporta emergencias y permisos.

Uso (en la carpeta backend, con el entorno virtual activado):
    python probar_perfiles.py

No necesita MongoDB ni internet: usa una base de datos de ejemplo en memoria y llama
directo a las funciones de la API.
"""
import sys
from copy import deepcopy

from fastapi import HTTPException

from app import repository, security
from app.routers import auth, flota as flota_api, portal
from app.schemas import (AmbulanciaPatch, CargaOperadorIn, EventoEmergenciaIn, LoginIn, RegisterIn, ReporteUsuarioIn,
                         RostroIn)

OK, BAD = "  [OK]  ", "  [X]   "
FOTO = "data:image/jpeg;base64,AAAA"


def cara(base: float, ruido: float = 0.0) -> list[float]:
    """Descriptor facial de ejemplo: 128 números parecidos entre sí si `base` es igual."""
    return [round(base + (i % 7) * 0.01 + ruido, 4) for i in range(128)]


class Coleccion:
    """Lo mínimo de una colección de pymongo para estas pruebas."""
    def __init__(self):
        self.docs: list[dict] = []

    @staticmethod
    def _coincide(doc, filtro):
        return all(doc.get(k) == v for k, v in (filtro or {}).items())

    def find(self, filtro=None, proyeccion=None):
        return Cursor([deepcopy(d) for d in self.docs if self._coincide(d, filtro)])

    def find_one(self, filtro=None, proyeccion=None):
        return next(iter(self.find(filtro)), None)

    def insert_one(self, doc):
        self.docs.append(deepcopy(doc))

    def update_one(self, filtro, cambios):
        for d in self.docs:
            if self._coincide(d, filtro):
                d.update(cambios.get("$set", {}))
                return

    def count_documents(self, filtro):
        return len(self.find(filtro).docs)

    def find_one_and_update(self, filtro, cambios, upsert=False, return_document=None):
        d = self.find_one(filtro)
        if not d:
            d = dict(filtro)
            self.docs.append(d)
        else:
            d = next(x for x in self.docs if self._coincide(x, filtro))
        for k, v in cambios.get("$inc", {}).items():
            d[k] = d.get(k, 0) + v
        return dict(d)


class Cursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, campo, orden=1):
        return Cursor(sorted(self.docs, key=lambda d: d.get(campo, 0), reverse=orden < 0))

    def __iter__(self):
        return iter(self.docs)


class Base(dict):
    name = "prueba"

    def __missing__(self, nombre):
        self[nombre] = Coleccion()
        return self[nombre]


def main() -> int:
    fallas = 0

    def revisar(cond, texto):
        nonlocal fallas
        print((OK if cond else BAD) + texto)
        fallas += 0 if cond else 1

    def error(fn, *a, **k):
        try:
            fn(*a, **k)
        except HTTPException as exc:
            return exc.status_code, exc.detail
        return None, ""

    db = Base()
    for m in (repository, auth):
        m.get_db = lambda: db
    for m in (auth, portal, flota_api):
        for f in ("list_rows", "insert_row", "update_row"):
            if hasattr(m, f):
                setattr(m, f, getattr(repository, f))
    flota_api._ubicacion = lambda em: None

    for i, (nombre, foto) in enumerate([("Mariana Torres", FOTO), ("Pablo Núñez", None), ("Elena Cruz", FOTO + "B")], 1):
        db["operators"].insert_one({"id": i, "nombre": nombre, "turno": "Matutino", "estado": "En línea", **({"foto": foto} if foto else {})})
    db["ambulances"].insert_one({"id": 1, "placa": "AMB-101", "tipo": "Avanzada", "hospital": "Hospital IMSS 220",
                                 "conductor": "Mariana Torres", "estado": "Libre", "tanque_litros": 80,
                                 "rendimiento_km_l": 6, "combustible_pct": 50, "kilometraje": 1000})
    db["counters"].insert_one({"_id": "ambulances", "seq": 1})
    db["counters"].insert_one({"_id": "operators", "seq": 3})

    print("\nFotos de los operadores")
    pendientes = auth.rostros_pendientes()
    revisar([p["id"] for p in pendientes] == [1, 3], "Se piden los descriptores de quienes tienen foto (Pablo no tiene)")
    cod, msg = error(auth.login_operador, RostroIn(descriptor=cara(0.2)))
    revisar(cod == 401, "Mientras no se calcula el descriptor de su foto, nadie entra")
    auth.guardar_rostro(1, RostroIn(descriptor=cara(0.2)))
    auth.guardar_rostro(3, RostroIn(descriptor=cara(0.6)))
    revisar(auth.rostros_pendientes() == [], "Con los descriptores guardados ya no hay pendientes")
    cod, _ = error(auth.guardar_rostro, 2, RostroIn(descriptor=cara(0.4)))
    revisar(cod == 404, "No se guarda descriptor para un operador sin foto")

    print("\nEntrada del operador solo con su rostro")
    r = auth.login_operador(RostroIn(descriptor=cara(0.2, ruido=0.02)))
    revisar(r["user"]["role"] == "Operador" and r["user"]["full_name"] == "Mariana Torres",
            "Mariana entra solo con su rostro, sin crear cuenta")
    revisar(repository.find_user("operador-1")["operador_id"] == 1, "Su cuenta interna se crea sola y queda ligada a su registro")
    r2 = auth.login_operador(RostroIn(descriptor=cara(0.2, ruido=-0.01)))
    revisar(r2["user"]["username"] == "operador-1" and len([u for u in db["users"].docs if u.get("operador_id") == 1]) == 1,
            "La segunda vez usa la misma cuenta")
    r3 = auth.login_operador(RostroIn(descriptor=cara(0.6)))
    revisar(r3["user"]["full_name"] == "Elena Cruz", "Otro rostro abre la sesión de otro operador")
    cod, msg = error(auth.login_operador, RostroIn(descriptor=cara(1.5)))
    revisar(cod == 401 and "No te reconocimos" in msg, "Un rostro que no está registrado no entra")
    cod, msg = error(auth.login, LoginIn(username="operador-1", password="cualquiera"))
    revisar(cod == 401, "La cuenta del operador no tiene contraseña con la que se pueda entrar")
    revisar(len(db["verificaciones"].docs) == 5 and not db["verificaciones"].docs[-1]["coincide"],
            "Cada intento (correcto o no) queda en la bitácora de verificaciones")
    db["operators"].update_one({"id": 1}, {"$set": {"foto": FOTO + "nueva"}})
    cod, _ = error(auth.login_operador, RostroIn(descriptor=cara(0.2)))
    revisar(cod == 401 and [p["id"] for p in auth.rostros_pendientes()] == [1],
            "Si le cambian la foto, no entra hasta recalcular su descriptor")
    auth.guardar_rostro(1, RostroIn(descriptor=cara(0.2)))
    try:
        RegisterIn(full_name="Juan", username="juan", password="secreta1", role="Operador")
        sin_registro = False
    except ValueError:
        sin_registro = True
    revisar(sin_registro, "Ya no se puede crear una cuenta con el rol Operador")
    print("\nPermisos por perfil")
    mariana = repository.find_user("operador-1")
    cod, _ = error(security.solo_personal, mariana)
    revisar(cod == 403, "Un operador no entra a las secciones del personal de la central")
    cod, _ = error(portal.solo_usuario, mariana)
    revisar(cod == 403, "Un operador no entra al portal de usuarios")

    print("\nPortal del operador")
    p = portal.portal_operador(mariana)
    revisar(p["ficha"]["ambulancia"]["placa"] == "AMB-101" and p["emergencia"] is None, "Ve su ambulancia y que no tiene emergencia")
    p = portal.operador_combustible(CargaOperadorIn(litros=20, costo=480), mariana)
    revisar(p["ficha"]["ambulancia"]["combustible_pct"] == 75 and p["ficha"]["cargas"][0]["verificado_facial"],
            "Registra gasolina de su ambulancia (50 % → 75 %), marcada como verificada con Face ID")
    cod, msg = error(portal.operador_evento, EventoEmergenciaIn(tipo="salida"), mariana)
    revisar(cod == 409, "Sin emergencia asignada no puede registrar salida")

    print("\nUsuario que reporta")
    u = auth.register(RegisterIn(full_name="Rosa Díaz", username="rosa", password="secreta1", role="Usuario", telefono="7221234567"))
    revisar(u["user"]["role"] == "Usuario" and "token" in u, "Un usuario se registra y entra sin Face ID")
    rosa = repository.find_user("rosa")
    cod, _ = error(portal.solo_operador, rosa)
    revisar(cod == 403, "Un usuario no entra al portal del operador")
    cod, msg = error(portal.reportar, ReporteUsuarioIn(tipo="Caída o fractura"), rosa)
    revisar(cod == 422 and "mapa" in msg, "Sin ubicación ni dirección no se puede reportar")
    rep = portal.reportar(ReporteUsuarioIn(canal="llamada", tipo="Accidente de tránsito", lat=19.29, lng=-99.65,
                                           direccion="Paseo Tollocan y Pino Suárez", personas=5), rosa)
    em = repository.list_rows("emergencies")[0]
    revisar(rep["folio"] == "EMG-0001" and em["canal"] == "llamada" and em["lat"] == 19.29,
            "El reporte llega a la central como emergencia con canal y punto del mapa")
    revisar(em["prioridad"] == "Alta" and em["ambulancias_requeridas"] == 3 and em["paciente_telefono"] == "7221234567",
            "Accidente con 5 personas: prioridad Alta, 3 ambulancias, y el teléfono de su cuenta")

    print("\nLa central asigna y el operador atiende")
    flota_api.asignar(em["id"], flota_api.AsignarIn(cantidad=1, confirmar=True), "admin")
    p = portal.portal_operador(mariana)
    revisar(p["emergencia"] and p["emergencia"]["emergencia"]["folio"] == "EMG-0001", "El operador ve la emergencia que le asignaron")
    cod, msg = error(portal.operador_estado, AmbulanciaPatch(estado="En reparación"), mariana)
    revisar(cod == 409, "No puede mandar su ambulancia a reparación mientras atiende")
    portal.operador_evento(EventoEmergenciaIn(tipo="salida"), mariana)
    mis = portal.mis_reportes(rosa)["items"][0]
    revisar(mis["estado"] == "En curso" and mis["ambulancias"][0]["conductor"] == "Mariana Torres",
            "Quien reportó ve que va en camino, en qué ambulancia y quién la maneja")
    portal.operador_evento(EventoEmergenciaIn(tipo="cierre", km_recorridos=6), mariana)
    p = portal.portal_operador(mariana)
    revisar(p["emergencia"] is None and p["ficha"]["ambulancia"]["estado"] == "Libre", "Al cerrar, su ambulancia queda libre")
    p = portal.operador_estado(AmbulanciaPatch(estado="En reparación", motivo="Llanta ponchada"), mariana)
    revisar(p["ficha"]["ambulancia"]["estado"] == "En reparación", "Puede reportar su ambulancia en reparación con el motivo")

    print("\nTodo bien.\n" if not fallas else f"\n{fallas} regla(s) fallaron.\n")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
