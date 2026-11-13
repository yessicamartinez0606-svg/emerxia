import { useEffect, useState } from 'react'
import { Calculator } from 'lucide-react'
import { COLOR_PERFIL, estimarSegmentacion, modeloSegmentacion } from '../../lib/clima.js'

// Práctica 07: perfiles de servicio con K-Means (aprendizaje no supervisado).
export default function SegmentacionPanel({ sinSimulador = false }) {
  const [ev, setEv] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { modeloSegmentacion().then(setEv).catch((e) => setError(e.message)) }, [])

  if (error) return <p className="form-error">{error}</p>
  if (!ev) return <div className="panel muted">Agrupando servicios con K-Means…</div>
  return (
    <>
      <section className="panel">
        <h2 className="form-section-title">Perfiles de servicio con K-Means</h2>
        <p className="ia-intro">
          K-Means agrupó {ev.servicios} servicios de ambulancia (de ejemplo) por su distancia desde el IMSS 220, el tráfico, el tiempo de
          respuesta y las ambulancias libres, <b>sin decirle cuál era cuál</b>: aprendizaje no supervisado. Antes se escalaron las 4 variables
          con StandardScaler para que el tiempo y la distancia no dominen. Cada emergencia abierta se acomoda en el perfil al que más se parece.
        </p>
        <div className="ia-perfiles">
          {ev.perfiles.map((p) => (
            <div key={p.perfil} className="ia-perfil" style={{ '--c': COLOR_PERFIL[p.perfil] }}>
              <strong>{p.perfil}</strong>
              <small>{p.servicios} servicios</small>
              <dl>
                <div><dt>Distancia</dt><dd>{p.promedio.distancia_km} km</dd></div>
                <div><dt>Tráfico</dt><dd>{p.promedio.nivel_trafico}/10</dd></div>
                <div><dt>Tiempo</dt><dd>{p.promedio.tiempo_respuesta_min} min</dd></div>
                <div><dt>Libres</dt><dd>{p.promedio.ambulancias_libres}</dd></div>
              </dl>
              <p>{p.estrategia}</p>
            </div>
          ))}
        </div>
      </section>

      <div className="ia-grid">
        <section className="panel">
          <h2 className="form-section-title">¿Cuántos grupos? Método del codo</h2>
          <Linea puntos={ev.codo.map((c) => ({ x: c.k, y: c.inercia }))} marcar={ev.k} etiquetaY="Inercia (WCSS)" decimales={0} />
          <p className="muted ia-nota">La inercia baja mucho hasta K = 3 y después casi se aplana: ahí está el codo.</p>
        </section>
        <section className="panel">
          <h2 className="form-section-title">Silhouette Score</h2>
          <Linea puntos={ev.silhouette.map((c) => ({ x: c.k, y: c.silhouette }))} marcar={ev.k} etiquetaY="Silhouette" decimales={2} />
          <p className="muted ia-nota">K = 2 da el valor más alto (0.47), pero K = 3 queda muy cerca ({ev.silhouette_final}) y separa los servicios intermedios de los que requieren apoyo, que es lo que necesita la central. Inercia final: {ev.inercia_final}.</p>
        </section>
      </div>

      <section className="panel">
        <h2 className="form-section-title">Servicios agrupados: distancia contra tiempo de respuesta</h2>
        <Dispersion ev={ev} />
      </section>

      {!sinSimulador && <Simulador />}
    </>
  )
}

function Linea({ puntos, marcar, etiquetaY, decimales }) {
  const W = 420, H = 200, m = { l: 48, r: 12, t: 12, b: 30 }
  const xs = puntos.map((p) => p.x), ys = puntos.map((p) => p.y)
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y1 = Math.max(...ys) * 1.05, y0 = Math.min(0, Math.min(...ys))
  const sx = (x) => m.l + ((x - x0) / (x1 - x0)) * (W - m.l - m.r)
  const sy = (y) => H - m.b - ((y - y0) / (y1 - y0)) * (H - m.t - m.b)
  const d = puntos.map((p, i) => `${i ? 'L' : 'M'}${sx(p.x)},${sy(p.y)}`).join(' ')
  const ticks = [0, 0.5, 1].map((f) => y0 + f * (y1 - y0))
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="ia-svg" role="img" aria-label={etiquetaY}>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={m.l} x2={W - m.r} y1={sy(t)} y2={sy(t)} className="rejilla" />
          <text x={m.l - 6} y={sy(t) + 4} textAnchor="end">{t.toFixed(decimales)}</text>
        </g>
      ))}
      <path d={d} className="linea" />
      {puntos.map((p) => (
        <g key={p.x}>
          <circle cx={sx(p.x)} cy={sy(p.y)} r={p.x === marcar ? 6 : 3.5} className={p.x === marcar ? 'marca' : 'punto'} />
          <text x={sx(p.x)} y={H - 10} textAnchor="middle">{p.x}</text>
          {p.x === marcar && <text x={sx(p.x) + 9} y={sy(p.y) - 8} className="valor">K={p.x}: {p.y.toFixed(decimales === 0 ? 0 : 3)}</text>}
        </g>
      ))}
    </svg>
  )
}

function Dispersion({ ev }) {
  const W = 760, H = 320, m = { l: 44, r: 16, t: 12, b: 36 }
  const maxX = Math.ceil(Math.max(...ev.puntos.map((p) => p.km)) / 5) * 5
  const maxY = Math.ceil(Math.max(...ev.puntos.map((p) => p.min)) / 10) * 10
  const sx = (x) => m.l + (x / maxX) * (W - m.l - m.r)
  const sy = (y) => H - m.b - (y / maxY) * (H - m.t - m.b)
  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} className="ia-svg ancho" role="img" aria-label="Servicios agrupados por K-Means">
        {Array.from({ length: maxY / 10 + 1 }, (_, i) => i * 10).map((t) => (
          <g key={`y${t}`}><line x1={m.l} x2={W - m.r} y1={sy(t)} y2={sy(t)} className="rejilla" /><text x={m.l - 6} y={sy(t) + 4} textAnchor="end">{t}</text></g>
        ))}
        {Array.from({ length: maxX / 5 + 1 }, (_, i) => i * 5).map((t) => (
          <text key={`x${t}`} x={sx(t)} y={H - 18} textAnchor="middle">{t}</text>
        ))}
        <text x={(W + m.l) / 2} y={H - 2} textAnchor="middle" className="eje">Distancia desde el IMSS 220 (km)</text>
        <text x={12} y={H / 2} textAnchor="middle" className="eje" transform={`rotate(-90 12 ${H / 2})`}>Minutos</text>
        {ev.puntos.map((p, i) => <circle key={i} cx={sx(p.km)} cy={sy(p.min)} r="3.2" fill={COLOR_PERFIL[p.perfil]} fillOpacity=".55" />)}
        {ev.perfiles.map((p) => (
          <g key={p.perfil} transform={`translate(${sx(p.centroide.distancia_km)},${sy(p.centroide.tiempo_respuesta_min)})`}>
            <path d="M-8,-8L8,8M8,-8L-8,8" stroke="#fff" strokeWidth="6" strokeLinecap="round" />
            <path d="M-8,-8L8,8M8,-8L-8,8" stroke={COLOR_PERFIL[p.perfil]} strokeWidth="3.2" strokeLinecap="round" />
          </g>
        ))}
      </svg>
      <p className="ia-leyenda">
        {Object.entries(COLOR_PERFIL).map(([k, c]) => <span key={k}><i style={{ background: c }} /> {k}</span>)}
        <span>✕ centroide de cada grupo</span>
      </p>
    </>
  )
}

function Simulador() {
  const [f, setF] = useState({ distancia_km: 12.5, nivel_trafico: 8, tiempo_respuesta_min: 25, ambulancias_libres: 1 })
  const [r, setR] = useState(null)
  const [error, setError] = useState('')
  const cambiar = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const enviar = async (e) => {
    e.preventDefault()
    setError('')
    try { setR(await estimarSegmentacion(Object.fromEntries(Object.entries(f).map(([k, v]) => [k, Number(v)])))) } catch (err) { setError(err.message) }
  }
  return (
    <section className="panel">
      <h2 className="form-section-title titulo-icono"><Calculator size={15} /> ¿A qué perfil se parece un servicio?</h2>
      <form className="ia-form" onSubmit={enviar}>
        <label>Distancia (km)<input type="number" min="0.5" max="100" step="0.1" value={f.distancia_km} onChange={cambiar('distancia_km')} /></label>
        <label>Tráfico (0-10)<input type="number" min="0" max="10" step="0.5" value={f.nivel_trafico} onChange={cambiar('nivel_trafico')} /></label>
        <label>Tiempo de respuesta (min)<input type="number" min="1" max="180" step="0.5" value={f.tiempo_respuesta_min} onChange={cambiar('tiempo_respuesta_min')} /></label>
        <label>Ambulancias libres<input type="number" min="0" max="50" value={f.ambulancias_libres} onChange={cambiar('ambulancias_libres')} /></label>
        <button className="btn-primary compact">Ubicar</button>
      </form>
      {error && <p className="form-error">{error}</p>}
      {r && (
        <div className="ia-resultado neutro" style={{ '--c': COLOR_PERFIL[r.perfil] }}>
          <div><span>Perfil</span><b style={{ color: COLOR_PERFIL[r.perfil] }}>{r.perfil}</b></div>
          <p>{r.estrategia}</p>
        </div>
      )}
    </section>
  )
}
