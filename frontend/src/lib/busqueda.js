// Búsqueda ciega de rutas con tráfico. El cálculo se hace en el backend (app/busqueda.py);
// aquí solo están las llamadas a la API y lo necesario para dibujar el mapa.
import { api } from './api.js'

export const NIVELES = ['libre', 'moderado', 'denso', 'bloqueado']

export const NIVEL_LABEL = {
  libre: 'Fluido',
  moderado: 'Lento',
  denso: 'Muy lento',
  bloqueado: 'Cerrada',
}

export const ALGORITMOS = [
  {
    key: 'anchura',
    label: 'Anchura',
    frontera: 'Cola (FIFO): sale primero el que entró primero',
    garantiza: 'la ruta con menos calles',
  },
  {
    key: 'profundidad',
    label: 'Profundidad',
    frontera: 'Pila (LIFO): sale primero el último que entró',
    garantiza: 'una ruta cualquiera, sin buscar la mejor',
  },
  {
    key: 'costo_uniforme',
    label: 'Costo uniforme',
    frontera: 'Ordenada por minutos acumulados g(n): sale el más barato',
    garantiza: 'la ruta más rápida considerando el tráfico',
  },
]

// Hora pico: las avenidas que normalmente fluyen también se cargan.
export const HORA_PICO = {
  c01: 'denso', c02: 'denso', c07: 'moderado', c08: 'moderado', c09: 'denso',
  c10: 'denso', c11: 'moderado', c14: 'denso', c15: 'moderado', c17: 'moderado',
}

export const siguienteNivel = (nivel) => NIVELES[(NIVELES.indexOf(nivel) + 1) % NIVELES.length]

export const obtenerMapa = () => api('/busqueda/mapa')

export const resolverRuta = ({ inicial, meta, trafico }) =>
  api('/busqueda/resolver', { method: 'POST', body: { inicial, meta, trafico } })

// ─── Indicaciones paso a paso, como las de una app de mapas ───
// En el mapa, x crece hacia el oriente y y crece hacia el sur.
const RUMBOS = ['norte', 'oriente', 'sur', 'poniente']

function rumbo(a, b) {
  const dx = b.x - a.x
  const dy = b.y - a.y
  if (Math.abs(dx) >= Math.abs(dy)) return dx > 0 ? 'oriente' : 'poniente'
  return dy > 0 ? 'sur' : 'norte'
}

function giro(antes, despues) {
  const d = (RUMBOS.indexOf(despues) - RUMBOS.indexOf(antes) + 4) % 4
  if (d === 1) return 'Gira a la derecha'
  if (d === 3) return 'Gira a la izquierda'
  if (d === 2) return 'Da vuelta en U'
  return 'Sigue'
}

/** Junta los tramos seguidos de la misma calle y devuelve instrucciones legibles. */
export function indicaciones({ ruta, calles }, mapa, minutosCalle) {
  const nodo = Object.fromEntries(mapa.nodos.map((n) => [n.id, n]))
  const calle = Object.fromEntries(mapa.calles.map((c) => [c.id, c]))
  const tramos = []
  calles.forEach((cid, i) => {
    const c = calle[cid]
    const a = nodo[ruta[i]]
    const b = nodo[ruta[i + 1]]
    const dir = rumbo(a, b)
    const ultimo = tramos[tramos.length - 1]
    if (ultimo && ultimo.calle === c.nombre && ultimo.rumbo === dir) {
      ultimo.hasta = b
      ultimo.km += c.distancia_km
      ultimo.min += minutosCalle(c)
      ultimo.niveles.push(c)
    } else {
      tramos.push({ calle: c.nombre, rumbo: dir, desde: a, hasta: b, km: c.distancia_km, min: minutosCalle(c), niveles: [c] })
    }
  })
  return tramos.map((t, i) => ({
    ...t,
    texto: i === 0
      ? `Sal por ${t.calle} hacia el ${t.rumbo}`
      : `${giro(tramos[i - 1].rumbo, t.rumbo)} en ${t.calle} hacia el ${t.rumbo}`,
  }))
}
