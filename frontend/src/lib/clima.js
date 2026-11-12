// Clima de las zonas (Open-Meteo, vía backend app/clima.py) y tiempo estimado de llegada
// con el árbol de regresión (app/eta.py).
import { api } from './api.js'

export const verClima = () => api('/clima')
export const simularLluvia = (zona, lluvia) => api('/clima/simular', { method: 'POST', body: { zona, lluvia } })
export const modeloLlegada = () => api('/eta/modelo')
export const estimarLlegada = (datos) => api('/eta/estimar', { method: 'POST', body: datos })
export const llegadaEmergencia = (id, km) => api(`/eta/emergencias/${id}${km ? `?km=${km}` : ''}`)

export const PERSONAL = ['Administrador', 'Despachador', 'Supervisor']

export const fmtActualizado = (seg) => {
  if (!seg) return ''
  return new Date(seg * 1000).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })
}

// Ícono simple según el código WMO.
export function tipoCielo(z) {
  if (z.tormenta) return 'tormenta'
  if (z.lluvia) return 'lluvia'
  if (z.codigo == null) return 'nada'
  if (z.codigo >= 45 && z.codigo <= 48) return 'niebla'
  if (z.codigo >= 2) return 'nublado'
  return 'sol'
}

// Práctica 04: ¿llega a tiempo? (árbol de decisión con profundidad elegida por validación)
export const modeloATiempo = () => api('/ia/a-tiempo/modelo')
export const estimarATiempo = (datos) => api('/ia/a-tiempo/estimar', { method: 'POST', body: datos })
export const aTiempoEmergencia = (id, km) => api(`/ia/a-tiempo/emergencias/${id}${km ? `?km=${km}` : ''}`)

// Práctica 05: triaje (árbol vs bosque aleatorio vs KNN)
export const modeloTriaje = () => api('/ia/triaje/modelo')
export const estimarTriaje = (signos) => api('/ia/triaje/estimar', { method: 'POST', body: signos })
export const colaTriaje = () => api('/ia/triaje/cola')
export const triajeEmergencia = (id) => api(`/ia/triaje/emergencias/${id}`)

export const pct = (x, d = 0) => `${(x * 100).toFixed(d)} %`
