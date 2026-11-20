import { useEffect, useRef, useState } from 'react'
import { Camera, CheckCircle2, Loader2, ShieldAlert, X } from 'lucide-react'
import { dataUrlToImage, faceDistance, getFaceDescriptor, isSamePerson, MATCH_THRESHOLD } from '../lib/faceApi.js'

/**
 * Verificación facial antes de que una ambulancia pueda salir con un paramédico a bordo.
 *
 * - `operador`: el registro completo del operador elegido (con su `foto` guardada al darlo de alta).
 * - Compara la foto registrada contra una captura en vivo de la cámara con face-api.js.
 * - Solo llama a onVerified(distancia) si la cara coincide (distancia <= MATCH_THRESHOLD).
 *   Mientras no coincida, el botón de confirmar sigue bloqueado: por diseño, no hay forma de
 *   "saltarse" la verificación desde esta ventana.
 */
export default function FaceIdModal({ operador, onVerified, onCancel }) {
  const [refDescriptor, setRefDescriptor] = useState(null)
  const [status, setStatus] = useState('loading')  // loading | ready | camera | comparing | match | nomatch | error
  const [message, setMessage] = useState('Preparando la cámara…')
  const [distance, setDistance] = useState(null)
  const videoRef = useRef(null)
  const streamRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    async function prep() {
      if (!operador?.foto) {
        setStatus('error')
        setMessage(`${operador?.nombre || 'Este operador'} no tiene una fotografía registrada. No se puede verificar.`)
        return
      }
      try {
        const img = await dataUrlToImage(operador.foto)
        const descriptor = await getFaceDescriptor(img)
        if (cancelled) return
        if (!descriptor) {
          setStatus('error')
          setMessage('La foto registrada de este operador no tiene una cara detectable. Pídele que actualice su foto.')
          return
        }
        setRefDescriptor(descriptor)
        setStatus('ready')
        setMessage('Listo. Abre la cámara para comparar la cara en vivo.')
      } catch (err) {
        if (!cancelled) {
          setStatus('error')
          setMessage(err.message || 'No se pudo procesar la foto registrada.')
        }
      }
    }
    prep()
    return () => { cancelled = true }
  }, [operador])

  useEffect(() => () => streamRef.current?.getTracks().forEach((t) => t.stop()), [])

  const openCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false })
      streamRef.current = stream
      setStatus('camera')
      setMessage('Mira a la cámara y presiona "Comparar cara".')
      requestAnimationFrame(() => { if (videoRef.current) videoRef.current.srcObject = stream })
    } catch {
      setStatus('error')
      setMessage('No se pudo abrir la cámara. Revisa los permisos del navegador.')
    }
  }

  const compare = async () => {
    if (!videoRef.current || !refDescriptor) return
    setStatus('comparing')
    setMessage('Comparando…')
    try {
      const liveDescriptor = await getFaceDescriptor(videoRef.current)
      if (!liveDescriptor) {
        setStatus('camera')
        setMessage('No se detectó una cara frente a la cámara. Acércate e inténtalo de nuevo.')
        return
      }
      const d = faceDistance(refDescriptor, liveDescriptor)
      setDistance(d)
      if (isSamePerson(d)) {
        setStatus('match')
        setMessage(`Coincide con ${operador.nombre}. Ya puedes confirmar la salida.`)
        streamRef.current?.getTracks().forEach((t) => t.stop())
      } else {
        setStatus('nomatch')
        setMessage(`La cara no coincide con ${operador.nombre}. La ambulancia no puede salir con esta verificación.`)
      }
    } catch (err) {
      setStatus('error')
      setMessage(err.message || 'Ocurrió un error comparando las caras.')
    }
  }

  const retry = () => { setStatus('ready'); setMessage('Vuelve a abrir la cámara para intentarlo de nuevo.'); setDistance(null) }

  return (
    <div className="face-modal-backdrop" role="dialog" aria-modal="true">
      <div className="face-modal">
        <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0 }}>Verificación facial · {operador?.nombre}</h3>
          <button type="button" className="btn-ghost" onClick={onCancel}><X size={16} /></button>
        </header>

        <div className="face-modal-compare">
          <div>
            <p className="muted small">Foto registrada</p>
            {operador?.foto
              ? <img className="face-ref" src={operador.foto} alt={operador.nombre} />
              : <p className="muted small">Sin foto</p>}
          </div>
          <div>
            <p className="muted small">Cámara en vivo</p>
            {status === 'camera' || status === 'comparing' || status === 'match' || status === 'nomatch'
              ? <video ref={videoRef} autoPlay playsInline muted />
              : <p className="muted small">Aún no se abre</p>}
          </div>
        </div>

        <p className={`face-modal-status ${status === 'match' ? 'ok' : status === 'nomatch' || status === 'error' ? 'fail' : 'pending'}`}>
          {(status === 'loading' || status === 'comparing') && <Loader2 size={15} className="spin" style={{ verticalAlign: 'middle', marginRight: 6 }} />}
          {status === 'match' && <CheckCircle2 size={15} style={{ verticalAlign: 'middle', marginRight: 6 }} />}
          {(status === 'nomatch' || status === 'error') && <ShieldAlert size={15} style={{ verticalAlign: 'middle', marginRight: 6 }} />}
          {message}
          {distance !== null && ` (distancia ${distance.toFixed(2)}, límite ${MATCH_THRESHOLD})`}
        </p>

        <div className="form-buttons">
          {status === 'ready' && (
            <button type="button" className="btn-primary compact" onClick={openCamera}><Camera size={15} /> Abrir cámara</button>
          )}
          {status === 'camera' && (
            <button type="button" className="btn-primary compact" onClick={compare}>Comparar cara</button>
          )}
          {status === 'nomatch' && (
            <button type="button" className="btn-ghost compact" onClick={retry}>Intentar de nuevo</button>
          )}
          {status === 'match' && (
            <button type="button" className="btn-primary compact" onClick={() => onVerified(distance)}>
              <CheckCircle2 size={15} /> Confirmar salida
            </button>
          )}
          <button type="button" className="btn-ghost compact" onClick={onCancel}>Cancelar</button>
        </div>
      </div>
    </div>
  )
}
