import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Regex simple para correo (sin depender del paquete "email-validator": ya nos pasó una vez
# que faltaba instalado y tumbó el backend con un ImportError en pleno arranque).
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _valida_correo(v: str) -> str:
    v = v.strip()
    if not EMAIL_RE.match(v):
        raise ValueError("Escribe un correo válido, con \"@\" y dominio (ej. nombre@correo.com).")
    return v.lower()


def _valida_celular(v: str) -> str:
    """Exige exactamente 10 dígitos (formato de celular en México). Se permite escribirlo con
    espacios o guiones ("55 1234 5678"), pero al final deben quedar 10 números."""
    digits = re.sub(r"[\s()\-]", "", v)
    if not digits.isdigit() or len(digits) != 10:
        raise ValueError("El celular debe tener exactamente 10 dígitos (solo números, ej. 5512345678).")
    return v.strip()


class LoginIn(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2)
    username: str = Field(min_length=3)
    password: str = Field(min_length=6)
    # El registro público solo crea cuentas de Usuario (quien reporta emergencias). Las de la
    # central las crea el Administrador en Cuentas; las de operadores y paramédicos, en sus
    # módulos. (Antes aquí se podía elegir Administrador: cualquiera se volvía administrador.)
    role: Literal["Usuario"] = "Usuario"
    telefono: str = ""


class RostroIn(BaseModel):
    """Descriptor facial de 128 números que calcula face-api.js en el navegador."""
    descriptor: list[float] = Field(min_length=128, max_length=128)


class ReporteUsuarioIn(BaseModel):
    """Emergencia reportada por una persona desde su perfil de Usuario."""
    canal: Literal["mensaje", "llamada"] = "mensaje"
    tipo: str = Field(min_length=2)
    descripcion: str = ""
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    direccion: str = ""
    referencias: str = ""
    paciente_nombre: str = ""
    paciente_edad: str = ""
    telefono: str = ""
    personas: int = Field(1, ge=1, le=50)
    # Preguntas de sí/no (app/reportes.py): clave → True «Sí», False «No», None «No sé».
    respuestas: dict[str, bool | None] = Field(default_factory=dict, max_length=30)


class CargaOperadorIn(BaseModel):
    litros: float = Field(gt=0, le=500)
    costo: float | None = Field(None, ge=0)
    kilometraje: float | None = Field(None, ge=0)
    estacion: str = ""
    notas: str = ""


class ForgotPasswordIn(BaseModel):
    username: str = Field(min_length=1)


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10)
    password: str = Field(min_length=6)


def _numero(default: float):
    """Los formularios mandan los números como texto; vacío = valor por defecto."""
    def convertir(v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return default
        return v
    return convertir


class AmbulanceIn(BaseModel):
    placa: str = Field(min_length=2)
    tipo: Literal["Básica", "Avanzada"] = "Básica"
    # Hospital donde está la ambulancia (ver app/flota.py y app/genetico.py).
    hospital: str = "Hospital IMSS 220"
    # Operador que la maneja: es quien registra sus cargas de gasolina.
    conductor: str = ""
    estado: Literal["Libre", "En reparación", "Fuera de servicio"] = "Libre"
    tanque_litros: float = Field(80, gt=0, le=500)
    rendimiento_km_l: float = Field(6, gt=0, le=50)
    combustible_pct: float = Field(100, ge=0, le=100)
    kilometraje: float = Field(0, ge=0)
    # Vehículo (app/vehiculos.py): marca y modelo confirmados con la API vPIC de la NHTSA.
    marca: str = ""
    modelo: str = ""
    anio: int | None = Field(None, ge=1990, le=2030)
    motor: str = ""
    model_id: int | None = None
    fuente_vehiculo: str = ""
    _anio = field_validator("anio", "model_id", mode="before")(_numero(None))

    _tanque = field_validator("tanque_litros", mode="before")(_numero(80))
    _rend = field_validator("rendimiento_km_l", mode="before")(_numero(6))
    _comb = field_validator("combustible_pct", mode="before")(_numero(100))
    _km = field_validator("kilometraje", mode="before")(_numero(0))

    @field_validator("hospital")
    @classmethod
    def _hospital_valido(cls, v: str) -> str:
        from .flota import NOMBRES_HOSPITALES
        if v not in NOMBRES_HOSPITALES:
            raise ValueError("Elige uno de los hospitales de la lista.")
        return v


class EmergencyIn(BaseModel):
    # Datos del paciente
    paciente_nombre: str = Field(min_length=2)
    paciente_edad: str = ""
    paciente_sexo: Literal["Masculino", "Femenino", "Otro"] = "Otro"
    paciente_telefono: str = ""
    direccion: str = Field(min_length=3)

    # Datos de la emergencia
    descripcion: str = Field(min_length=3)
    prioridad: Literal["Alta", "Media", "Baja"] = "Media"
    estado: Literal["Pendiente", "Asignada", "En curso", "Cerrada"] = "Pendiente"

    @field_validator("paciente_telefono")
    @classmethod
    def _tel_paciente_valido(cls, v: str) -> str:
        return _valida_celular(v) if v.strip() else v

    # Asignación: las ambulancias (y el operador que maneja la primera) se asignan solas al
    # guardar la emergencia (routers/flota.py → asignar_automatico).
    operador: str | None = None
    ambulancia: str | None = None
    # Cuántas ambulancias necesita (p. ej. un choque múltiple). Si son más de las que tiene
    # libres el hospital base, las demás se piden a otros hospitales (app/flota.py).
    ambulancias_requeridas: int = Field(1, ge=1, le=20)

    # Signos vitales reportados (opcionales). Con los tres, el modelo de triaje (app/triaje.py)
    # estima si la emergencia es crítica.
    saturacion_oxigeno: float | None = Field(None, ge=50, le=100)
    frecuencia_cardiaca: float | None = Field(None, ge=20, le=250)
    escala_glasgow: int | None = Field(None, ge=3, le=15)

    _req = field_validator("ambulancias_requeridas", mode="before")(_numero(1))
    _signos = field_validator("saturacion_oxigeno", "frecuencia_cardiaca", "escala_glasgow", mode="before")(_numero(None))


class EmergencyPatch(BaseModel):
    """Cambios parciales sobre una emergencia ya registrada (solo se aplican los
    campos que vienen en la petición). Se usa, por ejemplo, para asignar al
    operador una vez que su rostro fue validado."""
    operador: str | None = None
    ambulancia: str | None = None
    estado: Literal["Pendiente", "Asignada", "En curso", "Cerrada"] | None = None


USUARIO_RE = re.compile(r"^[a-z0-9._-]{3,40}$")


def _valida_usuario(v: str) -> str:
    v = v.strip().lower()
    if not USUARIO_RE.match(v):
        raise ValueError("El usuario debe tener de 3 a 40 caracteres: letras sin acento, números, punto, guion o guion bajo (sin espacios).")
    return v


class CredencialesIn(BaseModel):
    """Usuario y contraseña con los que entra un operador o un paramédico. Al cambiarlos,
    los dos son opcionales: se cambia solo lo que venga."""
    usuario: str | None = None
    password: str | None = Field(None, min_length=6)

    @field_validator("usuario")
    @classmethod
    def _usuario_valido(cls, v: str | None) -> str | None:
        return _valida_usuario(v) if v is not None else v


class OperatorIn(BaseModel):
    nombres: str = Field(min_length=2)
    apellidos: str = Field(min_length=2)
    celular: str = Field(min_length=10, max_length=20)
    correo: str = Field(min_length=5)
    turno: Literal["Matutino", "Vespertino", "Nocturno"] = "Matutino"
    extension: str = ""
    estado: Literal["En línea", "Desconectado"] = "En línea"
    # Años de experiencia manejando ambulancia (lo usa el modelo "¿llega a tiempo?", app/a_tiempo.py).
    experiencia: float | None = Field(None, ge=0, le=50)
    _exp = field_validator("experiencia", mode="before")(_numero(None))
    # Foto de referencia (imagen en base64, formato data URL) tomada al registrar
    # al operador. Se usa después para verificar por reconocimiento facial que es
    # el mismo operador antes de asignarlo a una emergencia y antes de que salga
    # la ambulancia.
    foto: str = Field(min_length=1, description="Foto de referencia en base64 (data URL)")

    # Acceso al sistema (además del rostro). La contraseña no se guarda en el registro del
    # operador: se guarda cifrada en su cuenta (colección users).
    usuario: str = Field(min_length=3)
    password: str = Field(min_length=6)

    @field_validator("celular")
    @classmethod
    def _celular_valido(cls, v: str) -> str:
        return _valida_celular(v)

    @field_validator("correo")
    @classmethod
    def _correo_valido(cls, v: str) -> str:
        return _valida_correo(v)

    _usuario = field_validator("usuario")(_valida_usuario)


NIVELES_PARAMEDICO = ("TUM Básico", "TUM Intermedio", "TUM Avanzado", "Paramédico")


class ParamedicIn(BaseModel):
    """Paramédico (Técnico en Urgencias Médicas) que va en una ambulancia."""
    nombres: str = Field(min_length=2)
    apellidos: str = Field(min_length=2)
    celular: str = Field(min_length=10, max_length=20)
    correo: str = Field(min_length=5)
    nivel: Literal["TUM Básico", "TUM Intermedio", "TUM Avanzado", "Paramédico"] = "TUM Básico"
    cedula: str = ""                      # cédula o número de certificación
    turno: Literal["Matutino", "Vespertino", "Nocturno"] = "Matutino"
    estado: Literal["En servicio", "Fuera de turno", "Baja"] = "En servicio"
    # La ambulancia NO se elige aquí: va en la de la emergencia a la que lo asigna la central
    # (2 paramédicos por emergencia, confirmados con su rostro; ver routers/flota.py).
    tipo_sangre: str = ""
    contacto_emergencia: str = ""
    # Foto de su rostro (data URL): con ella entra con Face ID, igual que el operador.
    foto: str = Field(min_length=1, description="Foto de referencia en base64 (data URL)")
    usuario: str = Field(min_length=3)
    password: str = Field(min_length=6)

    @field_validator("celular")
    @classmethod
    def _celular_valido(cls, v: str) -> str:
        return _valida_celular(v)

    @field_validator("correo")
    @classmethod
    def _correo_valido(cls, v: str) -> str:
        return _valida_correo(v)

    _usuario = field_validator("usuario")(_valida_usuario)


class AtencionParamedicoIn(BaseModel):
    """Lo que captura el paramédico de su paciente: signos vitales y la atención que le dio."""
    saturacion_oxigeno: float | None = Field(None, ge=50, le=100)
    frecuencia_cardiaca: float | None = Field(None, ge=20, le=250)
    escala_glasgow: int | None = Field(None, ge=3, le=15)
    presion_arterial: str = Field("", max_length=20)          # p. ej. "120/80"
    temperatura: float | None = Field(None, ge=30, le=45)
    glucosa: float | None = Field(None, ge=10, le=900)
    observaciones: str = Field("", max_length=2000)            # atención brindada, medicamentos, etc.
    _signos = field_validator("saturacion_oxigeno", "frecuencia_cardiaca", "escala_glasgow", "temperatura", "glucosa",
                              mode="before")(_numero(None))


class VerificacionIn(BaseModel):
    operador: str = Field(min_length=1)
    contexto: Literal["asignacion", "salida"]
    coincide: bool = True
    distancia: float | None = None
    emergencia_folio: str | None = None


class AmbulanciaPatch(BaseModel):
    """Cambios de la ficha de la ambulancia (cada uno queda en el historial)."""
    estado: Literal["Libre", "En reparación", "Fuera de servicio"] | None = None
    hospital: str | None = None
    conductor: str | None = None
    tanque_litros: float | None = Field(None, gt=0, le=500)
    rendimiento_km_l: float | None = Field(None, gt=0, le=50)
    motivo: str = ""


class CargaCombustibleIn(BaseModel):
    operador: str = Field(min_length=2)
    litros: float = Field(gt=0, le=500)
    costo: float | None = Field(None, ge=0)
    kilometraje: float | None = Field(None, ge=0)
    estacion: str = ""
    notas: str = ""
    # Rostro del conductor tomado en la central (128 números). El servidor lo compara con su
    # foto y decide si la carga queda verificada; el navegador ya no lo decide.
    descriptor: list[float] | None = Field(None, min_length=128, max_length=128)


class AsignarIn(BaseModel):
    cantidad: int | None = Field(None, ge=1, le=20)
    # Placas que eligió el administrador a mano (van primero si están listas).
    placas: list[str] = Field(default_factory=list)
    confirmar: bool = False


class ParamedicoEmergenciaIn(BaseModel):
    """Rostro tomado en la central (128 números). El servidor busca a qué paramédico
    corresponde y, si está disponible, lo manda a la emergencia."""
    descriptor: list[float] = Field(min_length=128, max_length=128)


class OperadorEmergenciaIn(BaseModel):
    """Rostro del operador tomado en la central (128 números). El servidor busca a qué
    operador corresponde y lo deja a cargo de la emergencia."""
    descriptor: list[float] = Field(min_length=128, max_length=128)


class EventoEmergenciaIn(BaseModel):
    tipo: Literal["salida", "llegada", "traslado", "cierre"]
    km_recorridos: float | None = Field(None, ge=0, le=2000)
    hospital_destino: str | None = None
    observaciones: str = ""
