import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Ambulance, MessageSquare, Phone, Plus, Siren, UserRound } from 'lucide-react'
import { api } from '../lib/api.js'
import { fmtHoraCorta } from '../lib/flota.js'
import { colaTriaje } from '../lib/clima.js'

// Inicio del administrador: las emergencias abiertas, de la más urgente a la menos, con lo
// que falta en cada una (asignar operador y ambulancia, salida, cierre). Se actualiza cada 30 s
// para ver al momento las que reportan los usuarios.

const PESO_ESTADO = { Pendiente: 0, Asignada: 1, 'En curso': 2 }
const PESO_PRIORIDAD = { Alta: 0, Media: 1, Baja: 2 }

function falta(e) {
  if (!e.ambulancia) return { texto: 'En espera de ambulancia', urgente: true }
  if (!e.operador) return { texto: 'Validar operador', urgente: true }
  if (e.estado === 'Asignada') return { texto: 'Esperando salida', urgente: false }
  return { texto: 'En atención', urgente: false }
}

export default function PendientesCentral() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [triaje, setTriaje] = useState({})      // id -> probabilidad de ser crítica (práctica 05)

  useEffect(() => {
    const cargar = () => api('/emergencias')
      .then((d) => { setItems((d.items ?? []).filter((e) => e.estado !== 'Cerrada')); setError('') })
      .catch((e) => setError(e.message))
      .then(() => colaTriaje())
      .then((c) => c && setTriaje(Object.fromEntries(c.cola.map((x) => [x.id, x.triaje]))))
      .catch(() => {})          // sin scikit-learn la lista funciona igual, solo sin triaje
    cargar()
    const t = setInterval(cargar, 30000)
    return () => clearInterval(t)
  }, [])

  const ordenadas = [...(items ?? [])].sort((a, b) =>
    (PESO_ESTADO[a.estado] ?? 9) - (PESO_ESTADO[b.estado] ?? 9)
    || Number(!!triaje[b.id]?.critica) - Number(!!triaje[a.id]?.critica)      // primero las críticas según la IA
    || (PESO_PRIORIDAD[a.prioridad] ?? 9) - (PESO_PRIORIDAD[b.prioridad] ?? 9)
    || b.id - a.id)
  const sinAsignar = ordenadas.filter((e) => !e.ambulancia).length

  return (
    <section className="panel central">
      <header className="central-head">
        <div>
          <h2><Siren size={18} aria-hidden="true" /> Emergencias por atender</h2>
          <p>
            {items === null ? 'Cargando…'
              : ordenadas.length === 0 ? 'No hay emergencias abiertas.'
                : `${ordenadas.length} abierta(s)${sinAsignar ? ` · ${sinAsignar} sin ambulancia` : ''}`}
          </p>
        </div>
        <Link to="/emergencias/nuevo" className="btn-primary compact"><Plus size={15} /> Nueva emergencia</Link>
      </header>
      {error && <p className="form-error">{error}</p>}
      {ordenadas.length > 0 && (
        <ul className="central-lista">
          {ordenadas.slice(0, 8).map((e) => {
            const f = falta(e)
            return (
              <li key={e.id} className={f.urgente ? 'urgente' : ''}>
                <Link to={`/emergencias/${e.id}`} className="central-fila">
                  <span className={`central-prio p-${(e.prioridad || '').toLowerCase()}`} aria-label={`Prioridad ${e.prioridad}`} />
                  <span className="central-info">
                    <strong>
                      {e.folio} · {e.descripcion}
                      {triaje[e.id] && (
                        <em className={`central-triaje${triaje[e.id].critica ? ' critica' : ''}`} title="Probabilidad de ser crítica según la IA (signos vitales)">
                          {triaje[e.id].critica ? 'Crítica' : 'No crítica'} {Math.round(triaje[e.id].probabilidad * 100)} %
                        </em>
                      )}
                    </strong>
                    <span>
                      {e.canal === 'llamada' ? <><Phone size={11} /> Llamada · </> : e.canal === 'mensaje' ? <><MessageSquare size={11} /> Mensaje · </> : null}
                      {e.direccion}
                    </span>
                  </span>
                  <span className="central-asig">
                    <span><UserRound size={12} aria-hidden="true" /> {e.operador || 'Sin operador'}</span>
                    <span><Ambulance size={12} aria-hidden="true" /> {e.ambulancia || 'Sin ambulancia'}</span>
                  </span>
                  <span className="central-hora">{fmtHoraCorta(e.created_at)}</span>
                  <span className={`central-falta${f.urgente ? ' urgente' : ''}`}>{f.texto}</span>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
      {ordenadas.length > 8 && <Link to="/emergencias" className="ruta-link">Ver las {ordenadas.length} emergencias</Link>}
    </section>
  )
}
