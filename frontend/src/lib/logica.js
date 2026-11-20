// Misma lógica que backend/app/logica.py, para explicar en el formulario cómo se asignará.
// p = prioridad alta · u = ambulancia disponible · v = ambulancia avanzada
//   M = u ∧ (p → v)  ambulancia adecuada
// La asignación es automática (backend: routers/flota.py → asignar_automatico): entre las
// ambulancias libres se eligen primero las Avanzadas, así que con prioridad Alta se cumple
// p → v siempre que haya una Avanzada libre.

export const implica = (a, b) => !a || b

export function evaluarFormulario({ prioridad, ambulancia }) {
  const p = prioridad === 'Alta'
  const u = ['Libre', 'Disponible'].includes(ambulancia?.estado)   // Disponible = nombre anterior
  const v = ambulancia?.tipo === 'Avanzada'
  const ambulanciaAdecuada = u && implica(p, v)

  const motivos = []
  if (ambulancia && !u) motivos.push('La ambulancia no está Libre.')
  else if (ambulancia && p && !v) motivos.push('Prioridad Alta: se requiere una ambulancia Avanzada.')

  return { p, u, v, ambulanciaAdecuada, motivos }
}
