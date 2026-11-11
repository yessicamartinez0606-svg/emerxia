import { useEffect, useState } from 'react'
import { ScanFace } from 'lucide-react'
import { api } from '../lib/api.js'
import { descriptorDeFoto } from '../lib/faceVerify.js'

// Calcula el descriptor facial de las fotos de los operadores que aún no lo tienen (o
// cuya foto cambió) y lo guarda en el servidor. Así el operador puede entrar solo con su
// rostro. Corre en el navegador del personal de la central, en segundo plano.

let enCurso = null   // una sola pasada a la vez aunque se monte en varios lugares

function preparar(onAvance) {
  if (enCurso) return enCurso
  enCurso = (async () => {
    const pendientes = await api('/auth/rostros/pendientes')
    let listos = 0
    const sinRostro = []
    onAvance({ total: pendientes.length, listos, sinRostro })
    for (const op of pendientes) {
      const descriptor = await descriptorDeFoto(op.foto).catch(() => null)
      if (descriptor) {
        await api(`/auth/rostros/${op.id}`, { method: 'PUT', body: { descriptor } })
        listos += 1
      } else {
        sinRostro.push(op.nombre)
      }
      onAvance({ total: pendientes.length, listos, sinRostro: [...sinRostro] })
    }
    return { total: pendientes.length, listos, sinRostro }
  })().finally(() => { enCurso = null })
  return enCurso
}

export default function PrepararRostros({ visible = false }) {
  const [avance, setAvance] = useState(null)

  useEffect(() => {
    let vigente = true
    preparar((a) => vigente && setAvance(a)).then((a) => vigente && setAvance(a)).catch(() => {})
    return () => { vigente = false }
  }, [])

  if (!visible || !avance || avance.total === 0) return null
  const terminado = avance.listos + avance.sinRostro.length >= avance.total
  return (
    <div className={`rostros-aviso${avance.sinRostro.length ? ' warn' : ''}`} role="status">
      <ScanFace size={16} aria-hidden="true" />
      {terminado
        ? <span>Face ID listo para {avance.listos} operador(es).{avance.sinRostro.length ? ` No se detectó un rostro en la foto de ${avance.sinRostro.join(', ')}: vuelve a tomarla para que pueda entrar.` : ''}</span>
        : <span>Preparando el Face ID de {avance.total} operador(es)… ({avance.listos} listos)</span>}
    </div>
  )
}
