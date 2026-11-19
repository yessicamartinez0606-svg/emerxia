import { useState } from 'react'
import { Eye, EyeOff, KeyRound, ShieldCheck, UserRound } from 'lucide-react'
import { api } from '../lib/api.js'
import { useAuth } from '../lib/auth.jsx'
import { PASSWORD_PATTERN, USUARIO_PATTERN } from '../lib/modules.js'

// «Acceso al sistema» en la ficha de un operador o un paramédico: el usuario con el que entra
// y, solo para el Administrador, el formulario para cambiar usuario y/o contraseña
// (backend: PUT /api/{operadores|paramedicos}/{id}/credenciales).
// La contraseña se guarda cifrada y no se puede volver a ver: si la olvidan, se pone una nueva.
// Los textos evitan lo técnico: los usa personal administrativo.

export default function AccesoSistema({ mod, item, onCambio }) {
  const { user } = useAuth()
  const esAdmin = user?.role === 'Administrador'
  const [usuario, setUsuario] = useState('')
  const [password, setPassword] = useState('')
  const [confirmar, setConfirmar] = useState('')
  const [ver, setVer] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')

  const guardar = async (e) => {
    e.preventDefault()
    setError('')
    setAviso('')
    const u = usuario.trim().toLowerCase()
    if (!u && !password) return setError('Escribe el usuario nuevo, la contraseña nueva o los dos.')
    if (u && !USUARIO_PATTERN.re.test(u)) return setError(USUARIO_PATTERN.message)
    if (password && !PASSWORD_PATTERN.re.test(password)) return setError(PASSWORD_PATTERN.message)
    if (password !== confirmar) return setError('Las contraseñas no coinciden.')
    if (!item.tiene_acceso && (!u || !password)) return setError('Para darle acceso escribe un usuario y una contraseña.')
    setGuardando(true)
    try {
      const r = await api(`/${mod.key}/${item.id}/credenciales`, {
        method: 'PUT',
        body: { ...(u ? { usuario: u } : {}), ...(password ? { password } : {}) },
      })
      setAviso(`Listo. ${item.nombre} entra con el usuario «${r.usuario}»${password ? ' y la contraseña nueva' : ''}.`)
      setUsuario('')
      setPassword('')
      setConfirmar('')
      onCambio?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <section className="panel form-section acceso-sistema">
      <h2 className="form-section-title titulo-icono"><ShieldCheck size={15} /> Acceso al sistema</h2>
      <dl className="kv profile-kv">
        <dt>Usuario</dt>
        <dd>{item.usuario ? <code>{item.usuario}</code> : 'Sin acceso todavía'}</dd>
        <dt>Contraseña</dt>
        <dd>{item.tiene_acceso ? 'Guardada de forma segura. Nadie puede verla; si la olvida, ponle una nueva.' : '—'}</dd>
        <dt>Cómo entra</dt>
        <dd>
          Con su usuario y contraseña, o mirando a la cámara («Entrar con mi rostro»)
        </dd>
      </dl>

      {esAdmin ? (
        <form className="acceso-form" onSubmit={guardar} noValidate>
          <p className="field-hint">Deja vacío lo que no quieras cambiar.</p>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="acc-usuario"><UserRound size={13} /> Usuario nuevo</label>
              <input id="acc-usuario" className="input" autoComplete="off" placeholder={item.usuario || 'maria.lopez'}
                     value={usuario} onChange={(e) => setUsuario(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="acc-pass"><KeyRound size={13} /> Contraseña nueva</label>
              <div className="input-with-action">
                <input id="acc-pass" className="input" type={ver ? 'text' : 'password'} autoComplete="new-password"
                       value={password} onChange={(e) => setPassword(e.target.value)} />
                <button type="button" className="icon-btn" aria-label={ver ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                        onClick={() => setVer((v) => !v)}>
                  {ver ? <Eye size={16} /> : <EyeOff size={16} />}
                </button>
              </div>
            </div>
            <div className="field">
              <label htmlFor="acc-pass2"><KeyRound size={13} /> Repite la contraseña</label>
              <input id="acc-pass2" className="input" type={ver ? 'text' : 'password'} autoComplete="new-password"
                     value={confirmar} onChange={(e) => setConfirmar(e.target.value)} />
            </div>
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
          {aviso && <p className="notice ok" role="status">{aviso}</p>}
          <div className="record-form-actions-row">
            <button className="btn-primary compact" disabled={guardando}>
              {guardando ? 'Guardando…' : item.tiene_acceso ? 'Cambiar acceso' : 'Dar acceso'}
            </button>
          </div>
        </form>
      ) : (
        <p className="field-hint">Solo el Administrador puede cambiar el usuario o la contraseña.</p>
      )}
    </section>
  )
}
