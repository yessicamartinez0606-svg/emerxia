const TOKEN_KEY = 'emergexia.token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

const PUBLIC_PATHS = ['/auth/login', '/auth/register', '/auth/forgot-password', '/auth/reset-password']

export async function api(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let res
  try {
    res = await fetch(`/api${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined })
  } catch {
    throw new Error('No se pudo conectar con el servidor. Verifica que el backend esté en marcha.')
  }

  if (res.status === 401 && !PUBLIC_PATHS.includes(path)) onUnauthorized()

  const data = await res.json().catch(() => null)

  if (!res.ok) {
    if (typeof data?.detail === 'string') throw new Error(data.detail)
    if (Array.isArray(data?.detail)) throw new Error('Revisa los datos del formulario.')
    if (res.status >= 500) {
      throw new Error(
        `El backend no respondió (código ${res.status}). Probablemente no está corriendo en el puerto 8000. ` +
        'En la carpeta backend ejecuta: python diagnostico.py',
      )
    }
    throw new Error('Ocurrió un error inesperado.')
  }
  return data ?? {}
}
