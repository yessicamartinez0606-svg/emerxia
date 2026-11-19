import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Trash2 } from 'lucide-react'
import { api } from '../lib/api.js'
import { useAuth } from '../lib/auth.jsx'

// «Eliminar» en la ficha de una ambulancia, un operador o un paramédico. Solo el
// Administrador. Pide confirmar escribiendo ELIMINAR, porque no se puede deshacer.
// El servidor no deja eliminar a quien está ocupado en una emergencia abierta.
// Backend: DELETE /api/{ambulancias|operadores|paramedicos}/{id} (routers/modules.py).

export default function EliminarRegistro({ mod, item }) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [abierto, setAbierto] = useState(false)
  const [texto, setTexto] = useState('')
  const [borrando, setBorrando] = useState(false)
  const [error, setError] = useState('')
  if (user?.role !== 'Administrador') return null

  const nombre = item.nombre || item.placa || `${mod.singular} #${item.id}`
  const conCuenta = mod.credenciales

  const eliminar = async () => {
    setBorrando(true)
    setError('')
    try {
      const r = await api(`/${mod.key}/${item.id}`, { method: 'DELETE' })
      navigate(`/${mod.key}`, { state: { notice: { kind: 'ok', text: `✓ ${r.mensaje}` } } })
    } catch (e) {
      setError(e.message)
      setBorrando(false)
    }
  }

  return (
    <section className="panel eliminar-registro">
      {!abierto ? (
        <button type="button" className="btn-ghost tall peligro" onClick={() => setAbierto(true)}>
          <Trash2 size={15} /> Eliminar {mod.singular}
        </button>
      ) : (
        <div className="eliminar-confirmar">
          <strong>¿Eliminar a {nombre}?</strong>
          <p>
            Se borra del sistema y no se puede deshacer.
            {conCuenta ? ' También se borra su acceso: ya no podrá entrar ni con contraseña ni con su rostro.' : ''}
            {' '}Lo que ya pasó (emergencias atendidas, historial) se conserva.
          </p>
          <label htmlFor="confirmar-eliminar">Para confirmar escribe <b>ELIMINAR</b></label>
          <input id="confirmar-eliminar" className="input" value={texto} autoComplete="off"
                 onChange={(e) => { setTexto(e.target.value); setError('') }} />
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="record-form-actions-row">
            <button type="button" className="btn-ghost tall" onClick={() => { setAbierto(false); setTexto(''); setError('') }}>Cancelar</button>
            <button type="button" className="btn-primary compact peligro" disabled={borrando || texto.trim().toUpperCase() !== 'ELIMINAR'}
                    onClick={eliminar}>
              <Trash2 size={15} /> {borrando ? 'Eliminando…' : 'Eliminar definitivamente'}
            </button>
          </div>
        </div>
      )}
    </section>
  )
}
