import { useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, ChevronDown, Dna, Search, TriangleAlert } from 'lucide-react'
import MapaToluca from '../components/MapaToluca.jsx'
import { geocodificar } from '../lib/busqueda.js'
import { PARAMETROS, obtenerHospitales, resolverDespacho } from '../lib/despacho.js'

// Despacho de ambulancia para UN accidente con algoritmo genético: la ambulancia sale de un
// hospital, va al accidente y regresa. El algoritmo elige el hospital de salida (y el de
// regreso, si puede ser otro) usando la distancia euclidiana en línea recta. Se muestran
// todas las opciones para comprobar que llegó al óptimo exacto.

const ACCIDENTE_INICIAL = { lat: 19.2655, lng: -99.6035, texto: 'Accidente' }
const IDA = '#c8202f'
const REGRESO = '#1d5fd6'
const fmtKm = (km) => `${km.toFixed(2)} km`
const fmtMin = (m) => `${m.toFixed(1)} min`

// incrustado: se muestra como pestaña de Inteligencia artificial (sin el título de página).
export default function DespachoPage({ incrustado = false, inicial = null }) {
  const [hospitales, setHospitales] = useState(null)
  const [ambulancias, setAmbulancias] = useState({})
  const [accidente, setAccidente] = useState(inicial || ACCIDENTE_INICIAL)
  const [mismo, setMismo] = useState(true)
  const [param, setParam] = useState(() => Object.fromEntries(PARAMETROS.map((p) => [p.key, p.def])))
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState('')
  const [calculando, setCalculando] = useState(false)
  const [busqueda, setBusqueda] = useState('')
  const [buscando, setBuscando] = useState(false)
  const [corrida, setCorrida] = useState(0)          // «Volver a correr»: el genético es aleatorio
  const pedido = useRef(0)

  useEffect(() => {
    obtenerHospitales()
      .then((d) => {
        setHospitales(d.hospitales)
        setAmbulancias(Object.fromEntries(d.hospitales.map((h) => [h.id, h.ambulancias])))
      })
      .catch((e) => setError(e.message))
  }, [])

  // Recalcular cuando cambia el problema (con una pequeña espera mientras se escribe).
  useEffect(() => {
    if (!hospitales) return
    const amb = Object.fromEntries(Object.entries(ambulancias).map(([k, v]) => [k, Number(v) || 0]))
    const id = ++pedido.current
    const t = setTimeout(() => {
      setCalculando(true)
      resolverDespacho({ accidente: { lat: accidente.lat, lng: accidente.lng }, ambulancias: amb, mismo_hospital: mismo, ...param })
        .then((r) => { if (id === pedido.current) { setResultado(r); setError('') } })
        .catch((e) => { if (id === pedido.current) setError(e.message) })
        .finally(() => { if (id === pedido.current) setCalculando(false) })
    }, 350)
    return () => clearTimeout(t)
  }, [hospitales, ambulancias, accidente, mismo, param, corrida])

  const buscar = async (e) => {
    e.preventDefault()
    if (busqueda.trim().length < 3) return
    setBuscando(true)
    try {
      const p = await geocodificar(busqueda.trim())
      setAccidente({ lat: p.lat, lng: p.lng, texto: busqueda.trim() })
    } catch (err) {
      setError(err.message)
    } finally {
      setBuscando(false)
    }
  }

  const porId = useMemo(() => Object.fromEntries((resultado?.hospitales ?? hospitales ?? []).map((h) => [h.id, h])), [resultado, hospitales])
  const mejor = resultado?.mejor
  const salida = mejor && porId[mejor.salida]
  const regreso = mejor && porId[mejor.regreso]
  const mismoDestino = mejor && mejor.salida === mejor.regreso

  const lineas = []
  if (salida && regreso) {
    lineas.push({ id: 'ida', coords: [[salida.lat, salida.lng], [accidente.lat, accidente.lng]], color: IDA, ancho: 5, borde: true, titulo: 'Ida' })
    lineas.push({ id: 'regreso', coords: [[accidente.lat, accidente.lng], [regreso.lat, regreso.lng]], color: REGRESO, ancho: 3.5, punteada: true, titulo: 'Regreso' })
  }
  const marcadores = [
    ...(hospitales ?? []).map((h) => {
      const elegido = mejor && (h.id === mejor.salida || h.id === mejor.regreso)
      return {
        id: h.id, lat: h.lat, lng: h.lng, tipo: elegido ? 'hospital' : 'hospital-otro',
        etiqueta: elegido ? h.nombre : `${h.nombre} · ${ambulancias[h.id] ?? 0} amb.`,
      }
    }),
    { id: 'acc', lat: accidente.lat, lng: accidente.lng, tipo: 'emergencia', etiqueta: accidente.texto },
  ]
  // Encuadre fijo: todos los hospitales y el accidente inicial (no se mueve con cada clic).
  const encuadre = useMemo(
    () => (hospitales ? [...hospitales.map((h) => [h.lat, h.lng]), [ACCIDENTE_INICIAL.lat, ACCIDENTE_INICIAL.lng]] : null),
    [hospitales],
  )

  return (
    <section className="rutas despacho">
      {incrustado ? null : (
        <header className="view-head">
          <div>
            <h1>Despacho de ambulancia</h1>
            <p>Algoritmo genético: elige de qué hospital sale la ambulancia hacia el accidente y a cuál regresa</p>
          </div>
          <Dna size={28} className="rutas-head-icon" aria-hidden="true" />
        </header>
      )}

      <div className="panel rutas-barra">
        <form className="rutas-buscar" onSubmit={buscar} role="search">
          <Search size={16} aria-hidden="true" />
          <label htmlFor="despacho-q" className="sr-only">Dirección del accidente</label>
          <input
            id="despacho-q"
            type="search"
            placeholder="Dirección del accidente, o toca el mapa para moverlo"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />
          <button className="btn-primary compact" disabled={buscando || busqueda.trim().length < 3}>
            {buscando ? 'Buscando…' : 'Ubicar'}
          </button>
        </form>
        <div className="segmentado" role="group" aria-label="Hospital de regreso">
          <button type="button" className={mismo ? 'on' : ''} aria-pressed={mismo} onClick={() => setMismo(true)}>Regresa al mismo hospital</button>
          <button type="button" className={!mismo ? 'on' : ''} aria-pressed={!mismo} onClick={() => setMismo(false)}>Puede regresar a otro</button>
        </div>
      </div>

      {error && <p className="form-error">{error}</p>}

      <div className="rutas-grid">
        <div className="panel">
          <MapaToluca
            lineas={lineas}
            marcadores={marcadores}
            encuadre={encuadre}
            onClick={(lat, lng) => setAccidente({ lat, lng, texto: 'Accidente' })}
            alto={500}
            etiquetaAccesible="Mapa de hospitales y lugar del accidente"
          />
          <ul className="ruta-leyenda">
            <li><span style={{ background: IDA }} />Ida (línea recta)</li>
            <li><span className="punteada" />Regreso</li>
            <li><span className="despacho-swatch-hosp" />Hospital elegido</li>
            <li><span className="despacho-swatch-otro" />Otros hospitales</li>
          </ul>
          <p className="rutas-nota">Toca el mapa para mover el accidente. Las distancias se miden en línea recta, no por calles.</p>
        </div>

        <div className="panel despacho-resumen">
          <span className="rutas-eyebrow">Mejor ruta {calculando && <em className="muted">· calculando…</em>}</span>
          {!resultado ? <p className="muted">Calculando…</p> : (
            <>
              <p className="rutas-destino">
                {salida.nombre} → accidente → {mismoDestino ? 'regresa al mismo' : regreso.nombre}
              </p>
              <dl className="kv rutas-kv">
                <dt>Sale de</dt><dd>{salida.nombre} <span className="muted">({salida.ambulancias} amb.)</span></dd>
                <dt>Ida</dt><dd>{fmtKm(mejor.ida_km)} · {fmtMin(mejor.ida_min)}</dd>
                <dt>En el lugar</dt><dd>{fmtMin(resultado.parametros.minutos_en_lugar)}</dd>
                <dt>Regreso</dt><dd>{fmtKm(mejor.regreso_km)} · {fmtMin(mejor.regreso_min)}{!mismoDestino && <> · a {regreso.nombre}</>}</dd>
              </dl>
              <div className="despacho-total">
                <div><b>{fmtKm(mejor.total_km)}</b><span>Distancia total</span></div>
                <div><b>{fmtMin(mejor.total_min)}</b><span>Tiempo total aprox.</span></div>
              </div>
              {resultado.mas_cercano !== mejor.salida && porId[resultado.mas_cercano].ambulancias <= 0 && (
                <p className="field-hint warn despacho-nota">
                  El hospital más cercano es {porId[resultado.mas_cercano].nombre}, pero no tiene ambulancias disponibles.
                </p>
              )}
              {resultado.coincide_con_optimo ? (
                <p className="field-hint ok despacho-nota"><CheckCircle2 size={14} /> Coincide con el óptimo exacto (verificado revisando las {resultado.opciones.length} opciones).</p>
              ) : (
                <p className="field-hint warn despacho-nota">
                  <TriangleAlert size={14} /> El óptimo exacto es {fmtKm(resultado.optimo_exacto_km)}; sube la población o las generaciones.
                </p>
              )}
              <button type="button" className="btn-ghost" onClick={() => setCorrida((n) => n + 1)}>Calcular de nuevo</button>
            </>
          )}

          <details className="ruta-comparacion despacho-param">
            <summary>Ajustes avanzados <ChevronDown size={15} aria-hidden="true" /></summary>
            <div className="despacho-param-grid">
              {PARAMETROS.map((p) => (
                <label key={p.key}>
                  <span>{p.label}</span>
                  <input
                    className="input" type="number" min={p.min} max={p.max} step={p.step} value={param[p.key]}
                    onChange={(e) => {
                      const v = Number(e.target.value)
                      if (e.target.value !== '' && v >= p.min && v <= p.max) setParam((prev) => ({ ...prev, [p.key]: v }))
                    }}
                  />
                </label>
              ))}
            </div>
          </details>
        </div>
      </div>

      {resultado && (
        <>
          <div className="panel">
            <h2 className="panel-title">Distancia de cada hospital al accidente</h2>
            <div className="table-wrap rutas-tabla">
              <table>
                <thead>
                  <tr><th>Cercanía</th><th>Hospital</th><th>Municipio</th><th>Ambulancias</th><th>Distancia</th><th>Tiempo de llegada</th></tr>
                </thead>
                <tbody>
                  {[...resultado.hospitales].sort((a, b) => a.cercania - b.cercania).map((h) => (
                    <tr key={h.id} className={h.id === mejor.salida ? 'sel' : ''}>
                      <td>#{h.cercania}</td>
                      <td><strong>{h.nombre}</strong></td>
                      <td>{h.municipio}</td>
                      <td>
                        <input
                          className="input despacho-amb" type="number" min={0} max={50}
                          aria-label={`Ambulancias de ${h.nombre}`}
                          value={ambulancias[h.id] ?? 0}
                          onChange={(e) => setAmbulancias((prev) => ({ ...prev, [h.id]: e.target.value === '' ? '' : Math.max(0, Math.floor(Number(e.target.value))) }))}
                        />
                      </td>
                      <td>{fmtKm(h.distancia_km)}</td>
                      <td>{fmtMin(h.minutos)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="field-hint">Puedes cambiar cuántas ambulancias tiene cada hospital: uno sin ambulancias no puede ser la salida.</p>
          </div>

          <DetallesTecnicos activo={incrustado}>
          <div className="panel">
            <h2 className="panel-title">Evolución del algoritmo genético</h2>
            <Convergencia historial={resultado.historial} optimo={resultado.optimo_exacto_km} />
          </div>

          <div className="panel">
            <div className="panel-title-row">
              <h2 className="panel-title">Todas las opciones de recorrido</h2>
              <span className="muted">{resultado.opciones.length} opciones · tiempo total = ida + en el lugar + regreso</span>
            </div>
            <div className="table-wrap rutas-tabla despacho-opciones">
              <table>
                <thead>
                  <tr><th>#</th><th>Sale de</th><th>Regresa a</th><th>Ida</th><th>Regreso</th><th>Distancia total</th><th>Tiempo total</th></tr>
                </thead>
                <tbody>
                  {resultado.opciones.map((o, i) => (
                    <tr key={`${o.salida}-${o.regreso}`} className={o.salida === mejor.salida && o.regreso === mejor.regreso ? 'sel' : ''}>
                      <td>{i + 1}</td>
                      <td>{porId[o.salida].nombre}</td>
                      <td>{porId[o.regreso].nombre}</td>
                      <td>{fmtKm(o.ida_km)}</td>
                      <td>{fmtKm(o.regreso_km)}</td>
                      <td><strong>{fmtKm(o.total_km)}</strong></td>
                      <td>{fmtMin(o.total_min)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel">
            <h2 className="panel-title">Cómo funciona</h2>
            <dl className="kv rutas-kv">
              <dt>Cromosoma</dt><dd>(hospital de salida, hospital de regreso){mismo && ' — aquí siempre el mismo'}</dd>
              <dt>Aptitud</dt><dd>distancia(salida → accidente) + distancia(accidente → regreso); +1000 si el hospital de salida no tiene ambulancias</dd>
              <dt>Distancia</dt><dd>euclidiana: d = √((x₂ − x₁)² + (y₂ − y₁)²), con las coordenadas pasadas a km</dd>
              <dt>Selección</dt><dd>torneo de 3; los 2 mejores pasan directo (elitismo)</dd>
              <dt>Cruce</dt><dd>la salida de un padre y el regreso del otro</dd>
              <dt>Mutación</dt><dd>con probabilidad {param.prob_mutacion}, cambia al azar la salida o el regreso</dd>
            </dl>
          </div>
          </DetallesTecnicos>
        </>
      )}
    </section>
  )
}

// Dentro de Inteligencia artificial, lo técnico (evolución, todas las opciones y cómo funciona el
// algoritmo genético) va plegado para no confundir a quien solo quiere saber de dónde sale.
function DetallesTecnicos({ activo, children }) {
  if (!activo) return children
  return (
    <details className="iah-tecnico">
      <summary><ChevronDown size={16} aria-hidden="true" /> Ver detalles técnicos <small>Cómo evolucionó el algoritmo y todas las opciones</small></summary>
      <div className="iah-tecnico-cuerpo">{children}</div>
    </details>
  )
}

// Gráfica de convergencia: mejor distancia y promedio de la población en cada generación.
function Convergencia({ historial, optimo }) {
  const W = 720, H = 240, M = { l: 52, r: 14, t: 12, b: 34 }
  // El promedio puede incluir el castigo de 1000; se recorta para que la gráfica se lea.
  const valores = historial.flatMap((g) => [g.mejor, g.promedio])
  const max = Math.min(Math.max(...valores), optimo * 4 + 1)
  const min = 0
  const x = (i) => M.l + (historial.length > 1 ? (i / (historial.length - 1)) : 0) * (W - M.l - M.r)
  const y = (v) => M.t + (1 - (Math.min(v, max) - min) / (max - min)) * (H - M.t - M.b)
  const linea = (k) => historial.map((g, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(g[k]).toFixed(1)}`).join('')
  const marcas = [0, 0.25, 0.5, 0.75, 1].map((f) => min + f * (max - min))
  const pasosX = [...new Set([0, Math.floor((historial.length - 1) / 2), historial.length - 1])]

  return (
    <div className="despacho-grafica">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Convergencia: la mejor distancia llega a ${historial.at(-1).mejor.toFixed(2)} km`}>
        {marcas.map((v) => (
          <g key={v}>
            <line x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} className="rejilla" />
            <text x={M.l - 8} y={y(v) + 4} textAnchor="end">{v.toFixed(1)}</text>
          </g>
        ))}
        {pasosX.map((i) => <text key={i} x={x(i)} y={H - 12} textAnchor="middle">{i + 1}</text>)}
        <text x={(W + M.l) / 2} y={H - 1} textAnchor="middle" className="eje">Generación</text>
        <path d={linea('promedio')} className="promedio" />
        <path d={linea('mejor')} className="mejor" />
      </svg>
      <ul className="ruta-leyenda">
        <li><span style={{ background: 'var(--red-600)' }} />Mejor distancia total (km)</li>
        <li><span style={{ background: '#9aa0a6' }} />Promedio de la población</li>
      </ul>
    </div>
  )
}
