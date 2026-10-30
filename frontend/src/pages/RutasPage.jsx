import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Pause, Play, RotateCcw, Siren, TrafficCone } from 'lucide-react'
import {
  ALGORITMOS, HORA_PICO, NIVEL_LABEL, NIVELES, obtenerMapa, resolverRuta, siguienteNivel,
} from '../lib/busqueda.js'

// Búsqueda ciega sobre el espacio de estados: la ambulancia va de una intersección a otra
// por calles que no estén bloqueadas. El backend resuelve con anchura, profundidad y costo
// uniforme; aquí se dibuja el mapa, se edita el tráfico y se recorre la búsqueda paso a paso.

const fmtMin = (m) => (m == null ? '—' : `${m.toFixed(1)} min`)

export default function RutasPage() {
  const [mapa, setMapa] = useState(null)
  const [error, setError] = useState('')
  const [inicial, setInicial] = useState('BASE')
  const [meta, setMeta] = useState('HS')
  const [cambios, setCambios] = useState({})          // calle → nivel distinto al de por defecto
  const [algoritmo, setAlgoritmo] = useState('costo_uniforme')
  const [solucion, setSolucion] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [paso, setPaso] = useState(null)               // null = ver el resultado final
  const [reproduciendo, setReproduciendo] = useState(false)
  const pedido = useRef(0)

  useEffect(() => {
    obtenerMapa().then(setMapa).catch((e) => setError(e.message))
  }, [])

  const nodo = useMemo(() => Object.fromEntries((mapa?.nodos ?? []).map((n) => [n.id, n])), [mapa])
  const nivelDe = useCallback(
    (c) => cambios[c.id] ?? c.trafico,
    [cambios],
  )

  // Resolver cada vez que cambia el problema.
  useEffect(() => {
    if (!mapa) return
    if (inicial === meta) {
      setSolucion(null)
      setError('El punto de salida y el destino deben ser distintos.')
      return
    }
    const id = ++pedido.current
    setCargando(true)
    setError('')
    resolverRuta({ inicial, meta, trafico: cambios })
      .then((s) => { if (id === pedido.current) { setSolucion(s); setPaso(null) } })
      .catch((e) => { if (id === pedido.current) setError(e.message) })
      .finally(() => { if (id === pedido.current) setCargando(false) })
  }, [mapa, inicial, meta, cambios])

  const resultado = solucion?.resultados.find((r) => r.algoritmo === algoritmo)
  const traza = resultado?.traza ?? []
  const pasoActual = paso ?? traza.length            // 1..n
  const final = pasoActual >= traza.length
  const estadoPaso = traza[pasoActual - 1]

  // Reproducción automática de la traza.
  useEffect(() => {
    if (!reproduciendo) return
    if (pasoActual >= traza.length) { setReproduciendo(false); return }
    const t = setTimeout(() => setPaso(pasoActual + 1), 700)
    return () => clearTimeout(t)
  }, [reproduciendo, pasoActual, traza.length])

  const reproducir = () => {
    if (reproduciendo) { setReproduciendo(false); return }
    if (final) setPaso(1)
    setReproduciendo(true)
  }

  const cambiarAlgoritmo = (key) => { setAlgoritmo(key); setPaso(null); setReproduciendo(false) }

  const ciclarCalle = (c) => {
    const nuevo = siguienteNivel(nivelDe(c))
    setCambios((prev) => {
      const next = { ...prev }
      if (nuevo === c.trafico) delete next[c.id]
      else next[c.id] = nuevo
      return next
    })
  }

  const minutosCalle = (c) => {
    const f = mapa.niveles[nivelDe(c)]
    return f == null ? null : (c.distancia_km / mapa.velocidad_kmh) * 60 * f
  }

  if (!mapa) {
    return (
      <section className="rutas">
        <Encabezado />
        {error ? <p className="form-error">{error}</p> : <p className="muted">Cargando mapa…</p>}
      </section>
    )
  }

  const info = ALGORITMOS.find((a) => a.key === algoritmo)
  const nombre = (id) => nodo[id]?.nombre ?? id

  return (
    <section className="rutas">
      <Encabezado />

      <div className="panel rutas-controles">
        <div className="form-grid">
          <div className="field">
            <label htmlFor="ruta-inicial">Sale de (estado inicial)</label>
            <select id="ruta-inicial" className="input" value={inicial} onChange={(e) => setInicial(e.target.value)}>
              {mapa.nodos.map((n) => <option key={n.id} value={n.id}>{n.id} · {n.nombre}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="ruta-meta">Llega a (estado meta)</label>
            <select id="ruta-meta" className="input" value={meta} onChange={(e) => setMeta(e.target.value)}>
              {mapa.nodos.map((n) => <option key={n.id} value={n.id}>{n.id} · {n.nombre}</option>)}
            </select>
          </div>
        </div>

        <div className="rutas-fila">
          <div className="segmentado" role="tablist" aria-label="Algoritmo de búsqueda">
            {ALGORITMOS.map((a) => (
              <button
                key={a.key}
                type="button"
                role="tab"
                aria-selected={algoritmo === a.key}
                className={algoritmo === a.key ? 'on' : ''}
                onClick={() => cambiarAlgoritmo(a.key)}
              >
                {a.label}
              </button>
            ))}
          </div>
          <div className="rutas-acciones">
            <button type="button" className="btn-ghost" onClick={() => setCambios(HORA_PICO)}>
              <TrafficCone size={14} /> Hora pico
            </button>
            <button type="button" className="btn-ghost" onClick={() => setCambios({})} disabled={!Object.keys(cambios).length}>
              <RotateCcw size={14} /> Tráfico normal
            </button>
          </div>
        </div>
        <p className="field-hint">
          <strong>{info.label}:</strong> frontera como {info.frontera.charAt(0).toLowerCase() + info.frontera.slice(1)}. Garantiza {info.garantiza}.
        </p>
      </div>

      {error && <p className="form-error">{error}</p>}

      <div className="rutas-grid">
        <div className="panel rutas-mapa-panel">
          <div className="panel-title-row">
            <h2 className="panel-title">Mapa del tráfico</h2>
            <span className="muted rutas-tip">Toca una calle para cambiar su tráfico</span>
          </div>

          <div className="rutas-mapa-wrap">
            <Mapa
              mapa={mapa}
              nivelDe={nivelDe}
              minutosCalle={minutosCalle}
              onCalle={ciclarCalle}
              inicial={inicial}
              meta={meta}
              ruta={final && resultado?.encontrado ? resultado.ruta : null}
              calles={final && resultado?.encontrado ? resultado.calles : []}
              estadoPaso={final ? null : estadoPaso}
            />
          </div>

          <ul className="rutas-leyenda" aria-label="Leyenda">
            {NIVELES.map((n) => (
              <li key={n}>
                <span className={`swatch t-${n}`} />{NIVEL_LABEL[n]}
                {mapa.niveles[n] != null ? <small>×{mapa.niveles[n]}</small> : <small>sin paso</small>}
              </li>
            ))}
            <li><span className="swatch ruta" />Ruta encontrada</li>
            {!final && <>
              <li><span className="dot actual" />Se expande</li>
              <li><span className="dot frontera" />En frontera</li>
              <li><span className="dot expandido" />Ya expandido</li>
            </>}
          </ul>
        </div>

        <div className="rutas-lado">
          <div className="panel">
            <h2 className="panel-title">Resultado · {info.label}</h2>
            {cargando && !resultado && <p className="muted">Buscando…</p>}
            {resultado && (resultado.encontrado ? (
              <>
                <div className="rutas-cifras">
                  <div><b>{fmtMin(resultado.minutos)}</b><span>tiempo estimado</span></div>
                  <div><b>{resultado.distancia_km} km</b><span>distancia</span></div>
                  <div><b>{resultado.num_calles}</b><span>calles</span></div>
                </div>
                <ol className="rutas-pasos-ruta">
                  {resultado.ruta.map((id, i) => {
                    const calle = i > 0 ? mapa.calles.find((c) => c.id === resultado.calles[i - 1]) : null
                    return (
                      <li key={id + i}>
                        {calle && <span className="via">por {calle.nombre} · {NIVEL_LABEL[nivelDe(calle)].toLowerCase()}</span>}
                        <strong>{id}</strong> {nombre(id)}
                      </li>
                    )
                  })}
                </ol>
              </>
            ) : (
              <p className="form-error">
                No hay ruta: con este tráfico no se puede llegar a {nombre(meta)}. Libera alguna calle bloqueada.
              </p>
            ))}
          </div>

          <div className="panel">
            <h2 className="panel-title">Espacio de estados</h2>
            <dl className="kv rutas-kv">
              <dt>Estado</dt><dd>La intersección donde está la ambulancia</dd>
              <dt>Estado inicial</dt><dd>{inicial} · {nombre(inicial)}</dd>
              <dt>Estado meta</dt><dd>{meta} · {nombre(meta)}</dd>
              <dt>Operadores</dt><dd>avanzar(i → j) si hay calle de i a j, no está bloqueada y se respeta su sentido</dd>
              <dt>Costo</dt><dd>minutos = km ÷ {mapa.velocidad_kmh} km/h × factor de tráfico</dd>
            </dl>
          </div>
        </div>
      </div>

      {resultado && (
        <div className="panel">
          <div className="panel-title-row">
            <h2 className="panel-title">Búsqueda paso a paso</h2>
            <div className="rutas-acciones">
              <button type="button" className="btn-ghost" onClick={reproducir} disabled={!traza.length}>
                {reproduciendo ? <><Pause size={14} /> Pausar</> : <><Play size={14} /> Reproducir</>}
              </button>
            </div>
          </div>
          <div className="rutas-slider">
            <label htmlFor="ruta-paso">Paso {Math.min(pasoActual, traza.length)} de {traza.length}</label>
            <input
              id="ruta-paso"
              type="range"
              min={1}
              max={Math.max(traza.length, 1)}
              value={Math.min(pasoActual, traza.length)}
              onChange={(e) => { setReproduciendo(false); const v = Number(e.target.value); setPaso(v >= traza.length ? null : v) }}
            />
          </div>
          {estadoPaso && (
            <p className="rutas-narra">
              {estadoPaso.meta
                ? <>Se saca <strong>{estadoPaso.estado}</strong> de la frontera y es la meta: termina la búsqueda con {fmtMin(estadoPaso.g)} acumulados.</>
                : <>Se expande <strong>{estadoPaso.estado}</strong> ({fmtMin(estadoPaso.g)} acumulados).{' '}
                  {estadoPaso.agregados.length
                    ? <>Sus sucesores nuevos entran a la frontera: {estadoPaso.agregados.join(', ')}.</>
                    : <>No genera sucesores nuevos.</>}</>}
            </p>
          )}
          <div className="table-wrap rutas-tabla">
            <table>
              <thead>
                <tr><th>Paso</th><th>Expande</th><th>g (min)</th><th>Agrega a la frontera</th><th>Frontera después del paso</th></tr>
              </thead>
              <tbody>
                {traza.map((t) => (
                  <tr
                    key={t.paso}
                    className={t.paso === Math.min(pasoActual, traza.length) ? 'sel' : ''}
                    onClick={() => { setReproduciendo(false); setPaso(t.paso >= traza.length ? null : t.paso) }}
                  >
                    <td>{t.paso}</td>
                    <td><strong>{t.estado}</strong>{t.meta && <span className="badge b-activo">meta</span>}</td>
                    <td>{t.g.toFixed(1)}</td>
                    <td>{t.agregados.join(', ') || '—'}</td>
                    <td className="mono">[{t.frontera.join(', ')}]</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {solucion && (
        <div className="panel">
          <h2 className="panel-title">Comparación de algoritmos</h2>
          <div className="table-wrap rutas-tabla">
            <table>
              <thead>
                <tr>
                  <th>Algoritmo</th><th>Ruta</th><th>Calles</th><th>km</th><th>Tiempo</th>
                  <th>Expandidos</th><th>Generados</th><th>Frontera máx.</th>
                </tr>
              </thead>
              <tbody>
                {solucion.resultados.map((r) => (
                  <tr key={r.algoritmo} className={r.algoritmo === algoritmo ? 'sel' : ''} onClick={() => cambiarAlgoritmo(r.algoritmo)}>
                    <td><strong>{r.nombre}</strong>{r.algoritmo === solucion.mas_rapido && <span className="badge b-activo">más rápida</span>}</td>
                    <td className="mono">{r.encontrado ? r.ruta.join(' → ') : 'sin ruta'}</td>
                    <td>{r.num_calles ?? '—'}</td>
                    <td>{r.distancia_km ?? '—'}</td>
                    <td>{fmtMin(r.minutos)}</td>
                    <td>{r.expandidos}</td>
                    <td>{r.generados}</td>
                    <td>{r.frontera_max}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="field-hint">
            Anchura y profundidad no miran el tráfico: cuentan calles o siguen el primer camino. Costo uniforme
            suma los minutos de cada calle, por eso evita las calles densas aunque recorra más.
          </p>
        </div>
      )}
    </section>
  )
}

function Encabezado() {
  return (
    <header className="view-head">
      <div>
        <h1>Rutas y tráfico</h1>
        <p>Búsqueda ciega sobre el espacio de estados para llevar la ambulancia evitando el tráfico</p>
      </div>
      <Siren size={28} className="rutas-head-icon" aria-hidden="true" />
    </header>
  )
}

function Mapa({ mapa, nivelDe, minutosCalle, onCalle, inicial, meta, ruta, calles, estadoPaso }) {
  const nodo = Object.fromEntries(mapa.nodos.map((n) => [n.id, n]))
  const enRuta = new Set(calles)
  const expandidos = new Set(estadoPaso?.expandidos ?? [])
  const frontera = new Set(estadoPaso?.frontera ?? [])

  return (
    <svg viewBox="0 0 1020 600" className="rutas-mapa" role="img" aria-label="Mapa de calles con su nivel de tráfico">
      <defs>
        <marker id="flecha" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto">
          <path d="M0 0 10 5 0 10z" className="flecha" />
        </marker>
      </defs>

      {/* Calles */}
      {mapa.calles.map((c) => {
        const a = nodo[c.a], b = nodo[c.b]
        const nivel = nivelDe(c)
        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2
        const min = minutosCalle(c)
        const vertical = a.x === b.x
        const titulo = `${c.nombre} (${c.a}–${c.b}) · ${c.distancia_km} km · ${NIVEL_LABEL[nivel]}` +
          (min != null ? ` · ${min.toFixed(1)} min` : '') + (c.sentido === 'ida' ? ' · un solo sentido' : '') +
          (c.nota && nivel === c.trafico ? ` · ${c.nota}` : '')
        const activar = () => onCalle(c)
        return (
          <g
            key={c.id}
            className={`calle t-${nivel}`}
            role="button"
            tabIndex={0}
            aria-label={`${titulo}. Cambiar tráfico`}
            onClick={activar}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activar() } }}
          >
            <title>{titulo}</title>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="hit" />
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="via" />
            {enRuta.has(c.id) && <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="ruta" />}
            {c.sentido === 'ida' && (
              <line
                x1={a.x + (b.x - a.x) * 0.3} y1={a.y + (b.y - a.y) * 0.3}
                x2={a.x + (b.x - a.x) * 0.36} y2={a.y + (b.y - a.y) * 0.36}
                className="sentido" markerEnd="url(#flecha)"
              />
            )}
            {nivel === 'bloqueado' ? (
              <g className="bloqueo" transform={`translate(${mx} ${my})`}>
                <circle r="13" />
                <path d="M-6 -6 6 6M6 -6-6 6" />
              </g>
            ) : (
              <text x={mx + (vertical ? 14 : 0)} y={my + (vertical ? 4 : -12)} className="min" textAnchor={vertical ? 'start' : 'middle'}>
                {min.toFixed(1)}′
              </text>
            )}
          </g>
        )
      })}

      {/* Intersecciones */}
      {mapa.nodos.map((n) => {
        const cls = [
          'nodo', `n-${n.tipo}`,
          n.id === inicial && 'inicial', n.id === meta && 'meta',
          ruta?.includes(n.id) && 'en-ruta',
          expandidos.has(n.id) && 'expandido',
          frontera.has(n.id) && 'frontera',
          estadoPaso?.estado === n.id && 'actual',
        ].filter(Boolean).join(' ')
        const etiqueta = n.tipo === 'cruce' ? null : n.nombre
        return (
          <g key={n.id} className={cls} transform={`translate(${n.x} ${n.y})`}>
            <title>{`${n.id} · ${n.nombre}`}</title>
            <circle r="19" className="halo" />
            <circle r="15" className="punto" />
            {n.tipo === 'hospital'
              ? <path d="M-2.5 -8h5v5.5h5.5v5H2.5v5.5h-5V2.5H-8v-5h5.5z" className="cruz" />
              : <text y="4" textAnchor="middle" className="id">{n.id === 'BASE' ? 'B' : n.id}</text>}
            {etiqueta && (
              <text
                y={n.y < 300 ? -28 : 40}
                x={n.x < 200 ? -18 : n.x > 820 ? 18 : 0}
                textAnchor={n.x < 200 ? 'start' : n.x > 820 ? 'end' : 'middle'}
                className="etiqueta"
              >
                {etiqueta}
              </text>
            )}
            {n.id === inicial && <text y={n.y < 300 ? 40 : -28} textAnchor="middle" className="rol">SALIDA</text>}
            {n.id === meta && <text y={n.y < 300 ? 40 : -28} textAnchor="middle" className="rol">DESTINO</text>}
          </g>
        )
      })}
    </svg>
  )
}
