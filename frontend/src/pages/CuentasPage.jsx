import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { KeyRound, Plus, Power, Trash2, UserPlus, X } from 'lucide-react'
import { api } from '../lib/api.js'
import { useAuth } from '../lib/auth.jsx'
import { fmtFecha } from '../lib/flota.js'
import { PASSWORD_PATTERN, USUARIO_PATTERN } from '../lib/modules.js'

// Cuentas del sistema (solo el Administrador). Aquí se crean las de la central
// (Administrador, Despachador, Supervisor). Las de operadores y paramédicos se dan en su ficha
// y las de Usuario las crea cada persona al registrarse para reportar. Backend: routers/cuentas.py.

const ROLES_CENTRAL = ['Despachador', 'Supervisor', 'Administrador']
const VACIA = { full_name: '', username: '', password: '', role: 'Despachador' }

export default function CuentasPage() {
  const { user } = useAuth()
  const [items, setItems] = useState(null)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const [nueva, setNueva] = useState(false)
  const [filtro, setFiltro] = useState('Todas')

  const cargar = () => api('/cuentas').then((d) => { setItems(d.items); setError('') }).catch((e) => setError(e.message))
  useEffect(() => { cargar() }, [])
  if (user?.role !== 'Administrador') return <Navigate to="/" replace />

  const accion = async (fn, texto) => {
    setError('')
    setAviso('')
    try {
      const r = await fn()
      setAviso(texto ?? r?.mensaje ?? 'Listo.')
      cargar()
    } catch (e) {
      setError(e.message)
    }
  }
  const cambiarClave = (c) => {
    const clave = window.prompt(`Contraseña nueva para ${c.full_name} (mínimo 6 caracteres):`)
    if (clave == null) return
    if (!PASSWORD_PATTERN.re.test(clave)) { setError(PASSWORD_PATTERN.message); return }
    accion(() => api(`/cuentas/${encodeURIComponent(c.username)}`, { method: 'PUT', body: { password: clave } }),
      `Contraseña de ${c.full_name} cambiada. Entrégasela en persona.`)
  }
  const borrar = (c) => {
    if (!window.confirm(`¿Borrar la cuenta de ${c.full_name} (${c.username})? Ya no podrá entrar. No se puede deshacer.`)) return
    accion(() => api(`/cuentas/${encodeURIComponent(c.username)}`, { method: 'DELETE' }))
  }

  const roles = ['Todas', ...new Set((items ?? []).map((c) => c.role))]
  const lista = (items ?? []).filter((c) => filtro === 'Todas' || c.role === filtro)

  return (
    <section className="module-view">
      <header className="view-head">
        <div>
          <h1>Cuentas</h1>
          <p>Quién puede entrar al sistema. Aquí creas las cuentas de la central; las de operadores y paramédicos se dan en su ficha.</p>
        </div>
        <div className="head-actions">
          <button className="btn-primary compact" onClick={() => setNueva(true)}><Plus size={16} /> Nueva cuenta</button>
        </div>
      </header>

      {aviso && <p className="notice ok" role="status">{aviso}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      {nueva && <NuevaCuenta onCerrar={() => setNueva(false)} onCreada={(c) => { setNueva(false); setAviso(`✓ Cuenta de ${c.full_name} creada (${c.role}). Entrégale su usuario y contraseña en persona.`); cargar() }} />}

      <div className="fh-filtros" role="group" aria-label="Filtrar por rol">
        {roles.map((r) => (
          <button key={r} type="button" className={filtro === r ? 'on' : ''} aria-pressed={filtro === r} onClick={() => setFiltro(r)}>
            {r} <b>{r === 'Todas' ? items?.length ?? 0 : (items ?? []).filter((c) => c.role === r).length}</b>
          </button>
        ))}
      </div>

      <div className="panel table-wrap">
        {!items && !error && <p className="muted pad">Cargando cuentas…</p>}
        {items && (
          <table>
            <thead>
              <tr><th>Nombre</th><th>Usuario</th><th>Rol</th><th>Estado</th><th>Creada</th><th aria-label="Acciones" /></tr>
            </thead>
            <tbody>
              {lista.map((c) => {
                const central = ROLES_CENTRAL.includes(c.role)
                const yo = c.username === user.username
                return (
                  <tr key={c.username}>
                    <td>{c.full_name}{yo && <span className="rd-sub-celda">Tú</span>}{c.ligada_a && <span className="rd-sub-celda">Se administra en {c.ligada_a}</span>}</td>
                    <td><code>{c.username}</code></td>
                    <td>
                      {central && !yo ? (
                        <select className="input cuentas-rol" value={c.role} aria-label={`Rol de ${c.full_name}`}
                                onChange={(e) => accion(() => api(`/cuentas/${encodeURIComponent(c.username)}`, { method: 'PUT', body: { role: e.target.value } }))}>
                          {ROLES_CENTRAL.map((r) => <option key={r}>{r}</option>)}
                        </select>
                      ) : c.role}
                    </td>
                    <td><span className={`badge b-${c.active ? 'activo' : 'desconectado'}`}>{c.active ? 'Activa' : 'Desactivada'}</span></td>
                    <td>{c.created_at ? fmtFecha(c.created_at, false) : '—'}</td>
                    <td className="cuentas-acciones">
                      {!c.ligada_a && (
                        <button type="button" className="btn-ghost" onClick={() => cambiarClave(c)}><KeyRound size={14} /> Contraseña</button>
                      )}
                      {!yo && (
                        <button type="button" className="btn-ghost"
                                onClick={() => accion(() => api(`/cuentas/${encodeURIComponent(c.username)}`, { method: 'PUT', body: { active: !c.active } }))}>
                          <Power size={14} /> {c.active ? 'Desactivar' : 'Activar'}
                        </button>
                      )}
                      {!yo && <button type="button" className="btn-ghost peligro" onClick={() => borrar(c)}><Trash2 size={14} /> Borrar</button>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}

function NuevaCuenta({ onCerrar, onCreada }) {
  const [f, setF] = useState(VACIA)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const cambia = (k) => (e) => { setF({ ...f, [k]: e.target.value }); setError('') }

  const guardar = async (e) => {
    e.preventDefault()
    const username = f.username.trim().toLowerCase()
    if (f.full_name.trim().length < 2) return setError('Escribe su nombre completo.')
    if (!USUARIO_PATTERN.re.test(username)) return setError(USUARIO_PATTERN.message)
    if (!PASSWORD_PATTERN.re.test(f.password)) return setError(PASSWORD_PATTERN.message)
    setGuardando(true)
    try {
      onCreada(await api('/cuentas', { method: 'POST', body: { ...f, username, full_name: f.full_name.trim() } }))
    } catch (err) {
      setError(err.message)
      setGuardando(false)
    }
  }

  return (
    <form className="panel form-section" onSubmit={guardar} noValidate>
      <div className="panel-title-row">
        <h2 className="form-section-title titulo-icono"><UserPlus size={15} /> Nueva cuenta de la central</h2>
        <button type="button" className="btn-ghost icon" onClick={onCerrar} aria-label="Cerrar"><X size={16} /></button>
      </div>
      <div className="form-grid">
        <div className="field"><label htmlFor="c-nombre">Nombre completo</label>
          <input id="c-nombre" className="input" value={f.full_name} onChange={cambia('full_name')} /></div>
        <div className="field"><label htmlFor="c-usuario">Usuario</label>
          <input id="c-usuario" className="input" autoComplete="off" placeholder="maria.lopez" value={f.username} onChange={cambia('username')} /></div>
        <div className="field"><label htmlFor="c-pass">Contraseña</label>
          <input id="c-pass" className="input" type="password" autoComplete="new-password" value={f.password} onChange={cambia('password')} />
          <p className="field-hint">Mínimo 6 caracteres. Entrégasela en persona.</p></div>
        <div className="field"><label htmlFor="c-rol">Rol</label>
          <select id="c-rol" className="input" value={f.role} onChange={cambia('role')}>
            {ROLES_CENTRAL.map((r) => <option key={r}>{r}</option>)}
          </select>
          <p className="field-hint">Administrador: todo, incluidas las cuentas. Despachador y Supervisor: la central, sin cuentas ni eliminar.</p></div>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="record-form-actions-row">
        <button type="button" className="btn-ghost tall" onClick={onCerrar}>Cancelar</button>
        <button className="btn-primary compact" disabled={guardando}>{guardando ? 'Creando…' : 'Crear cuenta'}</button>
      </div>
    </form>
  )
}
