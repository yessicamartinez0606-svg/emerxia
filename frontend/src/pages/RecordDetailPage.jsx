import { Fragment, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowUpRight, CalendarClock, ScanFace } from 'lucide-react'
import { api } from '../lib/api.js'
import { findModule } from '../lib/modules.js'
import { getPhoto, slug } from '../lib/moduleHelpers.js'

// Campo que se usa como título principal del perfil, por módulo.
const TITLE_KEY = { doctores: 'nombre', ambulancias: 'placa', emergencias: 'folio', operadores: 'nombre' }
const SUBTITLE_KEY = { emergencias: 'paciente_nombre' }

function formatDate(value) {
  if (!value) return null
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return null
  return {
    date: new Intl.DateTimeFormat('es-MX', { day: 'numeric', month: 'long', year: 'numeric' }).format(d),
    time: new Intl.DateTimeFormat('es-MX', { hour: '2-digit', minute: '2-digit', hour12: true }).format(d),
  }
}

// Agrupa los campos del módulo (igual que en el formulario) para mostrar el
// perfil en las mismas secciones lógicas; los campos sin `group` caen en
// "Datos generales". El campo de tipo foto no entra aquí: se usa en el avatar.
function groupFields(fields) {
  const groups = []
  fields.filter((f) => f.type !== 'photo').forEach((f) => {
    const name = f.group ?? 'Datos generales'
    let bucket = groups.find((b) => b.name === name)
    if (!bucket) {
      bucket = { name, fields: [] }
      groups.push(bucket)
    }
    bucket.fields.push(f)
  })
  return groups
}

export default function RecordDetailPage() {
  const { module: key, id } = useParams()
  const mod = findModule(key)
  if (!mod || mod.custom) return <Navigate to="/" replace />
  return <DetailView key={`${key}-${id}`} mod={mod} id={id} />
}

function DetailView({ mod, id }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [related, setRelated] = useState({})

  useEffect(() => {
    setError('')
    setItems(null)
    api(`/${mod.key}`)
      .then((d) => setItems(d.items ?? []))
      .catch((e) => setError(e.message))
  }, [mod.key])

  // Campos como "operador" o "ambulancia" (en Emergencias) apuntan a otra
  // colección: se carga esa lista para poder enlazar al perfil real.
  const linkedSources = useMemo(
    () => [...new Set(mod.fields.filter((f) => f.source).map((f) => f.source))],
    [mod.fields],
  )

  useEffect(() => {
    linkedSources.forEach((src) => {
      api(`/${src}`)
        .then((d) => setRelated((prev) => ({ ...prev, [src]: d.items ?? [] })))
        .catch(() => setRelated((prev) => ({ ...prev, [src]: null })))
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [linkedSources])

  if (error) {
    return (
      <section className="record-screen">
        <p className="form-error">{error}</p>
      </section>
    )
  }

  if (items === null) {
    return (
      <section className="record-screen">
        <p className="muted pad">Cargando perfil…</p>
      </section>
    )
  }

  const item = items.find((r) => String(r.id) === String(id))
  if (!item) {
    return (
      <section className="record-screen">
        <Link to={`/${mod.key}`} className="btn-back" aria-label="Volver a la lista">
          <ArrowLeft size={18} />
        </Link>
        <p className="muted pad">No se encontró este registro. Puede que haya sido eliminado o que el id no sea correcto.</p>
      </section>
    )
  }

  const titleKey = TITLE_KEY[mod.key]
  const subtitleKey = SUBTITLE_KEY[mod.key]
  const statusValue = item.estado
  const priorityValue = item.prioridad
  const photo = getPhoto(mod, item)
  const Icon = mod.icon
  const created = formatDate(item.created_at)
  const groups = groupFields(mod.fields)

  const resolveLink = (f, value) => {
    if (!value) return null
    const rows = related[f.source]
    const row = rows?.find((r) => f.optionValue(r) === value)
    if (!row) return null
    return `/${f.source}/${row.id}`
  }

  return (
    <section className="record-screen">
      <header className="record-screen-head">
        <Link to={`/${mod.key}`} className="btn-back" aria-label="Volver a la lista">
          <ArrowLeft size={18} />
        </Link>
        <div className="record-screen-title">
          <span className="record-screen-eyebrow">{mod.label}</span>
          <h1>{(titleKey && item[titleKey]) || `${mod.singular} #${item.id}`}</h1>
          {subtitleKey && item[subtitleKey] && <p>{item[subtitleKey]}</p>}
        </div>
        {mod.key === 'emergencias' && !item.operador && (
          <Link to={`/operadores/validar/${item.id}`} className="btn-primary compact record-screen-cta">
            <ScanFace size={16} /> Validar operador
          </Link>
        )}
      </header>

      <div className="panel profile-hero">
        <div className="profile-avatar">
          {photo ? <img src={photo} alt="" /> : <Icon size={30} strokeWidth={1.8} />}
        </div>
        <div className="profile-hero-info">
          <div className="profile-hero-badges">
            {statusValue && <span className={`badge b-${slug(statusValue)}`}>{statusValue}</span>}
            {priorityValue && <span className={`badge b-${slug(priorityValue)}`}>Prioridad {priorityValue}</span>}
          </div>
          <dl className="kv profile-hero-kv">
            <dt>Identificador</dt>
            <dd>{mod.key === 'emergencias' ? item.folio : `#${item.id}`}</dd>
            {created && (
              <>
                <dt>Registrado</dt>
                <dd className="profile-hero-date"><CalendarClock size={13} /> {created.date} · {created.time}</dd>
              </>
            )}
          </dl>
        </div>
      </div>

      <div className={`profile-sections ${groups.length === 1 ? 'single' : ''}`}>
        {groups.map((g) => (
          <div className="panel form-section" key={g.name}>
            <h2 className="form-section-title">{g.name}</h2>
            <dl className="kv profile-kv">
              {g.fields.map((f) => {
                const value = item[f.key]
                const col = mod.columns.find((c) => c.key === f.key)
                const isBadge = col?.badge
                const link = f.source ? resolveLink(f, value) : null
                return (
                  <Fragment key={f.key}>
                    <dt>{f.label}</dt>
                    <dd>
                      {!value && '—'}
                      {value && isBadge && <span className={`badge b-${slug(value)}`}>{value}</span>}
                      {value && !isBadge && link && (
                        <Link className="profile-link" to={link}>{value} <ArrowUpRight size={13} /></Link>
                      )}
                      {value && !isBadge && !link && value}
                    </dd>
                  </Fragment>
                )
              })}
            </dl>
          </div>
        ))}
      </div>
    </section>
  )
}
