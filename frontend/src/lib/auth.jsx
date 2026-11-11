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

  const aceptar = useCallback((data) => {
    setToken(data.token)
    setUser(data.user)
    return data.user
  }, [])

  const login = useCallback(async (username, password) => {
    const data = await api('/auth/login', { method: 'POST', body: { username, password } })
    return aceptar(data)
  }, [aceptar])

  // Operadores: entran solo con su rostro. `descriptor` son los 128 números que calcula
  // face-api.js de la foto recién tomada; el servidor busca a qué operador corresponde.
  const loginConRostro = useCallback(async (descriptor) => {
    const data = await api('/auth/operador', { method: 'POST', body: { descriptor } })
    return aceptar(data)
  }, [aceptar])

  const register = useCallback(async ({ fullName, username, password, role, telefono }) => {
    const data = await api('/auth/register', {
      method: 'POST',
      body: { full_name: fullName, username, password, role, telefono: telefono ?? '' },
    })
    return aceptar(data)
  }, [aceptar])

  const value = useMemo(() => ({ user, loading, login, loginConRostro, register, logout }), [user, loading, login, loginConRostro, register, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
