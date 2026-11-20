import { useCallback, useEffect, useRef, useState } from 'react'
import { Camera, Loader2, RefreshCw, Upload, User, X } from 'lucide-react'
import { dataUrlToImage, getFaceDescriptor } from '../lib/faceApi.js'

const MAX_SIDE = 480     // la foto se reduce a este tamaño máximo antes de enviarla
const JPEG_QUALITY = 0.72

/** Redibuja una imagen en un <canvas> más pequeño y la devuelve como JPEG en base64. */
function toCompressedDataUrl(source, sw, sh) {
  const scale = Math.min(1, MAX_SIDE / Math.max(sw, sh))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(sw * scale)
  canvas.height = Math.round(sh * scale)
  const ctx = canvas.getContext('2d')
  ctx.drawImage(source, 0, 0, canvas.width, canvas.height)
  return canvas.toDataURL('image/jpeg', JPEG_QUALITY)
}

/**
 * Fotografía de perfil: cámara en vivo (con vista previa) o subir un archivo.
 * Cualquiera de las dos rutas se comprime a un JPEG pequeño, y ANTES de aceptarla se corre
 * detección facial (face-api.js): si no hay una cara real y clara en la imagen, se rechaza.
 * Esto es lo que exige el registro: no se puede dar de alta a un operador sin una cara
 * verificable, porque esa misma foto es la que luego se usa para el Face ID al despachar
 * ambulancias.
 *
 * onChange(dataUrl, descriptor) recibe también el "descriptor" facial (arreglo de 128 números)
 * ya calculado, para no tener que volver a correr la detección después.
 */
export default function PhotoCapture({ value, onChange, required }) {
  const [mode, setMode] = useState('idle')   // idle | camera | checking | error
  const [error, setError] = useState('')
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const fileRef = useRef(null)

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  useEffect(() => stopCamera, [stopCamera])

  const openCamera = async () => {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false })
      streamRef.current = stream
      setMode('camera')
      // el <video> se monta en este mismo render; se conecta cuando ya existe
      requestAnimationFrame(() => {
        if (videoRef.current) videoRef.current.srcObject = stream
      })
    } catch {
      setError('No se pudo abrir la cámara. Revisa los permisos del navegador o sube una foto desde tu equipo.')
      setMode('error')
    }
  }

  /** Corre la detección facial sobre la imagen ya comprimida; si hay cara, la acepta. */
  const validateAndAccept = async (dataUrl) => {
    setMode('checking')
    setError('')
    try {
      const img = await dataUrlToImage(dataUrl)
      const descriptor = await getFaceDescriptor(img)
      if (!descriptor) {
        setError('No se detectó ninguna cara en la foto. Acércate más, con buena luz, mirando a la cámara.')
        setMode('idle')
        return
      }
      onChange(dataUrl, Array.from(descriptor))
      setMode('idle')
    } catch (err) {
      setError(err.message || 'No se pudo verificar la fotografía.')
      setMode('idle')
    }
  }

  const capture = () => {
    const video = videoRef.current
    if (!video || !video.videoWidth) return
    const shot = toCompressedDataUrl(video, video.videoWidth, video.videoHeight)
    stopCamera()
    validateAndAccept(shot)
  }

  const cancelCamera = () => {
    stopCamera()
    setMode('idle')
  }

  const onFile = (e) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError('Elige un archivo de imagen (JPG, PNG…).')
      return
    }
    setError('')
    const img = new Image()
    img.onload = () => validateAndAccept(toCompressedDataUrl(img, img.naturalWidth, img.naturalHeight))
    img.src = URL.createObjectURL(file)
  }

  return (
    <div className="photo-capture">
      <div className="photo-preview">
        {mode === 'camera' ? (
          <video ref={videoRef} autoPlay playsInline muted />
        ) : value ? (
          <img src={value} alt="Fotografía de la persona" />
        ) : (
          <User size={40} strokeWidth={1.5} />
        )}
      </div>

      <div className="photo-actions">
        {mode === 'camera' ? (
          <>
            <button type="button" className="btn-ghost" onClick={capture}>
              <Camera size={15} /> Capturar
            </button>
            <button type="button" className="btn-ghost" onClick={cancelCamera}>
              <X size={15} /> Cancelar
            </button>
          </>
        ) : (
          <>
            <button type="button" className="btn-ghost" onClick={openCamera} disabled={mode === 'checking'}>
              {mode === 'checking' ? <Loader2 size={15} className="spin" /> : <Camera size={15} />}
              {mode === 'checking' ? 'Verificando cara…' : value ? 'Volver a tomar' : 'Usar cámara'}
            </button>
            <button type="button" className="btn-ghost" onClick={() => fileRef.current?.click()} disabled={mode === 'checking'}>
              <Upload size={15} /> Subir archivo
            </button>
            {value && (
              <button type="button" className="btn-ghost" onClick={() => onChange(null, null)}>
                <RefreshCw size={15} /> Quitar
              </button>
            )}
          </>
        )}
        <input ref={fileRef} type="file" accept="image/*" capture="user" hidden onChange={onFile} />
      </div>

      {error && <p className="form-error">{error}</p>}
      {required && !value && mode === 'idle' && (
        <p className="muted small">Toma o sube una fotografía con una cara real y visible para continuar.</p>
      )}
    </div>
  )
}
