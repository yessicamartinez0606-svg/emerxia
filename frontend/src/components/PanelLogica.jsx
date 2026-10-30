import { CheckCircle2, X } from 'lucide-react'
import { evaluarFormulario } from '../lib/logica.js'

const Fila = ({ ok, texto }) => (
  <li className={`field-hint ${ok ? 'ok' : 'warn'}`} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
    {ok ? <CheckCircle2 size={14} /> : <X size={14} />}
    {texto}
  </li>
)

// Lista de requisitos para poder asignar la emergencia, en lenguaje sencillo.
// La lógica proposicional (D = s ∧ t, M = u ∧ (p → v)) vive en lib/logica.js.
// El operador no se evalúa aquí: se valida al guardar, en la ventana de Face ID.
export default function PanelLogica({ prioridad, doctor, doctorVerificado, ambulancia }) {
  const r = evaluarFormulario({ prioridad, doctor, doctorVerificado, ambulancia })
  const listo = r.doctorHabilitado && r.ambulanciaAdecuada

  return (
    <div className="panel form-section">
      <h2 className="form-section-title">Requisitos para asignar</h2>
      <ul style={{ listStyle: 'none', padding: 0, margin: '8px 0', display: 'grid', gap: 4 }}>
        <Fila ok={!!doctor} texto="Se eligió un doctor" />
        {doctor && <Fila ok={r.s} texto="El doctor está disponible (no está en descanso)" />}
        {doctor && <Fila ok={r.t} texto="Se verificó el rostro del doctor" />}
        <Fila ok={!!ambulancia} texto="Se eligió una ambulancia" />
        {ambulancia && <Fila ok={r.u} texto="La ambulancia está disponible" />}
        {ambulancia && r.p && <Fila ok={r.v} texto="La ambulancia es avanzada (obligatorio en prioridad Alta)" />}
      </ul>
      {listo && <p className="field-hint ok" style={{ margin: 0 }}>Todo listo: puedes guardar la emergencia.</p>}
    </div>
  )
}
