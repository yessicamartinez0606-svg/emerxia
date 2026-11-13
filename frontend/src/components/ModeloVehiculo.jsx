import { useEffect, useState } from 'react'
import { modelosVehiculo } from '../lib/flota.js'

// Selector de modelo para el formulario de Ambulancias: pide a la API vPIC (vía backend)
// los modelos reales de la marca y el año elegidos. Al elegir uno, avisa su ficha técnica
// (tanque, rendimiento, motor y tipo sugerido) para llenar los demás campos.
export default function ModeloVehiculo({ id, marca, anio, value, onElegir }) {
  const [r, setR] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!marca || !anio) return undefined
    let vigente = true
    setR(null)
    setError('')
    modelosVehiculo(marca, anio)
      .then((x) => {
        if (!vigente) return
        setR(x)
        // Si solo hay un modelo (o el elegido ya no existe para ese año), se elige el primero.
        if (x.modelos.length && !x.modelos.some((m) => m.modelo === value)) onElegir(x.modelos[0])
      })
      .catch((e) => vigente && setError(e.message))
    return () => { vigente = false }
  }, [marca, anio]) // eslint-disable-line react-hooks/exhaustive-deps

  if (error) return <p className="field-hint warn">No se pudieron consultar los modelos: {error}</p>
  return (
    <>
      <select id={id} className="input" value={value} disabled={!r}
              onChange={(e) => onElegir(r.modelos.find((m) => m.modelo === e.target.value))}>
        {!r && <option value="">Consultando la API…</option>}
        {r && r.modelos.length === 0 && <option value="">Sin modelos de ambulancia ese año</option>}
        {r?.modelos.map((m) => <option key={m.modelo} value={m.modelo}>{m.modelo}</option>)}
      </select>
      {r && (
        <p className={`field-hint${r.aviso ? ' warn' : ' ok'}`}>
          {r.aviso || `${r.fuente}: ${r.total_modelos_marca} modelos de ${r.marca} en ${r.anio}; ${r.modelos.length} sirven de ambulancia.`}
          {r.modelos[0] && ` Motor ${r.modelos[0].motor}, tanque ${r.modelos[0].tanque_litros} L.`}
        </p>
      )}
    </>
  )
}
