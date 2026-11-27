"""Carga datos de prueba coherentes en la base de Emergexia (MongoDB de backend/.env).

    python datos_prueba.py --password "TuContraseñaDePrueba"

Todas las cuentas de prueba usan esa contraseña (mínimo 8 caracteres). No se guarda en
el código porque el repositorio es público.

Qué crea (usando las mismas funciones que la API, con sus validaciones):
  - 3 cuentas de la central (1 Supervisor, 2 Despachadores)
  - 3 cuentas de Usuario (personas que reportan emergencias)
  - 6 operadores con su cuenta y 4 paramédicos con su cuenta
  - 6 ambulancias, cada una con su conductor, en hospitales del sistema
  - 20 emergencias en Toluca, Metepec, Lerma, San Mateo Atenco y Zinacantepec:
    12 cerradas (salida → llegada → traslado → cierre), las demás en curso, asignadas
    o esperando ambulancia. 4 las reportan las cuentas de Usuario.
  - 3 cargas de gasolina
El historial, la asignación automática y el consumo de gasolina los genera el sistema.

Lo que ya exista (mismo usuario o misma placa) no se toca: ni su contraseña ni sus datos.
Si las emergencias de prueba ya se cargaron, no se vuelven a crear.
Todo lo que crea lleva el campo datos_prueba: true para identificarlo.
"""
import argparse
import sys

# Foto de referencia de relleno (1x1 px): la API exige una. Para entrar con Face ID hay que
# tomarles su foto real desde Operadores / Paramédicos; con usuario y contraseña ya entran.
FOTO_RELLENO = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8"
                "/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==")

PERSONAL = [  # usuario, nombre, rol
    ("supervisor.carmen", "Carmen Rosales Vega", "Supervisor"),
    ("despacho.luis", "Luis Fernando Ortega", "Despachador"),
    ("despacho.ana", "Ana Karen Domínguez", "Despachador"),
]

USUARIOS = [  # usuario, nombre, teléfono
    ("maria.lopez", "María López Sánchez", "7221234501"),
    ("jorge.mendez", "Jorge Méndez Cruz", "7221234502"),
    ("sofia.reyes", "Sofía Reyes Bernal", "7221234503"),
]

OPERADORES = [  # usuario, nombres, apellidos, celular, turno, experiencia
    ("op.raul", "Raúl", "Hernández Gómez", "7225550101", "Matutino", 8),
    ("op.diana", "Diana", "Castillo Peña", "7225550102", "Matutino", 5),
    ("op.ernesto", "Ernesto", "Vargas Luna", "7225550103", "Vespertino", 12),
    ("op.patricia", "Patricia", "Morales Ríos", "7225550104", "Vespertino", 3),
    ("op.hugo", "Hugo", "Jiménez Torres", "7225550105", "Nocturno", 6),
    ("op.veronica", "Verónica", "Salgado Mejía", "7225550106", "Nocturno", 2),
]

PARAMEDICOS = [  # usuario, nombres, apellidos, celular, nivel, turno, tipo de sangre
    ("tum.alejandro", "Alejandro", "Pineda Ruiz", "7225550201", "TUM Avanzado", "Matutino", "O+"),
    ("tum.gabriela", "Gabriela", "Nava Ortiz", "7225550202", "TUM Intermedio", "Matutino", "A+"),
    ("tum.ricardo", "Ricardo", "Flores Islas", "7225550203", "Paramédico", "Vespertino", "B+"),
    ("tum.lucia", "Lucía", "Garduño Paz", "7225550204", "TUM Básico", "Nocturno", "O-"),
]

AMBULANCIAS = [  # placa, tipo, hospital, conductor (usuario del operador), gasolina %, km, marca, modelo, año
    ("I220-51", "Avanzada", "Hospital IMSS 220", "op.raul", 90, 48210, "Ford", "Transit", 2022),
    ("I220-52", "Básica", "Hospital IMSS 220", "op.diana", 75, 61530, "Mercedes-Benz", "Sprinter", 2021),
    ("NSJ-51", "Avanzada", "Hospital General Nicolás San Juan", "op.ernesto", 85, 39870, "Ford", "Transit", 2023),
    ("CRT-51", "Básica", "Cruz Roja Toluca", "op.patricia", 70, 72440, "Mercedes-Benz", "Sprinter", 2020),
    ("I251-51", "Avanzada", "Hospital IMSS 251", "op.hugo", 95, 25120, "Ford", "Transit", 2024),
    ("CRM-51", "Básica", "Cruz Roja Metepec", "op.veronica", 80, 55300, "Mercedes-Benz", "Sprinter", 2022),
]

# Emergencias capturadas en la central. avance: "cerrar" | "llegada" | "salida" | "asignar".
EMERGENCIAS = [
    dict(paciente_nombre="Roberto Salinas Ávila", paciente_edad="45", paciente_sexo="Masculino",
         direccion="Paseo Tollocan esq. Av. Las Torres, Toluca", lat=19.2795, lng=-99.6240,
         descripcion="Choque de dos autos, conductor con dolor de cuello", prioridad="Alta",
         saturacion_oxigeno=96, frecuencia_cardiaca=98, escala_glasgow=15, avance="cerrar", km=12, destino="Hospital IMSS 220"),
    dict(paciente_nombre="Guadalupe Torres Méndez", paciente_edad="72", paciente_sexo="Femenino",
         direccion="Portal Madero, Centro, Toluca", lat=19.2924, lng=-99.6557,
         descripcion="Adulta mayor con dolor en el pecho y sudoración", prioridad="Alta",
         saturacion_oxigeno=89, frecuencia_cardiaca=118, escala_glasgow=14, avance="cerrar", km=9, destino="Hospital IMSS 220"),
    dict(paciente_nombre="Daniel Esquivel Mora", paciente_edad="28", paciente_sexo="Masculino",
         direccion="Av. Tecnológico, Metepec", lat=19.2600, lng=-99.5800,
         descripcion="Caída de motocicleta, posible fractura de brazo", prioridad="Media",
         avance="cerrar", km=15, destino="Hospital IMSS 251"),
    dict(paciente_nombre="Fernanda Ruiz Carmona", paciente_edad="31", paciente_sexo="Femenino",
         direccion="Calle Hidalgo, Centro, San Mateo Atenco", lat=19.2672, lng=-99.5340,
         descripcion="Embarazo de 38 semanas con contracciones frecuentes", prioridad="Alta",
         saturacion_oxigeno=98, frecuencia_cardiaca=92, escala_glasgow=15, avance="cerrar", km=18, destino="Hospital IMSS 251"),
    dict(paciente_nombre="Arturo Pedraza Lara", paciente_edad="58", paciente_sexo="Masculino",
         direccion="Av. Venustiano Carranza, Col. Universidad, Toluca", lat=19.2858, lng=-99.6680,
         descripcion="Dificultad para respirar, antecedente de asma", prioridad="Alta",
         saturacion_oxigeno=87, frecuencia_cardiaca=110, escala_glasgow=15, avance="cerrar", km=10, destino="Hospital General Nicolás San Juan"),
    dict(paciente_nombre="Karla Becerril Soto", paciente_edad="19", paciente_sexo="Femenino",
         direccion="Ciudad Universitaria UAEMéx, Toluca", lat=19.2840, lng=-99.6780,
         descripcion="Desmayo en salón de clases, ya reaccionó", prioridad="Media",
         saturacion_oxigeno=97, frecuencia_cardiaca=88, escala_glasgow=15, avance="cerrar", km=8, destino="Hospital General Nicolás San Juan"),
    dict(paciente_nombre="Javier Montes de Oca", paciente_edad="40", paciente_sexo="Masculino",
         direccion="Parque Industrial Lerma, Lerma", lat=19.3000, lng=-99.5000,
         descripcion="Herida en mano con maquinaria, sangrado controlado", prioridad="Media",
         avance="cerrar", km=22, destino="Hospital Municipal Lerma"),
    dict(paciente_nombre="Teresa Albarrán Díaz", paciente_edad="66", paciente_sexo="Femenino",
         direccion="Centro de Zinacantepec", lat=19.2846, lng=-99.7355,
         descripcion="Caída en casa, dolor de cadera, no puede caminar", prioridad="Media",
         avance="cerrar", km=25, destino="Hospital IMSS 220"),
    dict(paciente_nombre="Óscar Quintana Rojas", paciente_edad="35", paciente_sexo="Masculino",
         direccion="Terminal de autobuses, Toluca", lat=19.2716, lng=-99.6421,
         descripcion="Quemadura en antebrazo con aceite caliente", prioridad="Media",
         avance="cerrar", km=7, destino="Cruz Roja Toluca"),
    dict(paciente_nombre="Rosa María Gil", paciente_edad="50", paciente_sexo="Femenino",
         direccion="Centro de Metepec", lat=19.2537, lng=-99.6047,
         descripcion="Posible intoxicación por alimentos, vómito y mareo", prioridad="Baja",
         avance="cerrar", km=11, destino="Hospital General ISSSTE"),
    dict(paciente_nombre="Miguel Ángel Cerón", paciente_edad="62", paciente_sexo="Masculino",
         direccion="Col. San Lorenzo Tepaltitlán, Toluca", lat=19.3150, lng=-99.6290,
         descripcion="Dolor de pecho intenso desde hace 20 minutos", prioridad="Alta",
         saturacion_oxigeno=90, frecuencia_cardiaca=124, escala_glasgow=15, avance="llegada"),
    dict(paciente_nombre="Andrea Valdés Núñez", paciente_edad="24", paciente_sexo="Femenino",
         direccion="Av. Solidaridad Las Torres, Metepec", lat=19.2560, lng=-99.6020,
         descripcion="Atropellamiento, golpe en pierna", prioridad="Alta",
         saturacion_oxigeno=97, frecuencia_cardiaca=105, escala_glasgow=15, avance="salida"),
    dict(paciente_nombre="Ignacio Fuentes Peralta", paciente_edad="80", paciente_sexo="Masculino",
         direccion="Col. La Merced, Toluca", lat=19.2830, lng=-99.6480,
         descripcion="Adulto mayor desorientado, posible hipoglucemia", prioridad="Media",
         saturacion_oxigeno=95, frecuencia_cardiaca=90, escala_glasgow=13, avance="asignar"),
    dict(paciente_nombre="Lorena Bastida Cruz", paciente_edad="43", paciente_sexo="Femenino",
         direccion="Aeropuerto Internacional de Toluca", lat=19.3371, lng=-99.5660,
         descripcion="Crisis convulsiva en sala de espera", prioridad="Alta",
         saturacion_oxigeno=93, frecuencia_cardiaca=112, escala_glasgow=12, avance="asignar"),
    dict(paciente_nombre="Héctor Ramírez Solís", paciente_edad="33", paciente_sexo="Masculino",
         direccion="Carretera Toluca-Naucalpan, San Cristóbal Huichochitlán", lat=19.3300, lng=-99.6400,
         descripcion="Choque múltiple, tres personas lesionadas", prioridad="Alta", ambulancias_requeridas=2,
         avance="asignar"),
    dict(paciente_nombre="Silvia Contreras León", paciente_edad="55", paciente_sexo="Femenino",
         direccion="Col. Seminario, Toluca", lat=19.2780, lng=-99.6700,
         descripcion="Esguince de tobillo al bajar escaleras", prioridad="Baja", avance="asignar"),
]

# Reportes de las cuentas de Usuario (como desde su perfil). avance igual que arriba.
REPORTES = [
    ("maria.lopez", dict(canal="llamada", tipo="Caída o fractura", descripcion="Mi mamá se cayó en el baño",
                         direccion="Calle Morelos 210, Col. Centro, Lerma", lat=19.2846, lng=-99.5113,
                         paciente_nombre="Carmen Sánchez", paciente_edad="74"), "cerrar"),
    ("jorge.mendez", dict(canal="mensaje", tipo="Accidente de tránsito", descripcion="Choque de moto contra auto",
                          direccion="Av. Comonfort y Av. Las Torres, Toluca", lat=19.2700, lng=-99.6600,
                          paciente_nombre="", personas=2), "cerrar"),
    ("sofia.reyes", dict(canal="mensaje", tipo="Dificultad para respirar", descripcion="Mi hijo tiene mucha tos y le falta el aire",
                         direccion="San Buenaventura, Toluca", lat=19.2600, lng=-99.6800,
                         paciente_nombre="Emiliano Reyes", paciente_edad="9"), "asignar"),
    ("maria.lopez", dict(canal="llamada", tipo="Herida o sangrado", descripcion="Vecino se cortó con un vidrio",
                         direccion="Calle Juárez 45, San Mateo Atenco", lat=19.2690, lng=-99.5370,
                         paciente_nombre="Pedro Galindo"), "asignar"),
]

CARGAS = [("I220-51", "op.raul"), ("NSJ-51", "op.ernesto"), ("CRT-51", "op.patricia")]   # placa, operador
PRECIO_LITRO = 24.5


def marcar(db, coleccion: str, filtro: dict) -> None:
    db[coleccion].update_one(filtro, {"$set": {"datos_prueba": True}})


def main() -> int:
    ap = argparse.ArgumentParser(description="Carga datos de prueba en Emergexia")
    ap.add_argument("--password", required=True, help="contraseña para todas las cuentas de prueba (mín. 8)")
    args = ap.parse_args()
    if len(args.password) < 8:
        print("La contraseña debe tener al menos 8 caracteres.")
        return 1

    from app import dbschema, mongo, repository
    from app.config import settings
    try:
        mongo.connect()
        dbschema.ensure_schema()
        repository.seed_admin()
    except RuntimeError as exc:
        print(f"\n{exc}")
        return 1

    from fastapi import HTTPException
    from app.routers import flota as flota_api, modules, portal
    from app.schemas import (AmbulanceIn, CargaCombustibleIn, EmergencyIn, EventoEmergenciaIn, OperatorIn,
                             ParamedicIn, ReporteUsuarioIn)
    db = mongo.get_db()
    pw = args.password
    responsable = settings.admin_username
    accesos: list[tuple[str, str, str]] = []

    def crear(path: str, body):
        router = next(r for r in modules.routers if r.prefix == f"/api/{path}")
        ruta = next(r for r in router.routes if "POST" in r.methods and r.path == f"/api/{path}")
        return ruta.endpoint(body=body)

    def existe_usuario(u: str) -> bool:
        return db["users"].find_one({"username": u}) is not None

    print("=" * 60)
    print(f"EMERGEXIA · datos de prueba en la base '{db.name}'")
    print("=" * 60)

    # ── Cuentas de la central y de usuarios ──
    for usuario, nombre, rol in PERSONAL:
        if existe_usuario(usuario):
            print(f"  ya existía {usuario} (no se cambió)")
        else:
            repository.create_user(usuario, pw, nombre, rol)
            marcar(db, "users", {"username": usuario})
        accesos.append((usuario, nombre, rol))
    for usuario, nombre, tel in USUARIOS:
        if existe_usuario(usuario):
            print(f"  ya existía {usuario} (no se cambió)")
        else:
            repository.create_user(usuario, pw, nombre, "Usuario")
            db["users"].update_one({"username": usuario}, {"$set": {"telefono": tel, "datos_prueba": True}})
        accesos.append((usuario, nombre, "Usuario"))

    # ── Operadores y paramédicos (con su cuenta) ──
    nombres_op = {}
    for usuario, nombres, apellidos, cel, turno, exp in OPERADORES:
        nombre = f"{nombres} {apellidos}"
        nombres_op[usuario] = nombre
        if existe_usuario(usuario):
            print(f"  ya existía {usuario} (no se cambió)")
        else:
            op = crear("operadores", OperatorIn(nombres=nombres, apellidos=apellidos, celular=cel,
                                                correo=f"{usuario.replace('op.', '')}@emergexia.mx", turno=turno,
                                                experiencia=exp, extension=str(300 + len(nombres_op)),
                                                foto=FOTO_RELLENO, usuario=usuario, password=pw))
            marcar(db, "operators", {"id": op["id"]})
            marcar(db, "users", {"username": usuario})
        accesos.append((usuario, nombre, "Operador"))
    for usuario, nombres, apellidos, cel, nivel, turno, sangre in PARAMEDICOS:
        nombre = f"{nombres} {apellidos}"
        if existe_usuario(usuario):
            print(f"  ya existía {usuario} (no se cambió)")
        else:
            pm = crear("paramedicos", ParamedicIn(nombres=nombres, apellidos=apellidos, celular=cel,
                                                  correo=f"{usuario.replace('tum.', '')}@emergexia.mx", nivel=nivel,
                                                  turno=turno, tipo_sangre=sangre, cedula=f"TUM-{cel[-4:]}",
                                                  contacto_emergencia="7220000000", foto=FOTO_RELLENO,
                                                  usuario=usuario, password=pw))
            marcar(db, "paramedics", {"id": pm["id"]})
            marcar(db, "users", {"username": usuario})
        accesos.append((usuario, nombre, "Paramédico"))

    # ── Ambulancias ──
    for placa, tipo, hospital, op, gas, km, marca, modelo, anio in AMBULANCIAS:
        if db["ambulances"].find_one({"placa": placa}):
            print(f"  ya existía la ambulancia {placa} (no se cambió)")
            continue
        conductor = nombres_op[op]
        if db["ambulances"].find_one({"conductor": conductor}):
            conductor = ""      # ese operador ya maneja otra ambulancia
        a = crear("ambulancias", AmbulanceIn(placa=placa, tipo=tipo, hospital=hospital, conductor=conductor,
                                             combustible_pct=gas, kilometraje=km, marca=marca, modelo=modelo, anio=anio))
        marcar(db, "ambulances", {"id": a["id"]})
    print(f"  ambulancias listas: {', '.join(a[0] for a in AMBULANCIAS)}")

    def cargar_gasolina() -> None:
        if db["cargas_combustible"].find_one({"datos_prueba": True}):
            return
        for placa, op in CARGAS:
            amb = db["ambulances"].find_one({"placa": placa}, {"_id": 0})
            if not amb or flota_api.flota.normalizar(amb)["estado"] == "Ocupada":
                continue
            a = flota_api.flota.normalizar(amb)
            litros = round(a["tanque_litros"] * (100 - a["combustible_pct"]) / 100 - 1, 1)   # casi lleno
            if litros < 5:
                continue
            try:
                flota_api.registrar_carga(amb["id"], CargaCombustibleIn(operador=nombres_op[op], litros=litros,
                                                                        costo=round(litros * PRECIO_LITRO, 2),
                                                                        estacion="Gasolinera Pemex Tollocan"),
                                          responsable, verificado=False)
                ultima = db["cargas_combustible"].find_one({"ambulancia": placa}, {"id": 1}, sort=[("id", -1)])
                marcar(db, "cargas_combustible", {"id": ultima["id"]})
            except (HTTPException, ValueError) as exc:
                print(f"  carga de {placa} no registrada: {getattr(exc, 'detail', exc)}")

    # ── Emergencias ──
    if db["emergencies"].find_one({"datos_prueba": True}):
        print("  las emergencias de prueba ya estaban cargadas: no se repiten")
        cargar_gasolina()
    else:
        def avanzar(em_id: int, avance: str, km: float = 10, destino: str | None = None) -> None:
            em = flota_api._emergencia(em_id)
            if avance == "asignar" or not flota_api._placas(em):
                return
            pasos = {"salida": ["salida"], "llegada": ["salida", "llegada"],
                     "cerrar": ["salida", "llegada", "traslado", "cierre"]}[avance]
            for paso in pasos:
                try:
                    flota_api.evento(em_id, EventoEmergenciaIn(tipo=paso, km_recorridos=km if paso == "cierre" else None,
                                                               hospital_destino=destino if paso == "traslado" else None),
                                     responsable)
                except HTTPException as exc:
                    print(f"    {em['folio']}: no se pudo registrar «{paso}» ({exc.detail})")
                    return

        def crear_emergencia(origen: str, dato) -> tuple[int, str, float, str | None]:
            if origen == "central":
                e = dict(dato)
                avance, km, destino = e.pop("avance"), e.pop("km", 10), e.pop("destino", None)
                lat, lng = e.pop("lat"), e.pop("lng")
                datos = {**EmergencyIn(**e).model_dump(), "lat": lat, "lng": lng}
                em = repository.insert_row("emergencies", datos)       # igual que POST /api/emergencias
                marcar(db, "emergencies", {"id": em["id"]})
                flota_api.asignar_automatico(em["id"], responsable)
                return em["id"], avance, km, destino
            usuario, cuerpo, avance = dato
            user = db["users"].find_one({"username": usuario}, {"_id": 0})
            r = portal.reportar(ReporteUsuarioIn(**cuerpo), user)       # igual que POST /api/usuario/reportes
            marcar(db, "emergencies", {"id": r["id"]})
            return r["id"], avance, 14, None

        todas = [("central", e) for e in EMERGENCIAS] + [("reporte", r) for r in REPORTES]
        cerradas = [t for t in todas if (t[1]["avance"] if t[0] == "central" else t[1][2]) == "cerrar"]
        abiertas = [t for t in todas if t not in cerradas]
        # Las cerradas van en tandas de 6: así se reparten entre varias ambulancias.
        for i in range(0, len(cerradas), 6):
            tanda = [crear_emergencia(*t) for t in cerradas[i:i + 6]]
            for em_id, avance, km, destino in tanda:
                avanzar(em_id, avance, km, destino)
        cargar_gasolina()
        for t in abiertas:
            avanzar(*crear_emergencia(*t))

    # ── Resumen ──
    ems = list(db["emergencies"].find({"datos_prueba": True}, {"_id": 0, "folio": 1, "estado": 1}))
    por_estado: dict[str, int] = {}
    for e in ems:
        por_estado[e["estado"]] = por_estado.get(e["estado"], 0) + 1
    print("\nEmergencias de prueba: " + ", ".join(f"{n} {k}" for k, n in sorted(por_estado.items())))
    print("\nACCESOS (todas con la contraseña que diste):")
    for usuario, nombre, rol in accesos:
        print(f"  {rol:<12} {usuario:<20} {nombre}")
    print(f"\nEl administrador sigue siendo '{settings.admin_username}' con la contraseña de ADMIN_PASSWORD en .env.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
