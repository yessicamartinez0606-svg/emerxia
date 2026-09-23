import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AlertTriangle, ArrowRight, KeyRound, Mail, User } from 'lucide-react'
import AuthAside from '../components/AuthAside.jsx'
import { api } from '../lib/api.js'

export default function ForgotPassword() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null) // { found, resetUrl }

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const data = await api('/auth/forgot-password', { method: 'POST', body: { username: username.trim() } })
      if (data.found) {
        const resetUrl = `${window.location.origin}/restablecer?token=${encodeURIComponent(data.reset_token)}`
        setResult({ found: true, resetUrl, token: data.reset_token })
      } else {
        setResult({ found: false })
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-stage">
      <section className="login-card">
        <AuthAside tagline={'No te preocupes,\nte ayudamos a entrar'} />

        <div className="login-form-wrap">
          <div className="login-form">
            <h1>Recuperar contraseña</h1>
            <p className="lead">Escribe tu usuario y te generamos un enlace para restablecerla</p>

            {!result && (
              <form onSubmit={onSubmit} noValidate>
                <label htmlFor="username"><User size={14} /> Usuario</label>
                <input
                  id="username"
                  className="input"
                  placeholder="Tu usuario"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />

                {error && <p className="form-error" role="alert">{error}</p>}

                <button className="btn-primary" type="submit" disabled={busy || !username}>
                  {busy ? 'Buscando…' : <>Generar enlace <ArrowRight size={16} /></>}
                </button>
                <Link className="forgot" to="/login">Volver a iniciar sesión</Link>
              </form>
            )}

            {result?.found && (
              <div className="reset-result">
                <p className="field-hint warn">
                  <Mail size={13} /> Este sistema todavía no tiene un servicio de correo configurado, así que
                  aquí abajo te mostramos directamente el enlace que normalmente se enviaría por email.
                  No lo compartas con nadie más.
                </p>
                <div className="reset-link-box">
                  <KeyRound size={15} />
                  <code>{result.resetUrl}</code>
                </div>
                <button className="btn-primary" type="button" onClick={() => navigate(`/restablecer?token=${encodeURIComponent(result.token)}`)}>
                  Ir a restablecer mi contraseña <ArrowRight size={16} />
                </button>
                <Link className="forgot" to="/login">Volver a iniciar sesión</Link>
              </div>
            )}

            {result?.found === false && (
              <div className="reset-result">
                <p className="form-error" role="alert"><AlertTriangle size={14} /> No encontramos ninguna cuenta con ese usuario.</p>
                <button className="btn-ghost tall" type="button" onClick={() => setResult(null)}>Intentar de nuevo</button>
                <Link className="forgot" to="/login">Volver a iniciar sesión</Link>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
