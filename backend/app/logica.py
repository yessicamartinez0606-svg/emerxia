"""Lógica proposicional de Emergexia (lado médico).

Funciones puras: reciben proposiciones ya calculadas (V/F) y devuelven el resultado
de cada regla. No tocan la base de datos, así que se pueden probar solas.

    O = q ∧ r              operador habilitado
    D = s ∧ t              doctor habilitado
    M = u ∧ (p → v)        ambulancia adecuada
    A = O ∧ D ∧ M          la emergencia puede pasar a Asignada
    S = g ∧ x              la ambulancia puede salir (En curso)
    L = p ∧ ¬A             alerta: prioridad alta sin poder asignarse
"""
from dataclasses import dataclass, asdict


def implica(a: bool, b: bool) -> bool:
    """a → b  es falso solo cuando a es verdadero y b es falso."""
    return (not a) or b


@dataclass(frozen=True)
class Proposiciones:
    prioridad_alta: bool          # p
    operador_en_linea: bool       # q
    rostro_operador: bool         # r
    doctor_disponible: bool       # s
    rostro_doctor: bool           # t
    ambulancia_disponible: bool   # u
    ambulancia_avanzada: bool     # v
    rostro_salida: bool = False   # x
    estado_asignada: bool = False # g


def evaluar(P: Proposiciones) -> dict:
    operador_ok = P.operador_en_linea and P.rostro_operador                              # R1
    doctor_ok = P.doctor_disponible and P.rostro_doctor                                  # R2
    ambulancia_ok = P.ambulancia_disponible and implica(P.prioridad_alta, P.ambulancia_avanzada)  # R3
    asignable = operador_ok and doctor_ok and ambulancia_ok                              # R4
    puede_salir = P.estado_asignada and P.rostro_salida                                  # R5
    alerta = P.prioridad_alta and not asignable                                          # R6

    # De Morgan sobre R4: cada condición que falla es un motivo.
    motivos = []
    if not P.operador_en_linea:
        motivos.append("El operador no está En línea.")
    if not P.rostro_operador:
        motivos.append("Falta validar el rostro del operador (Face ID).")
    if not P.doctor_disponible:
        motivos.append("El doctor está en Descanso o no existe.")
    if not P.rostro_doctor:
        motivos.append("Falta validar el rostro del doctor (Face ID).")
    if not P.ambulancia_disponible:
        motivos.append("La ambulancia no está Libre.")
    if P.prioridad_alta and not P.ambulancia_avanzada:
        motivos.append("La emergencia es de prioridad Alta y requiere ambulancia Avanzada.")

    return {
        "proposiciones": asdict(P),
        "operador_habilitado": operador_ok,
        "doctor_habilitado": doctor_ok,
        "ambulancia_adecuada": ambulancia_ok,
        "asignable": asignable,
        "puede_salir": puede_salir,
        "alerta": alerta,
        "motivos": motivos,
    }
