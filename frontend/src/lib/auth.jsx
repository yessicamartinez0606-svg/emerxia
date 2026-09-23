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

  const login = useCallback(async (username, password) => {
    const data = await api('/auth/login', { method: 'POST', body: { username, password } })
    setToken(data.token)
    setUser(data.user)
  }, [])

  const register = useCallback(async ({ fullName, username, password, role }) => {
    const data = await api('/auth/register', {
      method: 'POST',
      body: { full_name: fullName, username, password, role },
    })
    setToken(data.token)
    setUser(data.user)
  }, [])

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
