import { HeartPulse } from 'lucide-react'
import { useAuth } from '../lib/auth.jsx'
import PendientesCentral from '../components/PendientesCentral.jsx'
import ClimaZonas from '../components/ClimaZonas.jsx'

function HeroArt() {
  return (
    <div className="hero-art" aria-hidden="true">
      <div className="hero-swoosh" />
      <svg className="hero-cross" viewBox="0 0 200 200">
        <defs>
          <linearGradient id="crossGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#e04b58" />
            <stop offset="1" stopColor="#b3111f" />
          </linearGradient>
        </defs>
        <path d="M70 10h60v60h60v60h-60v60H70v-60H10V70h60z" fill="url(#crossGrad)" opacity=".92" />
        <path d="M14 104h44l14-30 24 66 16-36h74" fill="none" stroke="#fff" strokeWidth="9"
              strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div className="hero-ball" />
      <svg className="hero-steth" viewBox="0 0 300 330">
        <defs>
          <radialGradient id="chest" cx=".35" cy=".3" r=".9">
            <stop offset="0" stopColor="#f6f6f8" />
            <stop offset=".6" stopColor="#b9bcc4" />
            <stop offset="1" stopColor="#7c808a" />
          </radialGradient>
        </defs>
        <path d="M58 14C34 120 84 206 154 236" fill="none" stroke="#c0202f" strokeWidth="11" strokeLinecap="round" />
        <path d="M212 14C236 120 196 206 154 236" fill="none" stroke="#c0202f" strokeWidth="11" strokeLinecap="round" />
        <path d="M154 236C154 290 222 308 236 262" fill="none" stroke="#c0202f" strokeWidth="11" strokeLinecap="round" />
        <circle cx="58" cy="14" r="9" fill="#8e8f96" />
        <circle cx="212" cy="14" r="9" fill="#8e8f96" />
        <circle cx="240" cy="246" r="34" fill="url(#chest)" />
        <circle cx="240" cy="246" r="20" fill="#d9dbe0" stroke="#9a9da6" strokeWidth="3" />
      </svg>
    </div>
  )
}

export default function Home() {
  const { user } = useAuth()
  const firstName = user?.full_name?.split(' ')[0]

  return (
    <div className="home">
      <HeroArt />
      <header className="home-head">
        <h1>¡Bienvenido, {firstName}!</h1>
        <p>{user?.role === 'Administrador' ? 'Tú creas, asignas y das seguimiento a las emergencias' : 'Usa las pestañas de arriba para ir a cada sección'}</p>
      </header>

      <PendientesCentral />
      <ClimaZonas compacto />

      <footer className="banner">
        <span className="banner-icon"><HeartPulse size={18} /></span>
        <div className="banner-text">
          <strong>Tu trabajo hace la diferencia</strong>
          <span>Un sistema más conectado, una atención más rápida.</span>
        </div>
      </footer>
    </div>
  )
}
