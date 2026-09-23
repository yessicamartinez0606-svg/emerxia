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
    role: Literal["Administrador", "Despachador", "Supervisor"] = "Despachador"


class ForgotPasswordIn(BaseModel):
    username: str = Field(min_length=1)


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10)
    password: str = Field(min_length=6)


class DoctorIn(BaseModel):
    nombres: str = Field(min_length=2)
    apellidos: str = Field(min_length=2)
    fecha_nacimiento: str = ""
    direccion: str = ""
    celular: str = Field(min_length=10, max_length=20)
    correo: str = Field(min_length=5)
    contacto_emergencia: str = ""
    especialidad: str = Field(min_length=2)
    cedula_profesional: str = Field(min_length=2)
    turno: Literal["Matutino", "Vespertino", "Nocturno"] = "Matutino"
    estado: Literal["Activo", "En guardia", "Descanso"] = "Activo"
    # Foto de referencia (igual que en Operadores): se usa para verificar por
    # reconocimiento facial que es el mismo doctor antes de asignarlo a una emergencia.
    foto: str = Field(min_length=1, description="Foto de referencia en base64 (data URL)")

    @field_validator("celular")
    @classmethod
    def _celular_valido(cls, v: str) -> str:
        return _valida_celular(v)

    @field_validator("correo")
    @classmethod
    def _correo_valido(cls, v: str) -> str:
        return _valida_correo(v)


class AmbulanceIn(BaseModel):
    placa: str = Field(min_length=2)
    tipo: Literal["Básica", "Avanzada"] = "Básica"
    conductor: str = ""
    estado: Literal["Disponible", "En servicio", "Mantenimiento"] = "Disponible"


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

    # Asignación (idealmente elegidos de las bases de operadores/ambulancias/doctores)
    operador: str | None = None
    ambulancia: str | None = None
    doctor: str | None = None


class EmergencyPatch(BaseModel):
    """Cambios parciales sobre una emergencia ya registrada (solo se aplican los
    campos que vienen en la petición). Se usa, por ejemplo, para asignar al
    operador una vez que su rostro fue validado."""
    operador: str | None = None
    ambulancia: str | None = None
    doctor: str | None = None
    estado: Literal["Pendiente", "Asignada", "En curso", "Cerrada"] | None = None


class OperatorIn(BaseModel):
    nombres: str = Field(min_length=2)
    apellidos: str = Field(min_length=2)
    celular: str = Field(min_length=10, max_length=20)
    correo: str = Field(min_length=5)
    turno: Literal["Matutino", "Vespertino", "Nocturno"] = "Matutino"
    extension: str = ""
    estado: Literal["En línea", "Desconectado"] = "En línea"
    # Foto de referencia (imagen en base64, formato data URL) tomada al registrar
    # al operador. Se usa después para verificar por reconocimiento facial que es
    # el mismo operador antes de asignarlo a una emergencia y antes de que salga
    # la ambulancia.
    foto: str = Field(min_length=1, description="Foto de referencia en base64 (data URL)")

    @field_validator("celular")
    @classmethod
    def _celular_valido(cls, v: str) -> str:
        return _valida_celular(v)

    @field_validator("correo")
    @classmethod
    def _correo_valido(cls, v: str) -> str:
        return _valida_correo(v)


class VerificacionIn(BaseModel):
    operador: str = Field(min_length=1)
    contexto: Literal["asignacion", "salida"]
    coincide: bool = True
    distancia: float | None = None
    emergencia_folio: str | None = None
