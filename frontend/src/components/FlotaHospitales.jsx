import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Fuel, Hospital, UserRound } from 'lucide-react'
import { ESTADOS, ESTADO_INFO, colorGasolina, obtenerHospitales } from '../lib/flota.js'

// Ambulancias agrupadas por hospital, con su estatus, conductor y gasolina.
// Va arriba de la tabla del módulo Ambulancias.

export default function FlotaHospitales({ recarga = 0 }) {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [soloConAmbulancias, setSoloConAmbulancias] = useState(true)

  useEffect(() => {
    setError('')
    obtenerHospitales().then(setDatos).catch((e) => setError(e.message))
  }, [recarga])

  if (error) return <p className="form-error">No se pudo cargar la flota: {error}</p>
  if (!datos) return <div className="panel flota-cargando muted">Cargando ambulancias por hospital…</div>

  const minimo = datos.combustible_minimo
  const hospitales = datos.hospitales.filter((h) => !soloConAmbulancias || h.ambulancias.length)

  return (
    <section className="flota" aria-label="Ambulancias por hospital">
      <div className="flota-resumen">
        <div className="flota-total">
          <b>{datos.totales.total}</b>
          <span>ambulancias en {datos.hospitales.filter((h) => h.ambulancias.length).length} hospitales</span>
        </div>
        {ESTADOS.map((e) => (
          <div key={e} className="flota-estado" style={{ '--c': ESTADO_INFO[e].color, '--f': ESTADO_INFO[e].fondo }}>
            <b>{datos.totales[e]}</b>
            <span>{e}</span>
          </div>
        ))}
        <label className="flota-filtro">
          <input type="checkbox" checked={soloConAmbulancias} onChange={(e) => setSoloConAmbulancias(e.target.checked)} />
          Solo hospitales con ambulancias
        </label>
      </div>

      <div className="flota-grid">
        {hospitales.map((h) => (
          <article key={h.id} className="panel flota-hospital">
            <header>
              <span className="flota-hosp-icon" aria-hidden="true"><Hospital size={16} /></span>
              <div>
                <h3>{h.nombre}</h3>
                <p>{h.municipio} · {h.listas} de {h.ambulancias.length} listas para salir</p>
              </div>
            </header>
            {h.ambulancias.length === 0 && <p className="muted flota-vacio">Sin ambulancias registradas.</p>}
            <ul>
              {h.ambulancias.map((a) => {
                const info = ESTADO_INFO[a.estado]
                return (
                  <li key={a.id}>
                    <Link to={`/ambulancias/${a.id}`} className="flota-amb">
                      <span className="flota-amb-top">
                        <strong>{a.placa}</strong>
                        <span className="flota-chip" style={{ color: info.color, background: info.fondo }}>{a.estado}</span>
                      </span>
                      <span className="flota-amb-meta">
                        <UserRound size={12} aria-hidden="true" />
                        {a.conductor || <em>Sin conductor</em>}
                        <span className="sep">·</span>
                        {a.tipo}
                        {a.emergencia_actual && <><span className="sep">·</span>{a.emergencia_actual}</>}
                      </span>
                      <span className="flota-gas" title={`Gasolina: ${a.combustible_pct} %`}>
                        <Fuel size={12} aria-hidden="true" />
                        <span className="barra"><span style={{ width: `${a.combustible_pct}%`, background: colorGasolina(a.combustible_pct, minimo) }} /></span>
                        <span className={`pct${a.combustible_bajo ? ' bajo' : ''}`}>{Math.floor(a.combustible_pct)} %</span>
                      </span>
                    </Link>
                  </li>
                )
              })}
            </ul>
          </article>
        ))}
      </div>
    </section>
  )
}
