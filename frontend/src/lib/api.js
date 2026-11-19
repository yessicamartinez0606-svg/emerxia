const TOKEN_KEY = 'emergexia.token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

const PUBLIC_PATHS = ['/auth/login', '/auth/register', '/auth/forgot-password', '/auth/reset-password']

// Errores de validación (FastAPI/pydantic): si es uno de nuestros mensajes en español
// ("Value error, El celular debe…") se muestra tal cual; si no, se dice qué dato revisar.
const NOMBRES_CAMPO = {
  usuario: 'el usuario', password: 'la contraseña', celular: 'el celular', correo: 'el correo', telefono: 'el teléfono',
  nombres: 'el nombre', apellidos: 'los apellidos', foto: 'la foto', placa: 'la placa', direccion: 'la dirección',
  paciente_nombre: 'el nombre del paciente', descripcion: 'la descripción', litros: 'los litros', full_name: 'tu nombre',
  username: 'el usuario',
}
function mensajeDeValidacion(errores) {
  const propio = errores.find((e) => typeof e?.msg === 'string' && e.msg.startsWith('Value error, '))
  if (propio) return propio.msg.replace('Value error, ', '')
  const campo = errores[0]?.loc?.[errores[0].loc.length - 1]
  return NOMBRES_CAMPO[campo] ? `Revisa ${NOMBRES_CAMPO[campo]}: falta o no tiene el formato correcto.` : 'Revisa los datos del formulario.'
}

export async function api(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let res
  try {
    res = await fetch(`/api${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined })
  } catch {
    // Causa técnica probable: el backend no está corriendo (python diagnostico.py lo revisa).
    throw new Error('No hay conexión con el sistema. Revisa tu internet y vuelve a intentarlo; si sigue, avisa a soporte técnico.')
  }

  if (res.status === 401 && !PUBLIC_PATHS.includes(path)) onUnauthorized()

  const data = await res.json().catch(() => null)

  if (!res.ok) {
    // Lo técnico va a la consola (para soporte); a la persona se le explica en palabras sencillas.
    if (res.status === 503) {
      console.warn('Servicio no disponible:', data?.detail)
      throw new Error('El sistema no está disponible en este momento. Intenta de nuevo en unos minutos; si sigue, avisa a soporte técnico.')
    }
    if (typeof data?.detail === 'string') throw new Error(data.detail)
    if (Array.isArray(data?.detail)) throw new Error(mensajeDeValidacion(data.detail))
    if (res.status >= 500) {
      console.warn(`Error ${res.status} en ${path}. En la carpeta backend: python diagnostico.py`)
      throw new Error('Algo falló en el sistema. Vuelve a intentarlo; si sigue, avisa a soporte técnico.')
    }
    throw new Error('Ocurrió un error inesperado.')
  }
  return data ?? {}
}
