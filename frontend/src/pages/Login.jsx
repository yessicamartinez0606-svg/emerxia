import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Eye, EyeOff, Lock, User, ArrowRight } from 'lucide-react'
import AuthAside from '../components/AuthAside.jsx'
import { useAuth } from '../lib/auth.jsx'

export default function Login() {
  const { login } = useAuth()
  const location = useLocation()
  const notice = location.state?.notice
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [show, setShow] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(username.trim(), password)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-stage">
      <section className="login-card">
        <AuthAside />

        <div className="login-form-wrap">
          <form className="login-form" onSubmit={onSubmit} noValidate>
            <h1>Iniciar sesión</h1>
            <p className="lead">Ingresa tus credenciales para acceder al sistema</p>

            {notice && <p className="notice ok" role="status">{notice}</p>}

            <label htmlFor="username"><User size={14} /> Usuario</label>
            <input
              id="username"
              className="input"
              placeholder="Ingresa tu usuario"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />

            <label htmlFor="password"><Lock size={14} /> Contraseña</label>
            <div className="input-with-action">
              <input
                id="password"
                className="input"
                type={show ? 'text' : 'password'}
                placeholder="Ingresa tu contraseña"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
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

            {error && <p className="form-error" role="alert">{error}</p>}

            <button className="btn-primary" type="submit" disabled={busy || !username || !password}>
              {busy ? 'Ingresando…' : <>Iniciar sesión <ArrowRight size={16} /></>}
            </button>
            <div className="login-links">
              <Link className="forgot" to="/recuperar">¿Olvidaste tu contraseña?</Link>
              <Link className="forgot" to="/registro">Crear una cuenta</Link>
            </div>
          </form>
        </div>

      </section>
    </div>
  )
}
