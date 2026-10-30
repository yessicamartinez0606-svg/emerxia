import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Ambulance, ChevronDown, Clock, MapPin, Navigation, Pause, Play, RefreshCw, RotateCcw } from 'lucide-react'
import MapaToluca from './MapaToluca.jsx'
import {
  ALGORITMOS, HORAS, NIVEL_COLOR, NIVEL_LABEL, avanceEnRuta, fmtHora, fmtKm, fmtMin, rutaDeEmergencia,
} from '../lib/busqueda.js'

// Ruta de la ambulancia para una emergencia: sale del Hospital IMSS 220, llega a la
// dirección de la emergencia y regresa al hospital. La dirección se ubica sola en el mapa
// y la ruta la calcula el backend con búsqueda ciega (costo uniforme) sobre calles reales.
// Sobre esa ruta se simula el avance de la ambulancia en tiempo acelerado: cada tramo se
// recorre al ritmo de su tráfico, así se ve cuánto falta y a qué hora llega.

const VELOCIDADES = [1, 10, 30, 60]
// OpenStreetMap casi nunca tiene números de casa en México: se avisa cuando el punto es aproximado.
const PRECISION = {
  calle: 'Ubicación aproximada: se encontró la calle, pero no el número exacto.',
  colonia: 'Ubicación aproximada: se encontró la colonia o barrio, pero no la calle.',
}
const fmtReloj = (d) => new Intl.DateTimeFormat('es-MX', { hour: 'numeric', minute: '2-digit', hour12: true }).format(d)
const SVG_AMBULANCIA = (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 10H6M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2M19 18h2a1 1 0 0 0 1-1v-3.28a1 1 0 0 0-.684-.948l-1.923-.641a1 1 0 0 1-.578-.502l-1.539-3.076A1 1 0 0 0 16.382 8H14M8 8v4M9 18h6" />
    <circle cx="17" cy="18" r="2" /><circle cx="7" cy="18" r="2" />
  </svg>
)

export default function RutaAmbulancia({ emergencia }) {
  const [hora, setHora] = useState(null)
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(true)
  const [tramo, setTramo] = useState('ida')          // ida | regreso
  const [intento, setIntento] = useState(0)
  const [minuto, setMinuto] = useState(0)            // minutos simulados desde que salió
  const [corriendo, setCorriendo] = useState(true)
  const [velocidad, setVelocidad] = useState(10)
  const [salida, setSalida] = useState(() => new Date())

  useEffect(() => {
    if (!emergencia?.id || !emergencia.direccion) return
    let vigente = true
    setCargando(true)
    setError('')
    rutaDeEmergencia(emergencia.id, hora)
      .then((d) => { if (vigente) setDatos(d) })
      .catch((e) => { if (vigente) { setError(e.message); setDatos(null) } })
      .finally(() => { if (vigente) setCargando(false) })
    return () => { vigente = false }
  }, [emergencia?.id, emergencia?.direccion, hora, intento])

  const ida = datos?.ida?.resultados.find((r) => r.algoritmo === 'costo_uniforme')
  const regreso = datos?.regreso
  const actual = tramo === 'ida' ? ida : regreso
  const total = actual?.encontrado ? actual.tramos.reduce((s, t) => s + (t.minutos ?? 0), 0) : 0
  const simulable = total > 0

  // Cada vez que cambia la ruta (otro trayecto u otra hora), la ambulancia vuelve a salir.
  useEffect(() => { setMinuto(0); setCorriendo(true); setSalida(new Date()) }, [actual])

  // Reloj de la simulación: 10 cuadros por segundo bastan para verla avanzar.
  useEffect(() => {
    if (!simulable || !corriendo) return
    const id = setInterval(() => {
      setMinuto((m) => Math.min(total, m + (0.1 * velocidad) / 60))
    }, 100)
    return () => clearInterval(id)
  }, [simulable, corriendo, velocidad, total])

  useEffect(() => { if (simulable && minuto >= total) setCorriendo(false) }, [simulable, minuto, total])

  if (!emergencia?.direccion) {
    return (
      <div className="panel ruta-amb">
        <Encabezado />
        <p className="muted">Esta emergencia no tiene dirección; agrégala para trazar la ruta.</p>
      </div>
    )
  }

  const h = datos?.hospital
  const lugar = datos?.lugar

  const lineas = []
  if (ida?.encontrado && regreso?.encontrado) {
    const otra = tramo === 'ida' ? regreso : ida
    lineas.push({ id: 'otra', coords: otra.coords, color: '#1d5fd6', ancho: 3, opacidad: 0.55, punteada: true })
    actual.tramos.forEach((t, i) => lineas.push({
      id: `t${i}`, coords: t.coords, color: NIVEL_COLOR[t.nivel], ancho: 7, borde: true, titulo: NIVEL_LABEL[t.nivel],
    }))
  }
  const avance = simulable ? avanceEnRuta(actual, minuto) : null
  if (avance) lineas.push({ id: 'recorrido', coords: avance.atras, color: '#9aa0a6', ancho: 7, titulo: 'Ya recorrido' })
  const marcadores = datos ? [
    { id: 'h', lat: h.lat, lng: h.lng, tipo: 'hospital', etiqueta: h.corto },
    { id: 'e', lat: lugar.lat, lng: lugar.lng, tipo: 'emergencia', etiqueta: `Emergencia ${datos.emergencia.folio ?? ''}`.trim() },
  ] : []
  if (avance) {
    marcadores.push({
      id: 'amb', lat: avance.punto[0], lng: avance.punto[1], tipo: 'ambulancia', icono: SVG_AMBULANCIA,
      etiqueta: emergencia.ambulancia || 'Ambulancia',
    })
  }
  // Los últimos metros: de la esquina más cercana al punto exacto de la emergencia y del hospital.
  if (actual?.encontrado) {
    const ini = actual.coords[0], fin = actual.coords[actual.coords.length - 1]
    const [a, b] = tramo === 'ida' ? [[h.lat, h.lng], [lugar.lat, lugar.lng]] : [[lugar.lat, lugar.lng], [h.lat, h.lng]]
    lineas.push({ id: 'acc-a', coords: [a, ini], color: '#45454f', ancho: 2.5, punteada: true })
    lineas.push({ id: 'acc-b', coords: [fin, b], color: '#45454f', ancho: 2.5, punteada: true })
  }
  const encuadre = datos ? [...(ida?.encontrado ? ida.coords : []), [h.lat, h.lng], [lugar.lat, lugar.lng]] : null

  return (
    <div className="panel ruta-amb">
      <Encabezado>
        <label className="ruta-hora">
          <Clock size={14} aria-hidden="true" />
          <span className="sr-only">Tráfico estimado para</span>
          <select value={hora ?? ''} onChange={(e) => setHora(e.target.value === '' ? null : Number(e.target.value))}>
            {HORAS.map((o) => <option key={o.label} value={o.valor ?? ''}>{o.label}</option>)}
          </select>
        </label>
      </Encabezado>

      {cargando && !datos && (
        <div className="ruta-cargando">
          <span className="ruta-pulso" aria-hidden="true" />
          <div>
            <strong>Ubicando la emergencia y calculando la ruta…</strong>
            <span>La primera vez se descargan las calles de la zona; puede tardar unos segundos.</span>
          </div>
        </div>
      )}

      {error && (
        <div className="ruta-error">
          <p><strong>No se pudo trazar la ruta.</strong> {error}</p>
          <button type="button" className="btn-ghost" onClick={() => setIntento((n) => n + 1)}>
            <RefreshCw size={14} /> Reintentar
          </button>
        </div>
      )}

      {datos && (
        <div className={`ruta-amb-grid${cargando ? ' recalculando' : ''}`}>
          <div className="ruta-amb-mapa">
            <MapaToluca
              lineas={lineas}
              marcadores={marcadores}
              encuadre={encuadre}
              alto={440}
              etiquetaAccesible={`Ruta del ${h.corto} a la emergencia`}
            />
            <ul className="ruta-leyenda">
              {['libre', 'moderado', 'denso'].map((n) => (
                <li key={n}><span style={{ background: NIVEL_COLOR[n] }} />{NIVEL_LABEL[n]}</li>
              ))}
              {avance && <li><span style={{ background: '#9aa0a6' }} />Ya recorrido</li>}
              <li><span className="punteada" />{tramo === 'ida' ? 'Regreso' : 'Ida'}</li>
            </ul>
          </div>

          <div className="ruta-amb-info">
            <div className="ruta-lugar">
              <MapPin size={16} aria-hidden="true" />
              <div>
                <strong>{datos.emergencia.direccion}</strong>
                <span title={lugar.texto}>{lugar.texto}</span>
                {PRECISION[lugar.precision] && <em className="ruta-lugar-aviso">{PRECISION[lugar.precision]}</em>}
              </div>
            </div>

            <div className="segmentado ruta-tabs" role="group" aria-label="Trayecto">
              <button type="button" className={tramo === 'ida' ? 'on' : ''} aria-pressed={tramo === 'ida'} onClick={() => setTramo('ida')}>Ida a la emergencia</button>
              <button type="button" className={tramo === 'regreso' ? 'on' : ''} aria-pressed={tramo === 'regreso'} onClick={() => setTramo('regreso')}>Regreso al hospital</button>
            </div>

            {actual?.encontrado ? (
              <>
                <div className="ruta-eta">
                  <Ambulance size={26} aria-hidden="true" />
                  <div>
                    <b>{fmtMin(actual.minutos)}</b>
                    <span>{fmtKm(actual.km)} · {datos.periodo_nombre.toLowerCase()} · {fmtHora(datos.hora)}</span>
                  </div>
                </div>
                {avance && (
                  <Simulacion
                    ruta={actual}
                    avance={avance}
                    restante={total - minuto}
                    llegada={new Date(salida.getTime() + total * 60000)}
                    destino={tramo === 'ida' ? 'la emergencia' : h.corto}
                    corriendo={corriendo}
                    onPausa={() => setCorriendo((c) => !c)}
                    onRepetir={() => { setMinuto(0); setCorriendo(true); setSalida(new Date()) }}
                    velocidad={velocidad}
                    onVelocidad={setVelocidad}
                  />
                )}
                <ol className="ruta-pasos">
                  {actual.indicaciones.map((p, i) => (
                    <li key={i}>
                      <span className="num" aria-hidden="true">{i + 1}</span>
                      <div>
                        <strong>{p.texto}</strong>
                        <span>
                          {fmtKm(p.km)} · {fmtMin(p.minutos)}
                          {p.nivel !== 'libre' && <em style={{ color: NIVEL_COLOR[p.nivel] }}> · {NIVEL_LABEL[p.nivel].toLowerCase()}</em>}
                        </span>
                      </div>
                    </li>
                  ))}
                  <li className="llegada">
                    <span className="num" aria-hidden="true"><Navigation size={12} /></span>
                    <div><strong>Llegas a {tramo === 'ida' ? 'la emergencia' : h.corto}</strong></div>
                  </li>
                </ol>
              </>
            ) : (
              <p className="ruta-error">No hay ruta por calles abiertas para este trayecto.</p>
            )}

            {tramo === 'ida' && datos.ida && <Comparacion ida={datos.ida} />}
          </div>
        </div>
      )}
    </div>
  )
}

function Simulacion({ ruta, avance, restante, llegada, destino, corriendo, onPausa, onRepetir, velocidad, onVelocidad }) {
  const sinTrafico = ruta.minutos_sin_trafico
  const retraso = sinTrafico != null ? ruta.minutos - sinTrafico : null
  return (
    <div className="ruta-sim">
      <div className="ruta-sim-estado">
        <span className={`ruta-sim-chip${avance.llego ? ' llego' : ''}`}>
          {avance.llego ? `Llegó a ${destino}` : `En camino · llega en ${fmtMin(restante)}`}
        </span>
        <span className="ruta-sim-ahora">
          {avance.llego ? `${fmtKm(ruta.km)} recorridos` : `Ahora: ${NIVEL_LABEL[avance.nivel].toLowerCase()}`}
        </span>
      </div>
      <div className="ruta-sim-cifras">
        {sinTrafico != null && <div><b>{fmtMin(sinTrafico)}</b><span>Sin tráfico</span></div>}
        {retraso != null && (
          <div className={retraso >= 1 ? 'retraso' : ''}><b>{retraso >= 1 ? `+${fmtMin(retraso)}` : 'Ninguno'}</b><span>Retraso por tráfico</span></div>
        )}
        <div><b>{fmtReloj(llegada)}</b><span>Hora de llegada</span></div>
        <div><b>{fmtKm(Math.max(0, ruta.km - avance.km))}</b><span>Falta por recorrer</span></div>
      </div>
      <div className="ruta-sim-barra" aria-hidden="true">
        {ruta.tramos.map((t, i) => <span key={i} style={{ flexGrow: t.km, background: NIVEL_COLOR[t.nivel] }} />)}
        <i style={{ left: `${Math.min(100, (avance.km / ruta.km) * 100)}%` }} />
      </div>
      <div className="ruta-sim-controles">
        <button type="button" className="btn-ghost" onClick={avance.llego ? onRepetir : onPausa}>
          {avance.llego ? <><RotateCcw size={14} /> Repetir</> : corriendo ? <><Pause size={14} /> Pausar</> : <><Play size={14} /> Continuar</>}
        </button>
        <div className="segmentado" role="group" aria-label="Velocidad de la simulación">
          {VELOCIDADES.map((v) => (
            <button key={v} type="button" className={velocidad === v ? 'on' : ''} aria-pressed={velocidad === v} onClick={() => onVelocidad(v)}>×{v}</button>
          ))}
        </div>
        <span className="badge">Simulación</span>
      </div>
    </div>
  )
}

function Encabezado({ children }) {
  return (
    <div className="ruta-amb-head">
      <div>
        <h2 className="form-section-title">Ruta de la ambulancia</h2>
        <p className="muted">Sale del Hospital IMSS 220 · Toluca, Metepec, San Mateo Atenco y Lerma · tráfico estimado según la hora</p>
      </div>
      {children}
    </div>
  )
}

function Comparacion({ ida }) {
  return (
    <details className="ruta-comparacion">
      <summary>
        ¿Cómo se eligió esta ruta? <ChevronDown size={15} aria-hidden="true" />
      </summary>
      <p>
        Cada esquina es un estado y cada calle abierta es un operador. Con búsqueda ciega se probaron tres
        algoritmos sobre {ida.esquinas.toLocaleString('es-MX')} esquinas de la zona; se usa el de menor tiempo.
      </p>
      <table>
        <thead><tr><th>Algoritmo</th><th>Tiempo</th><th>Esquinas revisadas</th></tr></thead>
        <tbody>
          {ALGORITMOS.map((a) => {
            const r = ida.resultados.find((x) => x.algoritmo === a.key)
            return (
              <tr key={a.key} className={a.key === ida.mas_rapido ? 'sel' : ''}>
                <td>{a.label}</td>
                <td>{r?.encontrado ? fmtMin(r.minutos) : 'sin ruta'}</td>
                <td>{r?.expandidos?.toLocaleString('es-MX') ?? '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <Link to="/rutas" className="ruta-link">Ver la búsqueda paso a paso en Rutas y tráfico</Link>
    </details>
  )
}
