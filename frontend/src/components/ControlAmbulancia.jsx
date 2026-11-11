import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, Fuel, Gauge, History, ScanFace, UserRound, Wrench } from 'lucide-react'
import { api } from '../lib/api.js'
import {
  ESTADOS_MANUALES, ESTADO_INFO, HOSPITALES, TIPO_HISTORIAL, cambiarAmbulancia, cargarCombustible, colorGasolina,
  fichaAmbulancia, fmtDinero, fmtFecha, fmtLitros,
} from '../lib/flota.js'
import FaceCapture from './FaceCapture.jsx'

// Ficha de control de una ambulancia: estatus, hospital, conductor (un operador), gasolina
// con las cargas que registra su conductor, e historial.

const CARGA_VACIA = { litros: '', costo: '', kilometraje: '', estacion: '', notas: '' }

export default function ControlAmbulancia({ id, onCambio }) {
  const [ficha, setFicha] = useState(null)
  const [error, setError] = useState('')
  const [operadores, setOperadores] = useState([])

  const cargar = () => fichaAmbulancia(id).then((f) => { setFicha(f); setError('') }).catch((e) => setError(e.message))
  useEffect(() => { cargar() }, [id]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { api('/operadores').then((d) => setOperadores(d.items ?? [])).catch(() => {}) }, [])

  const actualizar = (f) => { setFicha(f); onCambio?.() }

  if (error && !ficha) return <p className="form-error">{error}</p>
  if (!ficha) return <div className="panel muted pad">Cargando control de la ambulancia…</div>

  return (
    <div className="control-amb">
      <div className="control-amb-top">
        <Estatus ficha={ficha} onGuardado={actualizar} operadores={operadores} />
        <Gasolina ficha={ficha} onGuardado={actualizar} />
      </div>
      <Cargas ficha={ficha} />
      <Historial filas={ficha.historial} />
    </div>
  )
}

function Estatus({ ficha, onGuardado, operadores }) {
  const a = ficha.ambulancia
  const [motivo, setMotivo] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const info = ESTADO_INFO[a.estado]

  const guardar = async (cambios) => {
    setGuardando(true)
    setError('')
    try {
      onGuardado(await cambiarAmbulancia(a.id, { ...cambios, motivo }))
      setMotivo('')
    } catch (e) {
      setError(e.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="panel control-card">
      <h2 className="form-section-title titulo-icono"><Wrench size={15} aria-hidden="true" /> Estatus y asignación</h2>

      <div className="estatus-actual" style={{ '--c': info.color, '--f': info.fondo }}>
        <span className="punto" aria-hidden="true" />
        <div>
          <strong>{a.estado}</strong>
          <span>
            {a.estado === 'Ocupada' && ficha.emergencia
              ? <>Atendiendo <Link to={`/emergencias/${ficha.emergencia.id}`}>{ficha.emergencia.folio}</Link></>
              : info.texto}
          </span>
        </div>
      </div>

      {a.estado !== 'Ocupada' ? (
        <>
          <p className="control-label">Cambiar estatus</p>
          <div className="segmentado estatus-botones" role="group" aria-label="Estatus">
            {ESTADOS_MANUALES.map((e) => (
              <button key={e} type="button" className={a.estado === e ? 'on' : ''} aria-pressed={a.estado === e}
                disabled={guardando || a.estado === e} onClick={() => guardar({ estado: e })}>
                {e}
              </button>
            ))}
          </div>
          <label className="control-label" htmlFor="amb-motivo">Motivo (queda en el historial)</label>
          <input id="amb-motivo" className="input" placeholder="Ej. cambio de frenos, sin verificación…" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
        </>
      ) : (
        <p className="field-hint">Se libera sola al cerrar la emergencia en su reporte.</p>
      )}

      <div className="control-dos">
        <div className="field">
          <label htmlFor="amb-hospital">Hospital</label>
          <select id="amb-hospital" className="input" value={a.hospital} disabled={guardando || a.estado === 'Ocupada'}
            onChange={(e) => guardar({ hospital: e.target.value })}>
            {HOSPITALES.map((h) => <option key={h}>{h}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="amb-conductor">Conductor (operador)</label>
          <select id="amb-conductor" className="input" value={a.conductor} disabled={guardando}
            onChange={(e) => guardar({ conductor: e.target.value })}>
            <option value="">Sin conductor</option>
            {operadores.map((o) => <option key={o.id} value={o.nombre}>{o.nombre} · turno {o.turno}</option>)}
          </select>
        </div>
      </div>
      {ficha.conductor && (
        <div className="conductor-card">
          {ficha.conductor_foto ? <img src={ficha.conductor_foto} alt="" /> : <span className="avatar"><UserRound size={16} /></span>}
          <div>
            <Link to={`/operadores/${ficha.conductor.id}`}><strong>{ficha.conductor.nombre}</strong></Link>
            <span>Turno {ficha.conductor.turno}{ficha.conductor.celular ? ` · ${ficha.conductor.celular}` : ''}{ficha.conductor.extension ? ` · ext. ${ficha.conductor.extension}` : ''}</span>
          </div>
          <span className={`badge b-${ficha.conductor.estado === 'En línea' ? 'en-linea' : 'desconectado'}`}>{ficha.conductor.estado}</span>
        </div>
      )}
      {error && <p className="form-error">{error}</p>}
    </section>
  )
}

function Gasolina({ ficha, onGuardado }) {
  const a = ficha.ambulancia
  const [form, setForm] = useState(CARGA_VACIA)
  const [verificado, setVerificado] = useState(false)
  const [camara, setCamara] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')

  const litros = (a.combustible_pct / 100) * a.tanque_litros
  const autonomia = litros * a.rendimiento_km_l
  const faltan = a.tanque_litros - litros
  const color = colorGasolina(a.combustible_pct, ficha.combustible_minimo)
  const num = (v) => (v === '' ? null : Number(v))

  const enviar = async (e) => {
    e.preventDefault()
    setGuardando(true)
    setError('')
    setAviso('')
    try {
      const f = await cargarCombustible(a.id, {
        operador: a.conductor, litros: Number(form.litros), costo: num(form.costo), kilometraje: num(form.kilometraje),
        estacion: form.estacion, notas: form.notas, verificado_facial: verificado,
      })
      setForm(CARGA_VACIA)
      setVerificado(false)
      setAviso(`Carga registrada: ${fmtLitros(form.litros)}. Ahora tiene ${Math.floor(f.ambulancia.combustible_pct)} %.`)
      onGuardado(f)
    } catch (err) {
      setError(err.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="panel control-card">
      <h2 className="form-section-title titulo-icono"><Fuel size={15} aria-hidden="true" /> Gasolina</h2>
      <div className="gas-medidor">
        <div className="gas-tanque" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={a.combustible_pct} aria-label="Nivel de gasolina">
          <span style={{ height: `${a.combustible_pct}%`, background: color }} />
          <b>{Math.floor(a.combustible_pct)}%</b>
        </div>
        <dl className="gas-datos">
          <dt>En el tanque</dt><dd>{fmtLitros(litros)} de {fmtLitros(a.tanque_litros)}</dd>
          <dt>Alcanza para</dt><dd>~{Math.round(autonomia)} km</dd>
          <dt>Rendimiento</dt><dd>{a.rendimiento_km_l} km/L</dd>
          <dt>Kilometraje</dt><dd>{a.kilometraje.toLocaleString('es-MX')} km</dd>
        </dl>
      </div>
      {a.combustible_bajo && (
        <p className="gas-alerta">Gasolina baja: con menos de {ficha.combustible_minimo} % no se manda a emergencias.</p>
      )}

      <form className="gas-form" onSubmit={enviar}>
        <p className="control-label">Registrar carga {a.conductor ? <>· la registra <strong>{a.conductor}</strong></> : ''}</p>
        {!a.conductor ? (
          <p className="field-hint warn">Asígnale un conductor para poder registrar gasolina.</p>
        ) : (
          <>
            <div className="gas-campos">
              <div className="field">
                <label htmlFor="gas-litros">Litros *</label>
                <input id="gas-litros" className="input" type="number" min="0.1" step="0.1" max={Math.ceil(faltan)} required
                  value={form.litros} onChange={(e) => setForm({ ...form, litros: e.target.value })} placeholder={`Máx. ${faltan.toFixed(0)}`} />
              </div>
              <div className="field">
                <label htmlFor="gas-costo">Costo ($)</label>
                <input id="gas-costo" className="input" type="number" min="0" step="0.01" value={form.costo} onChange={(e) => setForm({ ...form, costo: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="gas-km">Kilometraje</label>
                <input id="gas-km" className="input" type="number" min={a.kilometraje} step="1" value={form.kilometraje}
                  placeholder={String(a.kilometraje)} onChange={(e) => setForm({ ...form, kilometraje: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="gas-estacion">Gasolinera</label>
                <input id="gas-estacion" className="input" value={form.estacion} onChange={(e) => setForm({ ...form, estacion: e.target.value })} />
              </div>
            </div>
            <div className="gas-acciones">
              {verificado ? (
                <span className="field-hint ok"><CheckCircle2 size={13} /> {a.conductor} verificado con Face ID</span>
              ) : (
                <button type="button" className="btn-ghost" onClick={() => setCamara(true)} disabled={!ficha.conductor_foto}
                  title={ficha.conductor_foto ? '' : 'El conductor no tiene foto de referencia'}>
                  <ScanFace size={15} /> Confirmar con Face ID
                </button>
              )}
              <button className="btn-primary compact" disabled={guardando || !form.litros}>
                {guardando ? 'Guardando…' : 'Registrar carga'}
              </button>
            </div>
          </>
        )}
        {error && <p className="form-error">{error}</p>}
        {aviso && <p className="field-hint ok">{aviso}</p>}
      </form>

      <FaceCapture
        open={camara}
        mode="verify"
        title={`Carga de gasolina · ${a.placa}`}
        reference={ficha.conductor_foto}
        onSuccess={(_foto, r) => {
          setCamara(false)
          setVerificado(r?.match !== false)
          if (r?.match === false) setError(`El rostro no coincide con ${a.conductor}.`)
          api('/verificaciones', { method: 'POST', body: { operador: a.conductor, contexto: 'salida', coincide: r?.match ?? true, distancia: r?.distance ?? null } }).catch(() => {})
        }}
        onCancel={() => setCamara(false)}
      />
    </section>
  )
}

function Cargas({ ficha }) {
  if (!ficha.cargas.length) return null
  return (
    <section className="panel">
      <h2 className="form-section-title titulo-icono">
        <Gauge size={15} aria-hidden="true" /> Cargas de gasolina
        <span className="control-totales">{fmtLitros(ficha.litros_cargados)} · {fmtDinero(ficha.gasto_total)}</span>
      </h2>
      <div className="table-wrap control-tabla">
        <table>
          <thead><tr><th>Fecha</th><th>Conductor</th><th>Litros</th><th>Nivel</th><th>Costo</th><th>Km</th><th>Gasolinera</th></tr></thead>
          <tbody>
            {ficha.cargas.map((c) => (
              <tr key={c.id}>
                <td>{fmtFecha(c.created_at)}</td>
                <td>{c.operador}{c.verificado_facial && <CheckCircle2 size={13} className="ok-icon" aria-label="Verificado con Face ID" />}</td>
                <td>{fmtLitros(c.litros)}</td>
                <td>{Math.floor(c.combustible_antes)} % → {Math.floor(c.combustible_despues)} %</td>
                <td>{fmtDinero(c.costo)}</td>
                <td>{c.kilometraje != null ? c.kilometraje.toLocaleString('es-MX') : '—'}</td>
                <td>{c.estacion || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export function Historial({ filas, titulo = 'Historial', vacio = 'Todavía no hay movimientos.' }) {
  return (
    <section className="panel">
      <h2 className="form-section-title titulo-icono"><History size={15} aria-hidden="true" /> {titulo}</h2>
      {!filas?.length && <p className="muted">{vacio}</p>}
      <ol className="historial">
        {filas?.map((h) => (
          <li key={h.id} className={`h-${h.tipo}`}>
            <span className="h-punto" aria-hidden="true" />
            <div>
              <span className="h-tipo">{TIPO_HISTORIAL[h.tipo] ?? h.tipo}</span>
              <p>{h.detalle}</p>
              <span className="h-meta">{fmtFecha(h.created_at)}{h.usuario ? ` · registró ${h.usuario}` : ''}</span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
