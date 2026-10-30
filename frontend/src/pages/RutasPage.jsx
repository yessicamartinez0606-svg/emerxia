import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowDownUp, ChevronDown, Clock, ExternalLink, MapPin, Pause, Play, RotateCcw, Siren,
} from 'lucide-react'
import {
  ALGORITMOS, HORA_PICO, NIVEL_LABEL, NIVELES, indicaciones, obtenerMapa, resolverRuta, siguienteNivel,
} from '../lib/busqueda.js'

// Ruta de la ambulancia en Toluca, alrededor del Hospital General Regional No. 220 del IMSS.
// Arriba está lo que necesita quien despacha la ambulancia (de dónde sale, a dónde va, por
// dónde ir y cuánto tarda). Abajo, en "¿Cómo se calculó?", está la búsqueda ciega sobre el
// espacio de estados: anchura, profundidad y costo uniforme, paso a paso.

const redondear = (m) => (m == null ? '—' : m < 1 ? '< 1 min' : `${Math.round(m)} min`)
const fmtMin = (m) => (m == null ? '—' : `${m.toFixed(1)} min`)
const fmtKm = (km) => (km == null ? '—' : `${km.toFixed(1)} km`)

export default function RutasPage() {
  const [mapa, setMapa] = useState(null)
  const [error, setError] = useState('')
  const [inicial, setInicial] = useState('BASE')
  const [meta, setMeta] = useState('IMSS')
  const [cambios, setCambios] = useState({})          // calle → nivel distinto al de por defecto
  const [preset, setPreset] = useState('normal')      // normal | pico | personalizado
  const [algoritmo, setAlgoritmo] = useState('costo_uniforme')
  const [solucion, setSolucion] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [detalle, setDetalle] = useState(false)       // sección "¿Cómo se calculó?" abierta
  const [paso, setPaso] = useState(null)               // null = resultado final
  const [reproduciendo, setReproduciendo] = useState(false)
  const pedido = useRef(0)

  useEffect(() => {
    obtenerMapa().then(setMapa).catch((e) => setError(e.message))
  }, [])

  const nodo = useMemo(() => Object.fromEntries((mapa?.nodos ?? []).map((n) => [n.id, n])), [mapa])
  const nivelDe = useCallback((c) => cambios[c.id] ?? c.trafico, [cambios])
  const minutosCalle = useCallback((c) => {
    const f = mapa?.niveles[nivelDe(c)]
    return f == null ? null : (c.distancia_km / mapa.velocidad_kmh) * 60 * f
  }, [mapa, nivelDe])

  // Resolver cada vez que cambia el problema.
  useEffect(() => {
    if (!mapa) return
    if (inicial === meta) {
      setSolucion(null)
      setError('Elige un destino distinto al punto de salida.')
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

  const porAlgoritmo = Object.fromEntries((solucion?.resultados ?? []).map((r) => [r.algoritmo, r]))
  const resultado = porAlgoritmo[algoritmo]
  const traza = resultado?.traza ?? []
  const verPaso = detalle && paso != null && paso < traza.length
  const estadoPaso = verPaso ? traza[paso - 1] : null
  const pasoMostrado = paso ?? traza.length

  useEffect(() => {
    if (!reproduciendo) return
    if ((paso ?? traza.length) >= traza.length) { setReproduciendo(false); setPaso(null); return }
    const t = setTimeout(() => setPaso((paso ?? 0) + 1), 800)
    return () => clearTimeout(t)
  }, [reproduciendo, paso, traza.length])

  const reproducir = () => {
    if (reproduciendo) { setReproduciendo(false); return }
    setPaso(1)
    setReproduciendo(true)
  }

  const cambiarAlgoritmo = (key) => { setAlgoritmo(key); setPaso(null); setReproduciendo(false) }

  const ciclarCalle = (c) => {
    const nuevo = siguienteNivel(nivelDe(c))
    setPreset('personalizado')
    setCambios((prev) => {
      const next = { ...prev }
      if (nuevo === c.trafico) delete next[c.id]
      else next[c.id] = nuevo
      return next
    })
  }

  const elegirPreset = (p) => {
    setPreset(p)
    setCambios(p === 'pico' ? HORA_PICO : {})
  }

  const intercambiar = () => { setInicial(meta); setMeta(inicial) }

  if (!mapa) {
    return (
      <section className="rutas">
        <Encabezado />
        {error ? <p className="form-error">{error}</p> : <p className="muted">Cargando mapa…</p>}
      </section>
    )
  }

  const destino = nodo[meta]
  const pasos = resultado?.encontrado ? indicaciones(resultado, mapa, minutosCalle) : []
  const masRapido = porAlgoritmo.costo_uniforme
  const menosCalles = porAlgoritmo.anchura
  const info = ALGORITMOS.find((a) => a.key === algoritmo)
  const nodosOrdenados = [...mapa.nodos].sort((a, b) => (a.tipo === 'cruce') - (b.tipo === 'cruce') || a.corto.localeCompare(b.corto))
  const corto = (id) => nodo[id]?.corto ?? id

  return (
    <section className="rutas">
      <Encabezado zona={mapa.zona} />

      <div className="panel rutas-plan">
        <div className="rutas-puntos">
          <div className="field">
            <label htmlFor="ruta-inicial">¿De dónde sale la ambulancia?</label>
            <select id="ruta-inicial" className="input" value={inicial} onChange={(e) => setInicial(e.target.value)}>
              {nodosOrdenados.map((n) => <option key={n.id} value={n.id}>{n.corto}</option>)}
            </select>
          </div>
          <button type="button" className="btn-ghost icon rutas-swap" onClick={intercambiar} aria-label="Intercambiar salida y destino" title="Intercambiar">
            <ArrowDownUp size={15} />
          </button>
          <div className="field">
            <label htmlFor="ruta-meta">¿A dónde va?</label>
            <select id="ruta-meta" className="input" value={meta} onChange={(e) => setMeta(e.target.value)}>
              {nodosOrdenados.map((n) => <option key={n.id} value={n.id}>{n.corto}</option>)}
            </select>
          </div>
        </div>
        <div className="rutas-trafico">
          <span className="rutas-trafico-label">Tráfico</span>
          <div className="segmentado" role="group" aria-label="Escenario de tráfico">
            <button type="button" aria-pressed={preset === 'normal'} className={preset === 'normal' ? 'on' : ''} onClick={() => elegirPreset('normal')}>Normal</button>
            <button type="button" aria-pressed={preset === 'pico'} className={preset === 'pico' ? 'on' : ''} onClick={() => elegirPreset('pico')}>Hora pico</button>
          </div>
          {preset === 'personalizado' && (
            <button type="button" className="btn-ghost" onClick={() => elegirPreset('normal')}>
              <RotateCcw size={14} /> Quitar mis cambios
            </button>
          )}
          <span className="muted rutas-tip">Toca una calle del mapa para marcarla como fluida, lenta, muy lenta o cerrada.</span>
        </div>
      </div>

      {error && <p className="form-error">{error}</p>}

      <div className="rutas-grid">
        <div className="panel rutas-mapa-panel">
          <div className="rutas-mapa-wrap">
            <Mapa
              mapa={mapa}
              nivelDe={nivelDe}
              minutosCalle={minutosCalle}
              onCalle={ciclarCalle}
              inicial={inicial}
              meta={meta}
              resultado={!verPaso && resultado?.encontrado ? resultado : null}
              estadoPaso={estadoPaso}
            />
          </div>
          <ul className="rutas-leyenda" aria-label="Leyenda">
            {NIVELES.map((n) => <li key={n}><span className={`swatch t-${n}`} />{NIVEL_LABEL[n]}</li>)}
            <li><span className="swatch ruta" />Ruta sugerida</li>
          </ul>
          <p className="rutas-nota">Esquema simplificado de calles reales de Toluca; no está a escala.</p>
        </div>

        <aside className="panel rutas-resultado" aria-live="polite">
          {cargando && !resultado && <p className="muted">Calculando ruta…</p>}
          {resultado && !resultado.encontrado && (
            <div className="rutas-sinruta">
              <strong>No hay forma de llegar</strong>
              <p>Con las calles cerradas no se puede llegar a {corto(meta)}. Abre alguna calle tocándola en el mapa.</p>
            </div>
          )}
          {resultado?.encontrado && (
            <>
              <p className="rutas-eyebrow">
                {algoritmo === 'costo_uniforme' ? 'Ruta más rápida' : `Ruta por ${info.label.toLowerCase()}`}
              </p>
              <div className="rutas-eta">
                <Clock size={22} aria-hidden="true" />
                <div>
                  <b>{redondear(resultado.minutos)}</b>
                  <span>{fmtKm(resultado.distancia_km)} · llega a {corto(meta)}</span>
                </div>
              </div>

              {algoritmo === 'costo_uniforme' && menosCalles?.encontrado && menosCalles.minutos - resultado.minutos >= 1 && (
                <p className="rutas-ahorro">
                  La ruta más corta en calles tardaría {redondear(menosCalles.minutos)} por el tráfico.
                  Esta ahorra unos {Math.round(menosCalles.minutos - resultado.minutos)} min.
                </p>
              )}
              {algoritmo !== 'costo_uniforme' && masRapido?.encontrado && resultado.minutos - masRapido.minutos >= 1 && (
                <p className="rutas-ahorro warn">
                  Hay una ruta más rápida: {redondear(masRapido.minutos)}.{' '}
                  <button type="button" className="link" onClick={() => cambiarAlgoritmo('costo_uniforme')}>Verla</button>
                </p>
              )}

              <ol className="rutas-indicaciones">
                {pasos.map((t, i) => (
                  <li key={i}>
                    <span className="num" aria-hidden="true">{i + 1}</span>
                    <div>
                      <strong>{t.texto}</strong>
                      <span>
                        hasta {t.hasta.corto} · {fmtKm(t.km)} · {redondear(t.min)}
                        {t.niveles.some((c) => nivelDe(c) === 'denso') && <em className="t-denso-txt"> · tráfico muy lento</em>}
                      </span>
                    </div>
                  </li>
                ))}
                <li className="llegada">
                  <span className="num" aria-hidden="true"><MapPin size={13} /></span>
                  <div><strong>Llegas a {destino?.corto}</strong></div>
                </li>
              </ol>

              {destino?.lat != null && (
                <a
                  className="rutas-maps"
                  href={`https://www.google.com/maps/search/?api=1&query=${destino.lat}%2C${destino.lng}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  <ExternalLink size={14} /> Ver {destino.corto} en Google Maps
                </a>
              )}
            </>
          )}
        </aside>
      </div>

      <details className="panel rutas-detalle" open={detalle} onToggle={(e) => setDetalle(e.currentTarget.open)}>
        <summary>
          <div>
            <strong>¿Cómo se calculó la ruta?</strong>
            <span>Búsqueda ciega sobre el espacio de estados: anchura, profundidad y costo uniforme</span>
          </div>
          <ChevronDown size={18} className="chev" aria-hidden="true" />
        </summary>

        <div className="rutas-detalle-body">
          <dl className="kv rutas-kv">
            <dt>Estado</dt><dd>La esquina donde está la ambulancia</dd>
            <dt>Estado inicial</dt><dd>{nodo[inicial]?.nombre}</dd>
            <dt>Estado meta</dt><dd>{destino?.nombre}</dd>
            <dt>Operadores</dt><dd>Avanzar a la siguiente esquina por una calle que no esté cerrada, respetando su sentido</dd>
            <dt>Costo</dt><dd>Minutos de cada calle = km ÷ {mapa.velocidad_kmh} km/h × tráfico (fluido ×1, lento ×1.8, muy lento ×3)</dd>
          </dl>

          <h3 className="rutas-h3">Comparación de algoritmos</h3>
          <div className="table-wrap rutas-tabla">
            <table>
              <thead>
                <tr><th>Algoritmo</th><th>Qué garantiza</th><th>Tiempo</th><th>Calles</th><th>Esquinas revisadas</th></tr>
              </thead>
              <tbody>
                {ALGORITMOS.map((a) => {
                  const r = porAlgoritmo[a.key]
                  return (
                    <tr key={a.key} className={a.key === algoritmo ? 'sel' : ''} onClick={() => cambiarAlgoritmo(a.key)}>
                      <td><strong>{a.label}</strong>{a.key === solucion?.mas_rapido && <span className="badge b-activo">más rápida</span>}</td>
                      <td className="wrap">{a.garantiza}</td>
                      <td>{r?.encontrado ? fmtMin(r.minutos) : 'sin ruta'}</td>
                      <td>{r?.num_calles ?? '—'}</td>
                      <td>{r?.expandidos ?? '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="field-hint">
            Ninguno de los tres usa una estimación de qué tan lejos está el destino (por eso son búsqueda ciega).
            Anchura cuenta calles y profundidad sigue el primer camino que encuentra; ninguno de los dos mira el
            tráfico. Costo uniforme suma los minutos de cada calle, por eso evita las calles lentas aunque recorra más.
          </p>

          <div className="rutas-paso-head">
            <h3 className="rutas-h3">Búsqueda paso a paso · {info.label}</h3>
            <div className="segmentado" role="group" aria-label="Algoritmo">
              {ALGORITMOS.map((a) => (
                <button key={a.key} type="button" aria-pressed={algoritmo === a.key} className={algoritmo === a.key ? 'on' : ''} onClick={() => cambiarAlgoritmo(a.key)}>
                  {a.label}
                </button>
              ))}
            </div>
          </div>
          <p className="field-hint">Frontera: {info.frontera}.</p>

          {resultado && (
            <>
              <div className="rutas-slider">
                <button type="button" className="btn-ghost" onClick={reproducir} disabled={!traza.length}>
                  {reproduciendo ? <><Pause size={14} /> Pausar</> : <><Play size={14} /> Reproducir</>}
                </button>
                <label htmlFor="ruta-paso">Paso {Math.min(pasoMostrado, traza.length)} de {traza.length}</label>
                <input
                  id="ruta-paso"
                  type="range"
                  min={1}
                  max={Math.max(traza.length, 1)}
                  value={Math.min(pasoMostrado, traza.length)}
                  onChange={(e) => { setReproduciendo(false); const v = Number(e.target.value); setPaso(v >= traza.length ? null : v) }}
                />
              </div>
              {estadoPaso && (
                <p className="rutas-narra">
                  Se revisa <strong>{corto(estadoPaso.estado)}</strong> ({fmtMin(estadoPaso.g)} acumulados).{' '}
                  {estadoPaso.agregados.length
                    ? <>Pasan a la frontera: {estadoPaso.agregados.map(corto).join(', ')}.</>
                    : <>No agrega esquinas nuevas.</>}
                  {' '}El mapa marca en rojo la esquina revisada, con borde azul las que esperan en la frontera y en gris las ya revisadas.
                </p>
              )}
              <div className="table-wrap rutas-tabla">
                <table>
                  <thead>
                    <tr><th>Paso</th><th>Esquina revisada</th><th>Minutos</th><th>Se agregan a la frontera</th><th>Frontera</th></tr>
                  </thead>
                  <tbody>
                    {traza.map((t) => (
                      <tr
                        key={t.paso}
                        className={t.paso === Math.min(pasoMostrado, traza.length) ? 'sel' : ''}
                        onClick={() => { setReproduciendo(false); setPaso(t.paso >= traza.length ? null : t.paso) }}
                      >
                        <td>{t.paso}</td>
                        <td><strong>{corto(t.estado)}</strong>{t.meta && <span className="badge b-activo">destino</span>}</td>
                        <td>{t.g.toFixed(1)}</td>
                        <td className="wrap">{t.agregados.map(corto).join(', ') || '—'}</td>
                        <td className="wrap">{t.frontera.map(corto).join(', ') || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </details>
    </section>
  )
}

function Encabezado({ zona }) {
  return (
    <header className="view-head">
      <div>
        <h1>Rutas y tráfico</h1>
        <p>{zona ?? 'Encuentra la ruta más rápida para la ambulancia'}</p>
      </div>
      <Siren size={28} className="rutas-head-icon" aria-hidden="true" />
    </header>
  )
}

// ─── Mapa ───

const VB = { x: 70, y: 30, w: 830, h: 530 }   // área visible del dibujo

function Mapa({ mapa, nivelDe, minutosCalle, onCalle, inicial, meta, resultado, estadoPaso }) {
  const nodo = Object.fromEntries(mapa.nodos.map((n) => [n.id, n]))
  const enRuta = new Set(resultado?.calles ?? [])
  const expandidos = new Set(estadoPaso?.expandidos ?? [])
  const frontera = new Set(estadoPaso?.frontera ?? [])
  const xs = [...new Set(mapa.nodos.map((n) => n.x))].sort((a, b) => a - b)
  const ys = [...new Set(mapa.nodos.map((n) => n.y))].sort((a, b) => a - b)

  // Una etiqueta por calle: las horizontales sobre su primer tramo y las verticales a la
  // derecha de su tramo central, para no chocar con los nombres de las esquinas.
  const porNombre = new Map()
  const yCentro = (ys[0] + ys[ys.length - 1]) / 2
  for (const c of mapa.calles) {
    const a = nodo[c.a], b = nodo[c.b]
    const e = { nombre: c.nombre, vertical: a.x === b.x, x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
    const previa = porNombre.get(c.nombre)
    if (!previa || (e.vertical && Math.abs(e.y - yCentro) < Math.abs(previa.y - yCentro))) porNombre.set(c.nombre, e)
  }
  const etiquetas = [...porNombre.values()]

  return (
    <svg viewBox={`${VB.x} ${VB.y} ${VB.w} ${VB.h}`} className="rutas-mapa" role="img" aria-label="Mapa de calles con su tráfico y la ruta sugerida">
      <defs>
        <marker id="flecha" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="4" markerHeight="4" orient="auto">
          <path d="M0 0 10 5 0 10z" className="flecha" />
        </marker>
      </defs>

      <rect x={VB.x} y={VB.y} width={VB.w} height={VB.h} rx="12" className="fondo" />
      {/* Manzanas entre calles */}
      {xs.slice(0, -1).map((x, i) => ys.slice(0, -1).map((y, j) => (
        <rect key={`${i}-${j}`} x={x + 22} y={y + 22} width={xs[i + 1] - x - 44} height={ys[j + 1] - y - 44} rx="10" className="manzana" />
      )))}

      {/* Calles */}
      {mapa.calles.map((c) => {
        const a = nodo[c.a], b = nodo[c.b]
        const nivel = nivelDe(c)
        const min = minutosCalle(c)
        const titulo = `${c.nombre}: ${NIVEL_LABEL[nivel].toLowerCase()}` +
          (min != null ? `, ${min.toFixed(1)} min` : '') + (c.nota && nivel === 'bloqueado' ? ` (${c.nota.toLowerCase()})` : '') +
          '. Toca para cambiar.'
        const activar = () => onCalle(c)
        return (
          <g
            key={c.id}
            className={`calle t-${nivel}`}
            role="button"
            tabIndex={0}
            aria-label={titulo}
            onClick={activar}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activar() } }}
          >
            <title>{titulo}</title>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="hit" />
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="casing" />
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="via" />
            {c.sentido === 'ida' && (
              <line
                x1={a.x + (b.x - a.x) * 0.3} y1={a.y + (b.y - a.y) * 0.3}
                x2={a.x + (b.x - a.x) * 0.34} y2={a.y + (b.y - a.y) * 0.34}
                className="sentido" markerEnd="url(#flecha)"
              />
            )}
          </g>
        )
      })}

      {/* Ruta sugerida, encima del tráfico */}
      {resultado?.calles.map((cid, i) => {
        const a = nodo[resultado.ruta[i]], b = nodo[resultado.ruta[i + 1]]
        return <line key={cid} x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="ruta" />
      })}

      {/* Calles cerradas */}
      {mapa.calles.filter((c) => nivelDe(c) === 'bloqueado').map((c) => {
        const a = nodo[c.a], b = nodo[c.b]
        const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2
        return (
          <g key={c.id} className="bloqueo" transform={`translate(${mx} ${my})`} pointerEvents="none">
            <circle r="13" />
            <path d="M-5 -5 5 5M5 -5-5 5" />
            <text x={a.x === b.x ? -20 : 0} y={a.x === b.x ? 4 : 28} textAnchor={a.x === b.x ? 'end' : 'middle'}>Cerrada</text>
          </g>
        )
      })}

      {/* Nombres de calles */}
      {etiquetas.map((e) => (
        e.vertical
          ? <text key={e.nombre} className="nombre-calle" transform={`translate(${e.x + 24} ${e.y}) rotate(90)`} textAnchor="middle">{e.nombre}</text>
          : <text key={e.nombre} className={`nombre-calle${e.nombre === 'Paseo Tollocan' ? ' principal' : ''}`} x={e.x} y={e.y - 16} textAnchor="middle">{e.nombre}</text>
      ))}

      {/* Esquinas */}
      {mapa.nodos.map((n) => {
        const especial = n.tipo !== 'cruce'
        const cls = [
          'nodo', `n-${n.tipo}`,
          (n.id === inicial || n.id === meta) && 'marcado',
          expandidos.has(n.id) && 'expandido',
          frontera.has(n.id) && 'frontera',
          estadoPaso?.estado === n.id && 'actual',
        ].filter(Boolean).join(' ')
        return (
          <g key={n.id} className={cls} transform={`translate(${n.x} ${n.y})`}>
            <title>{n.nombre}</title>
            <circle r={especial ? 20 : 13} className="halo" />
            <circle r={especial ? 15 : 7} className="punto" />
            {n.tipo === 'hospital' && <path d="M-2.5 -8h5v5.5h5.5v5H2.5v5.5h-5V2.5H-8v-5h5.5z" className="cruz" />}
            {n.tipo === 'base' && (
              <g className="amb">
                <path d="M-9 3V-5h9l4 4h5v4z" />
                <circle cx="-5" cy="5" r="2.3" />
                <circle cx="5" cy="5" r="2.3" />
              </g>
            )}
          </g>
        )
      })}

      {/* Etiquetas de salida, destino, base y hospital */}
      {mapa.nodos.filter((n) => n.tipo !== 'cruce' || n.id === inicial || n.id === meta).map((n) => {
        const rol = n.id === inicial ? 'Salida' : n.id === meta ? 'Destino' : null
        // La etiqueta va dentro de la manzana vecina, que está vacía: a la derecha de la
        // esquina (a la izquierda en la última columna) y abajo (arriba en la última fila).
        const derecha = n.x < xs[xs.length - 1]
        const abajo = n.y < ys[ys.length - 1]
        const anchor = derecha ? 'start' : 'end'
        const tx = n.x + (derecha ? 26 : -26)
        const ty = n.y + (abajo ? 38 : -34)
        return (
          <g key={`lbl-${n.id}`} className="etiqueta" transform={`translate(${tx} ${ty})`} pointerEvents="none">
            {rol && <text className="rol" textAnchor={anchor} y={0}>{rol.toUpperCase()}</text>}
            <text className="nombre" textAnchor={anchor} y={rol ? 17 : 8}>{n.corto}</text>
          </g>
        )
      })}
    </svg>
  )
}
