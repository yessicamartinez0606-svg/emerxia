// Búsqueda ciega de rutas con tráfico. El cálculo se hace en el backend (app/busqueda.py);
// aquí solo están las llamadas a la API y lo necesario para dibujar el mapa.
import { api } from './api.js'

export const NIVELES = ['libre', 'moderado', 'denso', 'bloqueado']

export const NIVEL_LABEL = {
  libre: 'Libre',
  moderado: 'Moderado',
  denso: 'Denso',
  bloqueado: 'Bloqueado',
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

// Hora pico: las avenidas principales se saturan.
export const HORA_PICO = {
  c05: 'denso', c06: 'denso', c09: 'moderado', c11: 'moderado', c15: 'moderado',
  c16: 'moderado', c18: 'denso', c20: 'denso', c21: 'moderado',
}

export const siguienteNivel = (nivel) => NIVELES[(NIVELES.indexOf(nivel) + 1) % NIVELES.length]

export const obtenerMapa = () => api('/busqueda/mapa')

export const resolverRuta = ({ inicial, meta, trafico }) =>
  api('/busqueda/resolver', { method: 'POST', body: { inicial, meta, trafico } })
