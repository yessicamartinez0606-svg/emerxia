// Rutas de la ambulancia sobre calles reales de Toluca. La búsqueda ciega corre en el
// backend (app/busqueda.py y app/red_vial.py); aquí están las llamadas a la API y los
// textos que comparten la pantalla de Rutas y la ficha de cada emergencia.
import { api } from './api.js'

export const NIVEL_LABEL = {
  libre: 'Sin tráfico',
  moderado: 'Tráfico lento',
  denso: 'Tráfico pesado',
  bloqueado: 'Cerrada',
}

export const NIVEL_COLOR = {
  libre: '#2e9d5a',
  moderado: '#e3a114',
  denso: '#d9402a',
  bloqueado: '#45454f',
}

export const ALGORITMOS = [
  { key: 'costo_uniforme', label: 'Costo uniforme', frontera: 'ordenada por minutos acumulados g(n): sale primero la esquina más barata', garantiza: 'la ruta más rápida con el tráfico' },
  { key: 'anchura', label: 'Anchura', frontera: 'cola (FIFO): sale primero la esquina que entró primero', garantiza: 'la ruta con menos tramos de calle' },
  { key: 'profundidad', label: 'Profundidad', frontera: 'pila (LIFO): sale primero la última esquina que entró', garantiza: 'una ruta cualquiera, sin buscar la mejor' },
]

export const ALGORITMO_COLOR = { costo_uniforme: '#1d5fd6', anchura: '#7a3fd1', profundidad: '#6b7280' }

// Escenarios de hora para estimar el tráfico. null = la hora actual.
export const HORAS = [
  { valor: null, label: 'Ahora' },
  { valor: 8, label: 'Hora pico (8:00)' },
  { valor: 12, label: 'Mediodía' },
  { valor: 23, label: 'Noche' },
]

const conHora = (path, hora) => (hora == null ? path : `${path}${path.includes('?') ? '&' : '?'}hora=${hora}`)

export const obtenerZona = (hora) => api(conHora('/rutas/zona', hora))
export const geocodificar = (q) => api(`/rutas/geocodificar?q=${encodeURIComponent(q)}`)
export const calcularRuta = ({ origen, destino, hora }) =>
  api('/rutas/calcular', { method: 'POST', body: { origen, destino, hora } })
export const rutaDeEmergencia = (id, hora) => api(conHora(`/rutas/emergencias/${id}`, hora))

export const fmtMin = (m) => (m == null ? '—' : m < 1 ? 'menos de 1 min' : `${Math.round(m)} min`)
export const fmtKm = (km) => (km == null ? '—' : km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(1)} km`)
export const fmtHora = (h) => `${String(h).padStart(2, '0')}:00`
