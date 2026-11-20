import { useEffect, useMemo, useState } from 'react'
import { HeartPulse, ScanFace, UserMinus } from 'lucide-react'
import { api } from '../lib/api.js'
import FaceCapture from './FaceCapture.jsx'

// Paramédicos de una emergencia (se necesitan 2). Cada uno mira a la cámara de la central:
// el SERVIDOR compara su rostro con las fotos de los paramédicos y, si es uno disponible, va a
// esta emergencia en la ambulancia que la atiende. Así le aparece el paciente en su perfil.
// Backend: POST/DELETE /api/flota/emergencias/{id}/paramedicos (routers/flota.py).

export default function ParamedicosEmergencia({ emergencia, onCambio }) {
  const [rep, setRep] = useState(null)
  const [todos, setTodos] = useState(null)
  const [camara, setCamara] = useState(false)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')

  const cargar = () => Promise.all([api(`/flota/emergencias/${emergencia.id}/reporte`), api('/paramedicos')])
    .then(([r, p]) => { setRep(r); setTodos(p.items ?? []) })
    .catch((e) => setError(e.message))
  useEffect(() => { cargar() }, [emergencia.id, emergencia.updated_at]) // eslint-disable-line react-hooks/exhaustive-deps

  // Pueden ir: en servicio, con foto y que no estén ya en otra emergencia.
  const disponibles = useMemo(
    () => (todos ?? []).filter((p) => p.estado === 'En servicio' && p.foto && !p.emergencia_actual)
      .map((p) => ({ ...p, label: p.nombre })),
    [todos],
  )

  if (!rep) return error ? <section className="panel"><p className="form-error">{error}</p></section> : null
  const van = rep.paramedicos
  const faltan = Math.max(0, rep.paramedicos_requeridos - van.length)
  const cerrada = rep.emergencia.estado === 'Cerrada'

  // El servidor decide quién es (compara con las fotos de todos los paramédicos) y si puede ir.
  const enviarRostro = async (descriptor) => {
    setError('')
    setAviso('')
    const r = await api(`/flota/emergencias/${emergencia.id}/paramedicos`, { method: 'POST', body: { descriptor } })
    setRep(r)
    setAviso(`${r.reconocido} confirmado con su rostro. Ya le aparece el paciente en su perfil.`)
    cargar()
    onCambio?.()
    return { ...r, mensaje: `Es ${r.reconocido}. Va a esta emergencia.` }
  }

  const quitar = async (p) => {
    if (!window.confirm(`¿Quitar a ${p.nombre} de esta emergencia?`)) return
    setError('')
    setAviso('')
    try {
      setRep(await api(`/flota/emergencias/${emergencia.id}/paramedicos/${p.id}`, { method: 'DELETE' }))
      await cargar()
      onCambio?.()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <section className={`panel pm-emergencia${faltan && !cerrada ? ' faltan' : ''}`}>
      <h2 className="form-section-title titulo-icono"><HeartPulse size={15} /> Paramédicos de la emergencia</h2>
      <p className="muted">
        {cerrada
          ? 'La emergencia ya está cerrada.'
          : faltan
            ? `Se necesitan ${rep.paramedicos_requeridos} paramédicos. Falta${faltan > 1 ? 'n' : ''} ${faltan}: cada uno debe mirar a la cámara para confirmar que es él.`
            : 'Ya van los 2 paramédicos. Van en la ambulancia de esta emergencia.'}
      </p>

      {van.length > 0 && (
        <ul className="pm-lista">
          {van.map((p) => (
            <li key={p.id}>
              <ScanFace size={15} aria-hidden="true" />
              <span><strong>{p.nombre}</strong> · {p.nivel}</span>
              <small>Confirmado con su rostro</small>
              {!cerrada && (
                <button type="button" className="btn-ghost" onClick={() => quitar(p)} aria-label={`Quitar a ${p.nombre}`}>
                  <UserMinus size={14} /> Quitar
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {aviso && <p className="notice ok" role="status">{aviso}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}

      {!cerrada && faltan > 0 && (
        <>
          <button type="button" className="btn-primary compact" onClick={() => setCamara(true)} disabled={disponibles.length === 0}>
            <ScanFace size={16} /> {`Confirmar paramédico con su rostro (${van.length + 1} de ${rep.paramedicos_requeridos})`}
          </button>
          {todos && disponibles.length === 0 && (
            <p className="field-hint warn">No hay paramédicos disponibles: todos están fuera de turno, ya van a otra emergencia o no tienen foto.</p>
          )}
        </>
      )}

      <FaceCapture
        open={camara}
        mode="servidor"
        title={`Paramédico para ${rep.emergencia.folio}`}
        enviar={enviarRostro}
        onSuccess={() => setCamara(false)}
        onCancel={() => setCamara(false)}
      />
    </section>
  )
}
