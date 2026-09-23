import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowRight, Eye, EyeOff, KeyRound, Lock } from 'lucide-react'
import AuthAside from '../components/AuthAside.jsx'
import { api } from '../lib/api.js'

export default function ResetPassword() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [token, setToken] = useState(params.get('token') ?? '')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('Las contraseñas no coinciden.')
      return
    }
    if (password.length < 6) {
      setError('La contraseña debe tener al menos 6 caracteres.')
      return
    }
    setBusy(true)
    try {
      await api('/auth/reset-password', { method: 'POST', body: { token: token.trim(), password } })
      navigate('/login', { state: { notice: '✓ Tu contraseña se actualizó. Ya puedes iniciar sesión.' } })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-stage">
      <section className="login-card">
        <AuthAside tagline={'Ya casi terminas,\nelige tu nueva contraseña'} />

        <div className="login-form-wrap">
          <form className="login-form" onSubmit={onSubmit} noValidate>
            <h1>Restablecer contraseña</h1>
            <p className="lead">Escribe tu nueva contraseña para terminar</p>

            {!params.get('token') && (
              <>
                <label htmlFor="token"><KeyRound size={14} /> Código del enlace</label>
                <input
                  id="token"
                  className="input"
                  placeholder="Pega aquí el código que te dieron"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  required
                />
              </>
            )}

            <label htmlFor="password"><Lock size={14} /> Nueva contraseña</label>
            <div className="input-with-action">
              <input
                id="password"
                className="input"
                type={show ? 'text' : 'password'}
                placeholder="Mínimo 6 caracteres"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={6}
                required
              />
              <button
                type="button"
                className="icon-btn"
                aria-label={show ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                onClick={() => setShow((v) => !v)}
              >
                {show ? <Eye size={16} /> : <EyeOff size={16} />}
              </button>
            </div>

            <label htmlFor="confirm"><Lock size={14} /> Confirmar contraseña</label>
            <input
              id="confirm"
              className="input"
              type={show ? 'text' : 'password'}
              placeholder="Repite la nueva contraseña"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />

            {error && <p className="form-error" role="alert">{error}</p>}

            <button className="btn-primary" type="submit" disabled={busy || !token || !password || !confirm}>
              {busy ? 'Guardando…' : <>Guardar nueva contraseña <ArrowRight size={16} /></>}
            </button>
            <Link className="forgot" to="/login">Volver a iniciar sesión</Link>
          </form>
        </div>
      </section>
    </div>
  )
}
