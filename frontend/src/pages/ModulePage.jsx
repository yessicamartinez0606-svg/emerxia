import { useCallback, useEffect, useState } from 'react'
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'
import { Plus, RefreshCw } from 'lucide-react'
import { api } from '../lib/api.js'
import { findModule } from '../lib/modules.js'
import { getPhoto, slug } from '../lib/moduleHelpers.js'

export default function ModulePage() {
  const { module: key } = useParams()
  const mod = findModule(key)
  if (!mod || mod.custom) return <Navigate to="/" replace />
  return <ModuleView key={key} mod={mod} />
}

function ModuleView({ mod }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [items, setItems] = useState(null)
  const [source, setSource] = useState(null)
  const [notice, setNotice] = useState(location.state?.notice ?? null)
  const [error, setError] = useState('')

  // El aviso de "guardado con éxito" llega desde la pantalla del formulario a
  // través del estado de navegación; se limpia del historial para que no
  // reaparezca si el usuario recarga o vuelve con el botón "atrás".
  useEffect(() => {
    if (location.state?.notice) {
      navigate(location.pathname, { replace: true, state: {} })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const load = useCallback(() => {
    setError('')
    api(`/${mod.key}`)
      .then((d) => { setItems(d.items); setSource(d.source ?? null) })
      .catch((e) => setError(e.message))
  }, [mod.key])

  useEffect(load, [load])

  const goToRow = (row) => navigate(`/${mod.key}/${row.id}`)
  const Icon = mod.icon

  return (
    <section className="module-view">
      <header className="view-head">
        <div>
          <h1>{mod.label}</h1>
          <p>{mod.description}</p>
        </div>
        <div className="head-actions">
          <button className="btn-ghost tall" onClick={load} title="Volver a leer los datos de MongoDB">
            <RefreshCw size={15} /> Actualizar
          </button>
          <button className="btn-primary compact" onClick={() => navigate(`/${mod.key}/nuevo`)}>
            <Plus size={16} /> {mod.nuevo} {mod.singular}
          </button>
        </div>
      </header>

      {notice && <p className={`notice ${notice.kind}`} role="status">{notice.text}</p>}

      <div className="panel table-wrap">
        {error && <p className="form-error">{error} <button className="link" onClick={load}>Reintentar</button></p>}
        {!error && items === null && <p className="muted pad">Cargando datos…</p>}
        {!error && items?.length === 0 && (
          <p className="muted pad">Aún no hay registros. Usa “{mod.nuevo} {mod.singular}” para crear el primero.</p>
        )}
        {items?.length > 0 && (
          <table>
            <thead>
              <tr>
                <th aria-hidden="true"></th>
                {mod.columns.map((c) => <th key={c.key}>{c.label}</th>)}
                <th aria-hidden="true"></th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => {
                const photo = getPhoto(mod, row)
                return (
                  <tr
                    key={row.id}
                    className="row-link"
                    tabIndex={0}
                    role="link"
                    aria-label={`Ver perfil de ${row[mod.columns[0]?.key] ?? mod.singular}`}
                    onClick={() => goToRow(row)}
                    onKeyDown={(e) => { if (e.key === 'Enter') goToRow(row) }}
                  >
                    <td className="row-avatar-cell">
                      <span className="row-avatar">
                        {photo ? <img src={photo} alt="" /> : <Icon size={15} strokeWidth={1.8} />}
                      </span>
                    </td>
                    {mod.columns.map((c) => (
                      <td key={c.key}>
                        {c.badge && row[c.key]
                          ? <span className={`badge b-${slug(row[c.key])}`}>{row[c.key]}</span>
                          : row[c.key] ?? '—'}
                      </td>
                    ))}
                    <td className="row-link-arrow" aria-hidden="true">›</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
        {items && (
          <p className={`source-note ${source ? '' : 'warn'}`}>
            {source
              ? `${items.length} registro(s) · leído de MongoDB: ${source}`
              : '⚠ Este servidor no reporta MongoDB: probablemente es una versión antigua del backend.'}
          </p>
        )}
      </div>
    </section>
  )
}
