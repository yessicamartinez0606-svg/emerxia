import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api, clearToken, getToken, setToken, setUnauthorizedHandler } from './api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(getToken()))

  const logout = useCallback(() => {
    clearToken()
    setUser(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    if (!getToken()) return
    api('/auth/me')
      .then(setUser)
      .catch(logout)
      .finally(() => setLoading(false))
  }, [logout])

  // Si la respuesta trae sesión, se inicia; si es un operador, regresa el paso de Face ID
  // ({ faceToken, operador: { nombre, foto } }) y la sesión llega hasta completeFace().
  const aceptar = useCallback((data) => {
    if (data.face_required) return { faceToken: data.face_token, operador: data.operador }
    setToken(data.token)
    setUser(data.user)
    return null
  }, [])

  const login = useCallback(async (username, password) => {
    const data = await api('/auth/login', { method: 'POST', body: { username, password } })
    return aceptar(data)
  }, [aceptar])

  const completeFace = useCallback(async (faceToken, resultado) => {
    const data = await api('/auth/face', {
      method: 'POST',
      body: { face_token: faceToken, coincide: Boolean(resultado?.match), distancia: resultado?.distance ?? null },
    })
    return aceptar(data)
  }, [aceptar])

  const register = useCallback(async ({ fullName, username, password, role, telefono }) => {
    const data = await api('/auth/register', {
      method: 'POST',
      body: { full_name: fullName, username, password, role, telefono: telefono ?? '' },
    })
    return aceptar(data)
  }, [aceptar])

  const value = useMemo(() => ({ user, loading, login, completeFace, register, logout }), [user, loading, login, completeFace, register, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
