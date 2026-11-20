import { useEffect, useState } from 'react'
import { COLOR_PERFIL, confiabilidadSegmentacion, pct } from '../../lib/clima.js'

// Práctica 08: análisis avanzado de los perfiles de servicio (K-Means). Inicializaciones,
// escaladores, estabilidad con Adjusted Rand Index y servicios atípicos (percentil 95).
export default function ConfiabilidadPanel() {
  const [c, setC] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { confiabilidadSegmentacion().then(setC).catch((e) => setError(e.message)) }, [])

  if (error) return <p className="form-error">{error}</p>
  if (!c) return <div className="panel muted">Repitiendo K-Means con varias semillas (tarda unos segundos)…</div>
  const est = c.estabilidad
  const a = c.atipicos
  return (
    <>
      <section className="panel">
        <h2 className="form-section-title">Práctica 08 · ¿Qué tan confiables son los perfiles?</h2>
        <p className="ia-intro">
          Se repitió K-Means (K = {c.k}, n_init = {c.n_init}) cambiando la inicialización, el escalador y la semilla para ver si los
          {' '}{c.servicios} servicios siguen cayendo en los mismos grupos. Después se midió la distancia de cada servicio al centro de su
          perfil para encontrar los que se salen de lo normal.
        </p>
        <div className="ia-grid">
          <div>
            <h3 className="iah-h3">Inicialización</h3>
            <Tabla filas={c.inicializaciones} cols={[['inicializacion', 'Método'], ['inercia', 'Inercia'], ['silhouette', 'Silhouette']]} />
            <p className="muted ia-nota">Con n_init = {c.n_init} las dos llegan a la misma solución. Una inercia menor no basta para decidir.</p>
          </div>
          <div>
            <h3 className="iah-h3">Escalador</h3>
            <Tabla filas={c.escaladores} cols={[['escalador', 'Escalador'], ['silhouette', 'Silhouette'], ['ari_contra_standard', 'ARI vs Standard']]} />
            <p className="muted ia-nota">La inercia no se compara entre escalas distintas ({c.escaladores.map((e) => e.inercia).join(' vs ')}). Se compara el Silhouette y cuánto coinciden los grupos.</p>
          </div>
        </div>
      </section>

      <div className="ia-grid">
        <section className="panel">
          <h2 className="form-section-title">Estabilidad entre semillas (ARI)</h2>
          <MatrizARI est={est} />
          <p className="muted ia-nota">ARI promedio: <b>{est.ari_promedio}</b>. 1 = misma agrupación; cerca de 0 = como al azar.</p>
        </section>
        <section className="panel">
          <h2 className="form-section-title">Perfiles según el escalador</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Perfil</th>{c.escaladores.map((e) => <th key={e.escalador}>{e.escalador}</th>)}</tr></thead>
              <tbody>
                {c.escaladores[0].perfiles.map((p, i) => (
                  <tr key={p.perfil}>
                    <td style={{ color: COLOR_PERFIL[p.perfil], fontWeight: 600 }}>{p.perfil}</td>
                    {c.escaladores.map((e) => {
                      const q = e.perfiles[i]
                      return <td key={e.escalador}>{q.servicios} serv. · {q.promedio.tiempo_respuesta_min} min · {q.promedio.distancia_km} km</td>
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section className="panel">
        <h2 className="form-section-title">Servicios atípicos (percentil {a.percentil})</h2>
        <Distancias a={a} />
        <p className="muted ia-nota">
          Umbral de distancia: <b>{a.umbral}</b>. {a.total} servicios ({pct(a.porcentaje / 100, 1)}) lo superan:
          {' '}{Object.entries(a.por_perfil).map(([k, v]) => `${v} de ${k.toLowerCase()}`).join(', ')}.
          Es una regla exploratoria: estar lejos no significa que el servicio esté mal clasificado.
        </p>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Servicio</th><th>Perfil</th><th>Distancia</th><th>Silhouette</th><th>km</th><th>Tráfico</th><th>min</th><th>Libres</th></tr></thead>
            <tbody>
              {a.ejemplos.map((x) => (
                <tr key={x.servicio}>
                  <td>{x.servicio}</td><td style={{ color: COLOR_PERFIL[x.perfil] }}>{x.perfil}</td><td>{x.distancia}</td><td>{x.silhouette}</td>
                  <td>{x.distancia_km}</td><td>{x.nivel_trafico}</td><td>{x.tiempo_respuesta_min}</td><td>{x.ambulancias_libres}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}

function Tabla({ filas, cols }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{cols.map(([, t]) => <th key={t}>{t}</th>)}</tr></thead>
        <tbody>{filas.map((f, i) => <tr key={i}>{cols.map(([k]) => <td key={k}>{f[k]}</td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}

function MatrizARI({ est }) {
  const n = est.semillas.length, t = 44, m = 40
  return (
    <svg viewBox={`0 0 ${m + n * t} ${m + n * t}`} className="ia-svg" role="img" aria-label="Matriz de estabilidad ARI">
      {est.semillas.map((s, i) => (
        <g key={s}>
          <text x={m - 6} y={m + i * t + t / 2 + 4} textAnchor="end">{s}</text>
          <text x={m + i * t + t / 2} y={m - 8} textAnchor="middle">{s}</text>
        </g>
      ))}
      {est.matriz.map((fila, i) => fila.map((v, j) => (
        <g key={`${i}-${j}`}>
          <rect x={m + j * t} y={m + i * t} width={t - 2} height={t - 2} rx="4" fill="#1a7a41" fillOpacity={0.15 + 0.85 * Math.max(0, v)} />
          <text x={m + j * t + t / 2 - 1} y={m + i * t + t / 2 + 4} textAnchor="middle" fill="#fff" className="valor">{v.toFixed(2)}</text>
        </g>
      )))}
    </svg>
  )
}

function Distancias({ a }) {
  const W = 760, H = 220, m = { l: 40, r: 10, t: 10, b: 24 }
  const max = Math.max(...a.distancias) * 1.05
  const sx = (i) => m.l + (i / (a.distancias.length - 1)) * (W - m.l - m.r)
  const sy = (d) => H - m.b - (d / max) * (H - m.t - m.b)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="ia-svg ancho" role="img" aria-label="Distancia de cada servicio al centro de su perfil">
      {[0, max / 2, max].map((v) => (
        <g key={v}><line x1={m.l} x2={W - m.r} y1={sy(v)} y2={sy(v)} className="rejilla" /><text x={m.l - 6} y={sy(v) + 4} textAnchor="end">{v.toFixed(1)}</text></g>
      ))}
      {a.distancias.map((d, i) => (
        <circle key={i} cx={sx(i)} cy={sy(d)} r={d > a.umbral ? 3.6 : 2.4} fill={COLOR_PERFIL[a.perfiles[i]]} fillOpacity={d > a.umbral ? 1 : 0.4} />
      ))}
      <line x1={m.l} x2={W - m.r} y1={sy(a.umbral)} y2={sy(a.umbral)} stroke="currentColor" strokeDasharray="6 4" />
      <text x={W - m.r} y={sy(a.umbral) - 6} textAnchor="end" className="valor">Umbral P{a.percentil}</text>
      <text x={(W + m.l) / 2} y={H - 4} textAnchor="middle" className="eje">Servicio</text>
    </svg>
  )
}
