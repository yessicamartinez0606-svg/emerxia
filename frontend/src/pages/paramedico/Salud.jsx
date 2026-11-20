import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, HeartPulse, LineChart, Siren } from 'lucide-react'
import { fmtHoraCorta } from '../../lib/flota.js'
import { atencionParamedico } from '../../lib/portal.js'
import { pct } from '../../lib/clima.js'
import { usePortalParamedico } from './MiAtencion.jsx'

// «Salud»: lo clínico del paciente. Signos vitales con su rango normal, qué tan grave parece
// (modelo de triaje, práctica 05), la atención que se le dio y cómo ha evolucionado (cada
// captura queda guardada). Los rangos son de referencia para adultos en reposo.

const SIGNOS = [
  { k: 'saturacion_oxigeno', label: 'Oxigenación (SpO₂)', unidad: '%', normal: '95 a 100', ok: (v) => v >= 95, props: { min: 50, max: 100, inputMode: 'decimal' } },
  { k: 'frecuencia_cardiaca', label: 'Pulso (frecuencia cardiaca)', unidad: 'lpm', normal: '60 a 100', ok: (v) => v >= 60 && v <= 100, props: { min: 20, max: 250, inputMode: 'numeric' } },
  { k: 'escala_glasgow', label: 'Nivel de conciencia (Glasgow)', unidad: '/15', normal: '15', ok: (v) => v >= 15, props: { min: 3, max: 15, inputMode: 'numeric' } },
  { k: 'presion_arterial', label: 'Presión arterial', unidad: 'mmHg', normal: '90/60 a 139/89', texto: true, ok: (v) => {
    const [s, d] = String(v).split('/').map(Number)
    return s >= 90 && s < 140 && d >= 60 && d < 90
  } },
  { k: 'temperatura', label: 'Temperatura', unidad: '°C', normal: '36.5 a 37.5', ok: (v) => v >= 36.5 && v <= 37.5, props: { min: 30, max: 45, step: 0.1, inputMode: 'decimal' } },
  { k: 'glucosa', label: 'Glucosa', unidad: 'mg/dL', normal: '70 a 140', ok: (v) => v >= 70 && v <= 140, props: { min: 10, max: 900, inputMode: 'numeric' } },
]

const vacio = (v) => v === null || v === undefined || v === ''

export default function Salud() {
  const [datos, setDatos, error] = usePortalParamedico()
  if (error && !datos) return <p className="form-error">{error}</p>
  if (!datos) return <p className="muted">Cargando…</p>
  const em = datos.emergencia

  if (!em) {
    return (
      <section className="panel op-sin-emergencia">
        <Siren size={22} aria-hidden="true" />
        <div>
          <strong>Sin paciente por ahora</strong>
          <p>Cuando la central te mande a una emergencia, aquí anotas los signos vitales del paciente y la atención que le das.</p>
          <Link to="/atenciones">Ver mis atenciones anteriores</Link>
        </div>
      </section>
    )
  }

  return (
    <div className="op-turno">
      <header className="view-head">
        <div>
          <h1>Salud del paciente</h1>
          <p>{em.paciente_nombre}{em.paciente_edad ? `, ${em.paciente_edad} años` : ''} · {em.folio}</p>
        </div>
      </header>
      {error && <p className="form-error">{error}</p>}
      <Gravedad r={datos.triaje} />
      <FormAtencion key={em.id} em={em} onCambio={setDatos} />
      <Evolucion capturas={em.atenciones_paramedico ?? []} />
    </div>
  )
}

function Gravedad({ r }) {
  if (!r) {
    return (
      <section className="panel ia-em">
        <h2 className="form-section-title titulo-icono"><Activity size={15} /> ¿Qué tan grave está?</h2>
        <p className="muted">Anota la oxigenación, el pulso y el Glasgow: con los tres el sistema te dice si el paciente parece grave.</p>
      </section>
    )
  }
  return (
    <section className={`panel ia-em ${r.critica ? 'mal' : 'bien'}`}>
      <h2 className="form-section-title titulo-icono"><Activity size={15} /> ¿Qué tan grave está?</h2>
      <div className="ia-em-veredicto">
        <span className="ia-em-prob">{pct(r.probabilidad)}</span>
        <div>
          <b>{r.critica ? 'Parece GRAVE' : 'No parece grave'}</b>
          <span>según sus signos vitales, comparados con casos anteriores</span>
        </div>
      </div>
      <p className="field-hint">Es una ayuda, no un diagnóstico: tu valoración es la que cuenta.</p>
    </section>
  )
}

// Datos del paciente que el paramédico puede corregir en el lugar (la central los ve en la ficha).
const PACIENTE = [
  { k: 'paciente_nombre', label: 'Nombre del paciente' },
  { k: 'paciente_edad', label: 'Edad', props: { inputMode: 'numeric' } },
  { k: 'paciente_telefono', label: 'Teléfono de contacto (10 dígitos)', props: { inputMode: 'tel' } },
]
const sinNombre = (n) => !n || n.startsWith('Sin nombre')

function FormAtencion({ em, onCambio }) {
  const [f, setF] = useState(() => Object.fromEntries([...SIGNOS.map((s) => [s.k, vacio(em[s.k]) ? '' : String(em[s.k])]),
    ['observaciones', em.observaciones_paramedico ?? ''],
    ['paciente_nombre', sinNombre(em.paciente_nombre) ? '' : em.paciente_nombre],
    ['paciente_edad', em.paciente_edad ?? ''], ['paciente_sexo', em.paciente_sexo ?? 'Otro'],
    ['paciente_telefono', em.paciente_telefono ?? '']]))
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const cambia = (k) => (e) => { setF({ ...f, [k]: e.target.value }); setError(''); setAviso('') }

  const guardar = async (e) => {
    e.preventDefault()
    if (f.presion_arterial && !/^\d{2,3}\/\d{2,3}$/.test(f.presion_arterial.trim())) {
      setError('Escribe la presión como alta/baja, por ejemplo 120/80.')
      return
    }
    if (f.paciente_telefono.trim() && !/^\d{10}$/.test(f.paciente_telefono.replace(/[\s()-]/g, ''))) {
      setError('El teléfono debe tener 10 dígitos.')
      return
    }
    setGuardando(true)
    setError('')
    try {
      onCambio(await atencionParamedico({
        ...f, presion_arterial: f.presion_arterial.trim(),
        // Vacío = no se cambia (el servidor solo guarda los datos del paciente que cambiaron).
        paciente_nombre: f.paciente_nombre.trim() || null, paciente_edad: f.paciente_edad.trim() || null,
        paciente_telefono: f.paciente_telefono.trim() || null,
      }))
      setAviso('Guardado. La central ya lo ve en la emergencia.')
    } catch (err) {
      setError(err.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="panel">
      <h2 className="form-section-title titulo-icono"><HeartPulse size={15} /> Paciente, signos vitales y atención</h2>
      <form className="op-accion" onSubmit={guardar} noValidate>
        <p className="field-hint op-obs">Datos del paciente: corrígelos si ya sabes su nombre, edad o teléfono. La central los ve al momento.</p>
        {PACIENTE.map((p) => (
          <div className="field" key={p.k}>
            <label htmlFor={`pm-${p.k}`}>{p.label}</label>
            <input id={`pm-${p.k}`} className="input" value={f[p.k]} onChange={cambia(p.k)}
                   placeholder={p.k === 'paciente_nombre' && sinNombre(em.paciente_nombre) ? 'Todavía sin nombre' : ''} {...(p.props ?? {})} />
          </div>
        ))}
        <div className="field">
          <label htmlFor="pm-paciente_sexo">Sexo</label>
          <select id="pm-paciente_sexo" className="input" value={f.paciente_sexo} onChange={cambia('paciente_sexo')}>
            {['Masculino', 'Femenino', 'Otro'].map((x) => <option key={x}>{x}</option>)}
          </select>
        </div>
        <p className="field-hint op-obs">Signos vitales:</p>
        {SIGNOS.map((s) => {
          const v = f[s.k]
          const fuera = String(v).trim() && !s.ok(s.texto ? v : Number(v))
          return (
            <div className="field" key={s.k}>
              <label htmlFor={`pm-${s.k}`}>{s.label} <small className="muted">({s.unidad})</small></label>
              <input id={`pm-${s.k}`} className={`input${fuera ? ' fuera-rango' : ''}`} value={v} onChange={cambia(s.k)}
                     type={s.texto ? 'text' : 'number'} placeholder={s.texto ? '120/80' : ''} {...(s.props ?? {})} />
              <p className={`field-hint${fuera ? ' warn' : ''}`}>{fuera ? `Fuera de lo normal (normal: ${s.normal})` : `Normal: ${s.normal}`}</p>
            </div>
          )
        })}
        <div className="field op-obs">
          <label htmlFor="pm-observaciones">Atención que le diste</label>
          <textarea id="pm-observaciones" className="input" rows={3} value={f.observaciones} onChange={cambia('observaciones')}
                    placeholder="Ej. Oxígeno por puntas nasales 3 L/min, inmovilización del cuello, suero…" />
        </div>
        {error && <p className="form-error op-obs" role="alert">{error}</p>}
        {aviso && <p className="notice ok op-obs" role="status">{aviso}</p>}
        <div className="op-botones">
          <button className="btn-primary" disabled={guardando}>{guardando ? 'Guardando…' : 'Guardar'}</button>
        </div>
      </form>
      <p className="field-hint">Rangos de referencia para adultos en reposo. En niños, embarazadas y adultos mayores pueden ser distintos.</p>
    </section>
  )
}

function Evolucion({ capturas }) {
  if (!capturas.length) return null
  return (
    <section className="panel">
      <h2 className="form-section-title titulo-icono"><LineChart size={15} /> Cómo ha evolucionado</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Hora</th>{SIGNOS.map((s) => <th key={s.k}>{s.label.split(' (')[0]}</th>)}<th>Anotó</th></tr>
          </thead>
          <tbody>
            {[...capturas].reverse().map((c, i) => (
              <tr key={i}>
                <td>{fmtHoraCorta(c.momento)}</td>
                {SIGNOS.map((s) => {
                  const v = c[s.k]
                  const fuera = !vacio(v) && !s.ok(s.texto ? v : Number(v))
                  return <td key={s.k} className={fuera ? 'fuera-rango-celda' : ''}>{vacio(v) ? '—' : `${v}`}</td>
                })}
                <td>{c.paramedico}{c.observaciones ? <span className="rd-sub-celda">{c.observaciones}</span> : null}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
