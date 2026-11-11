// Llamadas de los portales Operador y Usuario (backend: app/routers/portal.py).
import { api } from './api.js'

export const portalOperador = () => api('/portal/operador')
export const cargaOperador = (carga) => api('/portal/operador/combustible', { method: 'POST', body: carga })
export const estadoOperador = (estado, motivo) => api('/portal/operador/estado', { method: 'POST', body: { estado, motivo } })
export const eventoOperador = (evento) => api('/portal/operador/evento', { method: 'POST', body: evento })

export const tiposEmergencia = () => api('/portal/usuario/tipos')
export const buscarDireccion = (q) => api(`/portal/usuario/buscar?q=${encodeURIComponent(q)}`)
export const enviarReporte = (reporte) => api('/portal/usuario/reportes', { method: 'POST', body: reporte })
export const misReportes = () => api('/portal/usuario/reportes')

// Pasos que ve quien reportó, con el campo de fecha que marca cada uno.
export const AVANCE = [
  { label: 'Reporte recibido', campo: 'created_at' },
  { label: 'Ambulancia asignada', campo: 'asignada_en' },
  { label: 'En camino', campo: 'hora_salida' },
  { label: 'En el lugar', campo: 'hora_llegada' },
  { label: 'Atendida', campo: 'hora_cierre' },
]
