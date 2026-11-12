import { pct } from '../../lib/clima.js'

// Piezas compartidas por las pantallas de las prácticas de clasificación.

export function Metricas({ m, nota }) {
  const items = [['Exactitud', m.exactitud], ['Precisión', m.precision], ['Recall', m.recall], ['F1-score', m.f1]]
  return (
    <div className="ia-metricas">
      {items.map(([t, v]) => <div key={t}><b>{pct(v, 1)}</b><span>{t}</span></div>)}
      {nota && <p className="muted">{nota}</p>}
    </div>
  )
}

export function Matriz({ m, etiquetas, positiva, explicacion }) {
  const [neg, pos] = etiquetas
  const celdas = [
    { v: m.vn, t: `Dijo ${neg.toLowerCase()} y fue ${neg.toLowerCase()}`, ok: true },
    { v: m.fp, t: `Dijo ${pos.toLowerCase()}, pero fue ${neg.toLowerCase()}`, ok: false, grave: positiva === 'fp' },
    { v: m.fn, t: `Dijo ${neg.toLowerCase()}, pero fue ${pos.toLowerCase()}`, ok: false, grave: positiva === 'fn' },
    { v: m.vp, t: `Dijo ${pos.toLowerCase()} y fue ${pos.toLowerCase()}`, ok: true },
  ]
  return (
    <div className="ia-matriz-wrap">
      <div className="ia-matriz">
        <span />
        <span className="eje">Predijo: {neg}</span>
        <span className="eje">Predijo: {pos}</span>
        <span className="eje lado">Real: {neg}</span>
        {celdas.slice(0, 2).map((c, i) => <Celda key={i} c={c} />)}
        <span className="eje lado">Real: {pos}</span>
        {celdas.slice(2).map((c, i) => <Celda key={i} c={c} />)}
      </div>
      {explicacion && <p className="ia-matriz-nota">{explicacion}</p>}
    </div>
  )
}

function Celda({ c }) {
  return (
    <div className={`ia-celda${c.ok ? ' ok' : ''}${c.grave ? ' grave' : ''}`}>
      <b>{c.v}</b><small>{c.t}</small>
    </div>
  )
}

export function ValidacionCruzada({ cv, metrica }) {
  return (
    <div className="ia-cv">
      <div className="ia-cv-barras">
        {cv.particiones.map((p, i) => (
          <div key={i} title={pct(p, 1)}><i style={{ height: `${p * 100}%` }} /><small>{i + 1}</small></div>
        ))}
      </div>
      <p><b>{pct(cv.promedio, 1)}</b> de {metrica} en promedio · ± {pct(cv.desviacion, 1)} entre las 5 particiones</p>
    </div>
  )
}

export function Conjuntos({ c }) {
  const total = c.entrenamiento + c.validacion + c.prueba
  return (
    <div className="ia-conjuntos" aria-label="División de los datos">
      <div style={{ flex: c.entrenamiento }} className="ent"><b>{c.entrenamiento}</b> entrenamiento · {Math.round(c.entrenamiento / total * 100)} %</div>
      <div style={{ flex: c.validacion }} className="val"><b>{c.validacion}</b> validación</div>
      <div style={{ flex: c.prueba }} className="pru"><b>{c.prueba}</b> prueba</div>
    </div>
  )
}
