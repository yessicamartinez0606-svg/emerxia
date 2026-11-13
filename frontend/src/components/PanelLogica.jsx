import { CheckCircle2, Zap } from 'lucide-react'
import { evaluarFormulario } from '../lib/logica.js'

const Fila = ({ texto }) => (
  <li className="field-hint ok" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
    <CheckCircle2 size={14} /> {texto}
  </li>
)

// Explica cómo se asignará la emergencia al guardarla. Ya no se eligen ambulancias ni
// operador a mano: el sistema los asigna solos (backend: routers/flota.py).
// La regla M = u ∧ (p → v) vive en lib/logica.js y en backend/app/logica.py.
export default function PanelLogica({ prioridad, requeridas }) {
  const { p } = evaluarFormulario({ prioridad })
  const n = Math.max(1, Number(requeridas) || 1)
  return (
    <div className="panel form-section">
      <h2 className="form-section-title titulo-icono"><Zap size={15} aria-hidden="true" /> Asignación automática</h2>
      <ul style={{ listStyle: 'none', padding: 0, margin: '8px 0', display: 'grid', gap: 4 }}>
        <Fila texto={`Al guardar se asigna${n > 1 ? `n ${n} ambulancias libres` : ' una ambulancia libre'}, con conductor y gasolina suficiente.`} />
        <Fila texto="Salen primero del Hospital IMSS 220; si no alcanzan, de los hospitales más cercanos." />
        <Fila texto={p ? 'Prioridad Alta: se eligen primero ambulancias Avanzadas.' : 'Se eligen primero las Avanzadas y con más gasolina.'} />
        <Fila texto="El operador a cargo es quien maneja la primera ambulancia, y la ve al instante en su app." />
        <Fila texto="Si no hay ambulancias libres, queda en espera y se asigna sola en cuanto se libere una." />
      </ul>
    </div>
  )
}
