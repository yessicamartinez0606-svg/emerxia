// Misma lógica que backend/app/logica.py, para dar retroalimentación inmediata en el formulario.
// p = prioridad alta · s = doctor disponible · t = rostro del doctor · u = ambulancia disponible
// v = ambulancia avanzada
//   D = s ∧ t        doctor habilitado
//   M = u ∧ (p → v)  ambulancia adecuada

export const implica = (a, b) => !a || b

export function evaluarFormulario({ prioridad, doctor, doctorVerificado, ambulancia }) {
  const p = prioridad === 'Alta'
  const s = !!doctor && doctor.estado !== 'Descanso'
  const t = !!doctor && !!doctorVerificado
  const u = ['Libre', 'Disponible'].includes(ambulancia?.estado)   // Disponible = nombre anterior
  const v = ambulancia?.tipo === 'Avanzada'

  const doctorHabilitado = s && t
  const ambulanciaAdecuada = u && implica(p, v)

  const motivos = []
  if (!doctor) motivos.push('Falta elegir un doctor.')
  else if (!s) motivos.push('El doctor está en Descanso.')
  else if (!t) motivos.push('Falta validar el rostro del doctor (Face ID).')
  if (!ambulancia) motivos.push('Falta elegir una ambulancia.')
  else if (!u) motivos.push('La ambulancia no está Libre.')
  else if (p && !v) motivos.push('Prioridad Alta: se requiere una ambulancia Avanzada.')

  return { p, s, t, u, v, doctorHabilitado, ambulanciaAdecuada, motivos }
}
