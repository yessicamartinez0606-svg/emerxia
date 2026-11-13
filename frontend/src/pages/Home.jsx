import { useAuth } from '../lib/auth.jsx'
import { useNow } from '../lib/useNow.js'
import PendientesCentral from '../components/PendientesCentral.jsx'
import ClimaZonas from '../components/ClimaZonas.jsx'

// Inicio de la central: lo que hay que atender ahora, y el clima de las zonas a un lado.
function saludo(hora) {
  if (hora < 12) return 'Buenos días'
  if (hora < 19) return 'Buenas tardes'
  return 'Buenas noches'
}

export default function Home() {
  const { user } = useAuth()
  const now = useNow()
  const nombre = user?.full_name?.split(' ')[0]
  const f = new Intl.DateTimeFormat('es-MX', { weekday: 'long', day: 'numeric', month: 'long' }).format(now)
  const fecha = f.charAt(0).toUpperCase() + f.slice(1)

  return (
    <div className="inicio">
      <header className="inicio-head">
        <h1>{saludo(now.getHours())}, {nombre}</h1>
        <p><span className="inicio-fecha">{fecha}</span>{user?.role === 'Administrador' ? ' — Tú creas, asignas y das seguimiento a las emergencias.' : ''}</p>
      </header>
      <div className="inicio-grid">
        <PendientesCentral />
        <aside className="inicio-lado">
          <ClimaZonas lista />
        </aside>
      </div>
    </div>
  )
}
