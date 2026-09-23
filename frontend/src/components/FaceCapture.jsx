import { useEffect, useRef, useState } from 'react'
import { Camera, CheckCircle2, AlertTriangle, RefreshCw, X } from 'lucide-react'
import { compareFaces, detectFace } from '../lib/faceVerify.js'

const REASON_MESSAGE = {
  'no-face-reference': 'No se detectó un rostro en la foto registrada. Vuelve a tomarla en el módulo de Operadores.',
  'no-face-capture': 'No se detectó un rostro claro en la foto. Acércate a la cámara, busca buena luz e inténtalo de nuevo.',
  models: 'No se pudieron cargar los modelos de reconocimiento facial. Revisa tu conexión a internet e inténtalo de nuevo.',
}

/**
 * mode="register": solo toma una foto (para guardarla como referencia de un operador).
 * mode="verify": toma una foto y la compara contra `reference` (foto base64 ya guardada).
 *   Si no coincide, deja reintentar tomando la foto de nuevo (no avanza hasta que coincida
 *   o el usuario cancele).
 */
export default function FaceCapture({ open, title, mode = 'verify', reference, onSuccess, onCancel }) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const [captured, setCaptured] = useState(null)
  const [status, setStatus] = useState('camera') // camera | checking | ok | fail | error
  const [message, setMessage] = useState('')
  const [cameraError, setCameraError] = useState('')

  useEffect(() => {
    if (!open) return undefined
    setCaptured(null)
    setStatus('camera')
    setMessage('')
    setCameraError('')

    let cancelled = false
    navigator.mediaDevices?.getUserMedia({ video: { facingMode: 'user' }, audio: false })
      .then((stream) => {
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return }
        streamRef.current = stream
        if (videoRef.current) videoRef.current.srcObject = stream
      })
      .catch(() => setCameraError('No se pudo acceder a la cámara. Revisa los permisos del navegador.'))

    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
  }, [open])

  if (!open) return null

  const takePhoto = () => {
    const video = videoRef.current
    if (!video) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth || 480
    canvas.height = video.videoHeight || 360
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
    const dataUrl = canvas.toDataURL('image/jpeg', 0.9)
    setCaptured(dataUrl)

    if (mode === 'register') {
      // No se acepta como foto de referencia cualquier imagen: se valida
      // primero que face-api.js detecte un rostro real (no una pared, una
      // mano, una foto borrosa o de espaldas). Si no hay rostro, se rechaza
      // y se deja volver a tomar la foto.
      setStatus('checking')
      setMessage('Verificando que se vea un rostro…')
      detectFace(dataUrl).then((result) => {
        if (!result.ok) {
          setStatus('error')
          setMessage(REASON_MESSAGE.models)
          return
        }
        if (!result.hasFace) {
          setStatus('fail')
          setMessage(REASON_MESSAGE['no-face-capture'])
          return
        }
        setStatus('ok')
        setMessage('Rostro detectado: foto lista para usarse como referencia.')
      })
      return
    }

    setStatus('checking')
    setMessage('Comparando rostro…')
    compareFaces(reference, dataUrl).then((result) => {
      if (!result.ok) {
        setStatus('error')
        setMessage(REASON_MESSAGE[result.reason] ?? 'No se pudo comparar el rostro.')
        return
      }
      if (result.match) {
        setStatus('ok')
        setMessage('Identidad verificada: coincide con la foto registrada.')
      } else {
        setStatus('fail')
        setMessage('La foto no coincide con la persona registrada. Vuelve a tomarla.')
      }
    })
  }

  const retake = () => { setCaptured(null); setStatus('camera'); setMessage('') }
  const confirm = () => onSuccess?.(captured)

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="panel modal face-modal">
        <div className="modal-head">
          <h3>{title}</h3>
          <button type="button" className="btn-ghost icon" onClick={onCancel} aria-label="Cerrar">
            <X size={16} />
          </button>
        </div>

        <div className="face-frame">
          {!captured ? (
            <video ref={videoRef} autoPlay playsInline muted />
          ) : (
            <img src={captured} alt="Foto capturada" />
          )}
        </div>

        {cameraError && <p className="face-message error"><AlertTriangle size={15} /> {cameraError}</p>}
        {message && (
          <p className={`face-message ${status}`}>
            {status === 'ok' && <CheckCircle2 size={15} />}
            {(status === 'fail' || status === 'error') && <AlertTriangle size={15} />}
            {message}
          </p>
        )}

        <div className="face-actions">
          {!captured && (
            <button type="button" className="btn-primary compact" onClick={takePhoto} disabled={!!cameraError}>
              <Camera size={15} /> Tomar foto
            </button>
          )}
          {captured && status !== 'checking' && status !== 'ok' && (
            <button type="button" className="btn-primary compact" onClick={retake}>
              <RefreshCw size={15} /> Tomar de nuevo
            </button>
          )}
          {captured && status === 'ok' && (
            <button type="button" className="btn-primary compact" onClick={confirm}>
              {mode === 'register' ? 'Usar esta foto' : 'Confirmar'}
            </button>
          )}
          <button type="button" className="btn-ghost compact" onClick={onCancel}>Cancelar</button>
        </div>
      </div>
    </div>
  )
}
