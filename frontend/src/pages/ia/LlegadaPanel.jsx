import { useEffect, useState } from 'react'
import { Trophy } from 'lucide-react'
import { modeloLlegada } from '../../lib/clima.js'

// Detalles técnicos del tiempo de llegada: fórmula fija contra árbol de regresión
// (backend/app/eta.py). Se muestran dentro de «Ver detalles técnicos».
export default function LlegadaPanel() {
  const [ev, setEv] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { modeloLlegada().then(setEv).catch((e) => setError(e.message)) }, [])
  if (error) return <p className="form-error">{error}</p>
  if (!ev) return <div className="panel muted">Cargando el modelo…</div>
  return (
    <>
      <Calificacion ev={ev} />
      <div className="ia-grid">
        <Importancias ev={ev} />
        <Efectos ev={ev} />
      </div>
      <Comparacion ev={ev} />
    </>
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
      <p className="muted ia-nota">El historial de {ev.servicios} servicios es de ejemplo (semilla 42). Con datos reales de la central, el modelo se entrena igual.</p>
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
