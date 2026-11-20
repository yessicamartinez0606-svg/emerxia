import { useEffect, useMemo, useState } from 'react'
import { History, RefreshCw } from 'lucide-react'
import { TIPO_HISTORIAL, fmtFecha, obtenerHistorial } from '../lib/flota.js'

// Historial de toda la flota: estatus, asignaciones, salidas, cargas de gasolina, etc.

export default function HistorialPage() {
  const [filas, setFilas] = useState(null)
  const [error, setError] = useState('')
  const [tipo, setTipo] = useState('')
  const [texto, setTexto] = useState('')
  const [recarga, setRecarga] = useState(0)

  useEffect(() => {
    setError('')
    obtenerHistorial({ tipo, limite: 1000 }).then((d) => setFilas(d.items)).catch((e) => setError(e.message))
  }, [tipo, recarga])

  const visibles = useMemo(() => {
    const q = texto.trim().toLowerCase()
    if (!q) return filas ?? []
    return (filas ?? []).filter((f) =>
      [f.detalle, f.ambulancia, f.operador, f.emergencia, f.hospital].some((v) => (v ?? '').toLowerCase().includes(q)))
  }, [filas, texto])

  return (
    <section className="module-view historial-page">
      <header className="view-head">
        <div>
          <h1>Historial</h1>
          <p>Todo lo que pasa con las ambulancias: estatus, emergencias, conductores y gasolina</p>
        </div>
        <div className="head-actions">
          <button className="btn-ghost tall" onClick={() => setRecarga((n) => n + 1)}><RefreshCw size={15} /> Actualizar</button>
        </div>
      </header>

      <div className="panel historial-filtros">
        <label className="sr-only" htmlFor="hist-q">Buscar</label>
        <input id="hist-q" className="input" type="search" placeholder="Buscar por placa, operador, folio u hospital" value={texto} onChange={(e) => setTexto(e.target.value)} />
        <label className="sr-only" htmlFor="hist-tipo">Tipo de movimiento</label>
        <select id="hist-tipo" className="input" value={tipo} onChange={(e) => setTipo(e.target.value)}>
          <option value="">Todos los movimientos</option>
          {Object.entries(TIPO_HISTORIAL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      {error && <p className="form-error">{error}</p>}

      <div className="panel table-wrap">
        {filas === null && !error && <p className="muted pad">Cargando historial…</p>}
        {filas && visibles.length === 0 && (
          <div className="historial-vacio">
            <History size={22} aria-hidden="true" />
            <p>{filas.length ? 'Ningún movimiento coincide con la búsqueda.' : 'Todavía no hay movimientos. Aparecen aquí al asignar ambulancias, cambiar su estatus o cargar gasolina.'}</p>
          </div>
        )}
        {visibles.length > 0 && (
          <table className="historial-tabla">
            <thead>
              <tr><th>Fecha</th><th>Movimiento</th><th>Detalle</th><th>Ambulancia</th><th>Operador</th><th>Emergencia</th></tr>
            </thead>
            <tbody>
              {visibles.map((f) => (
                <tr key={f.id}>
                  <td className="nowrap">{fmtFecha(f.created_at)}</td>
                  <td><span className={`h-chip h-${f.tipo}`}>{TIPO_HISTORIAL[f.tipo] ?? f.tipo}</span></td>
                  <td className="wrap">{f.detalle}</td>
                  <td>{f.ambulancia || '—'}</td>
                  <td>{f.operador || '—'}</td>
                  <td>{f.emergencia || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {filas && <p className="source-note">{visibles.length} movimiento(s)</p>}
      </div>
    </section>
  )
}
