import { useEffect, useState } from 'react'
import { Calculator } from 'lucide-react'
import { estimarATiempo, modeloATiempo, pct } from '../../lib/clima.js'
import { Conjuntos, Matriz, Metricas, ValidacionCruzada } from './comun.jsx'

// Detalles técnicos de «¿Llega a tiempo?»: entrenamiento, validación y prueba (backend/app/a_tiempo.py).
export default function ATiempoPanel({ sinSimulador = false }) {
  const [ev, setEv] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { modeloATiempo().then(setEv).catch((e) => setError(e.message)) }, [])

  if (error) return <p className="form-error">{error}</p>
  if (!ev) return <div className="panel muted">Entrenando los árboles…</div>
  return (
    <>
      <section className="panel">
        <h2 className="form-section-title">¿La ambulancia llegará a tiempo?</h2>
        <p className="ia-intro">
          Al asignar una emergencia, un árbol de decisión estima si la ambulancia llegará en {ev.umbral_min} minutos o menos,
          con la distancia desde el IMSS 220, el tráfico, las ambulancias libres y la experiencia del operador.
          Se aprendió con {ev.servicios} servicios de ejemplo ({ev.clases.a_tiempo} a tiempo, {ev.clases.tarde} tarde).
        </p>
        <Conjuntos c={ev.conjuntos} />
      </section>

      <section className="panel">
        <h2 className="form-section-title">1. Elegir la profundidad del árbol con VALIDACIÓN</h2>
        <div className="ia-prof">
          {ev.comparacion.map((c) => (
            <div key={c.profundidad} className={`ia-prof-col${c.elegido ? ' elegido' : ''}`}>
              <div className="ia-prof-barras">
                <i className="ent" style={{ height: `${c.entrenamiento * 100}%` }} title={`Entrenamiento ${pct(c.entrenamiento, 1)}`} />
                <i className="val" style={{ height: `${c.validacion * 100}%` }} title={`Validación ${pct(c.validacion, 1)}`} />
              </div>
              <b>{c.profundidad}</b>
              <small>{pct(c.entrenamiento, 1)} / {pct(c.validacion, 1)}</small>
              <em className={c.ajuste.includes('sobre') ? 'sobre' : c.ajuste.includes('sub') ? 'sub' : ''}>{c.ajuste}</em>
            </div>
          ))}
        </div>
        <p className="ia-leyenda"><i className="ent" /> Entrenamiento <i className="val" /> Validación · Elegido: profundidad <b>{ev.profundidad}</b>, la mejor en validación.</p>
        <p className="muted ia-nota">
          Los árboles de profundidad 10 y sin límite sacan 100 % en entrenamiento porque memorizan los servicios (incluido el ruido),
          pero bajan en validación: eso es sobreajuste. Los de profundidad 1 y 2 se quedan cortos. La profundidad {ev.profundidad} también
          tiene una brecha de más de 10 puntos, pero es la que mejor funciona con servicios que no vio.
        </p>
      </section>

      <div className="ia-grid">
        <section className="panel">
          <h2 className="form-section-title">2. Calificación final con PRUEBA</h2>
          <Metricas m={ev.prueba} nota={`Recall de «llega tarde»: ${pct(ev.prueba.recall_tarde, 1)}. El conjunto de prueba no se usó para entrenar ni para elegir la profundidad.`} />
          <Matriz m={ev.matriz} etiquetas={['Tarde', 'A tiempo']} positiva="fp"
                  explicacion="El error más costoso es el falso positivo (en rojo): el sistema dice «llegará a tiempo», no se pide apoyo y la ambulancia llega tarde." />
        </section>
        <section className="panel">
          <h2 className="form-section-title">3. Validación cruzada (5 particiones)</h2>
          <ValidacionCruzada cv={ev.validacion_cruzada} metrica="exactitud" />
          <h2 className="form-section-title ia-sub">¿En qué se fija?</h2>
          <ul className="ia-barras">
            {ev.importancias.map((i) => (
              <li key={i.factor}><span>{i.factor}</span><div className="ia-barra"><i style={{ width: `${i.peso * 100}%` }} /></div><b>{Math.round(i.peso * 100)} %</b></li>
            ))}
          </ul>
        </section>
      </div>

      {!sinSimulador && <Simulador />}
    </>
  )
}

function Simulador() {
  const [f, setF] = useState({ distancia_km: 9.5, nivel_trafico: 8, ambulancias_libres: 1, experiencia_operador: 3 })
  const [r, setR] = useState(null)
  const [error, setError] = useState('')
  const cambiar = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const enviar = async (e) => {
    e.preventDefault()
    setError('')
    try {
      setR(await estimarATiempo(Object.fromEntries(Object.entries(f).map(([k, v]) => [k, Number(v)]))))
    } catch (err) { setError(err.message) }
  }
  return (
    <section className="panel">
      <h2 className="form-section-title titulo-icono"><Calculator size={15} /> Probar una emergencia nueva</h2>
      <form className="ia-form" onSubmit={enviar}>
        <label>Distancia (km)<input type="number" min="0.5" max="100" step="0.1" value={f.distancia_km} onChange={cambiar('distancia_km')} /></label>
        <label>Tráfico (0 libre – 10 saturado)<input type="number" min="0" max="10" step="0.5" value={f.nivel_trafico} onChange={cambiar('nivel_trafico')} /></label>
        <label>Ambulancias libres<input type="number" min="0" max="50" value={f.ambulancias_libres} onChange={cambiar('ambulancias_libres')} /></label>
        <label>Experiencia del operador (años)<input type="number" min="0" max="50" step="0.5" value={f.experiencia_operador} onChange={cambiar('experiencia_operador')} /></label>
        <button className="btn-primary compact">Estimar</button>
      </form>
      {error && <p className="form-error">{error}</p>}
      {r && (
        <div className={`ia-resultado${r.llega_a_tiempo ? '' : ' alerta'}`}>
          <div><span>Probabilidad de llegar a tiempo</span><b>{pct(r.probabilidad)}</b></div>
          <p>{r.mensaje}</p>
        </div>
      )}
    </section>
  )
}
