import { useEffect, useState } from 'react'
import { Brain, CheckCircle2, AlertTriangle } from 'lucide-react'
import { api } from '../lib/api.js'

// Triage con Machine Learning (backend/app/ml): con los signos vitales del paciente,
// el modelo sugiere si la emergencia requiere ambulancia Avanzada. Es solo una sugerencia:
// los signos vitales no se guardan y la decisión final es del despachador / personal médico.
const CAMPOS = [
  { key: 'edad', label: 'Edad (años)', min: 0, max: 120 },
  { key: 'frecuencia_cardiaca', label: 'Frecuencia cardiaca (lpm)', min: 20, max: 250 },
  { key: 'saturacion_oxigeno', label: 'Saturación de oxígeno (%)', min: 50, max: 100 },
  { key: 'presion_sistolica', label: 'Presión sistólica (mmHg)', min: 40, max: 260 },
  { key: 'glasgow', label: 'Glasgow (3 a 15)', min: 3, max: 15 },
]

const INICIAL = { edad: '', frecuencia_cardiaca: '80', saturacion_oxigeno: '97', presion_sistolica: '120', glasgow: '15', dolor_toracico: false }

export default function PanelTriageML({ edadPaciente, ambulancia }) {
  const [signos, setSignos] = useState(INICIAL)
  const [resultado, setResultado] = useState(null)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  // La edad se toma del formulario del paciente mientras no la cambien aquí.
  useEffect(() => {
    if (edadPaciente && /^\d+$/.test(String(edadPaciente).trim())) {
      setSignos((s) => ({ ...s, edad: String(edadPaciente).trim() }))
    }
  }, [edadPaciente])

  const cambiar = (key, value) => {
    setSignos({ ...signos, [key]: value })
    setResultado(null)
  }

  async function calcular() {
    setError('')
    const faltan = CAMPOS.filter((c) => signos[c.key] === '' || Number.isNaN(Number(signos[c.key])))
    if (faltan.length) {
      setError(`Completa: ${faltan.map((c) => c.label).join(', ')}.`)
      return
    }
    setCargando(true)
    try {
      const body = Object.fromEntries(CAMPOS.map((c) => [c.key, Number(signos[c.key])]))
      body.dolor_toracico = signos.dolor_toracico
      setResultado(await api('/ml/predecir', { method: 'POST', body }))
    } catch (e) {
      setError(e.message)
    } finally {
      setCargando(false)
    }
  }

  const contradice = resultado?.requiere_avanzada && ambulancia && ambulancia.tipo !== 'Avanzada'

  return (
    <div className="panel form-section">
      <h2 className="form-section-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Brain size={16} /> Triage con Machine Learning
      </h2>
      <p className="field-hint" style={{ marginTop: 0, marginBottom: 12 }}>
        Captura los signos vitales y el modelo sugiere el tipo de ambulancia. Estos datos no se guardan.
      </p>

      <div className="form-grid">
        {CAMPOS.map((c) => (
          <div className="field" key={c.key}>
            <label htmlFor={`ml-${c.key}`}>{c.label}</label>
            <input id={`ml-${c.key}`} className="input" type="number" min={c.min} max={c.max}
                   value={signos[c.key]} onChange={(e) => cambiar(c.key, e.target.value)} />
          </div>
        ))}
        <div className="field">
          <label htmlFor="ml-dolor">Dolor torácico</label>
          <select id="ml-dolor" className="input" value={signos.dolor_toracico ? 'Sí' : 'No'}
                  onChange={(e) => cambiar('dolor_toracico', e.target.value === 'Sí')}>
            <option>No</option>
            <option>Sí</option>
          </select>
        </div>
      </div>

      <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <button type="button" className="btn-primary compact" onClick={calcular} disabled={cargando}>
          {cargando ? 'Calculando…' : 'Sugerir ambulancia'}
        </button>
        {error && <span className="field-hint warn" style={{ margin: 0 }}>{error}</span>}
      </div>

      {resultado && (
        <div style={{ marginTop: 12 }}>
          <p className={`field-hint ${resultado.requiere_avanzada ? 'warn' : 'ok'}`} style={{ fontSize: 13 }}>
            {resultado.requiere_avanzada ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
            <strong>{resultado.recomendacion}</strong>
            &nbsp;· probabilidad de requerir Avanzada {(resultado.probabilidad * 100).toFixed(0)} %
          </p>
          {contradice && (
            <p className="field-hint warn">
              La ambulancia elegida ({ambulancia.placa}) es {ambulancia.tipo}; el modelo sugiere una Avanzada.
            </p>
          )}
          <p className="field-hint">
            Modelo: {resultado.algoritmo} · recall en prueba {(resultado.recall_prueba * 100).toFixed(0)} %. {resultado.aviso}
          </p>
        </div>
      )}
    </div>
  )
}
