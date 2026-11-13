import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, Clock, Compass, FileText, Printer, RefreshCw, Truck, UserRound } from 'lucide-react'
import LlegadaEstimada from './LlegadaEstimada.jsx'
import { LlegaATiempo, PerfilServicio, TriajeEmergencia } from './IAEmergencia.jsx'
import {
  ESTADO_INFO, HOSPITALES, eventoEmergencia, fmtFecha, fmtHoraCorta, fmtLitros, reintentarAsignacion, reporteEmergencia,
} from '../lib/flota.js'

// Reporte de la emergencia: qué ambulancias van (de qué hospital y quién las maneja),
// los pasos de la atención y un reporte listo para imprimir.

const PASOS = [
  { key: 'registrada', label: 'Registrada', campo: 'created_at' },
  { key: 'asignada', label: 'Ambulancias asignadas', campo: 'asignada_en' },
  { key: 'salida', label: 'Salida', campo: 'hora_salida' },
  { key: 'llegada', label: 'Llegada al lugar', campo: 'hora_llegada' },
  { key: 'traslado', label: 'Traslado a hospital', campo: 'hora_traslado' },
  { key: 'cierre', label: 'Cerrada', campo: 'hora_cierre' },
]

function duracion(desde, hasta) {
  if (!desde || !hasta) return null
  const min = Math.round((new Date(hasta) - new Date(desde)) / 60000)
  if (Number.isNaN(min) || min < 0) return null
  return min < 60 ? `${min} min` : `${Math.floor(min / 60)} h ${min % 60} min`
}

export default function ReporteEmergencia({ emergencia, onCambio }) {
  const [rep, setRep] = useState(null)
  const [error, setError] = useState('')

  const cargar = () => reporteEmergencia(emergencia.id).then((r) => { setRep(r); setError('') }).catch((e) => setError(e.message))
  useEffect(() => { cargar() }, [emergencia.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const actualizar = (r) => { if (r) setRep(r); else cargar(); onCambio?.() }

  if (error && !rep) return <p className="form-error">No se pudo cargar el reporte: {error}</p>
  if (!rep) return <div className="panel muted pad">Cargando reporte…</div>

  const em = rep.emergencia
  const cerrada = em.estado === 'Cerrada'
  const faltan = rep.requeridas - rep.ambulancias.length

  return (
    <div className="reporte">
      {/* Asistente de despacho: mientras la ambulancia va en camino (registrada y sin llegar). */}
      {!cerrada && !em.hora_llegada && (
        <section className="asistente-em">
          <header className="asistente-em-head">
            <div>
              <h2><Compass size={17} aria-hidden="true" /> Asistente de despacho</h2>
              <p>Estimaciones para esta emergencia mientras la ambulancia va en camino.</p>
            </div>
            <Link to={`/asistente?emergencia=${em.id}`} className="btn-ghost tall">Abrir asistente completo</Link>
          </header>
          <div className="ia-em-grid">
            <TriajeEmergencia emergenciaId={em.id} />
            <LlegaATiempo emergenciaId={em.id} />
            <PerfilServicio emergenciaId={em.id} />
          </div>
          <LlegadaEstimada emergenciaId={em.id} />
        </section>
      )}
      {!cerrada && faltan > 0 && <EnEspera em={em} faltan={faltan} asignadas={rep.ambulancias.length} onListo={actualizar} />}
      {rep.ambulancias.length > 0 && !cerrada && <Pasos em={em} onListo={actualizar} />}
      <Documento rep={rep} />
    </div>
  )
}

// Las ambulancias se asignan solas al guardar la emergencia (backend: asignar_automatico).
// Este aviso solo aparece si faltan: la emergencia está en espera y se completa sola en cuanto
// se libera una ambulancia; también se puede volver a buscar a mano.
function EnEspera({ em, faltan, asignadas, onListo }) {
  const [buscando, setBuscando] = useState(false)
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')

  const buscar = async () => {
    setBuscando(true)
    setError('')
    try {
      const r = await reintentarAsignacion(em.id)
      setMensaje(r.mensaje)
      onListo(r.reporte)
    } catch (e) {
      setError(e.message)
    } finally {
      setBuscando(false)
    }
  }

  return (
    <section className="panel asignacion espera">
      <div className="asignacion-head">
        <div>
          <h2 className="form-section-title titulo-icono"><Clock size={15} aria-hidden="true" /> {asignadas ? `Falta${faltan === 1 ? '' : 'n'} ${faltan} ambulancia${faltan === 1 ? '' : 's'}` : 'En espera de ambulancia'}</h2>
          <p className="muted">
            No hay ambulancias libres con conductor y gasolina suficiente{asignadas ? ' para completar las que necesita' : ''}.
            Se asignará sola en cuanto se libere una (al cerrar otra emergencia, al cambiar el estatus de una ambulancia o al cargar gasolina);
            las de prioridad Alta y las críticas van primero.
          </p>
        </div>
        <button type="button" className="btn-ghost tall" onClick={buscar} disabled={buscando}>
          <RefreshCw size={15} className={buscando ? 'girando' : ''} /> {buscando ? 'Buscando…' : 'Buscar otra vez'}
        </button>
      </div>
      {mensaje && <p className="asignacion-resumen apoyo">{mensaje}</p>}
      {error && <p className="form-error">{error}</p>}
    </section>
  )
}

function Pasos({ em, onListo }) {
  const hecho = (p) => Boolean(em[p.campo])
  const siguiente = PASOS.find((p) => !hecho(p) && p.key !== 'registrada' && p.key !== 'asignada')
  const [km, setKm] = useState('')
  const [obs, setObs] = useState('')
  const [destino, setDestino] = useState('Hospital IMSS 220')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  const registrar = async (tipo) => {
    setGuardando(true)
    setError('')
    try {
      const r = await eventoEmergencia(em.id, {
        tipo, observaciones: obs,
        ...(tipo === 'cierre' ? { km_recorridos: Number(km) || 0 } : {}),
        ...(tipo === 'traslado' ? { hospital_destino: destino } : {}),
      })
      setObs('')
      setKm('')
      onListo(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="panel pasos-em">
      <h2 className="form-section-title titulo-icono"><Truck size={15} aria-hidden="true" /> Seguimiento</h2>
      <ol className="pasos-linea">
        {PASOS.map((p) => (
          <li key={p.key} className={hecho(p) ? 'hecho' : p === siguiente ? 'actual' : ''}>
            <span className="pl-punto" aria-hidden="true">{hecho(p) ? <Check size={12} /> : null}</span>
            <strong>{p.label}</strong>
            <span>{hecho(p) ? fmtHoraCorta(em[p.campo]) : '—'}</span>
          </li>
        ))}
      </ol>

      {siguiente && (
        <div className="pasos-accion">
          {siguiente.key === 'traslado' && (
            <div className="field">
              <label htmlFor="em-destino">Hospital al que llega el paciente</label>
              <select id="em-destino" className="input" value={destino} onChange={(e) => setDestino(e.target.value)}>
                {HOSPITALES.map((h) => <option key={h}>{h}</option>)}
              </select>
            </div>
          )}
          {(siguiente.key === 'cierre' || siguiente.key === 'traslado') && (
            <div className="field">
              <label htmlFor="em-km">Kilómetros recorridos por cada ambulancia</label>
              <input id="em-km" className="input" type="number" min="0" step="0.1" value={km} onChange={(e) => setKm(e.target.value)} placeholder="Ej. 12.5" />
            </div>
          )}
          <div className="field pasos-obs">
            <label htmlFor="em-obs">Observaciones (opcional)</label>
            <input id="em-obs" className="input" value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Estado del paciente, atención dada…" />
          </div>
          <div className="pasos-botones">
            {siguiente.key === 'traslado' ? (
              <button type="button" className="btn-ghost" disabled={guardando} onClick={() => registrar('cierre')}>Cerrar sin traslado</button>
            ) : null}
            <button type="button" className="btn-primary compact" disabled={guardando} onClick={() => registrar(siguiente.key)}>
              {{ salida: 'Registrar salida', llegada: 'Registrar llegada', traslado: 'Registrar traslado', cierre: 'Cerrar emergencia' }[siguiente.key]}
            </button>
          </div>
          {(siguiente.key === 'cierre' || siguiente.key === 'traslado') && <p className="field-hint">Al cerrar, las ambulancias quedan libres y se descuenta su gasolina según los km.</p>}
        </div>
      )}
      {error && <p className="form-error">{error}</p>}
    </section>
  )
}

function Documento({ rep }) {
  const em = rep.emergencia
  const total = duracion(em.created_at, em.hora_cierre)
  const respuesta = duracion(em.created_at, em.hora_llegada)
  return (
      <section className="panel reporte-doc" aria-label={`Reporte de la emergencia ${em.folio}`}>
        <header className="rd-head">
          <div>
            <span className="rd-eyebrow"><FileText size={13} aria-hidden="true" /> Reporte de emergencia</span>
            <h2>{em.folio}</h2>
            <p>{fmtFecha(em.created_at)}</p>
          </div>
          <div className="rd-badges">
            <span className={`badge b-${(em.estado || '').toLowerCase().replace(/\s+/g, '-')}`}>{em.estado}</span>
            <span className={`badge b-${(em.prioridad || '').toLowerCase()}`}>Prioridad {em.prioridad}</span>
            <button type="button" className="btn-ghost no-print" onClick={() => window.print()}><Printer size={14} /> Imprimir</button>
          </div>
        </header>

        <div className="rd-grid">
          <div className="rd-bloque">
            <h3>Paciente</h3>
            <dl>
              <dt>Nombre</dt><dd>{em.paciente_nombre || '—'}</dd>
              <dt>Edad / sexo</dt><dd>{[em.paciente_edad && `${em.paciente_edad} años`, em.paciente_sexo].filter(Boolean).join(' · ') || '—'}</dd>
              <dt>Teléfono</dt><dd>{em.paciente_telefono || '—'}</dd>
            </dl>
          </div>
          <div className="rd-bloque">
            <h3>Emergencia</h3>
            <dl>
              <dt>Qué pasó</dt><dd>{em.descripcion}</dd>
              <dt>Dirección</dt><dd>{em.direccion}</dd>
              <dt>Ambulancias</dt><dd>{rep.ambulancias.length} de {rep.requeridas} necesarias</dd>
            </dl>
          </div>
          <div className="rd-bloque">
            <h3>Personal</h3>
            <dl>
              <dt>Operador a cargo</dt><dd>{rep.operador ? `${rep.operador.nombre}${rep.operador.celular ? ` · ${rep.operador.celular}` : ''}` : em.operador || 'Sin asignar'}</dd>
              <dt>Face ID</dt><dd>{rep.verificaciones.length ? `${rep.verificaciones.filter((v) => v.coincide).length} verificación(es) correctas` : 'Sin verificaciones'}</dd>
            </dl>
          </div>
          <div className="rd-bloque">
            <h3>Tiempos y recorrido</h3>
            <dl>
              <dt>Llegada al lugar</dt><dd>{respuesta ? `${respuesta} después del reporte` : '—'}</dd>
              <dt>Duración total</dt><dd>{total ?? (em.estado === 'Cerrada' ? '—' : 'En atención')}</dd>
              <dt>Recorrido</dt><dd>{em.km_recorridos != null ? `${em.km_recorridos} km · ${fmtLitros(em.litros_consumidos)} de gasolina` : '—'}</dd>
              <dt>Hospital destino</dt><dd>{em.hospital_destino || '—'}</dd>
            </dl>
          </div>
        </div>

        <h3 className="rd-sub">Ambulancias y conductores</h3>
        {rep.ambulancias.length === 0 ? (
          <p className="muted">Todavía no hay ambulancias asignadas.</p>
        ) : (
          <div className="table-wrap rd-tabla">
            <table>
              <thead><tr><th>Ambulancia</th><th>Sale de</th><th>Conductor</th><th>Contacto</th><th>Estatus</th><th>Gasolina</th></tr></thead>
              <tbody>
                {rep.ambulancias.map((a) => {
                  const c = a.conductor_info
                  const info = ESTADO_INFO[a.estado]
                  return (
                    <tr key={a.id}>
                      <td><Link to={`/ambulancias/${a.id}`}><strong>{a.placa}</strong></Link><span className="rd-sub-celda">{a.tipo}</span></td>
                      <td>{a.hospital}</td>
                      <td>
                        <span className="rd-conductor"><UserRound size={13} aria-hidden="true" />{c ? <Link to={`/operadores/${c.id}`}>{c.nombre}</Link> : a.conductor || '—'}</span>
                        {c && <span className="rd-sub-celda">Turno {c.turno}</span>}
                      </td>
                      <td>{c?.celular || '—'}{c?.extension ? <span className="rd-sub-celda">ext. {c.extension}</span> : null}</td>
                      <td><span className="flota-chip" style={{ color: info.color, background: info.fondo }}>{a.estado}</span></td>
                      <td>{Math.floor(a.combustible_pct)} %</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {em.observaciones && (
          <>
            <h3 className="rd-sub">Observaciones</h3>
            <p className="rd-obs">{em.observaciones}</p>
          </>
        )}

        <h3 className="rd-sub">Línea de tiempo</h3>
        {rep.linea_tiempo.length === 0 ? <p className="muted">Sin movimientos todavía.</p> : (
          <ol className="rd-tiempo">
            {rep.linea_tiempo.map((h) => (
              <li key={h.id}><span>{fmtHoraCorta(h.created_at)}</span>{h.detalle}</li>
            ))}
          </ol>
        )}
        <p className="rd-pie">Generado por Emergexia · {fmtFecha(new Date())}</p>
      </section>
  )
}
