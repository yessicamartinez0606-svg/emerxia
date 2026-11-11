"""Evalúa las reglas de lógica proposicional (ver app/logica.py) para una emergencia.

La comparación de rostros sucede en el navegador, así que el frontend manda el resultado
(rostro_operador, rostro_doctor, rostro_salida). Los estados de operador, doctor y ambulancia
se leen de MongoDB, no se aceptan del cliente.
"""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..logica import Proposiciones, evaluar
from ..repository import list_rows
from ..security import current_username

router = APIRouter(prefix="/api/logica", tags=["logica"], dependencies=[Depends(current_username)])


class EvaluacionIn(BaseModel):
    prioridad: Literal["Alta", "Media", "Baja"] = "Media"
    estado: Literal["Pendiente", "Asignada", "En curso", "Cerrada"] = "Pendiente"
    operador: str | None = None      # nombre, como en la colección operators
    doctor: str | None = None        # nombre, como en la colección doctors
    ambulancia: str | None = None    # placa, como en la colección ambulances
    rostro_operador: bool = False
    rostro_doctor: bool = False
    rostro_salida: bool = False


def _buscar(coleccion: str, campo: str, valor: str | None) -> dict:
    if not valor:
        return {}
    return next((r for r in list_rows(coleccion) if r.get(campo) == valor), {})


@router.post("/evaluar")
def evaluar_emergencia(body: EvaluacionIn):
    operador = _buscar("operators", "nombre", body.operador)
    doctor = _buscar("doctors", "nombre", body.doctor)
    ambulancia = _buscar("ambulances", "placa", body.ambulancia)

    proposiciones = Proposiciones(
        prioridad_alta=body.prioridad == "Alta",                                  # p
        operador_en_linea=operador.get("estado") == "En línea",                   # q
        rostro_operador=body.rostro_operador and bool(operador),                  # r
        doctor_disponible=bool(doctor) and doctor.get("estado") != "Descanso",    # s
        rostro_doctor=body.rostro_doctor and bool(doctor),                        # t
        ambulancia_disponible=ambulancia.get("estado") in ("Libre", "Disponible"),   # u (Disponible = nombre anterior)
        ambulancia_avanzada=ambulancia.get("tipo") == "Avanzada",                 # v
        rostro_salida=body.rostro_salida and bool(operador),                      # x
        estado_asignada=body.estado == "Asignada",                                # g
    )
    return evaluar(proposiciones)
