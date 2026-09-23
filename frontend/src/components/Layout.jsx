import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { ChevronDown, LogOut, Search, UserRound } from 'lucide-react'
import { Logo } from './Logo.jsx'
import ClockWidget from './ClockWidget.jsx'
import { useAuth } from '../lib/auth.jsx'
import { HOME, MODULES } from '../lib/modules.js'

const NAV = [{ ...HOME, key: 'inicio', path: '/' }, ...MODULES.map((m) => ({ ...m, path: `/${m.key}` }))]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)

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
    <div className="app-shell">
      <aside className="sidebar">
        <Logo size={34} className="sidebar-logo" />
        <nav aria-label="Principal">
          {NAV.map(({ key, path, label, navIcon: Icon }) => (
            <NavLink key={key} to={path} end={path === '/'} className="nav-item">
              <Icon size={19} strokeWidth={2.2} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <button type="button" className="nav-item logout" onClick={logout}>
          <LogOut size={19} strokeWidth={2.2} />
          <span>Cerrar sesión</span>
        </button>
      </aside>

      <div className="content">
        <header className="topbar">
          <form className="search" onSubmit={onSearch} role="search">
            <Search size={16} aria-hidden="true" />
            <input
              type="search"
              placeholder="Buscar en el sistema..."
              aria-label="Buscar en el sistema"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </form>

          <div className="user-wrap">
            <button
              type="button"
              className="user-chip"
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((v) => !v)}
            >
              <span className="avatar"><UserRound size={18} /></span>
              <span className="user-meta">
                <strong>{user?.full_name}</strong>
                <small>{user?.role}</small>
              </span>
              <ChevronDown size={15} />
            </button>
            {menuOpen && (
              <div className="user-menu" role="menu">
                <button role="menuitem" onClick={logout}><LogOut size={15} /> Cerrar sesión</button>
              </div>
            )}
          </div>
        </header>

        <main className="page">
          <Outlet />
        </main>
      </div>

      <ClockWidget />
    </div>
  )
}
