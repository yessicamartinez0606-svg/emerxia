import { useEffect, useMemo, useState } from 'react'
import { ChevronDown, Search, Siren, X } from 'lucide-react'
import MapaToluca from '../components/MapaToluca.jsx'
import {
  ALGORITMOS, ALGORITMO_COLOR, HORAS, NIVEL_COLOR, NIVEL_LABEL, calcularRuta, fmtHora, fmtKm, fmtMin,
  geocodificar, obtenerZona,
} from '../lib/busqueda.js'

// Mapa de Toluca, Metepec, San Mateo Atenco y Lerma con el tráfico estimado de las avenidas y las rutas de la ambulancia desde
// el Hospital IMSS 220. Al tocar el mapa (o buscar una dirección) se calcula la ruta con los
// cinco algoritmos (tres de búsqueda ciega y dos heurísticos: greedy y A*) y se comparan; abajo se
// ve la búsqueda paso a paso.

export default function RutasPage() {
  const [hora, setHora] = useState(null)
  const [zona, setZona] = useState(null)
  const [errorZona, setErrorZona] = useState('')
  const [punto, setPunto] = useState(null)            // {lat, lng, texto}
  const [busqueda, setBusqueda] = useState('')
  const [buscando, setBuscando] = useState(false)
  const [ruta, setRuta] = useState(null)
  const [cargandoRuta, setCargandoRuta] = useState(false)
  const [errorRuta, setErrorRuta] = useState('')
  const [algoritmo, setAlgoritmo] = useState('costo_uniforme')
  const [verTodas, setVerTodas] = useState(false)

  useEffect(() => {
    setErrorZona('')
    obtenerZona(hora).then(setZona).catch((e) => setErrorZona(e.message))
  }, [hora])

  const h = zona?.hospital
  useEffect(() => {
    if (!punto || !h) { setRuta(null); return }
    let vigente = true
    setCargandoRuta(true)
    setErrorRuta('')
    calcularRuta({ origen: { lat: h.lat, lng: h.lng }, destino: { lat: punto.lat, lng: punto.lng }, hora })
      .then((r) => { if (vigente) setRuta(r) })
      .catch((e) => { if (vigente) { setErrorRuta(e.message); setRuta(null) } })
      .finally(() => { if (vigente) setCargandoRuta(false) })
    return () => { vigente = false }
  }, [punto, hora, h?.lat, h?.lng]) // eslint-disable-line react-hooks/exhaustive-deps

  const buscar = async (e) => {
    e.preventDefault()
    if (busqueda.trim().length < 3) return
    setBuscando(true)
    setErrorRuta('')
    try {
      const p = await geocodificar(busqueda.trim())
      setPunto({ lat: p.lat, lng: p.lng, texto: busqueda.trim() })
    } catch (err) {
      setErrorRuta(err.message)
    } finally {
      setBuscando(false)
    }
  }

  const porAlgoritmo = Object.fromEntries((ruta?.resultados ?? []).map((r) => [r.algoritmo, r]))
  const elegido = porAlgoritmo[algoritmo]

  // Avenidas sin tráfico, agrupadas por nombre, de la más larga a la más corta.
  const despejadas = useMemo(() => {
    if (!zona) return []
    const largo = new Map()
    for (const v of zona.vias) {
      if (v.nivel !== 'libre' || !v.nombre || !['trunk', 'primary', 'secondary'].includes(v.tipo)) continue
      let km = 0
      for (let i = 1; i < v.coords.length; i++) {
        const a = v.coords[i - 1], b = v.coords[i]
        km += Math.hypot((b[0] - a[0]) * 111, (b[1] - a[1]) * 105)
      }
      largo.set(v.nombre, (largo.get(v.nombre) ?? 0) + km)
    }
    return [...largo.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8)
  }, [zona])

  const lineas = useMemo(() => {
    const out = []
    for (const v of zona?.vias ?? []) {
      const principal = ['motorway', 'trunk', 'primary'].includes(v.tipo.replace('_link', ''))
      out.push({
        id: `v${v.id}`, coords: v.coords, color: NIVEL_COLOR[v.nivel], ancho: principal ? 3.5 : 2.5,
        opacidad: ruta ? 0.35 : 0.85, titulo: `${v.nombre ?? 'Sin nombre'}: ${NIVEL_LABEL[v.nivel].toLowerCase()}`,
      })
    }
    if (verTodas) {
      for (const r of ruta?.resultados ?? []) {
        if (!r.encontrado || r.algoritmo === algoritmo) continue
        out.push({ id: `r-${r.algoritmo}`, coords: r.coords, color: ALGORITMO_COLOR[r.algoritmo], ancho: 4, opacidad: 0.85, punteada: true, titulo: r.nombre })
      }
    }
    if (elegido?.encontrado) {
      out.push({ id: 'elegida', coords: elegido.coords, color: ALGORITMO_COLOR[algoritmo], ancho: 7, borde: true, titulo: elegido.nombre })
    }
    return out
  }, [zona, ruta, algoritmo, verTodas, elegido])

  const marcadores = []
  if (h) marcadores.push({ id: 'h', lat: h.lat, lng: h.lng, tipo: 'hospital', etiqueta: h.corto })
  if (punto) marcadores.push({ id: 'p', lat: punto.lat, lng: punto.lng, tipo: 'emergencia', etiqueta: punto.texto })

  const lineasFinal = [...lineas]
  // Del punto exacto a la esquina donde empieza o termina la ruta (los últimos metros).
  if (elegido?.encontrado && punto) {
    const fin = elegido.coords[elegido.coords.length - 1]
    lineasFinal.push({ id: 'acceso', coords: [fin, [punto.lat, punto.lng]], color: '#45454f', ancho: 2.5, punteada: true })
  }

  const encuadre = elegido?.encontrado
    ? [...elegido.coords, [punto.lat, punto.lng]]
    : zona ? [[zona.zona[0], zona.zona[1]], [zona.zona[2], zona.zona[3]]] : null

  return (
    <section className="rutas">
      <header className="view-head">
        <div>
          <h1>Rutas y tráfico</h1>
          <p>Toluca, Metepec, San Mateo Atenco y Lerma · tráfico estimado de las avenidas y rutas de la ambulancia desde el Hospital IMSS 220</p>
        </div>
        <Siren size={28} className="rutas-head-icon" aria-hidden="true" />
      </header>

      <div className="panel rutas-barra">
        <form className="rutas-buscar" onSubmit={buscar} role="search">
          <Search size={16} aria-hidden="true" />
          <label htmlFor="rutas-q" className="sr-only">Dirección de la emergencia</label>
          <input
            id="rutas-q"
            type="search"
            placeholder="Escribe una dirección (Toluca, Metepec, San Mateo Atenco o Lerma) o toca el mapa"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />
          <button className="btn-primary compact" disabled={buscando || busqueda.trim().length < 3}>
            {buscando ? 'Buscando…' : 'Trazar ruta'}
          </button>
        </form>
        <div className="segmentado" role="group" aria-label="Hora del tráfico">
          {HORAS.map((o) => (
            <button key={o.label} type="button" className={hora === o.valor ? 'on' : ''} aria-pressed={hora === o.valor} onClick={() => setHora(o.valor)}>
              {o.label}
            </button>
          ))}
        </div>
      </div>

      {errorZona && <p className="form-error">{errorZona}</p>}

      <div className="rutas-grid">
        <div className="panel rutas-mapa-panel">
          <MapaToluca
            lineas={lineasFinal}
            marcadores={marcadores}
            encuadre={encuadre}
            onClick={(lat, lng) => setPunto({ lat, lng, texto: 'Punto elegido' })}
            alto={560}
          />
          <ul className="ruta-leyenda">
            {['libre', 'moderado', 'denso'].map((n) => (
              <li key={n}><span style={{ background: NIVEL_COLOR[n] }} />{NIVEL_LABEL[n]}</li>
            ))}
            <li><span style={{ background: ALGORITMO_COLOR[algoritmo] }} />Ruta de la ambulancia</li>
          </ul>
          <p className="rutas-nota">
            Tráfico estimado {zona ? `para las ${fmtHora(zona.hora)} (${zona.periodo_nombre.toLowerCase()})` : ''} según el tipo de avenida; no son datos en vivo.
          </p>
        </div>

        <aside className="rutas-lado">
          {!punto && (
            <div className="panel">
              <h2 className="panel-title">¿A dónde va la ambulancia?</h2>
              <p className="muted rutas-ayuda">Toca cualquier punto del mapa o escribe una dirección. La ruta sale del Hospital IMSS 220.</p>
              {despejadas.length > 0 && (
                <>
                  <h3 className="rutas-h3">Avenidas sin tráfico {hora == null ? 'ahora' : 'a esa hora'}</h3>
                  <ul className="rutas-despejadas">
                    {despejadas.map(([nombre, km]) => (
                      <li key={nombre}><span className="dot-libre" />{nombre}<small>{km.toFixed(1)} km</small></li>
                    ))}
                  </ul>
                </>
              )}
              {zona && despejadas.length === 0 && <p className="muted">A esta hora todas las avenidas principales tienen tráfico.</p>}
              {!zona && !errorZona && <p className="muted">Cargando el mapa…</p>}
            </div>
          )}

          {punto && (
            <div className="panel rutas-resultado">
              <div className="rutas-resultado-head">
                <p className="rutas-eyebrow">Del Hospital IMSS 220 a</p>
                <button type="button" className="btn-ghost icon" onClick={() => { setPunto(null); setBusqueda('') }} aria-label="Quitar destino"><X size={14} /></button>
              </div>
              <p className="rutas-destino">{ruta?.destino?.esquina ?? punto.texto}</p>

              {cargandoRuta && <p className="muted">Calculando con los cinco algoritmos…</p>}
              {errorRuta && <p className="form-error">{errorRuta}</p>}

              {ruta && (
                <>
                  <div className="rutas-algos" role="group" aria-label="Algoritmo">
                    {ALGORITMOS.map((a) => {
                      const r = porAlgoritmo[a.key]
                      return (
                        <button
                          key={a.key}
                          type="button"
                          className={`rutas-algo${algoritmo === a.key ? ' on' : ''}`}
                          aria-pressed={algoritmo === a.key}
                          onClick={() => setAlgoritmo(a.key)}
                          style={{ '--c': ALGORITMO_COLOR[a.key] }}
                        >
                          <span className="nombre">
                            {a.label}
                            {a.heuristico && <i className="tipo">heurística</i>}
                            {r?.encontrado && r.minutos === porAlgoritmo[ruta.mas_rapido]?.minutos && <em>más rápida</em>}
                          </span>
                          <b>{r?.encontrado ? fmtMin(r.minutos) : 'sin ruta'}</b>
                          <small>{r?.encontrado ? `${fmtKm(r.km)} · ${r.expandidos.toLocaleString('es-MX')} esquinas revisadas` : ''}</small>
                        </button>
                      )
                    })}
                  </div>
                  <label className="rutas-check">
                    <input type="checkbox" checked={verTodas} onChange={(e) => setVerTodas(e.target.checked)} /> Mostrar todas las rutas en el mapa
                  </label>

                  {elegido?.encontrado && (
                    <ol className="ruta-pasos">
                      {elegido.indicaciones.map((p, i) => (
                        <li key={i}>
                          <span className="num" aria-hidden="true" style={{ background: ALGORITMO_COLOR[algoritmo] }}>{i + 1}</span>
                          <div>
                            <strong>{p.texto}</strong>
                            <span>
                              {fmtKm(p.km)} · {fmtMin(p.minutos)}
                              {p.nivel !== 'libre' && <em style={{ color: NIVEL_COLOR[p.nivel] }}> · {NIVEL_LABEL[p.nivel].toLowerCase()}</em>}
                            </span>
                          </div>
                        </li>
                      ))}
                    </ol>
                  )}
                </>
              )}
            </div>
          )}
        </aside>
      </div>

      {ruta && <Explicacion ruta={ruta} algoritmo={algoritmo} setAlgoritmo={setAlgoritmo} />}
    </section>
  )
}

function Explicacion({ ruta, algoritmo, setAlgoritmo }) {
  const info = ALGORITMOS.find((a) => a.key === algoritmo)
  const r = ruta.resultados.find((x) => x.algoritmo === algoritmo)
  return (
    <details className="panel rutas-detalle">
      <summary>
        <div>
          <strong>¿Cómo se calculó la ruta?</strong>
          <span>Búsqueda ciega y heurística sobre el espacio de estados de las calles reales</span>
        </div>
        <ChevronDown size={18} className="chev" aria-hidden="true" />
      </summary>
      <div className="rutas-detalle-body">
        <dl className="kv rutas-kv">
          <dt>Estado</dt><dd>La esquina donde está la ambulancia ({ruta.esquinas.toLocaleString('es-MX')} esquinas en el mapa descargado)</dd>
          <dt>Estado inicial</dt><dd>{ruta.origen.esquina} (junto al Hospital IMSS 220)</dd>
          <dt>Estado meta</dt><dd>{ruta.destino.esquina}</dd>
          <dt>Operadores</dt><dd>Avanzar a la siguiente esquina por una calle abierta, respetando su sentido</dd>
          <dt>Costo g(n)</dt><dd>Minutos de cada tramo = distancia ÷ velocidad de la vía × tráfico (sin tráfico ×1, lento ×1.8, pesado ×3)</dd>
          <dt>Heurística h(n)</dt>
          <dd>
            Minutos estimados que faltan = distancia en línea recta hasta el destino ÷ {ruta.heuristica.velocidad_kmh} km/h × 60.
            Esos {ruta.heuristica.velocidad_kmh} km/h son lo más rápido que se puede ir a esta hora con el tráfico, así que h(n) nunca
            sobreestima (es admisible) y A* encuentra la misma ruta que costo uniforme. Desde la salida, h = {ruta.heuristica.h_inicial} min.
          </dd>
        </dl>

        <div className="rutas-paso-head">
          <h3 className="rutas-h3">Búsqueda paso a paso · {info.label}</h3>
          <div className="segmentado" role="group" aria-label="Algoritmo">
            {ALGORITMOS.map((a) => (
              <button key={a.key} type="button" className={algoritmo === a.key ? 'on' : ''} aria-pressed={algoritmo === a.key} onClick={() => setAlgoritmo(a.key)}>{a.label}</button>
            ))}
          </div>
        </div>
        <p className="field-hint">
          Frontera: {info.frontera}. Garantiza {info.garantiza}.
          {r && !r.traza_completa && ` Se muestran los primeros ${r.traza.length} de ${r.expandidos.toLocaleString('es-MX')} pasos.`}
        </p>
        {r && (
          <div className="table-wrap rutas-tabla">
            <table>
              <thead>
                <tr>
                  <th>Paso</th><th>Esquina revisada</th><th>g(n) min</th>
                  {info.heuristico && <th>h(n) min</th>}
                  {algoritmo === 'a_estrella' && <th>f(n) = g + h</th>}
                  <th>Esquinas nuevas en la frontera</th><th>Frontera</th>
                </tr>
              </thead>
              <tbody>
                {r.traza.map((t) => (
                  <tr key={t.paso} className={t.meta ? 'sel' : ''}>
                    <td>{t.paso}</td>
                    <td className="wrap"><strong>{t.estado}</strong>{t.meta && <span className="badge b-activo">destino</span>}</td>
                    <td>{t.g.toFixed(1)}</td>
                    {info.heuristico && <td>{t.h?.toFixed(1)}</td>}
                    {algoritmo === 'a_estrella' && <td>{t.f?.toFixed(1)}</td>}
                    <td className="wrap">{t.agregados.join(' · ') || '—'}</td>
                    <td>{t.frontera}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </details>
  )
}
