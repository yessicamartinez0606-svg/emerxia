import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Ambulance, Check, MapPin, MessageSquare, Phone, Plus } from 'lucide-react'
import { fmtFecha, fmtHoraCorta } from '../../lib/flota.js'
import { AVANCE, misReportes } from '../../lib/portal.js'

// Los reportes de la persona y cómo van. Se actualiza solo cada 20 s.

export default function MisReportes() {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    const cargar = () => misReportes().then((d) => { setDatos(d); setError('') }).catch((e) => setError(e.message))
    cargar()
    const t = setInterval(cargar, 20000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="us-mis">
      <header className="view-head">
        <div>
          <h1>Mis reportes</h1>
          <p>Se actualiza solo. Para hablar con la central llama al {datos?.telefono_central ?? '911'}.</p>
        </div>
        <div className="head-actions">
          <Link className="btn-primary compact" to="/"><Plus size={15} /> Reportar</Link>
        </div>
      </header>
      {error && <p className="form-error">{error}</p>}
      {!datos && !error && <p className="muted">Cargando…</p>}
      {datos && datos.items.length === 0 && (
        <section className="panel us-vacio">
          <p>Todavía no has reportado emergencias.</p>
          <Link className="btn-primary compact" to="/">Reportar una emergencia</Link>
        </section>
      )}
      <div className="us-lista">
        {datos?.items.map((r) => {
          const actual = [...AVANCE].reverse().find((p) => r[p.campo])
          return (
            <article key={r.id} className={`panel us-reporte${r.estado === 'Cerrada' ? ' cerrado' : ''}`}>
              <header>
                <div>
                  <span className="op-eyebrow">{r.folio} · {r.canal === 'llamada' ? <><Phone size={11} /> llamada</> : <><MessageSquare size={11} /> mensaje</>}</span>
                  <h2>{r.tipo || r.descripcion}</h2>
                  <p><MapPin size={12} /> {r.direccion}</p>
                </div>
                <span className="us-estado">{actual?.label ?? 'Reporte recibido'}</span>
              </header>
              <ol className="us-avance">
                {AVANCE.map((p) => (
                  <li key={p.campo} className={r[p.campo] ? 'hecho' : ''}>
                    <span className="op-paso-punto" aria-hidden="true">{r[p.campo] ? <Check size={11} /> : null}</span>
                    <span>{p.label}</span>
                    <small>{r[p.campo] ? fmtHoraCorta(r[p.campo]) : ''}</small>
                  </li>
                ))}
              </ol>
              {r.ambulancias.length > 0 && (
                <ul className="us-ambs">
                  {r.ambulancias.map((a) => (
                    <li key={a.placa}><Ambulance size={14} aria-hidden="true" /> <strong>{a.placa}</strong> de {a.hospital}{a.conductor ? ` · la maneja ${a.conductor}` : ''}</li>
                  ))}
                </ul>
              )}
              {r.hospital_destino && <p className="field-hint">Trasladado a {r.hospital_destino}.</p>}
              <p className="us-fecha">Reportado {fmtFecha(r.created_at)}</p>
            </article>
          )
        })}
      </div>
    </div>
  )
}
