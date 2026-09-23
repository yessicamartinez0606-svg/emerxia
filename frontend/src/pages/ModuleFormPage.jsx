import { useState } from 'react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Camera, CheckCircle2, X } from 'lucide-react'
import { api } from '../lib/api.js'
import { findModule } from '../lib/modules.js'
import { emptyForm, useSourcedOptions } from '../lib/moduleHelpers.js'
import FaceCapture from '../components/FaceCapture.jsx'

const OLD_BACKEND =
  'El servidor no confirmó que guardó en MongoDB: seguramente hay una versión ANTIGUA del backend corriendo en el puerto 8000. ' +
  'Ciérrala (python diagnostico.py te dice cuál) y vuelve a iniciar el backend.'

// Etiqueta legible del módulo dueño de una colección referenciada por `source`
// (p. ej. "doctores" → "Doctores"), para armar mensajes genéricos sin
// hardcodear qué módulos existen.
const sourceLabel = (src) => findModule(src)?.label ?? src

// Agrupa los campos del módulo respetando su orden, usando `group` cuando
// existe (p. ej. Emergencias: Paciente / Emergencia / Asignación).
function groupFields(fields) {
  const groups = []
  fields.forEach((f) => {
    const name = f.group ?? null
    let bucket = groups.find((b) => b.name === name)
    if (!bucket) {
      bucket = { name, fields: [] }
      groups.push(bucket)
    }
    bucket.fields.push(f)
  })
  return groups
}

export default function ModuleFormPage() {
  const { module: key } = useParams()
  const mod = findModule(key)
  if (!mod || mod.custom) return <Navigate to="/" replace />
  return <FormView key={key} mod={mod} />
}

function FormView({ mod }) {
  const navigate = useNavigate()
  const [form, setForm] = useState(() => emptyForm(mod.fields))
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const { options: sourcedOptions, loading: sourcedLoading } = useSourcedOptions(mod.fields)

  // Verificación por reconocimiento facial: modal de cámara abierto y, por
  // cada campo que la requiere (operador, doctor…), qué valor quedó
  // verificado en este formulario (se reinicia si cambia la selección).
  const [faceModal, setFaceModal] = useState(null)
  const [verifiedFields, setVerifiedFields] = useState({})

  const logVerification = (persona, contexto, result) => {
    api('/verificaciones', {
      method: 'POST',
      body: {
        operador: persona,
        contexto,
        coincide: result?.match ?? true,
        distancia: result?.distance ?? null,
      },
    }).catch(() => {}) // el registro de auditoría no debe bloquear el flujo si falla
  }

  const openPhotoCapture = (f) => {
    setFaceModal({
      mode: 'register',
      title: `Foto de referencia · ${f.label}`,
      reference: null,
      onSuccess: (photo) => {
        setForm((prev) => ({ ...prev, [f.key]: photo }))
        setFaceModal(null)
      },
      onCancel: () => setFaceModal(null),
    })
  }

  const handleSourcedChange = (f, value) => {
    if (!f.requireFaceVerification || !value) {
      setForm({ ...form, [f.key]: value })
      if (f.requireFaceVerification && !value) {
        setVerifiedFields((prev) => ({ ...prev, [f.key]: null }))
      }
      return
    }
    const row = sourcedOptions[f.key]?.find((o) => o.value === value)
    const foto = row?.raw?.foto
    if (!foto) {
      setFormError(`"${value}" no tiene foto de referencia registrada. Agrégala en el módulo de ${sourceLabel(f.source)} antes de asignarlo.`)
      return
    }
    setFormError('')
    setFaceModal({
      mode: 'verify',
      title: `Verificar identidad · ${value}`,
      reference: foto,
      onSuccess: () => {
        setForm((prev) => ({ ...prev, [f.key]: value }))
        setVerifiedFields((prev) => ({ ...prev, [f.key]: value }))
        logVerification(value, 'asignacion', { match: true })
        setFaceModal(null)
      },
      onCancel: () => setFaceModal(null),
    })
  }

  const doSave = async () => {
    setSaving(true)
    try {
      const body = { ...form }
      if (body.ambulancia === '') body.ambulancia = null
      if (body.operador === '') body.operador = null
      if (body.doctor === '') body.doctor = null
      const saved = await api(`/${mod.key}`, { method: 'POST', body })
      if (!saved.saved_in) {
        setFormError(OLD_BACKEND)
        setSaving(false)
        return
      }
      const done = mod.nuevo === 'Nueva' ? 'guardada' : 'guardado'
      const name = mod.singular.charAt(0).toUpperCase() + mod.singular.slice(1)
      navigate(`/${mod.key}`, {
        state: { notice: { kind: 'ok', text: `✓ ${name} ${done} en MongoDB (${saved.saved_in}), id ${saved.id}.` } },
      })
    } catch (err) {
      setFormError(err.message)
      setSaving(false)
    }
  }

  const save = async (e) => {
    e.preventDefault()
    setFormError('')

    const missingPhoto = mod.fields.find((f) => f.type === 'photo' && f.required && !form[f.key])
    if (missingPhoto) {
      setFormError(`Falta tomar la foto: "${missingPhoto.label}".`)
      return
    }

    // Formato de campos como correo/celular: se avisa aquí mismo, sin esperar a que
    // el servidor lo rechace. Los campos vacíos y no obligatorios se dejan pasar.
    for (const f of mod.fields) {
      if (!f.pattern) continue
      const raw = (form[f.key] ?? '').trim()
      if (!raw) continue
      const value = f.pattern.normalize ? f.pattern.normalize(raw) : raw
      if (!f.pattern.re.test(value)) {
        setFormError(f.pattern.message)
        return
      }
    }

    // Salida de la ambulancia: si la emergencia queda "En curso" con un
    // operador asignado, se vuelve a verificar su identidad justo antes de
    // guardar, aunque ya se haya verificado al asignarlo.
    if (mod.key === 'emergencias' && form.estado === 'En curso' && form.operador) {
      const row = sourcedOptions.operador?.find((o) => o.value === form.operador)
      const foto = row?.raw?.foto
      if (!foto) {
        setFormError(`"${form.operador}" no tiene foto de referencia; no se puede confirmar la salida de la ambulancia.`)
        return
      }
      setFaceModal({
        mode: 'verify',
        title: `Confirmar salida de la ambulancia · ${form.operador}`,
        reference: foto,
        onSuccess: () => {
          logVerification(form.operador, 'salida', { match: true })
          setFaceModal(null)
          doSave()
        },
        onCancel: () => setFaceModal(null),
      })
      return
    }

    await doSave()
  }

  const groups = groupFields(mod.fields)
  const Icon = mod.icon

  return (
    <section className="record-screen">
      <header className="record-screen-head">
        <Link to={`/${mod.key}`} className="btn-back" aria-label="Volver a la lista">
          <ArrowLeft size={18} />
        </Link>
        <span className="record-screen-icon"><Icon size={22} strokeWidth={1.8} /></span>
        <div className="record-screen-title">
          <span className="record-screen-eyebrow">{mod.label}</span>
          <h1>{mod.nuevo} {mod.singular}</h1>
          <p>{mod.description}</p>
        </div>
      </header>

      <form className="record-form" onSubmit={save}>
        {groups.map((g, gi) => (
          <div className="panel form-section" key={g.name ?? `grupo-${gi}`}>
            {g.name && <h2 className="form-section-title">{g.name}</h2>}
            <div className="form-grid">
              {g.fields.map((f) => {
                const list = sourcedOptions[f.key]
                const isLoading = f.source && sourcedLoading[f.key] && list === undefined

                return (
                  <div className="field" key={f.key}>
                    <label htmlFor={f.key}>{f.label}</label>
                    {f.type === 'photo' ? (
                      <div className="photo-field">
                        {form[f.key] && <img className="photo-thumb" src={form[f.key]} alt="" />}
                        <button type="button" className="btn-ghost compact" onClick={() => openPhotoCapture(f)}>
                          <Camera size={15} /> {form[f.key] ? 'Repetir foto' : 'Tomar foto'}
                        </button>
                      </div>
                    ) : f.type === 'date' ? (
                      <input id={f.key} type="date" className="input" value={form[f.key]} required={f.required}
                             onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} />
                    ) : f.source ? (
                      <select id={f.key} className="input" value={form[f.key]} required={f.required}
                              disabled={isLoading}
                              onChange={(e) => handleSourcedChange(f, e.target.value)}>
                        {(f.allowEmpty || !form[f.key]) && (
                          <option value="">{isLoading ? 'Cargando…' : (f.emptyLabel ?? 'Selecciona una opción')}</option>
                        )}
                        {list?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    ) : f.options ? (
                      <select id={f.key} className="input" value={form[f.key]}
                              onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}>
                        {f.options.map((o) => <option key={o}>{o}</option>)}
                      </select>
                    ) : (
                      <input id={f.key} className="input" type={f.type || 'text'} value={form[f.key]} required={f.required}
                             onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} />
                    )}
                    {f.pattern && <p className="field-hint">{f.type === 'tel' ? 'Solo números, 10 dígitos.' : 'Debe verse como un correo real.'}</p>}
                    {f.source && list && list.length === 0 && (
                      <p className="field-hint">
                        No hay {sourceLabel(f.source).toLowerCase()} registrados todavía —
                        agrega uno primero en el módulo de {sourceLabel(f.source)}.
                      </p>
                    )}
                    {f.source && list === null && (
                      <p className="field-hint warn">No se pudo cargar la lista de {sourceLabel(f.source).toLowerCase()}.</p>
                    )}
                    {f.requireFaceVerification && form[f.key] && verifiedFields[f.key] === form[f.key] && (
                      <p className="field-hint ok"><CheckCircle2 size={13} /> Identidad verificada por reconocimiento facial.</p>
                    )}
                    {f.type === 'photo' && f.hint && (
                      <p className="field-hint">{f.hint}</p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ))}

        <div className="record-form-actions">
          {formError && <p className="form-error wide">{formError}</p>}
          <div className="record-form-actions-row">
            <Link to={`/${mod.key}`} className="btn-ghost tall"><X size={15} /> Cancelar</Link>
            <button className="btn-primary compact" disabled={saving}>
              {saving ? 'Guardando…' : `Guardar ${mod.singular}`}
            </button>
          </div>
        </div>
      </form>

      <FaceCapture
        open={!!faceModal}
        title={faceModal?.title}
        mode={faceModal?.mode}
        reference={faceModal?.reference}
        onSuccess={faceModal?.onSuccess}
        onCancel={faceModal?.onCancel}
      />
    </section>
  )
}
