import { useEffect, useState } from 'react'
import { fmtFecha } from '../../lib/flota.js'
import { portalParamedico } from '../../lib/portal.js'

// Emergencias ya cerradas a las que fue el paramédico, con lo que se capturó.

export default function MisAtenciones() {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { portalParamedico().then(setDatos).catch((e) => setError(e.message)) }, [])

  if (error) return <p className="form-error">{error}</p>
  if (!datos) return <p className="muted">Cargando…</p>
  const filas = datos.atendidas
  return (
    <>
      <header className="view-head">
        <div>
          <h1>Mis atenciones</h1>
          <p>Emergencias que ya atendiste y lo que se anotó del paciente</p>
        </div>
      </header>
      <div className="panel table-wrap">
        {filas.length === 0 ? <p className="muted pad">Todavía no hay emergencias cerradas.</p> : (
          <table>
            <thead>
              <tr><th>Folio</th><th>Fecha</th><th>Paciente</th><th>Qué pasó</th><th>Signos</th><th>Atención que se dio</th><th>Hospital</th></tr>
            </thead>
            <tbody>
              {filas.map((e) => (
                <tr key={e.id}>
                  <td><strong>{e.folio}</strong></td>
                  <td>{fmtFecha(e.hora_cierre || e.created_at)}</td>
                  <td>{e.paciente_nombre}{e.paciente_edad ? `, ${e.paciente_edad}` : ''}</td>
                  <td>{e.descripcion}</td>
                  <td>
                    {[e.saturacion_oxigeno && `SpO₂ ${e.saturacion_oxigeno} %`, e.frecuencia_cardiaca && `${e.frecuencia_cardiaca} lpm`,
                      e.escala_glasgow && `Glasgow ${e.escala_glasgow}`, e.presion_arterial && `TA ${e.presion_arterial}`]
                      .filter(Boolean).join(' · ') || '—'}
                  </td>
                  <td>{e.observaciones_paramedico || '—'}{e.atendio_paramedico ? <span className="rd-sub-celda">{e.atendio_paramedico}</span> : null}</td>
                  <td>{e.hospital_destino || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
