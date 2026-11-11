import { useState } from 'react'
import { ArrowLeft, ScanFace } from 'lucide-react'
import FaceCapture from './FaceCapture.jsx'
import { useAuth } from '../lib/auth.jsx'

// Segundo paso del inicio de sesión de un operador: su rostro debe coincidir con la foto
// que la central registró en Operadores. Sin esto no recibe su sesión.

export default function PasoFaceId({ paso, onVolver, textoVolver = 'Volver' }) {
  const { completeFace } = useAuth()
  const [camara, setCamara] = useState(false)
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const verificado = async (_foto, resultado) => {
    setCamara(false)
    setEnviando(true)
    setError('')
    try {
      await completeFace(paso.faceToken, resultado)
    } catch (e) {
      setError(e.message)
      setEnviando(false)
    }
  }

  return (
    <div className="login-form paso-face">
      <h1>Verifica tu rostro</h1>
      <p className="lead">Hola, {paso.operador.nombre}. Como operador, entras con tu contraseña y tu rostro.</p>

      <div className="paso-face-ref">
        <img src={paso.operador.foto} alt={`Foto registrada de ${paso.operador.nombre}`} />
        <div>
          <strong>Foto registrada en la central</strong>
          <span>Mira a la cámara con buena luz y sin lentes oscuros.</span>
        </div>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}

      <button className="btn-primary" type="button" onClick={() => setCamara(true)} disabled={enviando}>
        <ScanFace size={17} /> {enviando ? 'Entrando…' : 'Abrir cámara'}
      </button>
      <button className="btn-ghost tall paso-volver" type="button" onClick={onVolver}>
        <ArrowLeft size={15} /> {textoVolver}
      </button>
      <p className="field-hint">El pase para verificar tu rostro dura 5 minutos.</p>

      <FaceCapture
        open={camara}
        mode="verify"
        title="Inicio de sesión del operador"
        reference={paso.operador.foto}
        onSuccess={verificado}
        onCancel={() => setCamara(false)}
      />
    </div>
  )
}
