import { CheckCircle2, X } from 'lucide-react'
import { evaluarFormulario } from '../lib/logica.js'

// neutro: una proposición en falso no es un error (p. ej. una emergencia que no es Alta)
const Fila = ({ ok, formula, texto, neutro }) => (
  <li className={`field-hint ${ok ? 'ok' : neutro ? '' : 'warn'}`} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
    {ok ? <CheckCircle2 size={14} /> : <X size={14} />}
    <strong>{formula}</strong> {texto}
  </li>
)

// Muestra, con la lógica proposicional de la emergencia, qué falta para poder asignarla.
// El operador (q, r) no se evalúa aquí: se valida al guardar, en la ventana de Face ID.
export default function PanelLogica({ prioridad, doctor, doctorVerificado, ambulancia }) {
  const r = evaluarFormulario({ prioridad, doctor, doctorVerificado, ambulancia })

  return (
    <div className="panel form-section">
      <h2 className="form-section-title">Lógica de asignación</h2>
      <ul style={{ listStyle: 'none', padding: 0, margin: '8px 0', display: 'grid', gap: 4 }}>
        <Fila ok={r.p} neutro formula="p" texto="La emergencia es de prioridad Alta" />
        <Fila ok={r.s} formula="s" texto="El doctor está disponible (Activo o En guardia)" />
        <Fila ok={r.t} formula="t" texto="El rostro del doctor fue verificado" />
        <Fila ok={r.u} formula="u" texto="La ambulancia está Disponible" />
        <Fila ok={r.v} neutro formula="v" texto="La ambulancia es Avanzada" />
        <Fila ok={r.doctorHabilitado} formula="D = s ∧ t" texto="Doctor habilitado" />
        <Fila ok={r.ambulanciaAdecuada} formula="M = u ∧ (p → v)" texto="Ambulancia adecuada" />
      </ul>
      {r.motivos.length > 0 && (
        <ul className="field-hint warn" style={{ margin: 0, paddingLeft: 18 }}>
          {r.motivos.map((m) => <li key={m}>{m}</li>)}
        </ul>
      )}
    </div>
  )
}
