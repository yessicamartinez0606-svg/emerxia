import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Save, X } from 'lucide-react'
import { api } from '../lib/api.js'
import { findModule } from '../lib/modules.js'
import PhotoCapture from '../components/PhotoCapture.jsx'

function emptyForm(fields) {
  return Object.fromEntries(
    fields.map((f) => [f.key, f.type === 'checkboxes' ? [] : f.options ? f.options[0] : '']),
  )
}

/** Pantalla completa para dar de alta un operador: datos personales + fotografía. */
export default function PersonFormPage({ moduleKey }) {
  const mod = findModule(moduleKey)
  const navigate = useNavigate()
  const [form, setForm] = useState(() => emptyForm(mod.personFields))
  const [foto, setFoto] = useState(null)
  const [fotoVerificada, setFotoVerificada] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }))

  const toggleCheckbox = (key, option) => {
    setForm((f) => {
      const current = f[key] || []
      const next = current.includes(option) ? current.filter((v) => v !== option) : [...current, option]
      return { ...f, [key]: next }
    })
  }

  const onFotoChange = (dataUrl, descriptor) => {
    setFoto(dataUrl)
    // PhotoCapture solo llama onChange con una imagen cuando ya detectó una cara real en ella;
    // si dataUrl es null (el usuario quitó la foto), no hay nada verificado.
    setFotoVerificada(Boolean(dataUrl && descriptor))
  }

  const save = async (e) => {
    e.preventDefault()
    setError('')

    if (!foto || !fotoVerificada) {
      setError('Toma o sube una fotografía con una cara real y visible antes de guardar.')
      return
    }

    for (const f of mod.personFields) {
      if (f.pattern && form[f.key] && !f.pattern.test(form[f.key].trim())) {
        setError(f.patternError || `El campo "${f.label}" no tiene un formato válido.`)
        return
      }
      if (f.type === 'checkboxes' && f.required && (!form[f.key] || form[f.key].length === 0)) {
        setError(`Elige al menos una opción en "${f.label}".`)
        return
      }
    }

    setSaving(true)
    try {
      const body = { ...form, foto, foto_verificada: true }
      const saved = await api(`/${mod.key}`, { method: 'POST', body })
      const name = mod.singular.charAt(0).toUpperCase() + mod.singular.slice(1)
      navigate(`/${mod.key}`, {
        state: {
          notice: saved.saved_in
            ? { kind: 'ok', text: `✓ ${name} guardado en MongoDB (${saved.saved_in}), id ${saved.id}.` }
            : { kind: 'warn', text: 'El servidor no confirmó el guardado en MongoDB: revisa que el backend esté actualizado.' },
        },
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  let lastSection = null

  return (
    <section className="module-view">
      <header className="view-head">
        <div>
          <button type="button" className="btn-ghost" onClick={() => navigate(`/${mod.key}`)}>
            <ArrowLeft size={15} /> Volver a {mod.label.toLowerCase()}
          </button>
          <h1 className="form-page-title">{mod.nuevo} {mod.singular}</h1>
          <p>Completa los datos y toma o sube una fotografía (con una cara real y visible) para dar de alta el registro.</p>
        </div>
      </header>

      <form className="panel person-form" onSubmit={save}>
        <div className="person-form-photo">
          <label>Fotografía *</label>
          <PhotoCapture value={foto} onChange={onFotoChange} required />
        </div>

        <div className="person-form-grid">
          {mod.personFields.map((f) => {
            const showSection = f.section && f.section !== lastSection
            lastSection = f.section || lastSection
            return (
              <FragmentField
                key={f.key}
                f={f}
                showSection={showSection}
                form={form}
                set={set}
                toggleCheckbox={toggleCheckbox}
              />
            )
          })}
        </div>

        {error && <p className="form-error wide" role="alert">{error}</p>}

        <div className="wide form-buttons">
          <button className="btn-primary compact" disabled={saving}>
            <Save size={16} /> {saving ? 'Guardando…' : `Guardar ${mod.singular}`}
          </button>
          <button type="button" className="btn-ghost compact" onClick={() => navigate(`/${mod.key}`)} disabled={saving}>
            <X size={16} /> Cancelar
          </button>
        </div>
      </form>
    </section>
  )
}

function FragmentField({ f, showSection, form, set, toggleCheckbox }) {
  return (
    <>
      {showSection && <h3 className="form-section wide">{f.section}</h3>}
      <div className={`field ${f.wide ? 'wide' : ''}`}>
        <label htmlFor={f.key}>{f.label}{f.required ? ' *' : ''}</label>
        {f.type === 'checkboxes' ? (
          <div className="checkbox-group">
            {f.options.map((o) => (
              <label key={o} className="checkbox-option">
                <input
                  type="checkbox"
                  checked={(form[f.key] || []).includes(o)}
                  onChange={() => toggleCheckbox(f.key, o)}
                />
                {o}
              </label>
            ))}
          </div>
        ) : f.options ? (
          <select id={f.key} className="input" value={form[f.key]} onChange={(e) => set(f.key, e.target.value)}>
            {f.options.map((o) => <option key={o}>{o}</option>)}
          </select>
        ) : (
          <input
            id={f.key}
            className="input"
            type={f.type || 'text'}
            autoComplete={f.autoComplete}
            placeholder={f.placeholder}
            required={f.required}
            value={form[f.key]}
            onChange={(e) => set(f.key, e.target.value)}
          />
        )}
        {f.hint && <p className="muted small">{f.hint}</p>}
      </div>
    </>
  )
}
