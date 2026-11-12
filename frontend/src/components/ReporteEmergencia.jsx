import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Ambulance, Check, FileText, Hospital, Printer, Truck, UserRound } from 'lucide-react'
import LlegadaEstimada from './LlegadaEstimada.jsx'
import { LlegaATiempo, PerfilServicio, TriajeEmergencia } from './IAEmergencia.jsx'
import {
  ESTADO_INFO, HOSPITALES, confirmarAsignacion, obtenerHospitales, eventoEmergencia, fmtFecha, fmtHoraCorta, fmtLitros, planAsignacion,
  reporteEmergencia,
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
      {!cerrada && (
        <div className="ia-em-grid">
          <TriajeEmergencia emergenciaId={em.id} />
          {!em.hora_llegada && <LlegaATiempo emergenciaId={em.id} />}
          {!em.hora_llegada && <PerfilServicio emergenciaId={em.id} />}
        </div>
      )}
      {!cerrada && !em.hora_llegada && <LlegadaEstimada emergenciaId={em.id} />}
      {!cerrada && faltan > 0 && <Asignacion em={em} requeridas={rep.requeridas} asignadas={rep.ambulancias.length} onListo={() => actualizar()} />}
      {rep.ambulancias.length > 0 && !cerrada && <Pasos em={em} onListo={actualizar} />}
      <Documento rep={rep} />
    </div>
  )
}

function Asignacion({ em, requeridas, asignadas, onListo }) {
  const [cantidad, setCantidad] = useState(requeridas)
  const [plan, setPlan] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [aMano, setAMano] = useState(false)
  const [elegidas, setElegidas] = useState([])     // placas elegidas por el administrador
  const [flota, setFlota] = useState(null)

  useEffect(() => {
    let vigente = true
    setCargando(true)
    setError('')
    planAsignacion(em.id, cantidad, elegidas)
      .then((r) => { if (vigente) setPlan(r.plan) })
      .catch((e) => { if (vigente) setError(e.message) })
      .finally(() => { if (vigente) setCargando(false) })
    return () => { vigente = false }
  }, [em.id, cantidad, elegidas])

  useEffect(() => { if (aMano && !flota) obtenerHospitales().then(setFlota).catch(() => {}) }, [aMano, flota])

  const alternar = (placa) => {
    setElegidas((ps) => {
      const nuevas = ps.includes(placa) ? ps.filter((p) => p !== placa) : [...ps, placa]
      if (nuevas.length > cantidad) setCantidad(nuevas.length)
      return nuevas
    })
  }

  const confirmar = async () => {
    setCargando(true)
    setError('')
    try {
      await confirmarAsignacion(em.id, cantidad, elegidas)
      onListo()
    } catch (e) {
      setError(e.message)
      setCargando(false)
    }
  }

  return (
    <section className="panel asignacion">
      <div className="asignacion-head">
        <div>
          <h2 className="form-section-title titulo-icono"><Ambulance size={15} aria-hidden="true" /> Ambulancias para esta emergencia</h2>
          <p className="muted">Salen primero del Hospital IMSS 220; si no alcanzan, se piden a los hospitales más cercanos.</p>
        </div>
        <label className="asignacion-cantidad">
          <span>¿Cuántas se necesitan?</span>
          <span className="stepper">
            <button type="button" onClick={() => setCantidad((c) => Math.max(1, c - 1))} aria-label="Una menos">−</button>
            <input type="number" min="1" max="20" value={cantidad} onChange={(e) => setCantidad(Math.min(20, Math.max(1, Number(e.target.value) || 1)))} />
            <button type="button" onClick={() => setCantidad((c) => Math.min(20, c + 1))} aria-label="Una más">+</button>
          </span>
        </label>
      </div>

      {asignadas > 0 && <p className="field-hint">Ya tiene {asignadas}; se buscan las que faltan.</p>}
      {cargando && !plan && <p className="muted">Buscando ambulancias libres…</p>}
      {error && <p className="form-error">{error}</p>}

      {plan && (
        <>
          <p className={`asignacion-resumen${plan.usa_otros_hospitales || plan.faltan ? ' apoyo' : ''}`}>
            {plan.usa_otros_hospitales && <strong>Se necesitan apoyos de otros hospitales. </strong>}
            {plan.resumen}
          </p>
          {em.operador && <p className="field-hint">A cargo: <strong>{em.operador}</strong>. Si su ambulancia está lista, sale primero en ella.</p>}

          <button type="button" className="link asignacion-toggle" onClick={() => setAMano((v) => !v)}>
            {aMano ? 'Ocultar la lista de ambulancias' : 'Elegir las ambulancias a mano'}
          </button>
          {aMano && (
            <div className="asignacion-manual">
              {!flota && <p className="muted">Cargando ambulancias…</p>}
              {flota?.hospitales.filter((h) => h.ambulancias.length).map((h) => (
                <div key={h.id} className="am-hospital">
                  <strong>{h.nombre}</strong>
                  <div className="am-placas">
                    {h.ambulancias.map((a) => {
                      const lista = a.estado === 'Libre' && a.conductor && !a.combustible_bajo
                      const on = elegidas.includes(a.placa)
                      return (
                        <button key={a.id} type="button" className={`am-placa${on ? ' on' : ''}`} disabled={!lista}
                          aria-pressed={on} onClick={() => alternar(a.placa)}
                          title={lista ? `Conduce ${a.conductor}` : `${a.estado}${!a.conductor ? ', sin conductor' : ''}${a.combustible_bajo ? ', gasolina baja' : ''}`}>
                          <b>{a.placa}</b>
                          <span>{lista ? a.conductor : a.estado === 'Libre' ? (a.conductor ? 'gasolina baja' : 'sin conductor') : a.estado.toLowerCase()}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              ))}
              {elegidas.length > 0 && <p className="field-hint">Elegiste {elegidas.join(', ')}. Si faltan, el sistema completa con las más cercanas.</p>}
            </div>
          )}

          <ul className="asignacion-hospitales">
            {plan.por_hospital.filter((h) => h.aporta.length || h.hospital === 'Hospital IMSS 220').map((h) => (
              <li key={h.hospital}>
                <div className="ah-nombre">
                  <Hospital size={14} aria-hidden="true" />
                  <strong>{h.hospital}</strong>
                  {h.km != null && <span>{h.km} km de la emergencia</span>}
                </div>
                <div className="ah-placas">
                  {h.aporta.map((p) => {
                    const a = plan.elegidas.find((x) => x.placa === p)
                    return (
                      <span key={p} className="ah-placa">
                        <b>{p}</b> {a?.conductor}
                      </span>
                    )
                  })}
                  {h.aporta.length === 0 && <span className="muted">No aporta ambulancias</span>}
                </div>
                {h.no_disponibles.length > 0 && (
                  <p className="ah-no">No salen: {h.no_disponibles.map((n) => `${n.placa} (${n.motivo})`).join(', ')}</p>
                )}
              </li>
            ))}
          </ul>
          <div className="asignacion-acciones">
            <button type="button" className="btn-primary compact" onClick={confirmar} disabled={cargando || !plan.elegidas.length}>
              <Check size={15} /> Asignar {plan.elegidas.length} ambulancia{plan.elegidas.length === 1 ? '' : 's'}
            </button>
          </div>
        </>
      )}
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
              <dt>Doctor</dt><dd>{rep.doctor ? `${rep.doctor.nombre} · ${rep.doctor.especialidad}` : em.doctor || 'Sin doctor'}</dd>
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
