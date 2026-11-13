import { NavLink, Outlet } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import { Logo } from './Logo.jsx'
import { useAuth } from '../lib/auth.jsx'

// Marco de los portales de Operador y Usuario: barra superior con pestañas, pensado para
// usarse también desde el celular.

const iniciales = (nombre = '') => nombre.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('') || '?'

export default function PortalLayout({ nav, etiqueta }) {
  const { user, logout } = useAuth()
  return (
    <div className="portal">
      <header className="portal-top">
        <div className="portal-top-in">
          <Logo size={28} className="portal-logo" />
          <span className="portal-sep" aria-hidden="true" />
          <span className="portal-area">{etiqueta}</span>
          <div className="portal-user">
            <span className="portal-quien">
              <span className="portal-avatar" aria-hidden="true">{iniciales(user?.full_name)}</span>
              <span className="portal-quien-txt"><b>{user?.full_name}</b><small>{etiqueta}</small></span>
            </span>
            <button type="button" className="portal-salir" onClick={logout} aria-label="Cerrar sesión">
              <LogOut size={16} /> <span>Salir</span>
            </button>
          </div>
        </div>
        <nav className="portal-tabs" aria-label="Secciones">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === '/'} className="portal-tab">
              <Icon size={16} aria-hidden="true" /> {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="portal-main">
        <Outlet />
      </main>
    </div>
  )
}
