import { useCallback, useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { api } from '../lib/api.js'
import { useAuth } from '../lib/auth.jsx'

/** Tarjeta que consulta el estado de un servicio (MongoDB o Spark). */
function ServiceCard({ title, path, rows, note }) {
  const [info, setInfo] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const check = useCallback(() => {
    setBusy(true)
    setError('')
    api(path)
      .then(setInfo)
      .catch((e) => { setInfo(null); setError(e.message) })
      .finally(() => setBusy(false))
  }, [path])

  useEffect(check, [check])

  return (
    <div className="panel">
      <div className="panel-title-row">
        <h2 className="panel-title">{title}</h2>
        <button className="btn-ghost" onClick={check} disabled={busy}>
          <RefreshCw size={14} className={busy ? 'spin' : ''} /> Verificar
        </button>
      </div>
      {error && <p className="form-error">{error}</p>}
      {info && (
        <dl className="kv">
          <dt>Estado</dt><dd><span className="badge b-activo">Conectado</span></dd>
          {rows(info).map(([label, value]) => (
            <FragmentRow key={label} label={label} value={value} />
          ))}
        </dl>
      )}
      {!info && !error && <p className="muted">{note ?? 'Verificando…'}</p>}
    </div>
  )
}

function FragmentRow({ label, value }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  )
}

export default function SettingsPage() {
  const { user } = useAuth()
  const [tecnico, setTecnico] = useState(false)

  return (
    <section className="module-view">
      <header className="view-head">
        <div>
          <h1>Configuración</h1>
          <p>Ajusta las preferencias del sistema y tu cuenta</p>
        </div>
      </header>

      <div className="settings-grid">
        <div className="panel">
          <h2 className="panel-title">Tu cuenta</h2>
          <dl className="kv">
            <dt>Nombre</dt><dd>{user.full_name}</dd>
            <dt>Usuario</dt><dd>{user.username}</dd>
            <dt>Rol</dt><dd>{user.role}</dd>
          </dl>
        </div>
      </div>

      {/* Solo para soporte técnico: estado de la base de datos y de Spark. Se consulta al abrirlo. */}
      {user.role === 'Administrador' && (
        <details className="detalles-tecnicos" onToggle={(e) => setTecnico(e.currentTarget.open)}>
          <summary>Ver detalles técnicos <small>Estado de la conexión, para soporte técnico</small></summary>
          {tecnico && (
            <div className="detalles-cuerpo settings-grid">
              <ServiceCard
                title="Conexión con MongoDB"
                path="/mongo/status"
                rows={(i) => [
                  ['Servidor', i.uri],
                  ['Base de datos', i.database],
                  ['Versión', `MongoDB ${i.version}`],
                  ['Colecciones', Object.entries(i.collections).map(([k, v]) => `${k} (${v})`).join(', ') || '—'],
                ]}
              />

              <ServiceCard
                title="Conexión con Spark"
                path="/spark/status"
                note="Iniciando Spark (la primera vez tarda unos segundos)…"
                rows={(i) => [
                  ['Master', i.master],
                  ['Versión', `Spark ${i.version}`],
                  ['Aplicación', i.app_name],
                  ['ID de aplicación', i.app_id],
                ]}
              />
            </div>
          )}
        </details>
      )}
    </section>
  )
}
