// Rutas de la ambulancia sobre calles reales de Toluca, Metepec, San Mateo Atenco y Lerma. La búsqueda (ciega y
// heurística) corre en el
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
  { key: 'costo_uniforme', label: 'Costo uniforme', corto: 'UCS', frontera: 'ordenada por minutos acumulados g(n): sale primero la esquina más barata', garantiza: 'la ruta más rápida con el tráfico' },
  { key: 'anchura', label: 'Anchura', corto: 'BFS', frontera: 'cola (FIFO): sale primero la esquina que entró primero', garantiza: 'la ruta con menos tramos de calle' },
  { key: 'profundidad', label: 'Profundidad', corto: 'DFS', frontera: 'pila (LIFO): sale primero la última esquina que entró', garantiza: 'una ruta cualquiera, sin buscar la mejor' },
  { key: 'greedy', label: 'Voraz (greedy)', corto: 'Greedy', heuristico: true, frontera: 'ordenada por h(n), los minutos estimados que faltan: sale primero la esquina que parece más cerca', garantiza: 'decidir rápido, pero no la ruta más rápida (se deja llevar por lo que parece cerca)' },
  { key: 'a_estrella', label: 'A*', corto: 'A*', heuristico: true, frontera: 'ordenada por f(n) = g(n) + h(n): minutos recorridos + minutos estimados que faltan', garantiza: 'la ruta más rápida con el tráfico, revisando menos esquinas que costo uniforme' },
]

export const ALGORITMO_COLOR = { costo_uniforme: '#1d5fd6', anchura: '#7a3fd1', profundidad: '#6b7280', greedy: '#d97706', a_estrella: '#0f8a6c' }

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

const distanciaKm = ([lat1, lng1], [lat2, lng2]) => {
  const rad = Math.PI / 180
  const a = Math.sin(((lat2 - lat1) * rad) / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lng2 - lng1) * rad) / 2) ** 2
  return 6371 * 2 * Math.asin(Math.sqrt(a))
}

// Simulación: dónde va la ambulancia después de `min` minutos sobre la ruta, avanzando
// cada tramo al ritmo de su tráfico. Devuelve también los puntos ya recorridos.
export function avanceEnRuta(ruta, min) {
  let t = 0
  let km = 0
  const atras = []
  for (const tr of ruta.tramos) {
    if (min < t + tr.minutos) {
      const objetivo = ((min - t) / tr.minutos) * tr.km
      let acum = 0
      for (let j = 1; j < tr.coords.length; j++) {
        const a = tr.coords[j - 1], b = tr.coords[j]
        const d = distanciaKm(a, b)
        atras.push(a)
        if (acum + d >= objetivo) {
          const f = d ? (objetivo - acum) / d : 0
          const punto = [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]
          atras.push(punto)
          return { punto, km: km + objetivo, nivel: tr.nivel, atras, llego: false }
        }
        acum += d
      }
    }
    atras.push(...tr.coords)
    t += tr.minutos
    km += tr.km
  }
  return { punto: ruta.coords[ruta.coords.length - 1], km: ruta.km, nivel: null, atras, llego: true }
}
