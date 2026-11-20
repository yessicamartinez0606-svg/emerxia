// Despacho de ambulancia con algoritmo genético. El cálculo corre en el backend
// (app/genetico.py); aquí solo están las llamadas a la API.
import { api } from './api.js'

export const obtenerHospitales = () => api('/despacho/hospitales')
export const resolverDespacho = (datos) => api('/despacho/resolver', { method: 'POST', body: datos })

export const PARAMETROS = [
  { key: 'poblacion', label: 'Tamaño de población', min: 2, max: 2000, step: 1, def: 100 },
  { key: 'generaciones', label: 'Generaciones', min: 1, max: 1000, step: 1, def: 100 },
  { key: 'prob_mutacion', label: 'Probabilidad de mutación (0 a 1)', min: 0, max: 1, step: 0.05, def: 0.2 },
  { key: 'velocidad_kmh', label: 'Velocidad de la ambulancia (km/h)', min: 5, max: 200, step: 5, def: 40 },
  { key: 'minutos_en_lugar', label: 'Tiempo en el lugar (min)', min: 0, max: 240, step: 1, def: 10 },
]
