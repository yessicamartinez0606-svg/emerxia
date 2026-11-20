import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Camera, CheckCircle2, X } from 'lucide-react'
import { api } from '../lib/api.js'
import { findModule } from '../lib/modules.js'
import { emptyForm, useSourcedOptions } from '../lib/moduleHelpers.js'
import FaceCapture from '../components/FaceCapture.jsx'
import PanelLogica from '../components/PanelLogica.jsx'
import PanelTriageML from '../components/PanelTriageML.jsx'
import ModeloVehiculo from '../components/ModeloVehiculo.jsx'

// Para quien usa el sistema no se mencionan detalles técnicos. (Causa probable: hay una
// versión antigua del backend en el puerto 8000; `python diagnostico.py` dice cuál.)
const OLD_BACKEND = 'No se pudo confirmar que se guardó. Avisa a soporte técnico antes de volver a intentarlo.'

// Etiqueta legible del módulo dueño de una colección referenciada por `source`
// (p. ej. "operadores" → "Operadores"), para armar mensajes genéricos sin
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

// Sirve para agregar (/:module/nuevo) y para editar (/:module/:id/editar, solo los módulos con
// `editar: true`, p. ej. Ambulancias). Al editar se llena con los datos guardados y se manda
// con PUT; el servidor aplica las mismas reglas que al registrar.
export default function ModuleFormPage() {
  const { module: key, id } = useParams()
  const mod = findModule(key)
  if (!mod || mod.custom || (id && !mod.editar)) return <Navigate to="/" replace />
  return <FormView key={`${key}-${id ?? 'nuevo'}`} mod={mod} editId={id} />
}

function FormView({ mod, editId }) {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [form, setForm] = useState(() => {
    const f = emptyForm(mod.fields)
    // p. ej. «Agregar ambulancia» desde un hospital: /ambulancias/nuevo?hospital=...
    mod.fields.forEach((x) => { if (params.get(x.key)) f[x.key] = params.get(x.key) })
    return f
  })
  const [formError, setFormError] = useState('')
  const [original, setOriginal] = useState(editId ? null : {})
  useEffect(() => {
    if (!editId) return
    api(`/${mod.key}`).then((d) => {
      const item = (d.items ?? []).find((r) => String(r.id) === String(editId))
      if (!item) { setFormError('No se encontró este registro. Puede que lo hayan eliminado.'); return }
      setOriginal(item)
      setForm(Object.fromEntries(mod.fields.map((x) => [x.key, item[x.key] == null ? '' : String(item[x.key])])))
    }).catch((e) => setFormError(e.message))
  }, [editId, mod])
  const [saving, setSaving] = useState(false)
  // Campos con `hideInForm` (p. ej. el operador de una emergencia) no se piden aquí:
  // se llenan en otro paso. useMemo mantiene la misma referencia entre renders, porque
  // useSourcedOptions vuelve a leer las listas cada vez que cambia el arreglo recibido.
  const formFields = useMemo(() => mod.fields.filter((f) => !f.hideInForm), [mod.fields])
  const { options: sourcedOptions, loading: sourcedLoading } = useSourcedOptions(formFields)

  // Verificación por reconocimiento facial: modal de cámara abierto y, por
  // cada campo que la requiere (p. ej. operador), qué valor quedó
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
      if (typeof body.usuario === 'string') body.usuario = body.usuario.trim().toLowerCase()
      if (body.ambulancia === '') body.ambulancia = null
      if (body.operador === '') body.operador = null
      const saved = await api(editId ? `/${mod.key}/${editId}` : `/${mod.key}`, { method: editId ? 'PUT' : 'POST', body })
      if (!saved.saved_in) {
        setFormError(OLD_BACKEND)
        setSaving(false)
        return
      }
      const done = editId ? (mod.nuevo === 'Nueva' ? 'actualizada' : 'actualizado') : (mod.nuevo === 'Nueva' ? 'guardada' : 'guardado')
      const name = mod.singular.charAt(0).toUpperCase() + mod.singular.slice(1)
      // Si el módulo define `afterSave`, ese paso va justo después de guardar
      // (Emergencias → su reporte, con las ambulancias ya asignadas); si no, se
      // regresa a la lista con el aviso de guardado.
      const asig = saved.asignacion
      const notice = asig
        ? { kind: asig.faltan ? 'warn' : 'ok', text: `✓ ${name} ${saved.folio || ''} ${done}. ${asig.mensaje}` }
        : { kind: 'ok', text: `✓ ${name} ${saved.nombre ?? saved.placa ?? ''} ${done}.`.replace(/\s+\./, '.') }
      if (editId && saved.cambios?.length === 0) notice.text = 'No cambiaste ningún dato.'
      navigate(editId ? `/${mod.key}/${editId}` : mod.afterSave ? mod.afterSave(saved) : `/${mod.key}`, { state: { notice } })
    } catch (err) {
      setFormError(err.message)
      setSaving(false)
    }
  }

  const save = async (e) => {
    e.preventDefault()
    setFormError('')

    const missingPhoto = formFields.find((f) => f.type === 'photo' && f.required && !form[f.key])
    if (missingPhoto) {
      setFormError(`Falta tomar la foto: "${missingPhoto.label}".`)
      return
    }

    // Formato de campos como correo/celular: se avisa aquí mismo, sin esperar a que
    // el servidor lo rechace. Los campos vacíos y no obligatorios se dejan pasar.
    for (const f of formFields) {
      if (!f.pattern) continue
      const raw = (form[f.key] ?? '').trim()
      if (!raw) continue
      const value = f.pattern.normalize ? f.pattern.normalize(raw) : raw
      if (!f.pattern.re.test(value)) {
        setFormError(f.pattern.message)
        return
      }
    }

    await doSave()
  }

  const groups = groupFields(formFields)
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
          <h1>{editId ? `Editar ${mod.singular}${original?.placa ? ` ${original.placa}` : ''}` : `${mod.nuevo} ${mod.singular}`}</h1>
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
                    ) : f.type === 'modeloApi' ? (
                      <ModeloVehiculo id={f.key} marca={form.marca} anio={form.anio} value={form[f.key]}
                        onElegir={(m) => m && setForm((prev) => ({
                          ...prev, modelo: m.modelo, model_id: m.model_id, motor: m.motor, tipo: m.tipo_sugerido,
                          tanque_litros: String(m.tanque_litros), rendimiento_km_l: String(m.rendimiento_km_l),
                          fuente_vehiculo: m.model_id ? 'API vPIC · NHTSA' : 'Respaldo sin conexión',
                        }))} />
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
                             autoComplete={f.type === 'password' ? 'new-password' : f.key === 'usuario' ? 'off' : undefined}
                             onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} />
                    )}
                    {f.pattern && (f.type === 'tel' || f.type === 'email') && <p className="field-hint">{f.type === 'tel' ? 'Solo números, 10 dígitos.' : 'Debe verse como un correo real.'}</p>}
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
                    {f.hint && (
                      <p className="field-hint">{f.hint}</p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ))}

        {mod.key === 'emergencias' && (
          <PanelTriageML
            edadPaciente={form.paciente_edad}
            ambulancia={sourcedOptions.ambulancia?.find((o) => o.value === form.ambulancia)?.raw}
          />
        )}

        {mod.key === 'emergencias' && (
          <PanelLogica prioridad={form.prioridad} requeridas={form.ambulancias_requeridas} />
        )}

        <div className="record-form-actions">
          {formError && <p className="form-error wide">{formError}</p>}
          <div className="record-form-actions-row">
            <Link to={editId ? `/${mod.key}/${editId}` : `/${mod.key}`} className="btn-ghost tall"><X size={15} /> Cancelar</Link>
            <button className="btn-primary compact" disabled={saving || original === null}>
              {saving ? 'Guardando…' : editId ? 'Guardar cambios' : `Guardar ${mod.singular}`}
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
