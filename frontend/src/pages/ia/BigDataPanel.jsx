import { useEffect, useState } from 'react'
import { pct, verBigData } from '../../lib/clima.js'

// Prácticas 20 a 27 (backend/ia_bigdata): 50,000 servicios procesados con Spark, CNN 1D que
// clasifica la tendencia (p24) comparada con Random Forest (p25) y CNN de regresión que predice
// el tiempo del mes 3 y avisa si pasará de 15 minutos (p27). Los scripts se corren aparte y
// exportar_resumen_sistema.py deja sus resultados en la API (GET /api/ia/bigdata).

const COLOR_TENDENCIA = { Mejora: '#1a7a41', Estable: '#c98a12', Deterioro: '#c8202f' }
const NOMBRE_METRICA = { accuracy: 'Exactitud', precision_macro: 'Precisión', recall_macro: 'Recall', f1_macro: 'F1-score' }
const num = (n) => Number(n).toLocaleString('es-MX')

export default function BigDataPanel({ Tecnico = ({ children }) => <>{children}</> }) {
  const [d, setD] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { verBigData().then(setD).catch((e) => setError(e.message)) }, [])

  if (error) return <section className="panel"><p className="form-error">{error}</p></section>
  if (!d) return <div className="panel muted">Cargando los resultados de Big Data…</div>
  const pendientes = d.practicas.filter((p) => !p.listo)

  return (
    <>
      <Avance d={d} pendientes={pendientes} />
      {d.prediccion?.por_hospital ? <Prediccion p={d.prediccion} meta={d.meta_minutos} /> : <Pendiente que="p27" texto="Aquí aparecerán las ambulancias que probablemente pasarán de 15 minutos el próximo mes, por hospital y por tipo de emergencia." />}
      {d.datos ? <Datos x={d.datos} /> : <Pendiente que="p20" texto="Aquí aparecerá el resumen de los 50,000 servicios por hospital y tipo de emergencia." />}
      <Tecnico>
        <DetalleTecnico d={d} />
      </Tecnico>
    </>
  )
}

function Avance({ d, pendientes }) {
  return (
    <section className="panel">
      <h3 className="iah-h3">Avance de las prácticas 20 a 27</h3>
      <ol className="bd-pasos">
        {d.practicas.map((p) => (
          <li key={p.clave} className={p.listo ? 'listo' : ''}>
            <span className="bd-paso-marca" aria-hidden="true">{p.listo ? '✓' : '…'}</span>
            <b>{p.clave.toUpperCase()}</b>
            <span>{p.titulo}</span>
            <small>{p.listo ? 'Con resultados' : 'Pendiente'}</small>
          </li>
        ))}
      </ol>
      {pendientes.length > 0 && (
        <p className="iah-nota">
          Para completar el panel: en <code>backend/ia_bigdata</code> corre {pendientes.map((p) => p.clave).join(', ')} (ver su README) y después
          {' '}<code>python exportar_resumen_sistema.py</code>. Sube a GitHub el archivo <code>backend/app/datos_ia/bigdata_resumen.json</code> que se actualiza.
        </p>
      )}
      <p className="iah-nota">Resultados exportados el {new Date(d.generado).toLocaleString('es-MX', { dateStyle: 'long', timeStyle: 'short' })} · {d.advertencia}</p>
    </section>
  )
}

function Pendiente({ que, texto }) {
  return (
    <section className="panel bd-pendiente">
      <h3 className="iah-h3">Falta correr {que.toUpperCase()}</h3>
      <p className="iah-desc">{texto}</p>
    </section>
  )
}

// ─────────────── p27: ¿qué ambulancias pasarán de 15 minutos el mes 3? ───────────────

function Prediccion({ p, meta }) {
  const mejora = p.modelo_base?.MAE ? 1 - p.metricas.MAE / p.modelo_base.MAE : null
  return (
    <>
      <div className="iah-grid">
        <section className="panel">
          <h3 className="iah-h3">Ambulancias que probablemente pasarán de {meta} min el próximo mes</h3>
          <p className="iah-desc">
            Con los tiempos y la disponibilidad de los meses 1 y 2, la red neuronal predijo el tiempo del mes 3 de {num(p.servicios_prueba)} servicios
            que nunca vio al entrenar. En <b>{num(p.alertas_total)}</b> ({pct(p.alertas_total / p.servicios_prueba)}) marcó <b>ALERTA</b>: conviene
            revisar esas ambulancias o pedir apoyo antes de que lleguen tarde.
          </p>
          <Barras filas={p.por_hospital} />
          <h3 className="iah-h3 bd-sub">Por tipo de emergencia</h3>
          <Barras filas={p.por_tipo} />
        </section>
        <div className="iah-lado">
          <section className="panel iah-confianza">
            <h3 className="iah-h3">¿Qué tan confiable es?</h3>
            <div className="iah-conf"><b>± {p.metricas.MAE.toFixed(1)} min</b><p>de error promedio al predecir el tiempo del mes 3.</p></div>
            <p className="iah-nota">
              {mejora != null && <>Un cálculo simple (siempre el promedio) se equivoca ± {p.modelo_base.MAE.toFixed(1)} min: la red neuronal reduce el error un {pct(mejora)}. </>}
              De las ambulancias que de verdad pasaron de {meta} min, la alerta detectó el {pct(p.alerta.recall)}; y cuando avisó, acertó el {pct(p.alerta.precision)}.
            </p>
          </section>
          <section className="panel">
            <h3 className="iah-h3">Real contra predicho</h3>
            <Dispersion puntos={p.dispersion} meta={meta} />
            <p className="iah-nota">Cada punto es un servicio de prueba. Mientras más cerca de la diagonal, mejor la predicción. Las líneas rojas son la meta de {meta} min.</p>
          </section>
        </div>
      </div>
      <section className="panel">
        <h3 className="iah-h3">Las alertas más urgentes</h3>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Ambulancia</th><th>Hospital</th><th>Tipo de emergencia</th><th>Predicho mes 3</th><th>Real mes 3</th></tr></thead>
            <tbody>
              {p.mas_urgentes.map((a) => (
                <tr key={`${a.ambulancia}-${a.tipo}`}>
                  <td>{a.ambulancia}</td><td>{a.hospital}</td><td>{a.tipo}</td>
                  <td><b className="bd-alerta">{a.predicho} min</b></td><td>{a.real} min</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}

function Barras({ filas }) {
  return (
    <ul className="iah-factores bd-barras">
      {filas.map((f) => (
        <li key={f.nombre}>
          <span title={f.nombre}>{f.nombre}</span>
          <div className="iah-barra"><i style={{ width: `${f.porcentaje * 100}%` }} /></div>
          <small>{pct(f.porcentaje)} · {num(f.alertas)} de {num(f.servicios)}</small>
        </li>
      ))}
    </ul>
  )
}

function Dispersion({ puntos, meta }) {
  const W = 360, H = 300, m = { l: 34, r: 10, t: 10, b: 30 }
  const max = Math.ceil(Math.max(...puntos.flat(), meta + 5) / 5) * 5
  const sx = (v) => m.l + (v / max) * (W - m.l - m.r)
  const sy = (v) => H - m.b - (v / max) * (H - m.t - m.b)
  const marcas = Array.from({ length: max / 10 + 1 }, (_, i) => i * 10)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="ia-svg" role="img" aria-label="Tiempo real contra tiempo predicho del mes 3">
      {marcas.map((v) => (
        <g key={v}>
          <line x1={m.l} x2={W - m.r} y1={sy(v)} y2={sy(v)} className="rejilla" />
          <text x={m.l - 5} y={sy(v) + 4} textAnchor="end">{v}</text>
          <text x={sx(v)} y={H - m.b + 14} textAnchor="middle">{v}</text>
        </g>
      ))}
      <line x1={sx(0)} y1={sy(0)} x2={sx(max)} y2={sy(max)} stroke="currentColor" strokeOpacity=".35" strokeDasharray="5 4" />
      <line x1={sx(meta)} x2={sx(meta)} y1={sy(0)} y2={sy(max)} stroke="#c8202f" strokeOpacity=".5" />
      <line x1={sx(0)} x2={sx(max)} y1={sy(meta)} y2={sy(meta)} stroke="#c8202f" strokeOpacity=".5" />
      {puntos.map(([real, pred], i) => (
        <circle key={i} cx={sx(real)} cy={sy(pred)} r="2.3" fill={pred > meta ? '#c8202f' : '#1d5fd6'} fillOpacity=".45" />
      ))}
      <text x={(W + m.l) / 2} y={H - 2} textAnchor="middle" className="eje">Real (min)</text>
      <text x={10} y={(H - m.b) / 2} textAnchor="middle" className="eje" transform={`rotate(-90 10 ${(H - m.b) / 2})`}>Predicho (min)</text>
    </svg>
  )
}

// ─────────────── p20: los 50,000 servicios ───────────────

function Datos({ x }) {
  const total = Object.values(x.tendencias).reduce((a, b) => a + b, 0)
  return (
    <section className="panel">
      <h3 className="iah-h3">Los {num(x.registros)} servicios analizados</h3>
      <p className="iah-desc">
        {num(x.ambulancias)} ambulancias de 5 hospitales de Toluca, cada una con 5 tipos de emergencia y sus tiempos de 3 meses. Solo el
        {' '}<b>{pct(x.cumple_meta)}</b> cumple la meta de 15 minutos en promedio.
      </p>
      <div className="ia-metricas bd-cinco">
        <div><b>{num(x.registros)}</b><span>Servicios</span></div>
        <div><b>{num(x.ambulancias)}</b><span>Ambulancias</span></div>
        {x.tiempo_por_mes.map((t, i) => <div key={i}><b>{t} min</b><span>Promedio mes {i + 1}</span></div>)}
      </div>
      <h3 className="iah-h3 bd-sub">¿Cómo van sus tiempos?</h3>
      <div className="bd-tendencia" aria-label="Tendencia de los tiempos de respuesta">
        {Object.entries(x.tendencias).map(([t, n]) => (
          <div key={t} style={{ flex: n, background: COLOR_TENDENCIA[t] || '#777' }} title={`${t}: ${num(n)}`}>
            <b>{t}</b> {pct(n / total)}
          </div>
        ))}
      </div>
      <div className="bd-tablas">
        <Tabla titulo="Por hospital" filas={x.por_hospital} />
        <Tabla titulo="Por tipo de emergencia" filas={x.por_tipo} />
      </div>
    </section>
  )
}

function Tabla({ titulo, filas }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>{titulo}</th><th>Servicios</th><th>Tiempo promedio</th><th>Disponibilidad</th><th>Cumple 15 min</th></tr></thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.nombre}>
              <td>{f.nombre}</td><td>{num(f.registros)}</td><td>{f.tiempo_promedio} min</td><td>{f.disponibilidad} %</td><td>{pct(f.cumple_meta, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─────────────── Detalles técnicos (p21 a p26) ───────────────

function DetalleTecnico({ d }) {
  const { spark, mongo, tensores, cnn, comparacion, preparacion_prediccion: prep, prediccion } = d
  return (
    <>
      <section className="panel">
        <h2 className="form-section-title">P21 a P23 · Spark, MongoDB y tensores</h2>
        <ul className="bd-lista">
          <li><b>P21 Spark:</b> {spark ? `${spark.archivos_parquet} archivos Parquet (${spark.megabytes} MB) particionados por tipo: ${spark.particiones.join(', ')}.` : 'pendiente.'}</li>
          <li><b>P22 MongoDB Atlas:</b> {mongo ? `${num(mongo.documentos)} documentos en la colección ${mongo.coleccion}.` : 'sin verificar (se comprueba al exportar si hay conexión a MongoDB).'}</li>
          <li><b>P23 Tensores:</b> {tensores ? `entrada [N, ${tensores.forma_entrada.join(', ')}] con los canales ${tensores.canales.join(' y ')}; división ${tensores.separacion?.metodo}.` : 'pendiente.'}</li>
          <li><b>P26 Predicción:</b> {prep ? `entradas ${prep.variables_entrada.join(', ')} → objetivo ${prep.variable_objetivo}; división ${prep.separacion?.metodo} por ${prep.separacion?.grupo} (una ambulancia nunca está en entrenamiento y prueba a la vez).` : 'pendiente.'}</li>
        </ul>
      </section>

      <div className="ia-grid">
        <section className="panel">
          <h2 className="form-section-title">P24 · CNN 1D: tendencia del servicio</h2>
          {cnn ? (
            <>
              <div className="ia-metricas">
                {Object.entries(cnn.metricas).map(([k, v]) => <div key={k}><b>{pct(v, 1)}</b><span>{NOMBRE_METRICA[k] || k}</span></div>)}
              </div>
              {cnn.matriz && <MatrizConfusion m={cnn.matriz} />}
              <p className="muted ia-nota">Métricas casi perfectas porque la tendencia se calcula con los mismos tiempos que recibe la red. Sirve para practicar CNN 1D, no para anticipar.</p>
            </>
          ) : <p className="muted">Pendiente: corre p23 y p24.</p>}
        </section>
        <section className="panel">
          <h2 className="form-section-title">P25 · CNN 1D contra Random Forest</h2>
          {comparacion ? (
            <>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Modelo</th>{Object.values(NOMBRE_METRICA).map((t) => <th key={t}>{t}</th>)}</tr></thead>
                  <tbody>
                    {comparacion.modelos.map((m) => (
                      <tr key={m.modelo}><td>{m.modelo}</td>{Object.keys(NOMBRE_METRICA).map((k) => <td key={k}>{m[k] != null ? pct(m[k], 1) : '—'}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {comparacion.importancia_rf && (
                <>
                  <h3 className="iah-h3 bd-sub">¿En qué se fija el Random Forest?</h3>
                  <ul className="iah-factores">
                    {comparacion.importancia_rf.map((i) => (
                      <li key={i.variable}><span>{i.variable}</span><div className="iah-barra"><i style={{ width: `${(i.importancia / comparacion.importancia_rf[0].importancia) * 100}%` }} /></div></li>
                    ))}
                  </ul>
                </>
              )}
            </>
          ) : <p className="muted">Pendiente: corre p25 (necesita p23 y p24).</p>}
        </section>
      </div>

      {prediccion && (
        <section className="panel">
          <h2 className="form-section-title">P27 · CNN de regresión (mes 3)</h2>
          <div className="ia-metricas">
            <div><b>{prediccion.metricas.MAE.toFixed(2)}</b><span>MAE (min)</span></div>
            <div><b>{prediccion.metricas.RMSE.toFixed(2)}</b><span>RMSE (min)</span></div>
            <div><b>{prediccion.metricas.R2.toFixed(3)}</b><span>R²</span></div>
            <div><b>{prediccion.modelo_base.MAE.toFixed(2)}</b><span>MAE modelo base</span></div>
          </div>
          <p className="muted ia-nota">
            Alerta de {prediccion.alerta.umbral_minutos} min: exactitud {pct(prediccion.alerta.exactitud, 1)}, precisión {pct(prediccion.alerta.precision, 1)},
            recall {pct(prediccion.alerta.recall, 1)}. Mejor época: {prediccion.mejor_epoca}. El tiempo del mes 3 no se usó como entrada.
          </p>
        </section>
      )}
    </>
  )
}

function MatrizConfusion({ m }) {
  return (
    <div className="table-wrap">
      <table className="bd-matriz">
        <thead><tr><th>Real \ Predicho</th>{m.clases.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {m.valores.map((fila, i) => (
            <tr key={m.clases[i]}>
              <th>{m.clases[i]}</th>
              {fila.map((v, j) => <td key={j} className={i === j ? 'ok' : ''}>{num(v)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
