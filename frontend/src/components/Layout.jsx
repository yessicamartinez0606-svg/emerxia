import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Clock, LogOut, Search } from 'lucide-react'
import { Logo } from './Logo.jsx'
import PrepararRostros from './PrepararRostros.jsx'
import { useAuth } from '../lib/auth.jsx'
import { useNow } from '../lib/useNow.js'
import { HOME, MODULES } from '../lib/modules.js'

// Marco de la central (Administrador, Despachador, Supervisor). Usa el mismo diseño que el
// portal del Operador (components/PortalLayout.jsx): barra roja arriba con pestañas, en lugar
// del menú lateral, para que todo el sistema se vea igual.

const NAV = [{ ...HOME, key: 'inicio', path: '/' }, ...MODULES.map((m) => ({ ...m, path: `/${m.key}` }))]

const iniciales = (nombre = '') => nombre.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('') || '?'

function Reloj() {
  const now = useNow()
  const hora = new Intl.DateTimeFormat('es-MX', { hour: '2-digit', minute: '2-digit', hour12: true }).format(now)
  return (
    <span className="portal-reloj" role="status" aria-label="Hora actual">
      <Clock size={14} aria-hidden="true" /> <b>{hora}</b>
    </span>
  )
}

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  const onSearch = (e) => {
    e.preventDefault()
    const q = query.trim().toLowerCase()
    if (!q) return
    const hit = NAV.find((n) => n.label.toLowerCase().includes(q))
    if (hit) {
      navigate(hit.path)
      setQuery('')
    }
  }

  return (
    <div className="portal central">
      <header className="portal-top">
        <div className="portal-top-in">
          <Logo size={26} className="portal-logo" />
          <span className="portal-sep" aria-hidden="true" />
          <span className="portal-area">Central de emergencias</span>
          <form className="portal-buscar" onSubmit={onSearch} role="search">
            <Search size={15} aria-hidden="true" />
            <input
              type="search"
              placeholder="Buscar sección…"
              aria-label="Buscar en el sistema"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </form>
          <div className="portal-user">
            <Reloj />
            <span className="portal-quien">
              <span className="portal-avatar" aria-hidden="true">{iniciales(user?.full_name)}</span>
              <span className="portal-quien-txt">
                <b>{user?.full_name}</b>
                <small>{user?.role || 'Central'}</small>
              </span>
            </span>
            <button type="button" className="portal-salir" onClick={logout} aria-label="Cerrar sesión">
              <LogOut size={16} /> <span>Salir</span>
            </button>
          </div>
        </div>
        <nav className="portal-tabs" aria-label="Secciones">
          {NAV.map(({ key, path, label, navIcon: Icon }) => (
            <NavLink key={key} to={path} end={path === '/'} className="portal-tab">
              <Icon size={16} aria-hidden="true" /> {label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="page central-page">
        <Outlet />
      </main>

      {/* Descriptores faciales de los operadores, para que entren solo con su rostro. */}
      <PrepararRostros />
    </div>
  )
}
