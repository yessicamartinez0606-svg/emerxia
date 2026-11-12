import { useEffect, useState } from 'react'
import { BrainCircuit, Calculator, Trophy } from 'lucide-react'
import ClimaZonas from '../components/ClimaZonas.jsx'
import { estimarLlegada, modeloLlegada } from '../lib/clima.js'

// Práctica de regresión (backend/ia/enfoque2_tiempo_llegada.py) dentro del sistema:
// ¿cuánto tarda en llegar la ambulancia? Fórmula fija vs. árbol de regresión.
export default function TiempoLlegadaPage() {
  const [ev, setEv] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => { modeloLlegada().then(setEv).catch((e) => setError(e.message)) }, [])

  return (
    <section className="ia">
      <header className="view-head">
        <div>
          <h1>Tiempo de llegada (IA)</h1>
          <p>¿Cuánto tarda en llegar la ambulancia? Una fórmula fija contra un modelo que aprende de servicios pasados (árbol de regresión). La lluvia de cada emergencia sale del clima real de su zona.</p>
        </div>
        <BrainCircuit size={28} className="rutas-head-icon" aria-hidden="true" />
      </header>

      <ClimaZonas puedeSimular />

      {error && <p className="form-error">{error}</p>}
      {!ev && !error && <div className="panel muted">Entrenando el modelo…</div>}
      {ev && (
        <>
          <Calificacion ev={ev} />
          <Simulador ev={ev} />
          <div className="ia-grid">
            <Importancias ev={ev} />
            <Efectos ev={ev} />
          </div>
          <Comparacion ev={ev} />
        </>
      )}
    </section>
  )
}

function Calificacion({ ev }) {
  const { formula, modelo } = ev.calificacion
  const tarjeta = (titulo, sub, c, gana) => (
    <div className={`ia-calif${gana ? ' gana' : ''}`}>
      {gana && <span className="ia-gana"><Trophy size={13} /> Más preciso</span>}
      <strong>{titulo}</strong>
      <small>{sub}</small>
      <div className="ia-numeros">
        <div><b>{c.mae}</b><span>min de error promedio</span></div>
        <div><b>{Math.round(c.r2 * 100)} %</b><span>de la variación explicada (R²)</span></div>
      </div>
    </div>
  )
  return (
    <section className="panel">
      <h2 className="form-section-title">Calificación con {ev.prueba} servicios que el modelo nunca vio</h2>
      <div className="ia-califs">
        {tarjeta('Fórmula fija', '2 min para salir + distancia a 40 km/h', formula, ev.ganador === 'formula')}
        {tarjeta('Modelo que aprende', `Árbol de regresión entrenado con ${ev.entrenamiento} servicios`, modelo, ev.ganador === 'modelo')}
      </div>
      <p className="muted ia-nota">El historial de {ev.servicios} servicios es ficticio (semilla 42), igual que en la práctica. Con datos reales de la central, el modelo se entrena igual.</p>
    </section>
  )
}

function Importancias({ ev }) {
  return (
    <section className="panel">
      <h2 className="form-section-title">¿En qué se fija el modelo?</h2>
      <ul className="ia-barras">
        {ev.importancias.map((i) => (
          <li key={i.factor}>
            <span>{i.factor}</span>
            <div className="ia-barra"><i style={{ width: `${i.peso * 100}%` }} /></div>
            <b>{Math.round(i.peso * 100)} %</b>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Efectos({ ev }) {
  const max = Math.max(...ev.promedio_por_zona.map((z) => z.minutos))
  return (
    <section className="panel">
      <h2 className="form-section-title">Lo que se ve en el historial</h2>
      <div className="ia-efectos">
        <div><span>Hora pico</span><b>{ev.efectos.hora_pico.con} min</b><small>vs {ev.efectos.hora_pico.sin} sin hora pico</small></div>
        <div><span>Lluvia</span><b>{ev.efectos.lluvia.con} min</b><small>vs {ev.efectos.lluvia.sin} sin lluvia</small></div>
      </div>
      <ul className="ia-barras zonas">
        {ev.promedio_por_zona.map((z) => (
          <li key={z.zona}>
            <span>{z.zona}</span>
            <div className="ia-barra"><i style={{ width: `${(z.minutos / max) * 100}%` }} /></div>
            <b>{z.minutos} min</b>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Simulador({ ev }) {
  const [f, setF] = useState({ zona: ev.zonas[0], distancia_km: 3, hora: 8, fin_de_semana: false, lluvia: 'actual' })
  const [r, setR] = useState(null)
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState(false)

  const cambiar = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))
  const calcular = async (e) => {
    e.preventDefault()
    setOcupado(true)
    setError('')
    try {
      setR(await estimarLlegada({
        zona: f.zona, distancia_km: Number(f.distancia_km), hora: Number(f.hora), fin_de_semana: f.fin_de_semana,
        lluvia: f.lluvia === 'actual' ? null : f.lluvia === 'si',
      }))
    } catch (err) {
      setError(err.message)
    } finally {
      setOcupado(false)
    }
  }

  return (
    <section className="panel">
      <h2 className="form-section-title titulo-icono"><Calculator size={15} /> Probar una emergencia nueva</h2>
      <form className="ia-form" onSubmit={calcular}>
        <label>Zona<select value={f.zona} onChange={cambiar('zona')}>{ev.zonas.map((z) => <option key={z}>{z}</option>)}</select></label>
        <label>Distancia (km)<input type="number" min="0.5" max="100" step="0.1" value={f.distancia_km} onChange={cambiar('distancia_km')} /></label>
        <label>Hora<select value={f.hora} onChange={cambiar('hora')}>{Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{String(h).padStart(2, '0')}:00</option>)}</select></label>
        <label>Lluvia<select value={f.lluvia} onChange={cambiar('lluvia')}>
          <option value="actual">La de ahora en la zona</option><option value="si">Sí</option><option value="no">No</option>
        </select></label>
        <label className="check"><input type="checkbox" checked={f.fin_de_semana} onChange={cambiar('fin_de_semana')} /> Fin de semana</label>
        <button className="btn-primary compact" disabled={ocupado}>{ocupado ? 'Calculando…' : 'Estimar'}</button>
      </form>
      {error && <p className="form-error">{error}</p>}
      {r && (
        <div className={`ia-resultado${r.cumple_meta ? '' : ' alerta'}`}>
          <div><span>Fórmula fija</span><b>{r.formula_min} min</b></div>
          <div><span>Modelo</span><b>{r.modelo_min} min</b></div>
          <p>{r.hora_pico ? 'Hora pico. ' : ''}{r.lluvia ? 'Con lluvia. ' : ''}{r.mensaje}</p>
        </div>
      )}
    </section>
  )
}

function Comparacion({ ev }) {
  return (
    <section className="panel">
      <h2 className="form-section-title">Servicios de prueba: real vs. fórmula vs. modelo</h2>
      <div className="table-wrap">
        <table className="ia-tabla">
          <thead><tr><th>Zona</th><th>Km</th><th>Hora</th><th>Lluvia</th><th>Real</th><th>Fórmula</th><th>Modelo</th><th>Más cercano</th></tr></thead>
          <tbody>
            {ev.comparacion.map((c, i) => (
              <tr key={i}>
                <td>{c.zona}</td><td>{c.km}</td><td>{String(c.hora).padStart(2, '0')}:00{c.hora_pico ? ' · pico' : ''}</td>
                <td>{c.lluvia ? 'Sí' : 'No'}</td><td><b>{c.real}</b></td>
                <td className={c.mas_cercano === 'formula' ? 'mejor' : ''}>{c.formula}</td>
                <td className={c.mas_cercano === 'modelo' ? 'mejor' : ''}>{c.modelo}</td>
                <td>{c.mas_cercano === 'modelo' ? 'Modelo' : 'Fórmula'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
