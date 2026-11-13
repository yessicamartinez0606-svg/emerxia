import { useEffect, useState } from 'react'
import { Activity, CircleCheck, CircleAlert, Shapes } from 'lucide-react'
import { COLOR_PERFIL, aTiempoEmergencia, pct, segmentacionEmergencia, triajeEmergencia } from '../lib/clima.js'

function useDato(fn, id) {
  const [d, setD] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let vigente = true
    setError('')
    fn(id).then((x) => { if (vigente) setD(x) }).catch((e) => { if (vigente) setError(e.message) })
    return () => { vigente = false }
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps
  return [d, error]
}

// Práctica 04 aplicada a la emergencia: ¿la ambulancia llega en 15 min o menos?
export function LlegaATiempo({ emergenciaId }) {
  const [r, error] = useDato(aTiempoEmergencia, emergenciaId)
  if (error) return <section className="panel ia-em"><h2 className="form-section-title">¿Llega a tiempo?</h2><p className="muted">{error}</p></section>
  if (!r) return <section className="panel ia-em muted">Evaluando si llega a tiempo…</section>
  const Icono = r.llega_a_tiempo ? CircleCheck : CircleAlert
  return (
    <section className={`panel ia-em ${r.llega_a_tiempo ? 'bien' : 'mal'}`}>
      <h2 className="form-section-title">¿Llega a tiempo?</h2>
      <div className="ia-em-veredicto">
        <Icono size={26} aria-hidden="true" />
        <div>
          <b>{r.llega_a_tiempo ? 'Llegará a tiempo' : 'Llegará tarde'}</b>
          <span>{r.llega_a_tiempo ? `${pct(r.probabilidad)} de probabilidad de llegar en ${r.umbral_min} min o menos` : `solo ${pct(r.probabilidad)} de probabilidad de llegar en ${r.umbral_min} min o menos`}</span>
        </div>
      </div>
      {!r.llega_a_tiempo && <p className="ia-em-aviso">Considera pedir apoyo a otro hospital.</p>}
      <ul className="llegada-factores">
        <li>{r.datos.distancia_km} km {r.distancia_fuente === 'ruta' ? 'por la ruta' : 'aprox.'}</li>
        <li>Tráfico {r.datos.nivel_trafico}/10{r.lluvia ? ' (con lluvia)' : ''}</li>
        <li>{r.datos.ambulancias_libres} ambulancia(s) libres en el IMSS 220</li>
        <li title={r.operador}>Operador: {r.datos.experiencia_operador} años{r.operador.includes('promedio') ? ' (promedio)' : ''}</li>
      </ul>
    </section>
  )
}

// Práctica 05 aplicada a la emergencia: ¿es crítica según sus signos vitales?
export function TriajeEmergencia({ emergenciaId }) {
  const [r, error] = useDato(triajeEmergencia, emergenciaId)
  if (error) return <section className="panel ia-em"><h2 className="form-section-title">Prioridad del paciente</h2><p className="muted">{error}</p></section>
  if (!r) return <section className="panel ia-em muted">Evaluando la prioridad…</section>
  if (r.sin_signos) {
    return (
      <section className="panel ia-em">
        <h2 className="form-section-title titulo-icono"><Activity size={15} /> Prioridad del paciente</h2>
        <p className="muted">{r.mensaje} Se capturan al editar la emergencia, en «Signos vitales».</p>
      </section>
    )
  }
  return (
    <section className={`panel ia-em ${r.critica ? 'mal' : 'bien'}`}>
      <h2 className="form-section-title titulo-icono"><Activity size={15} /> Prioridad del paciente</h2>
      <div className="ia-em-veredicto">
        <span className="ia-em-prob">{pct(r.probabilidad)}</span>
        <div>
          <b>{r.critica ? 'Emergencia CRÍTICA' : 'No crítica'}</b>
          <span>probabilidad de que sea crítica</span>
        </div>
      </div>
      <p className={`ia-em-aviso${r.critica ? '' : ' suave'}`}>{r.mensaje}</p>
      <ul className="llegada-factores">
        <li>SpO₂ {r.signos.saturacion_oxigeno} %</li>
        <li>{r.signos.frecuencia_cardiaca} lpm</li>
        <li>Glasgow {r.signos.escala_glasgow}</li>
        <li>{r.signos.edad} años{r.edad_estimada ? ' (sin edad, se supone 40)' : ''}</li>
      </ul>
    </section>
  )
}

// Práctica 07 aplicada a la emergencia: ¿a qué perfil de servicio se parece? (K-Means)
export function PerfilServicio({ emergenciaId }) {
  const [r, error] = useDato(segmentacionEmergencia, emergenciaId)
  if (error) return <section className="panel ia-em"><h2 className="form-section-title">Tipo de servicio</h2><p className="muted">{error}</p></section>
  if (!r) return <section className="panel ia-em muted">Buscando el tipo de servicio…</section>
  const c = COLOR_PERFIL[r.perfil]
  return (
    <section className="panel ia-em perfil" style={{ '--c': c }}>
      <h2 className="form-section-title titulo-icono"><Shapes size={15} /> Tipo de servicio</h2>
      <div className="ia-em-veredicto">
        <span className="ia-em-nivel" aria-hidden="true">{[0, 1, 2].map((i) => <i key={i} className={i <= r.nivel ? 'on' : ''} />)}</span>
        <div>
          <b style={{ color: c }}>{r.perfil}</b>
          <span>tipo de servicio al que más se parece</span>
        </div>
      </div>
      <p className="ia-em-aviso suave">{r.estrategia}</p>
      <ul className="llegada-factores">
        <li>{r.datos.distancia_km} km</li>
        <li>Tráfico {r.datos.nivel_trafico}/10</li>
        <li>~{r.datos.tiempo_respuesta_min} min (estimado)</li>
        <li>{r.datos.ambulancias_libres} ambulancia(s) libres</li>
      </ul>
    </section>
  )
}
