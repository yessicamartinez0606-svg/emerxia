import { useEffect, useState } from 'react'
import { Historial } from '../../components/ControlAmbulancia.jsx'
import { portalOperador } from '../../lib/portal.js'

// Historial de la ambulancia del operador: emergencias, cargas, cambios de estatus.

export default function MiHistorial() {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { portalOperador().then(setDatos).catch((e) => setError(e.message)) }, [])

  if (error) return <p className="form-error">{error}</p>
  if (!datos) return <p className="muted">Cargando…</p>
  return (
    <>
      <header className="view-head">
        <div>
          <h1>Mi historial</h1>
          <p>{datos.ficha ? `Movimientos de ${datos.ficha.ambulancia.placa}` : 'No tienes una ambulancia asignada'}</p>
        </div>
      </header>
      {datos.ficha && <Historial filas={datos.ficha.historial} vacio="Todavía no hay movimientos de tu ambulancia." />}
    </>
  )
}
