import { useEffect, useState } from 'react'
import { COLOR_PERFIL, pcaSegmentacion, pct } from '../../lib/clima.js'

// Práctica 09: reducción de dimensionalidad con PCA. Las 4 variables de cada servicio
// (estandarizadas) se resumen en componentes principales; PC1 y PC2 dibujan el mapa.
export default function PcaPanel() {
  const [p, setP] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { pcaSegmentacion().then(setP).catch((e) => setError(e.message)) }, [])

  if (error) return <p className="form-error">{error}</p>
  if (!p) return <div className="panel muted">Calculando las componentes principales…</div>
  const vars = Object.keys(p.columnas)
  return (
    <>
      <section className="panel">
        <h2 className="form-section-title">Práctica 09 · Reducción de dimensionalidad con PCA</h2>
        <p className="ia-intro">
          Las 4 variables de los {p.servicios} servicios se estandarizaron (PCA es sensible a la escala) y se transformaron en 4 componentes
          principales. Con <b>{p.componentes_necesarias}</b> componentes se conserva al menos el {pct(p.objetivo, 0)} de la varianza
          ({pct(p.varianza[p.componentes_necesarias - 1].acumulada, 2)}). Los perfiles de K-Means solo colorean el mapa: PCA no los usa.
        </p>
        <div className="ia-grid">
          <div className="table-wrap">
            <table>
              <thead><tr><th>Componente</th><th>Varianza explicada</th><th>Acumulada</th><th>MSE con esas PCs</th></tr></thead>
              <tbody>
                {p.varianza.map((v, i) => (
                  <tr key={v.componente}>
                    <td>{v.componente}</td><td>{pct(v.explicada, 2)}</td><td>{pct(v.acumulada, 2)}</td><td>{p.reconstruccion[i].mse}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Varianza p={p} />
        </div>
      </section>

      <div className="ia-grid">
        <section className="panel">
          <h2 className="form-section-title">Cargas de las componentes</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th />{vars.map((k) => <th key={k}>{p.columnas[k]}</th>)}</tr></thead>
              <tbody>
                {p.cargas.map((c) => (
                  <tr key={c.componente}>
                    <td>{c.componente}</td>
                    {vars.map((k) => (
                      <td key={k} style={{ background: c[k] >= 0 ? `rgba(200,32,47,${Math.abs(c[k]) * 0.5})` : `rgba(37,99,235,${Math.abs(c[k]) * 0.5})` }}>{c[k]}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted ia-nota">PC1 sube con la distancia, el tráfico y el tiempo, y baja con las ambulancias libres: mide qué tan difícil es el servicio.</p>
        </section>
        <section className="panel">
          <h2 className="form-section-title">Servicios en PCA 2D</h2>
          <MapaPCA p={p} />
        </section>
      </div>
    </>
  )
}

function Varianza({ p }) {
  const W = 360, H = 200, m = { l: 40, r: 12, t: 12, b: 28 }
  const bw = (W - m.l - m.r) / p.varianza.length
  const sy = (v) => H - m.b - v * (H - m.t - m.b)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="ia-svg" role="img" aria-label="Varianza explicada y acumulada">
      {[0, 0.5, 1].map((t) => <g key={t}><line x1={m.l} x2={W - m.r} y1={sy(t)} y2={sy(t)} className="rejilla" /><text x={m.l - 6} y={sy(t) + 4} textAnchor="end">{t * 100}%</text></g>)}
      {p.varianza.map((v, i) => (
        <g key={v.componente}>
          <rect x={m.l + i * bw + 8} y={sy(v.explicada)} width={bw - 16} height={sy(0) - sy(v.explicada)} rx="3" fill="#2563eb" fillOpacity=".7" />
          <text x={m.l + i * bw + bw / 2} y={H - 10} textAnchor="middle">{v.componente}</text>
        </g>
      ))}
      <path d={p.varianza.map((v, i) => `${i ? 'L' : 'M'}${m.l + i * bw + bw / 2},${sy(v.acumulada)}`).join(' ')} className="linea" />
      {p.varianza.map((v, i) => <circle key={i} cx={m.l + i * bw + bw / 2} cy={sy(v.acumulada)} r="3.5" className="punto" />)}
      <line x1={m.l} x2={W - m.r} y1={sy(p.objetivo)} y2={sy(p.objetivo)} stroke="currentColor" strokeDasharray="5 4" />
      <text x={W - m.r} y={sy(p.objetivo) - 5} textAnchor="end" className="valor">Objetivo {p.objetivo * 100}%</text>
    </svg>
  )
}

// Mapa de servicios (PC1 vs PC2). Si se pasa «marca» ({pc1, pc2, texto}) se dibuja encima.
export function MapaPCA({ p, marca }) {
  const W = 560, H = 300, m = { l: 34, r: 12, t: 12, b: 30 }
  const xs = p.puntos.map((q) => q.pc1).concat(marca ? [marca.pc1] : [])
  const ys = p.puntos.map((q) => q.pc2).concat(marca ? [marca.pc2] : [])
  const x0 = Math.floor(Math.min(...xs)), x1 = Math.ceil(Math.max(...xs))
  const y0 = Math.floor(Math.min(...ys)), y1 = Math.ceil(Math.max(...ys))
  const sx = (x) => m.l + ((x - x0) / (x1 - x0)) * (W - m.l - m.r)
  const sy = (y) => H - m.b - ((y - y0) / (y1 - y0)) * (H - m.t - m.b)
  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} className="ia-svg ancho" role="img" aria-label="Mapa de servicios con PCA">
        <line x1={sx(0)} x2={sx(0)} y1={m.t} y2={H - m.b} className="rejilla" />
        <line x1={m.l} x2={W - m.r} y1={sy(0)} y2={sy(0)} className="rejilla" />
        {p.puntos.map((q, i) => <circle key={i} cx={sx(q.pc1)} cy={sy(q.pc2)} r="3" fill={COLOR_PERFIL[q.perfil]} fillOpacity=".5" />)}
        {p.centros.map((c) => (
          <g key={c.perfil} transform={`translate(${sx(c.pc1)},${sy(c.pc2)})`}>
            <path d="M-7,-7L7,7M7,-7L-7,7" stroke="#fff" strokeWidth="6" strokeLinecap="round" />
            <path d="M-7,-7L7,7M7,-7L-7,7" stroke={COLOR_PERFIL[c.perfil]} strokeWidth="3" strokeLinecap="round" />
          </g>
        ))}
        {marca && (
          <g transform={`translate(${sx(marca.pc1)},${sy(marca.pc2)})`}>
            <circle r="9" fill="#fff" stroke="#111" strokeWidth="3" />
            <circle r="3.5" fill="#111" />
            <text x="13" y="4" className="valor">{marca.texto}</text>
          </g>
        )}
        <text x={(W + m.l) / 2} y={H - 6} textAnchor="middle" className="eje">PC1 ({pct(p.varianza[0].explicada, 0)}) · más a la derecha = servicio más difícil</text>
        <text x={12} y={H / 2} textAnchor="middle" className="eje" transform={`rotate(-90 12 ${H / 2})`}>PC2 ({pct(p.varianza[1].explicada, 0)})</text>
      </svg>
      <p className="ia-leyenda">
        {Object.entries(COLOR_PERFIL).map(([k, c]) => <span key={k}><i style={{ background: c }} /> {k}</span>)}
        <span>✕ centro de cada tipo</span>
        {marca && <span>◉ {marca.texto}</span>}
      </p>
    </>
  )
}
