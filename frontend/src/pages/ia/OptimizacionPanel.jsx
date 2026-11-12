import { useEffect, useState } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'
import { NOMBRE_ALGORITMO, iniciarOptimizacion, pct, verOptimizacion } from '../../lib/clima.js'
import { Matriz, Metricas } from './comun.jsx'

const fmtValor = (v) => (typeof v === 'number' ? String(v) : v)
const Params = ({ p }) => (
  <span className="ia-params">{Object.entries(p).map(([k, v]) => <code key={k}>{k}={fmtValor(v)}</code>)}</span>
)

// Práctica 06: GridSearchCV y RandomizedSearchCV sobre el triaje de la práctica 05.
export default function OptimizacionPanel() {
  const [r, setR] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let vigente = true
    let t
    const cargar = () => verOptimizacion()
      .then((x) => {
        if (!vigente) return
        setR(x); setError('')
        if (x.estado === 'entrenando') t = setTimeout(cargar, 4000)     // revisa hasta que termine
      })
      .catch((e) => vigente && setError(e.message))
    cargar()
    return () => { vigente = false; clearTimeout(t) }
  }, [])

  if (error) return <p className="form-error">{error}</p>
  if (!r) return <div className="panel muted">Consultando la optimización…</div>
  if (r.estado === 'error') {
    return (
      <section className="panel">
        <p className="form-error">La optimización falló: {r.error}</p>
        <button type="button" className="btn-ghost tall" onClick={() => iniciarOptimizacion().then(setR)}><RefreshCw size={14} /> Intentar de nuevo</button>
      </section>
    )
  }
  if (r.estado !== 'listo') {
    return (
      <section className="panel ia-esperando">
        <Loader2 size={22} className="girando" aria-hidden="true" />
        <div>
          <strong>Probando combinaciones de hiperparámetros…</strong>
          <p className="muted">GridSearchCV entrena más de 1,600 modelos (324 combinaciones × 5 particiones). Tarda alrededor de un minuto la primera vez{r.segundos ? ` · ${r.segundos} s` : ''}. Después queda guardado y carga al instante. Mientras tanto, el triaje usa el modelo de la práctica 05.</p>
        </div>
      </section>
    )
  }

  const porAlg = Object.fromEntries(r.random.map((x) => [x.algoritmo, x]))
  const elegido = r.grid.find((g) => g.algoritmo === r.elegido)
  const mejora = r.prueba.f1 - r.antes.prueba.f1
  return (
    <>
      <section className="panel">
        <h2 className="form-section-title">Optimización de hiperparámetros del triaje</h2>
        <p className="ia-intro">
          En la práctica 05 cada algoritmo usó una configuración fija. Aquí se prueban muchas configuraciones con validación cruzada
          estratificada de 5 particiones (métrica F1) usando el 80 % de los reportes ({r.conjuntos.entrenamiento});
          el 20 % de prueba ({r.conjuntos.prueba}) no se toca hasta el final y es el mismo de la práctica 05.
          <b> El triaje del sistema ya usa el modelo optimizado.</b>
        </p>
        <div className="ia-gs">
          {r.grid.map((g) => {
            const rnd = porAlg[g.algoritmo]
            return (
              <div key={g.algoritmo} className={`ia-gs-alg${g.algoritmo === r.elegido ? ' elegido' : ''}`}>
                <strong>{NOMBRE_ALGORITMO[g.algoritmo]}{g.algoritmo === r.elegido && <span className="ia-chip">Elegido</span>}</strong>
                <div className="ia-gs-barra"><span>GridSearchCV</span><div><i className="grid" style={{ width: `${g.mejor_f1 * 100}%` }} /></div><b>{pct(g.mejor_f1, 2)}</b></div>
                <div className="ia-gs-barra"><span>RandomizedSearchCV</span><div><i className="rnd" style={{ width: `${rnd.mejor_f1 * 100}%` }} /></div><b>{pct(rnd.mejor_f1, 2)}</b></div>
                <small>Grid: {g.combinaciones} combinaciones ({g.entrenamientos} entrenamientos, {g.segundos} s) · Random: 20 al azar ({rnd.segundos} s)</small>
                <div className="ia-gs-params"><span>Grid</span><Params p={g.hiperparametros} /></div>
                <div className="ia-gs-params"><span>Random</span><Params p={rnd.hiperparametros} /></div>
              </div>
            )
          })}
        </div>
        <p className="muted ia-nota">
          RandomizedSearchCV probó solo 20 configuraciones por algoritmo y llegó cerca (incluso arriba en el árbol y en KNN, porque
          explora valores fuera de la rejilla). Se elige con GridSearchCV, como en la práctica: el mayor F1 en validación cruzada.
        </p>
      </section>

      <div className="ia-grid">
        <section className="panel">
          <h2 className="form-section-title">{NOMBRE_ALGORITMO[r.elegido]} optimizado, calificado con PRUEBA</h2>
          <Metricas m={r.prueba} />
          <div className="ia-antes">
            <div><span>Práctica 05 (sin optimizar)</span><b>{pct(r.antes.prueba.f1, 2)}</b><small>F1 en prueba</small></div>
            <div className="flecha" aria-hidden="true">→</div>
            <div className="despues"><span>Práctica 06 (optimizado)</span><b>{pct(r.prueba.f1, 2)}</b><small>{mejora >= 0 ? '+' : ''}{(mejora * 100).toFixed(2)} puntos</small></div>
          </div>
          <Matriz m={r.matriz} etiquetas={['No crítica', 'Crítica']} positiva="fn"
                  explicacion={`Antes: ${r.antes.matriz.fp} falsas alarmas y ${r.antes.matriz.fn} críticas no detectadas. Ahora: ${r.matriz.fp} y ${r.matriz.fn}. La mejora viene de menos falsas alarmas; las críticas no detectadas siguen igual.`} />
        </section>
        <section className="panel">
          <h2 className="form-section-title">Las 5 mejores combinaciones de {NOMBRE_ALGORITMO[r.elegido]}</h2>
          <div className="table-wrap">
            <table className="ia-tabla compacta">
              <thead><tr><th>#</th><th>Hiperparámetros</th><th>F1 entren.</th><th>F1 valid.</th></tr></thead>
              <tbody>
                {elegido.top.map((t, i) => (
                  <tr key={i}><td>{i + 1}</td><td className="envolver"><Params p={t.hiperparametros} /></td><td>{pct(t.f1_entrenamiento, 1)}</td><td className={i === 0 ? 'mejor' : ''}>{pct(t.f1_validacion, 2)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted ia-nota">Si el F1 de entrenamiento es mucho mayor que el de validación, la combinación se está sobreajustando. max_depth = 5 limita cada árbol del bosque y reduce esa brecha.</p>
        </section>
      </div>
    </>
  )
}
