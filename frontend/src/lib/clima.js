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
