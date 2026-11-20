import { useState } from 'react'
import { ArrowLeft, ScanFace } from 'lucide-react'
import FaceCapture from './FaceCapture.jsx'
import { useAuth } from '../lib/auth.jsx'
import { descriptorDeFoto } from '../lib/faceVerify.js'

// Entrada de operadores y paramédicos: sin usuario ni contraseña. Se toma su foto, se calcula su
// descriptor facial y el servidor busca a qué operador registrado corresponde. Si su foto
// no está registrada en Operadores, no lo reconoce y no entra.

export default function EntrarConRostro({ onVolver }) {
  const { loginConRostro } = useAuth()
  const [camara, setCamara] = useState(false)
  const [estado, setEstado] = useState('')      // '' | 'reconociendo'
  const [error, setError] = useState('')

  const conFoto = async (foto) => {
    setCamara(false)
    setEstado('reconociendo')
    setError('')
    try {
      const descriptor = await descriptorDeFoto(foto)
      if (!descriptor) throw new Error('No se vio tu rostro con claridad. Busca buena luz y vuelve a intentarlo.')
      await loginConRostro(descriptor)
    } catch (e) {
      setError(e.message)
      setEstado('')
    }
  }

  return (
    <div className="login-form entrar-rostro">
      <span className="entrar-rostro-icono" aria-hidden="true"><ScanFace size={30} /></span>
      <h1>Entrar con mi rostro</h1>
      <p className="lead">Para operadores y paramédicos. Mira a la cámara y te reconocemos con la foto que tomó la central. No necesitas usuario ni contraseña.</p>

      <ul className="entrar-rostro-tips">
        <li>Buena luz de frente, sin lentes oscuros ni cubrebocas.</li>
        <li>Tu cara completa dentro del recuadro.</li>
      </ul>

      {error && <p className="form-error" role="alert">{error}</p>}

      <button className="btn-primary" type="button" onClick={() => setCamara(true)} disabled={estado === 'reconociendo'}>
        <ScanFace size={17} /> {estado === 'reconociendo' ? 'Reconociendo…' : error ? 'Intentar de nuevo' : 'Abrir cámara'}
      </button>
      <button className="btn-ghost tall entrar-rostro-volver" type="button" onClick={onVolver}>
        <ArrowLeft size={15} /> Entrar con usuario y contraseña
      </button>
      <p className="field-hint">¿No te reconoce? Pide a la central que vuelva a tomar tu foto.</p>

      <FaceCapture
        open={camara}
        mode="register"
        title="Entrar con mi rostro"
        textoConfirmar="Entrar"
        onSuccess={conFoto}
        onCancel={() => setCamara(false)}
      />
    </div>
  )
}
