// Flota de ambulancias: hospital, estatus, conductor, gasolina, historial y reportes.
// Las reglas viven en el backend (app/flota.py y app/routers/flota.py).
import { api } from './api.js'

// Mismos hospitales que app/genetico.py (el backend valida el nombre).
export const HOSPITALES = [
  'Hospital IMSS 220',
  'Hospital General Nicolás San Juan',
  'Cruz Roja Toluca',
  'Hospital General ISSSTE',
  'Hospital IMSS 251',
  'Cruz Roja Metepec',
  'Cruz Roja San Mateo Atenco',
  'Cruz Roja Lerma',
  'Hospital Municipal Lerma',
]

export const ESTADOS = ['Libre', 'Ocupada', 'En reparación', 'Fuera de servicio']
export const ESTADOS_MANUALES = ['Libre', 'En reparación', 'Fuera de servicio']

export const ESTADO_INFO = {
  Libre: { color: '#1a7a41', fondo: '#e5f6ec', texto: 'Lista para salir' },
  Ocupada: { color: '#1d5fd6', fondo: '#e6eefc', texto: 'Atendiendo una emergencia' },
  'En reparación': { color: '#a0630a', fondo: '#fff2dc', texto: 'En el taller' },
  'Fuera de servicio': { color: '#5b5b68', fondo: '#ececf1', texto: 'No puede salir' },
}

export const TIPO_HISTORIAL = {
  estado: 'Cambio de estatus',
  asignacion: 'Asignada a emergencia',
  salida: 'Salida',
  llegada: 'Llegada al lugar',
  traslado: 'Traslado a hospital',
  liberacion: 'Regresa libre',
  combustible: 'Carga de gasolina',
  consumo: 'Gasolina usada',
  conductor: 'Cambio de conductor',
  hospital: 'Cambio de hospital',
  aviso: 'Aviso',
}

export const obtenerHospitales = () => api('/flota/hospitales')
export const fichaAmbulancia = (id) => api(`/flota/ambulancias/${id}`)
export const cambiarAmbulancia = (id, cambios) => api(`/flota/ambulancias/${id}`, { method: 'PATCH', body: cambios })
export const cargarCombustible = (id, carga) => api(`/flota/ambulancias/${id}/combustible`, { method: 'POST', body: carga })
export const obtenerHistorial = (filtros = {}) => {
  const q = new URLSearchParams(Object.entries(filtros).filter(([, v]) => v)).toString()
  return api(`/flota/historial${q ? `?${q}` : ''}`)
}
// `placas`: las que eligió el administrador a mano (van primero si están listas).
export const planAsignacion = (id, cantidad, placas = []) => api(`/flota/emergencias/${id}/asignar`, { method: 'POST', body: { cantidad, placas, confirmar: false } })
export const confirmarAsignacion = (id, cantidad, placas = []) => api(`/flota/emergencias/${id}/asignar`, { method: 'POST', body: { cantidad, placas, confirmar: true } })
// Vuelve a buscar ambulancias libres para una emergencia que se quedó en espera.
export const reintentarAsignacion = (id) => api(`/flota/emergencias/${id}/asignar-automatico`, { method: 'POST' })
export const eventoEmergencia = (id, evento) => api(`/flota/emergencias/${id}/evento`, { method: 'POST', body: evento })
export const reporteEmergencia = (id) => api(`/flota/emergencias/${id}/reporte`)

const fecha = new Intl.DateTimeFormat('es-MX', { day: 'numeric', month: 'short', year: 'numeric' })
const hora = new Intl.DateTimeFormat('es-MX', { hour: '2-digit', minute: '2-digit', hour12: true })

export function fmtFecha(v, conHora = true) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return '—'
  return conHora ? `${fecha.format(d)} · ${hora.format(d)}` : fecha.format(d)
}
export function fmtHoraCorta(v) {
  if (!v) return '—'
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? '—' : hora.format(d)
}
export const fmtLitros = (l) => `${Number(l ?? 0).toLocaleString('es-MX', { maximumFractionDigits: 1 })} L`
export const fmtDinero = (n) => (n == null ? '—' : Number(n).toLocaleString('es-MX', { style: 'currency', currency: 'MXN' }))

// Color de la barra de gasolina.
export const colorGasolina = (pct, minimo = 25) => (pct < minimo ? '#c8202f' : pct < 50 ? '#e3a114' : '#2e9d5a')
