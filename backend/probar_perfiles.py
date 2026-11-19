"""Prueba los perfiles: Operador con Face ID, Paramédico, Usuario que reporta emergencias,
usuarios y contraseñas que da la central, y permisos.

Uso (en la carpeta backend, con el entorno virtual activado):
    python probar_perfiles.py

No necesita MongoDB ni internet: usa una base de datos de ejemplo en memoria y llama
directo a las funciones de la API.
"""
import sys
from copy import deepcopy

from fastapi import HTTPException

from app import repository, security
from app.routers import auth, cuentas, flota as flota_api, modules, portal
from app.schemas import (AmbulanciaPatch, AtencionParamedicoIn, CargaOperadorIn, CredencialesIn, EventoEmergenciaIn,
                         LoginIn, OperatorIn, ParamedicIn, RegisterIn, ReporteUsuarioIn, RostroIn)

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
        def ok(valor, cond):
            if isinstance(cond, dict) and cond and all(str(k).startswith("$") for k in cond):
                return all((op == "$ne" and valor != x) or (op == "$in" and valor in x)
                           or (op == "$exists" and (valor is not None) == x) for op, x in cond.items())
            return valor == cond
        return all(ok(doc.get(k), v) for k, v in (filtro or {}).items())

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
                for k in cambios.get("$unset", {}):
                    d.pop(k, None)
                return

    def delete_one(self, filtro):
        antes = len(self.docs)
        for i, d in enumerate(self.docs):
            if self._coincide(d, filtro):
                del self.docs[i]
                break
        return type("R", (), {"deleted_count": antes - len(self.docs)})()

    def delete_many(self, filtro):
        self.docs = [d for d in self.docs if not self._coincide(d, filtro)]

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
    # Ninguna prueba debe tocar la base real del .env: se reemplaza get_db en TODOS los módulos
    # que lo importaron y cualquier intento de conexión real falla de inmediato.
    from app import mongo

    def sin_conexion():
        raise RuntimeError("probar_perfiles.py no debe conectarse a MongoDB")
    mongo.get_client = sin_conexion
    for nombre, mod in list(sys.modules.items()):
        if (nombre == "app" or nombre.startswith("app.")) and hasattr(mod, "get_db"):
            mod.get_db = lambda: db
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
    cod, msg = error(auth.login_operador, RostroIn(descriptor=cara(0.2, ruido=0.02)))
    revisar(cod == 403 and "no tienes acceso" in msg and repository.find_user("operador-1") is None,
            "Sin cuenta, la reconoce pero NO entra: el sistema ya no crea cuentas solo")
    # El administrador les da acceso (lo que hace la ficha del operador).
    for i, nombre in ((1, "Mariana Torres"), (3, "Elena Cruz")):
        repository.guardar_credenciales("operators", "operador_id", "Operador", i, nombre, f"operador-{i}", "clave-segura-1")
    r = auth.login_operador(RostroIn(descriptor=cara(0.2, ruido=0.02)))
    revisar(r["user"]["role"] == "Operador" and r["user"]["full_name"] == "Mariana Torres",
            "Con su acceso, Mariana entra solo con su rostro")
    revisar(repository.find_user("operador-1")["operador_id"] == 1, "Entra a la cuenta que le dio el administrador")
    r2 = auth.login_operador(RostroIn(descriptor=cara(0.2, ruido=-0.01)))
    revisar(r2["user"]["username"] == "operador-1" and len([u for u in db["users"].docs if u.get("operador_id") == 1]) == 1,
            "La segunda vez usa la misma cuenta")
    r3 = auth.login_operador(RostroIn(descriptor=cara(0.6)))
    revisar(r3["user"]["full_name"] == "Elena Cruz", "Otro rostro abre la sesión de otro operador")
    cod, msg = error(auth.login_operador, RostroIn(descriptor=cara(1.5)))
    revisar(cod == 401 and "No te reconocimos" in msg, "Un rostro que no está registrado no entra")
    cod, msg = error(auth.login, LoginIn(username="operador-1", password="cualquiera"))
    revisar(cod == 401, "Con una contraseña equivocada no entra")
    revisar(len(db["verificaciones"].docs) == 6 and not db["verificaciones"].docs[-1]["coincide"],
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
    for rol in ("Administrador", "Despachador", "Supervisor"):
        try:
            RegisterIn(full_name="Intruso", username="intruso", password="secreta1", role=rol)
            abierto = True
        except ValueError:
            abierto = False
        revisar(not abierto, f"En el registro público nadie se puede hacer {rol}")
    print("\nPermisos por perfil")
    mariana = repository.find_user("operador-1")
    cod, _ = error(security.solo_personal, mariana)
    revisar(cod == 403, "Un operador no entra a las secciones del personal de la central")
    cod, _ = error(portal.solo_usuario, mariana)
    revisar(cod == 403, "Un operador no entra al portal de usuarios")

    print("\nPortal del operador")
    p = portal.portal_operador(mariana)
    revisar(p["ficha"]["ambulancia"]["placa"] == "AMB-101" and p["emergencia"] is None, "Ve su ambulancia y que no tiene emergencia")
    p = portal.operador_combustible(CargaOperadorIn(litros=10), mariana, metodo="contraseña")
    revisar(p["ficha"]["ambulancia"]["combustible_pct"] == 62.5 and not p["ficha"]["cargas"][0]["verificado_facial"],
            "Si entró con contraseña, su carga NO cuenta como verificada con el rostro")
    p = portal.operador_combustible(CargaOperadorIn(litros=10, costo=480), mariana, metodo="rostro")
    revisar(p["ficha"]["ambulancia"]["combustible_pct"] == 75 and p["ficha"]["cargas"][0]["verificado_facial"],
            "Registra gasolina de su ambulancia (50 % → 75 %), marcada como verificada con Face ID")
    CC = flota_api.CargaCombustibleIn
    cod, msg = error(flota_api.cargar_combustible, 1, CC(operador="Mariana Torres", litros=1, descriptor=cara(0.6)), "admin")
    revisar(cod == 403 and "no coincide" in msg, "En la central, si el rostro no es del conductor, la carga se rechaza")
    f = flota_api.cargar_combustible(1, CC(operador="Mariana Torres", litros=1, descriptor=cara(0.2, ruido=0.01)), "admin")
    revisar(f["cargas"][0]["verificado_facial"], "Si es su rostro (lo compara el servidor), queda verificada")
    f = flota_api.cargar_combustible(1, CC(operador="Mariana Torres", litros=1, verificado_facial=True), "admin")
    revisar(not f["cargas"][0]["verificado_facial"], "Aunque el navegador diga «verificado», sin rostro no cuenta")
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
    revisar(rep["duplicado"] is False and em["num_reportes"] == 1, "Es el primer reporte de esta emergencia")

    print("\nPreguntas de sí/no y reportes repetidos")
    cat = portal.tipos(rosa)
    revisar(cat["generales"][1]["clave"] == "respira" and "atrapados" in [p["clave"] for p in cat["por_tipo"]["Accidente de tránsito"]],
            "La pantalla recibe las preguntas generales y las de cada tipo")
    u2 = auth.register(RegisterIn(full_name="Tomás Vega", username="tomas", password="secreta1", role="Usuario"))
    tomas = repository.find_user("tomas")
    rep2 = portal.reportar(ReporteUsuarioIn(tipo="Accidente de tránsito", lat=19.2908, lng=-99.6503, personas=8,
                                            respuestas={"atrapados": True, "respira": True}), tomas)
    em = repository.list_rows("emergencies")[0]
    revisar(rep2["duplicado"] and rep2["folio"] == "EMG-0001" and len(repository.list_rows("emergencies")) == 1,
            "Otra persona reporta el mismo choque a ~100 m: no se crea otra emergencia")
    revisar(em["num_reportes"] == 2 and em["reportes_adicionales"][0]["nombre"] == "Tomás Vega"
            and "Hay personas atrapadas" in em["prioridad_motivos"],
            "Su reporte se suma, con sus respuestas y la señal de alarma nueva")
    revisar(em["ambulancias_requeridas"] == 4 and em["personas"] == 8, "Dijo 8 personas: ahora se piden 4 ambulancias")
    revisar(portal.mis_reportes(tomas)["items"][0]["folio"] == "EMG-0001", "Tomás también ve el avance en «Mis reportes»")
    revisar(any("también reportó EMG-0001" in h["detalle"] for h in db["historial"].docs),
            "La central ve en el historial que lo reportó alguien más")
    rep3 = portal.reportar(ReporteUsuarioIn(tipo="Caída o fractura", direccion="Av. Morelos 900, Toluca",
                                            respuestas={"mover": False}), tomas)
    em3_ = next(e for e in repository.list_rows("emergencies") if e["folio"] == rep3["folio"])
    revisar(not rep3["duplicado"] and em3_["prioridad"] == "Alta" and em3_["prioridad_base"] == "Media"
            and "Señales de alarma: No puede mover brazos o piernas" in em3_["descripcion"],
            "Una caída es Media, pero «no puede mover brazos o piernas» la sube a Alta y se explica")
    em3_["estado"] = "Cerrada"
    db["emergencies"].update_one({"id": em3_["id"]}, {"$set": {"estado": "Cerrada"}})

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

    print("\nLa central crea la emergencia y asigna al operador con Face ID")
    portal.operador_estado(AmbulanciaPatch(estado="Libre"), mariana)
    em2 = repository.insert_row("emergencies", {"paciente_nombre": "Luis Romero", "direccion": "Av. Morelos 1200",
                                                "descripcion": "Dolor torácico", "prioridad": "Alta", "estado": "Pendiente",
                                                "ambulancias_requeridas": 1})
    OE = flota_api.OperadorEmergenciaIn
    cod, msg = error(flota_api.asignar_operador, em2["id"], OE(descriptor=cara(1.9)), "admin")
    revisar(cod == 403 and "No te reconocimos" in msg and db["verificaciones"].docs[-1]["coincide"] is False,
            "Un rostro desconocido no queda a cargo, y el intento queda en la bitácora")
    r = flota_api.asignar_operador(em2["id"], OE(descriptor=cara(0.2, ruido=0.01)), "admin")
    em2 = next(e for e in repository.list_rows("emergencies") if e["id"] == em2["id"])
    revisar(r["listo"] and r["ambulancia"] == "AMB-101" and em2["ambulancia"] == "AMB-101" and em2["operador"] == "Mariana Torres",
            "Al validar a Mariana, la emergencia queda con ella y con su ambulancia")
    p = portal.portal_operador(mariana)
    revisar(p["emergencia"]["emergencia"]["folio"] == em2["folio"] and p["ficha"]["ambulancia"]["estado"] == "Ocupada",
            "En su perfil de Operador le aparece la emergencia con la ambulancia asignada")
    em3 = repository.insert_row("emergencies", {"paciente_nombre": "Ana", "direccion": "Centro", "descripcion": "Caída",
                                                "prioridad": "Media", "estado": "Pendiente", "ambulancias_requeridas": 1})
    r = flota_api.asignar_operador(em3["id"], OE(descriptor=cara(0.6)), "admin")
    revisar(not r["listo"] and "no maneja ninguna ambulancia" in r["mensaje"], "Si el operador no maneja ambulancia, se avisa a la central")
    elena = repository.find_user("operador-3")
    p = portal.portal_operador(elena)
    revisar(p["emergencia"] and p["emergencia"]["emergencia"]["folio"] == em3["folio"] and p["ficha"] is None,
            "Elena ve la emergencia a su cargo aunque todavía no tenga ambulancia")

    print("\nUsuarios y contraseñas que da la central")

    def endpoint(ruta, nombre):
        for r in modules.routers:
            for x in r.routes:
                if x.path.startswith(f"/api/{ruta}") and x.name == nombre:
                    return x.endpoint
        raise KeyError(nombre)

    datos = dict(nombres="Hugo", apellidos="Leal", celular="7221112233", correo="hugo@imss.mx", foto=FOTO + "H",
                 usuario="Hugo.Leal", password="ambulancia1")
    nuevo = endpoint("operadores", "create_item")(OperatorIn(**datos))
    op_doc = next(o for o in db["operators"].docs if o["id"] == nuevo["id"])
    revisar(nuevo["usuario"] == "hugo.leal" and "password" not in op_doc and op_doc["usuario"] == "hugo.leal",
            "Al registrar un operador queda su usuario; la contraseña NO se guarda en el registro")
    revisar(security.verify_password("ambulancia1", repository.find_user("hugo.leal")["password_hash"]),
            "Su contraseña queda cifrada en su cuenta")
    r = auth.login(LoginIn(username="hugo.leal", password="ambulancia1"))
    revisar(r["user"]["role"] == "Operador" and r["user"]["operador"]["nombre"] == "Hugo Leal",
            "El operador entra con su usuario y contraseña (además de con su rostro)")
    cod, msg = error(endpoint("operadores", "create_item"), OperatorIn(**{**datos, "correo": "otro@imss.mx"}))
    revisar(cod == 409, "No se repite un usuario que ya existe")
    lista = endpoint("operadores", "list_items")()["items"]
    revisar(next(o for o in lista if o["nombre"] == "Mariana Torres")["usuario"] == "operador-1",
            "En la lista de Operadores se ve el usuario de cada uno (también los que entraban solo con rostro)")
    endpoint("operadores", "cambiar_credenciales")(1, CredencialesIn(usuario="mariana", password="nueva123"))
    r = auth.login(LoginIn(username="mariana", password="nueva123"))
    revisar(r["user"]["full_name"] == "Mariana Torres" and repository.find_user("operador-1") is None,
            "El administrador le cambia usuario y contraseña a Mariana y ya entra con ellos")
    r = auth.login_operador(RostroIn(descriptor=cara(0.2)))
    revisar(r["user"]["username"] == "mariana", "Con su rostro sigue entrando a la misma cuenta")
    cod, _ = error(endpoint("operadores", "cambiar_credenciales"), 1, CredencialesIn(usuario="hugo.leal"))
    revisar(cod == 409, "No se le puede poner el usuario de otra persona")
    admin = {"username": "admin", "role": "Administrador"}
    despachador = {"username": "desp", "role": "Despachador"}
    revisar(error(modules.solo_admin, despachador)[0] == 403 and error(modules.solo_admin, admin)[0] is None,
            "Solo el Administrador cambia usuarios y contraseñas")
    mariana = repository.find_user("mariana")

    print("\nPerfil de paramédico")
    alta = lambda **k: endpoint("paramedicos", "create_item")(ParamedicIn(**{  # noqa: E731
        "celular": "7224445566", "nivel": "TUM Básico", "foto": FOTO + k["usuario"], "password": "tum12345", **k}))
    pm = alta(nombres="Sofía", apellidos="Ruiz", correo="sofia@imss.mx", nivel="TUM Avanzado", usuario="sofia.ruiz")
    pm2 = alta(nombres="Iván", apellidos="Mora", correo="ivan@imss.mx", usuario="ivan.mora")
    pm3 = alta(nombres="Lía", apellidos="Paz", correo="lia@imss.mx", usuario="lia.paz")
    revisar(pm["nombre"] == "Sofía Ruiz" and pm["usuario"] == "sofia.ruiz" and "password" not in db["paramedics"].docs[0],
            "La central registra a la paramédica con su usuario (sin guardar la contraseña en el registro)")
    revisar("ambulancia" not in ParamedicIn.model_fields, "Al registrarla ya no se elige ambulancia")
    r = auth.login(LoginIn(username="sofia.ruiz", password="tum12345"))
    revisar(r["user"]["role"] == "Paramédico" and r["user"]["paramedico"]["nivel"] == "TUM Avanzado",
            "La paramédica entra con su usuario y contraseña")
    sofia, ivan = repository.find_user("sofia.ruiz"), repository.find_user("ivan.mora")
    pend = auth.rostros_pendientes()
    revisar(any(p["tipo"] == "paramedico" and p["id"] == pm["id"] for p in pend),
            "La foto de la paramédica queda pendiente de preparar para el Face ID")
    cod, _ = error(auth.login_rostro, RostroIn(descriptor=cara(0.9)))
    revisar(cod == 401, "Antes de preparar su foto, no entra con su rostro")
    auth.guardar_rostro_de("paramedico", pm["id"], RostroIn(descriptor=cara(0.9)))
    r = auth.login_rostro(RostroIn(descriptor=cara(0.9, ruido=0.01)))
    revisar(r["user"]["username"] == "sofia.ruiz" and r["user"]["role"] == "Paramédico",
            "La paramédica entra con su rostro, a su misma cuenta")
    r = auth.login_rostro(RostroIn(descriptor=cara(0.2)))
    revisar(r["user"]["role"] == "Operador" and r["user"]["full_name"] == "Mariana Torres",
            "Con el mismo botón, el rostro de Mariana sigue abriendo su sesión de operadora")
    cod, _ = error(auth.guardar_rostro_de, "otro", 1, RostroIn(descriptor=cara(0.9)))
    revisar(cod == 404, "Solo operadores y paramédicos guardan rostro")
    revisar(error(security.solo_personal, sofia)[0] == 403 and error(portal.solo_operador, sofia)[0] == 403,
            "No entra a la central ni al portal del operador")
    revisar(error(portal.solo_paramedico, mariana)[0] == 403, "Un operador no entra al portal del paramédico")
    p = portal.portal_paramedico(sofia)
    revisar(p["emergencia"] is None and p["ambulancia"] is None, "Mientras no la mandan a una emergencia, no tiene ambulancia")
    cod, _ = error(portal.paramedico_atencion, AtencionParamedicoIn(escala_glasgow=15), sofia)
    revisar(cod == 409, "Sin emergencia no registra atención")

    print("\nDos paramédicos por emergencia, confirmados con su rostro")
    PE = flota_api.ParamedicoEmergenciaIn
    for p_, base in ((pm2, 1.2), (pm3, 1.5)):
        auth.guardar_rostro_de("paramedico", p_["id"], RostroIn(descriptor=cara(base)))
    cara_pm = {pm["id"]: cara(0.9, ruido=0.01), pm2["id"]: cara(1.2, ruido=0.01), pm3["id"]: cara(1.5, ruido=0.01)}
    cod, msg = error(flota_api.agregar_paramedico, em2["id"], PE(descriptor=cara(2.5)), "admin")
    revisar(cod == 403, "Un rostro que no es de ningún paramédico se rechaza (lo decide el servidor)")
    rep = flota_api.agregar_paramedico(em2["id"], PE(descriptor=cara_pm[pm["id"]]), "admin")
    revisar([x["nombre"] for x in rep["paramedicos"]] == ["Sofía Ruiz"] and rep["paramedicos_requeridos"] == 2,
            "La central confirma a Sofía con su rostro: va a la emergencia (falta 1)")
    revisar(db["verificaciones"].docs[-1]["operador"] == "Sofía Ruiz" and db["verificaciones"].docs[-1]["tipo"] == "paramedico",
            "Queda en la bitácora de verificaciones")
    cod, msg = error(flota_api.agregar_paramedico, em2["id"], PE(descriptor=cara_pm[pm["id"]]), "admin")
    revisar(cod == 409 and "ya va" in msg, "No se repite a la misma persona")
    cod, msg = error(flota_api.agregar_paramedico, em3["id"], PE(descriptor=cara_pm[pm["id"]]), "admin")
    revisar(cod == 409 and em2["folio"] in msg, "Si ya está en otra emergencia, no se puede mandar a otra")
    flota_api.agregar_paramedico(em2["id"], PE(descriptor=cara_pm[pm2["id"]]), "admin")
    cod, msg = error(flota_api.agregar_paramedico, em2["id"], PE(descriptor=cara_pm[pm3["id"]]), "admin")
    revisar(cod == 409 and "2 paramédicos" in msg, "Con 2 ya está completa: no se agrega un tercero")
    db["paramedics"].update_one({"id": pm3["id"]}, {"$set": {"estado": "Fuera de turno"}})
    cod, msg = error(flota_api.agregar_paramedico, em3["id"], PE(descriptor=cara_pm[pm3["id"]]), "admin")
    revisar(cod == 409 and "en servicio" in msg, "Un paramédico fuera de turno no puede ir")
    db["paramedics"].update_one({"id": pm3["id"]}, {"$set": {"estado": "En servicio"}})
    p = portal.portal_paramedico(sofia)
    revisar(p["ambulancia"]["placa"] == "AMB-101" and p["conductor"]["nombre"] == "Mariana Torres",
            "Su ambulancia es la de la emergencia, y ve quién la maneja")
    revisar(p["emergencia"]["folio"] == em2["folio"] and p["emergencia"]["paciente_nombre"] == "Luis Romero"
            and [c["nombre"] for c in p["companeros"]] == ["Iván Mora"],
            "Ve al paciente y a su compañero")
    lista = endpoint("paramedicos", "list_items")()["items"]
    revisar(next(x for x in lista if x["id"] == pm["id"])["emergencia_actual"] == em2["folio"],
            "En la lista de Paramédicos la central ve a qué emergencia va cada uno")
    cod, _ = error(portal.paramedico_atencion, AtencionParamedicoIn(), sofia)
    revisar(cod == 422, "No se guarda una atención vacía")
    portal.paramedico_atencion(AtencionParamedicoIn(saturacion_oxigeno=88, frecuencia_cardiaca=120, escala_glasgow=13,
                                                    presion_arterial="140/90", observaciones="Oxígeno por puntas 3 L/min"), sofia)
    p = portal.paramedico_atencion(AtencionParamedicoIn(saturacion_oxigeno=94, frecuencia_cardiaca=104), ivan)
    e = p["emergencia"]
    revisar(e["saturacion_oxigeno"] == 94 and e["presion_arterial"] == "140/90" and e["atendio_paramedico"] == "Iván Mora",
            "Los dos registran signos; la emergencia guarda los últimos")
    revisar([c["paramedico"] for c in e["atenciones_paramedico"]] == ["Sofía Ruiz", "Iván Mora"]
            and e["atenciones_paramedico"][0]["saturacion_oxigeno"] == 88,
            "Cada captura queda en la lista, para ver cómo evoluciona el paciente")
    revisar(any(h["tipo"] == "atención" and h["emergencia"] == em2["folio"] for h in db["historial"].docs),
            "La atención queda en el historial")
    rep = flota_api.quitar_paramedico(em2["id"], pm2["id"], "admin")
    revisar([x["nombre"] for x in rep["paramedicos"]] == ["Sofía Ruiz"] and portal.portal_paramedico(ivan)["emergencia"] is None,
            "La central puede quitar a uno; a él ya no le aparece")
    portal.operador_evento(EventoEmergenciaIn(tipo="cierre", km_recorridos=4), mariana)
    p = portal.portal_paramedico(sofia)
    revisar(p["emergencia"] is None and p["atendidas"][0]["folio"] == em2["folio"],
            "Al cerrarse, pasa a sus atenciones anteriores y queda libre para otra")
    rep = flota_api.agregar_paramedico(em3["id"], PE(descriptor=cara_pm[pm["id"]]), "admin")
    revisar(rep["paramedicos"][0]["nombre"] == "Sofía Ruiz", "Ya libre, la pueden mandar a la siguiente emergencia")

    print("\nEliminar registros (solo el Administrador)")
    borrar = lambda ruta, i: endpoint(ruta, "delete_item")(i, "admin")  # noqa: E731
    cod, msg = error(borrar, "paramedicos", pm["id"])
    revisar(cod == 409 and em3["folio"] in msg, "No se elimina a un paramédico que está en una emergencia abierta")
    r = borrar("paramedicos", pm3["id"])
    revisar(r["ok"] and not any(x["id"] == pm3["id"] for x in db["paramedics"].docs) and repository.find_user("lia.paz") is None,
            "Se elimina a Lía y también su cuenta: ya no puede entrar")
    cod, _ = error(borrar, "paramedicos", pm3["id"])
    revisar(cod == 404, "Eliminar dos veces avisa que ya no existe")
    cod, msg = error(borrar, "operadores", 3)
    revisar(cod == 409 and em3["folio"] in msg, "No se elimina a un operador a cargo de una emergencia abierta")
    db["ambulances"].update_one({"id": 1}, {"$set": {"estado": "Ocupada"}})
    cod, msg = error(borrar, "ambulancias", 1)
    revisar(cod == 409, "No se elimina una ambulancia ocupada")
    db["ambulances"].update_one({"id": 1}, {"$set": {"estado": "Libre"}})
    r = borrar("operadores", 1)
    revisar(r["ok"] and repository.find_user("mariana") is None and db["ambulances"].docs[0]["conductor"] == "",
            "Al eliminar a Mariana se borra su cuenta y su ambulancia queda sin conductor")
    revisar(any(h["tipo"] == "baja" and "Mariana Torres" in h["detalle"] for h in db["historial"].docs),
            "La eliminación queda en el historial")
    revisar(error(modules.solo_admin, {"username": "d", "role": "Supervisor"})[0] == 403,
            "Solo el Administrador puede eliminar")

    print("\nCuentas (solo el Administrador crea las de la central)")
    revisar(error(security.require_roles("Administrador"), {"username": "d", "role": "Despachador"})[0] == 403,
            "Un Despachador no entra a Cuentas")
    jefa = cuentas.crear(cuentas.CuentaIn(full_name="Ana Jefa", username="ana.jefa", password="segura123", role="Administrador"))
    yo = repository.find_user("ana.jefa")
    revisar(jefa["role"] == "Administrador" and "password_hash" not in jefa, "El Administrador crea una cuenta (sin regresar la contraseña)")
    d = cuentas.crear(cuentas.CuentaIn(full_name="Diego Turno", username="diego.turno", password="segura123"))
    revisar(d["role"] == "Despachador" and auth.login(LoginIn(username="diego.turno", password="segura123"))["user"]["role"] == "Despachador",
            "Crea un Despachador y ya puede entrar")
    try:
        cuentas.CuentaIn(full_name="X", username="xx.yy", password="segura123", role="Operador")
        acepto = True
    except ValueError:
        acepto = False
    revisar(not acepto, "Aquí no se crean operadores ni paramédicos (van en sus módulos)")
    cod, _ = error(cuentas.crear, cuentas.CuentaIn(full_name="Otro Diego", username="diego.turno", password="segura123"))
    revisar(cod == 409, "No se repite un usuario")
    lista = cuentas.listar()["items"]
    revisar(lista[0]["role"] == "Administrador" and all("password_hash" not in c for c in lista)
            and next(c for c in lista if c["username"] == "operador-3")["ligada_a"] == "Operadores",
            "La lista muestra todas, sin contraseñas, y cuáles se administran en Operadores o Paramédicos")
    cuentas.cambiar("diego.turno", cuentas.CuentaPatch(password="nueva4567", role="Supervisor"), yo)
    revisar(auth.login(LoginIn(username="diego.turno", password="nueva4567"))["user"]["role"] == "Supervisor",
            "Le cambia la contraseña y el rol")
    cuentas.cambiar("diego.turno", cuentas.CuentaPatch(active=False), yo)
    revisar(error(auth.login, LoginIn(username="diego.turno", password="nueva4567"))[0] == 401, "Una cuenta desactivada no entra")
    revisar(error(cuentas.cambiar, "ana.jefa", cuentas.CuentaPatch(active=False), yo)[0] == 409, "No puedes desactivarte tú misma")
    revisar(error(cuentas.borrar, "ana.jefa", yo)[0] == 409, "No puedes borrar tu propia cuenta")
    luis = cuentas.crear(cuentas.CuentaIn(full_name="Luis Admin", username="luis.admin", password="segura123", role="Administrador"))
    cuentas.cambiar("luis.admin", cuentas.CuentaPatch(active=False), yo)
    revisar(not next(c for c in cuentas.listar()["items"] if c["username"] == "luis.admin")["active"],
            "Con dos administradores, uno puede desactivar al otro")
    otro = repository.find_user("luis.admin")
    revisar(error(cuentas.borrar, "ana.jefa", otro)[0] == 409,
            "Pero no se puede borrar a la única Administradora activa: nunca se queda sin Administrador")
    revisar(error(cuentas.cambiar, "ana.jefa", cuentas.CuentaPatch(role="Despachador"), otro)[0] == 409,
            "Ni quitarle el rol")
    cuentas.cambiar("luis.admin", cuentas.CuentaPatch(active=True), yo)
    r = cuentas.cambiar("ana.jefa", cuentas.CuentaPatch(role="Supervisor"), otro)
    revisar(r["role"] == "Supervisor", "Con otro Administrador activo, ya se le puede cambiar el rol")
    r = cuentas.borrar("operador-3", otro)
    revisar(r["ok"] and repository.find_user("operador-3") is None and "usuario" not in next(o for o in db["operators"].docs if o["id"] == 3),
            "Borrar la cuenta de un operador le quita el acceso, pero su registro se queda")

    print("\nTodo bien.\n" if not fallas else f"\n{fallas} regla(s) fallaron.\n")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
