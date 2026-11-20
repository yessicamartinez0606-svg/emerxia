import { useEffect, useState } from 'react'
import { BrainCircuit, CloudRain, Timer } from 'lucide-react'
import { llegadaEmergencia } from '../lib/clima.js'

// Tiempo estimado de llegada a una emergencia: fórmula fija vs. árbol de regresión.
// La lluvia sale del clima real de la zona; la hora y el día, del momento actual.
export default function LlegadaEstimada({ emergenciaId, km }) {
  const [r, setR] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let vigente = true
    setError('')
    llegadaEmergencia(emergenciaId, km).then((x) => { if (vigente) setR(x) }).catch((e) => { if (vigente) setError(e.message) })
    return () => { vigente = false }
  }, [emergenciaId, km])

  if (error) return <section className="panel llegada"><h2 className="form-section-title titulo-icono"><Timer size={15} /> Llegada estimada</h2><p className="muted">{error}</p></section>
  if (!r) return <section className="panel llegada muted">Calculando el tiempo de llegada…</section>

  const max = Math.max(r.modelo_min, r.formula_min, r.meta_min) * 1.1
  return (
    <section className={`panel llegada${r.cumple_meta ? '' : ' no-cumple'}`}>
      <h2 className="form-section-title titulo-icono"><Timer size={15} /> Llegada estimada</h2>
      <div className="llegada-cifras">
        <div className="llegada-principal">
          <BrainCircuit size={22} aria-hidden="true" />
          <div>
            <b>{r.modelo_min} min</b>
            <span>tiempo estimado</span>
          </div>
        </div>
        <div className="llegada-secundaria">
          <b>{r.formula_min} min</b>
          <span>cuenta simple, solo distancia</span>
        </div>
      </div>

      <div className="llegada-barras" aria-hidden="true">
        <div className="barra modelo" style={{ width: `${(r.modelo_min / max) * 100}%` }} />
        <div className="barra formula" style={{ width: `${(r.formula_min / max) * 100}%` }} />
        <span className="meta" style={{ left: `${(r.meta_min / max) * 100}%` }}>meta {r.meta_min} min</span>
      </div>

      <p className={`llegada-mensaje${r.cumple_meta ? '' : ' alerta'}`}>{r.mensaje}</p>
      <ul className="llegada-factores">
        <li>{r.zona} · {r.distancia_km} km {r.distancia_fuente === 'ruta' ? 'por la ruta' : 'aprox.'}</li>
        <li>{String(r.hora).padStart(2, '0')}:00 h{r.hora_pico ? ' · hora pico' : ''}{r.fin_de_semana ? ' · fin de semana' : ''}</li>
        <li className={r.lluvia ? 'lluvia' : ''}>
          {r.lluvia && <CloudRain size={13} aria-hidden="true" />}
          {r.clima?.descripcion || (r.lluvia ? 'Lluvia' : 'Sin lluvia')}{r.clima?.simulado ? ' (simulado)' : ''}
        </li>
      </ul>
      {r.diferencia_min > 1 && (
        <p className="muted llegada-nota">La cuenta simple se queda corta por {r.diferencia_min} min porque no toma en cuenta {[r.hora_pico && 'la hora pico', r.lluvia && 'la lluvia', r.zona === 'Lerma' && 'la zona'].filter(Boolean).join(' ni ') || 'el contexto'}.</p>
      )}
    </section>
  )
}
