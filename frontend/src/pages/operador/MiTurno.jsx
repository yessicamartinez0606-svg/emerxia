import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Ambulance, Check, Fuel, MapPin, Phone, ScanFace, Siren, UserRound, Wrench } from 'lucide-react'
import RutaAmbulancia from '../../components/RutaAmbulancia.jsx'
import { ESTADOS_MANUALES, ESTADO_INFO, HOSPITALES, colorGasolina, fmtFecha, fmtHoraCorta } from '../../lib/flota.js'
import { estadoOperador, eventoOperador, portalOperador } from '../../lib/portal.js'

// Inicio del operador: su ambulancia, su emergencia asignada (con pasos y rutas) y avisos.
// Se actualiza solo cada 30 s para que vea en cuanto la central le asigna una emergencia.

const PASOS = [
  { key: 'salida', label: 'Salí del hospital', campo: 'hora_salida', boton: 'Registrar salida' },
  { key: 'llegada', label: 'Llegué al lugar', campo: 'hora_llegada', boton: 'Registrar llegada' },
  { key: 'traslado', label: 'Traslado a hospital', campo: 'hora_traslado', boton: 'Registrar traslado' },
  { key: 'cierre', label: 'Emergencia cerrada', campo: 'hora_cierre', boton: 'Cerrar emergencia' },
]

export default function MiTurno() {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')

  const cargar = () => portalOperador().then((d) => { setDatos(d); setError('') }).catch((e) => setError(e.message))
  useEffect(() => {
    cargar()
    const t = setInterval(cargar, 30000)
    return () => clearInterval(t)
  }, [])

  if (error && !datos) return <p className="form-error">{error}</p>
  if (!datos) return <p className="muted">Cargando tu turno…</p>

  const op = datos.operador
  const ficha = datos.ficha
  const ultimaFace = datos.verificaciones.find((v) => v.coincide)

  return (
    <div className="op-turno">
      <section className="op-saludo">
        {datos.foto ? <img src={datos.foto} alt="" /> : <span className="avatar"><UserRound size={20} /></span>}
        <div>
          <h1>Hola, {op.nombre.split(' ')[0]}</h1>
          <p>Turno {op.turno}{ultimaFace ? <> · <ScanFace size={13} aria-hidden="true" /> Rostro verificado {fmtHoraCorta(ultimaFace.momento)}</> : null}</p>
        </div>
      </section>

      {error && <p className="form-error">{error}</p>}

      {datos.emergencia
        ? <EmergenciaAsignada rep={datos.emergencia} onCambio={setDatos} />
        : (
          <section className="panel op-sin-emergencia">
            <Siren size={22} aria-hidden="true" />
            <div>
              <strong>Sin emergencia asignada</strong>
              <p>Cuando la central te asigne una, aparece aquí con la dirección, el paciente y la ruta. Esta pantalla se actualiza sola.</p>
            </div>
          </section>
        )}

      {ficha ? <MiAmbulancia ficha={ficha} minimo={datos.combustible_minimo} onCambio={setDatos} /> : (
        <section className="panel">
          <h2 className="form-section-title titulo-icono"><Ambulance size={15} /> Mi ambulancia</h2>
          <p className="muted">No tienes una ambulancia asignada. Pide a la central que te asigne una.</p>
        </section>
      )}
    </div>
  )
}

function EmergenciaAsignada({ rep, onCambio }) {
  const em = rep.emergencia
  const siguiente = PASOS.find((p) => !em[p.campo])
  const [km, setKm] = useState('')
  const [obs, setObs] = useState('')
  const [destino, setDestino] = useState('Hospital IMSS 220')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  const registrar = async (tipo) => {
    setGuardando(true)
    setError('')
    try {
      onCambio(await eventoOperador({
        tipo, observaciones: obs,
        ...(tipo === 'cierre' ? { km_recorridos: Number(km) || 0 } : {}),
        ...(tipo === 'traslado' ? { hospital_destino: destino } : {}),
      }))
      setObs('')
    } catch (e) {
      setError(e.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <>
      <section className="panel op-emergencia">
        <div className="op-em-head">
          <span className="op-em-alerta"><Siren size={18} aria-hidden="true" /></span>
          <div>
            <span className="op-eyebrow">Emergencia asignada · {em.folio}</span>
            <h2>{em.descripcion}</h2>
          </div>
          <span className={`badge b-${(em.prioridad || '').toLowerCase()}`}>Prioridad {em.prioridad}</span>
        </div>

        <dl className="op-em-datos">
          <div><dt><MapPin size={13} /> Dirección</dt><dd>{em.direccion}</dd></div>
          <div><dt><UserRound size={13} /> Paciente</dt><dd>{em.paciente_nombre}{em.paciente_edad ? `, ${em.paciente_edad} años` : ''}</dd></div>
          {em.paciente_telefono && <div><dt><Phone size={13} /> Teléfono</dt><dd><a href={`tel:${em.paciente_telefono}`}>{em.paciente_telefono}</a></dd></div>}
          <div><dt><Ambulance size={13} /> Van</dt><dd>{rep.ambulancias.map((a) => `${a.placa} (${a.conductor || 'sin conductor'})`).join(', ')}</dd></div>
          {em.canal && <div><dt>Reportada por</dt><dd>{em.canal === 'llamada' ? 'Llamada' : 'Mensaje'}{em.reportante ? ` de ${em.reportante}` : ''}</dd></div>}
        </dl>

        <ol className="op-pasos">
          {PASOS.map((p) => (
            <li key={p.key} className={em[p.campo] ? 'hecho' : p === siguiente ? 'actual' : ''}>
              <span className="op-paso-punto" aria-hidden="true">{em[p.campo] ? <Check size={12} /> : null}</span>
              <span>{p.label}</span>
              <small>{em[p.campo] ? fmtHoraCorta(em[p.campo]) : ''}</small>
            </li>
          ))}
        </ol>

        {siguiente && (
          <div className="op-accion">
            {siguiente.key === 'traslado' && (
              <div className="field">
                <label htmlFor="op-destino">Hospital al que llevas al paciente</label>
                <select id="op-destino" className="input" value={destino} onChange={(e) => setDestino(e.target.value)}>
                  {HOSPITALES.map((h) => <option key={h}>{h}</option>)}
                </select>
              </div>
            )}
            {(siguiente.key === 'traslado' || siguiente.key === 'cierre') && (
              <div className="field">
                <label htmlFor="op-km">Km recorridos (ida y vuelta)</label>
                <input id="op-km" className="input" type="number" min="0" step="0.1" value={km} onChange={(e) => setKm(e.target.value)} placeholder="Ej. 12.5" />
              </div>
            )}
            <div className="field op-obs">
              <label htmlFor="op-obs">Observaciones (opcional)</label>
              <input id="op-obs" className="input" value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Estado del paciente, atención dada…" />
            </div>
            <div className="op-botones">
              {siguiente.key === 'traslado' && (
                <button type="button" className="btn-ghost tall" disabled={guardando} onClick={() => registrar('cierre')}>Cerrar sin traslado</button>
              )}
              <button type="button" className="btn-primary" disabled={guardando} onClick={() => registrar(siguiente.key)}>
                {guardando ? 'Guardando…' : siguiente.boton}
              </button>
            </div>
          </div>
        )}
        {error && <p className="form-error">{error}</p>}
      </section>

      {/* Ruta del IMSS 220 a la emergencia, con las rutas alternas de cada algoritmo. */}
      <RutaAmbulancia emergencia={em} />
    </>
  )
}

function MiAmbulancia({ ficha, minimo, onCambio }) {
  const a = ficha.ambulancia
  const info = ESTADO_INFO[a.estado]
  const [motivo, setMotivo] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  const cambiar = async (estado) => {
    setGuardando(true)
    setError('')
    try {
      onCambio(await estadoOperador(estado, motivo))
      setMotivo('')
    } catch (e) {
      setError(e.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="panel op-ambulancia">
      <h2 className="form-section-title titulo-icono"><Ambulance size={15} /> Mi ambulancia</h2>
      <div className="op-amb-fila">
        <div className="op-amb-placa">
          <strong>{a.placa}</strong>
          <span>{a.tipo} · {a.hospital}</span>
        </div>
        <span className="flota-chip op-chip" style={{ color: info.color, background: info.fondo }}>{a.estado}</span>
      </div>

      <Link to="/gasolina" className="op-gas">
        <Fuel size={15} aria-hidden="true" />
        <span className="barra"><span style={{ width: `${a.combustible_pct}%`, background: colorGasolina(a.combustible_pct, minimo) }} /></span>
        <b>{Math.floor(a.combustible_pct)} %</b>
        <span className="op-gas-link">{a.combustible_bajo ? 'Carga gasolina' : 'Ver gasolina'}</span>
      </Link>
      {a.combustible_bajo && <p className="gas-alerta">Tienes menos de {minimo} % de gasolina: la central no puede mandarte a emergencias hasta que cargues.</p>}

      {a.estado !== 'Ocupada' && (
        <div className="op-estatus">
          <p className="control-label"><Wrench size={12} /> ¿Algún problema con la ambulancia?</p>
          <input className="input" aria-label="Motivo" placeholder="Motivo (ej. llanta ponchada)" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          <div className="segmentado estatus-botones" role="group" aria-label="Estatus de mi ambulancia">
            {ESTADOS_MANUALES.map((e) => (
              <button key={e} type="button" className={a.estado === e ? 'on' : ''} aria-pressed={a.estado === e}
                disabled={guardando || a.estado === e} onClick={() => cambiar(e)}>{e}</button>
            ))}
          </div>
        </div>
      )}
      {error && <p className="form-error">{error}</p>}
      <p className="field-hint">Último movimiento: {ficha.historial[0] ? `${ficha.historial[0].detalle} (${fmtFecha(ficha.historial[0].created_at)})` : '—'}</p>
    </section>
  )
}
