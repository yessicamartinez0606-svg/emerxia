import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Eye, EyeOff, Lock, User, UserPlus, ArrowRight } from 'lucide-react'
import AuthAside from '../components/AuthAside.jsx'
import { useAuth } from '../lib/auth.jsx'

const ROLES = ['Despachador', 'Supervisor', 'Administrador']

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [username, setUsername] = useState('')
  const [role, setRole] = useState(ROLES[0])
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
      await register({ fullName: fullName.trim(), username: username.trim(), password, role })
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-stage">
      <section className="login-card">
        <AuthAside tagline={'Únete al equipo,\nmarca la diferencia'} />

        <div className="login-form-wrap">
          <form className="login-form" onSubmit={onSubmit} noValidate>
            <h1>Crear una cuenta</h1>
            <p className="lead">Regístrate para acceder al sistema de Emergexia</p>

            <label htmlFor="fullName"><User size={14} /> Nombre completo</label>
            <input
              id="fullName"
              className="input"
              placeholder="Tu nombre y apellido"
              autoComplete="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
            />

            <label htmlFor="username"><User size={14} /> Usuario</label>
            <input
              id="username"
              className="input"
              placeholder="Elige un nombre de usuario"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              minLength={3}
              required
            />

            <label htmlFor="role"><UserPlus size={14} /> Rol</label>
            <select id="role" className="input" value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map((r) => <option key={r}>{r}</option>)}
            </select>

            <label htmlFor="password"><Lock size={14} /> Contraseña</label>
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
              placeholder="Repite la contraseña"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />

            {error && <p className="form-error" role="alert">{error}</p>}

            <button className="btn-primary" type="submit" disabled={busy || !fullName || !username || !password || !confirm}>
              {busy ? 'Creando cuenta…' : <>Crear cuenta <ArrowRight size={16} /></>}
            </button>
            <Link className="forgot" to="/login">¿Ya tienes cuenta? Inicia sesión</Link>
          </form>
        </div>
      </section>
    </div>
  )
}
