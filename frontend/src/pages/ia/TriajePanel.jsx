import { useEffect, useState } from 'react'
import { Activity } from 'lucide-react'
import { estimarTriaje, modeloTriaje, pct } from '../../lib/clima.js'
import { Conjuntos, Matriz, Metricas, ValidacionCruzada } from './comun.jsx'

const NOMBRE = { 'Decision Tree': 'Árbol de decisión', 'Random Forest': 'Bosque aleatorio', KNN: 'KNN (vecinos más cercanos)' }

// Detalles técnicos del triaje: comparación de algoritmos (backend/app/triaje.py).
export default function TriajePanel({ sinSimulador = false }) {
  const [ev, setEv] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { modeloTriaje().then(setEv).catch((e) => setError(e.message)) }, [])

  if (error) return <p className="form-error">{error}</p>
  if (!ev) return <div className="panel muted">Entrenando y comparando los tres algoritmos…</div>
  return (
    <>
      <section className="panel">
        <h2 className="form-section-title">Triaje: ¿la emergencia es crítica?</h2>
        <p className="ia-intro">
          Cuando llegan varias emergencias a la vez y hay pocas ambulancias libres, la IA estima cuáles son críticas con
          la saturación de oxígeno, la frecuencia cardiaca, la escala de Glasgow y la edad. Las críticas suben al principio
          de «Emergencias por atender». Se aprendió con {ev.reportes} reportes de ejemplo ({ev.clases.critica} críticos);
          la regla que los etiqueta <b>no</b> es un protocolo clínico real.
        </p>
        <Conjuntos c={ev.conjuntos} />
      </section>

      <section className="panel">
        <h2 className="form-section-title">1. Comparación de algoritmos con VALIDACIÓN (ordenados por F1)</h2>
        <div className="table-wrap">
          <table className="ia-tabla">
            <thead><tr><th>Algoritmo</th><th>Exactitud</th><th>Precisión</th><th>Recall</th><th>F1-score</th></tr></thead>
            <tbody>
              {ev.comparacion.map((c) => (
                <tr key={c.algoritmo} className={c.algoritmo === ev.elegido ? 'elegido' : ''}>
                  <td><b>{NOMBRE[c.algoritmo]}</b>{c.algoritmo === ev.elegido && <span className="ia-chip">Elegido</span>}</td>
                  <td>{pct(c.exactitud, 2)}</td><td>{pct(c.precision, 2)}</td><td>{pct(c.recall, 2)}</td><td className="mejor">{pct(c.f1, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted ia-nota">Se elige por F1 porque equilibra no dejar pasar críticas (recall) sin llenar la cola de falsas alarmas (precisión). La ventaja es pequeña y podría cambiar con otros datos.</p>
      </section>

      <div className="ia-grid">
        <section className="panel">
          <h2 className="form-section-title">2. {NOMBRE[ev.elegido]} reentrenado y calificado con PRUEBA</h2>
          <Metricas m={ev.prueba} />
          <Matriz m={ev.matriz} etiquetas={['No crítica', 'Crítica']} positiva="fn"
                  explicacion={`El error más grave es el falso negativo (en rojo): ${ev.matriz.fn} emergencias críticas se habrían quedado esperando en la cola.`} />
        </section>
        <section className="panel">
          <h2 className="form-section-title">3. Validación cruzada (F1, 5 particiones)</h2>
          <ValidacionCruzada cv={ev.validacion_cruzada} metrica="F1" />
          {!sinSimulador && <Simulador />}
        </section>
      </div>

      <section className="panel">
        <h2 className="form-section-title">4. Experimentos: cambiar un solo hiperparámetro</h2>
        <div className="ia-experimentos">
          {ev.experimentos.map((x) => {
            const max = Math.max(...x.filas.map((f) => f.f1))
            return (
              <div key={x.clave} className="ia-exp">
                <strong>Exp. {x.clave}: {NOMBRE[x.algoritmo]}</strong>
                <small>variando <code>{x.parametro}</code></small>
                <table className="ia-tabla compacta">
                  <thead><tr><th>{x.parametro}</th><th>Entren.</th><th>F1 valid.</th></tr></thead>
                  <tbody>
                    {x.filas.map((f) => (
                      <tr key={f.valor}><td>{f.valor}</td><td>{pct(f.exactitud_entrenamiento, 1)}</td><td className={f.f1 === max ? 'mejor' : ''}>{pct(f.f1, 2)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          })}
        </div>
      </section>
    </>
  )
}

function Simulador() {
  const [f, setF] = useState({ saturacion_oxigeno: 84, frecuencia_cardiaca: 132, escala_glasgow: 10, edad: 71 })
  const [r, setR] = useState(null)
  const [error, setError] = useState('')
  const cambiar = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const enviar = async (e) => {
    e.preventDefault()
    setError('')
    try {
      setR(await estimarTriaje(Object.fromEntries(Object.entries(f).map(([k, v]) => [k, Number(v)]))))
    } catch (err) { setError(err.message) }
  }
  return (
    <>
      <h2 className="form-section-title titulo-icono ia-sub"><Activity size={15} /> Probar un reporte</h2>
      <form className="ia-form" onSubmit={enviar}>
        <label>SpO₂ (%)<input type="number" min="50" max="100" value={f.saturacion_oxigeno} onChange={cambiar('saturacion_oxigeno')} /></label>
        <label>Frecuencia cardiaca<input type="number" min="20" max="250" value={f.frecuencia_cardiaca} onChange={cambiar('frecuencia_cardiaca')} /></label>
        <label>Glasgow<input type="number" min="3" max="15" value={f.escala_glasgow} onChange={cambiar('escala_glasgow')} /></label>
        <label>Edad<input type="number" min="0" max="120" value={f.edad} onChange={cambiar('edad')} /></label>
        <button className="btn-primary compact">Clasificar</button>
      </form>
      {error && <p className="form-error">{error}</p>}
      {r && (
        <div className={`ia-resultado${r.critica ? ' alerta' : ''}`}>
          <div><span>Probabilidad de ser crítica</span><b>{pct(r.probabilidad)}</b></div>
          <p>{r.mensaje}</p>
        </div>
      )}
    </>
  )
}
