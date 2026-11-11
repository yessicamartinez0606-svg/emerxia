import { useEffect, useState } from 'react'
import { CheckCircle2, Fuel, Gauge } from 'lucide-react'
import { colorGasolina, fmtDinero, fmtFecha, fmtLitros } from '../../lib/flota.js'
import { cargaOperador, portalOperador } from '../../lib/portal.js'

// Gasolina de la ambulancia del operador. Ya entró con su rostro, así que cada carga queda
// registrada a su nombre y como verificada con Face ID.

const VACIA = { litros: '', costo: '', kilometraje: '', estacion: '', notas: '' }

export default function Gasolina() {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [form, setForm] = useState(VACIA)
  const [guardando, setGuardando] = useState(false)
  const [aviso, setAviso] = useState('')

  useEffect(() => { portalOperador().then(setDatos).catch((e) => setError(e.message)) }, [])

  if (error && !datos) return <p className="form-error">{error}</p>
  if (!datos) return <p className="muted">Cargando…</p>
  if (!datos.ficha) return <p className="muted">No tienes una ambulancia asignada.</p>

  const { ficha, combustible_minimo: minimo } = datos
  const a = ficha.ambulancia
  const litros = (a.combustible_pct / 100) * a.tanque_litros
  const faltan = a.tanque_litros - litros
  const num = (v) => (v === '' ? null : Number(v))

  const enviar = async (e) => {
    e.preventDefault()
    setGuardando(true)
    setError('')
    setAviso('')
    try {
      const d = await cargaOperador({
        litros: Number(form.litros), costo: num(form.costo), kilometraje: num(form.kilometraje),
        estacion: form.estacion, notas: form.notas,
      })
      setDatos(d)
      setAviso(`Listo: cargaste ${fmtLitros(form.litros)}. Ahora tienes ${Math.floor(d.ficha.ambulancia.combustible_pct)} %.`)
      setForm(VACIA)
    } catch (err) {
      setError(err.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <div className="op-gasolina">
      <header className="view-head">
        <div>
          <h1>Gasolina · {a.placa}</h1>
          <p>Registra cada carga al salir de la gasolinera</p>
        </div>
      </header>

      <div className="control-amb-top">
        <section className="panel control-card">
          <h2 className="form-section-title titulo-icono"><Fuel size={15} /> Nivel actual</h2>
          <div className="gas-medidor">
            <div className="gas-tanque" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={a.combustible_pct} aria-label="Nivel de gasolina">
              <span style={{ height: `${a.combustible_pct}%`, background: colorGasolina(a.combustible_pct, minimo) }} />
              <b>{Math.floor(a.combustible_pct)}%</b>
            </div>
            <dl className="gas-datos">
              <dt>En el tanque</dt><dd>{fmtLitros(litros)} de {fmtLitros(a.tanque_litros)}</dd>
              <dt>Alcanza para</dt><dd>~{Math.round(litros * a.rendimiento_km_l)} km</dd>
              <dt>Le caben</dt><dd>{fmtLitros(faltan)}</dd>
              <dt>Kilometraje</dt><dd>{a.kilometraje.toLocaleString('es-MX')} km</dd>
            </dl>
          </div>
          {a.combustible_bajo && <p className="gas-alerta">Menos de {minimo} %: no te pueden mandar a emergencias hasta que cargues.</p>}
        </section>

        <form className="panel control-card" onSubmit={enviar}>
          <h2 className="form-section-title titulo-icono"><Gauge size={15} /> Registrar carga</h2>
          <p className="field-hint ok"><CheckCircle2 size={13} /> Se registra a tu nombre, verificado con tu rostro al entrar.</p>
          <div className="gas-campos">
            <div className="field">
              <label htmlFor="og-litros">Litros *</label>
              <input id="og-litros" className="input" type="number" inputMode="decimal" min="0.1" step="0.1" required
                value={form.litros} onChange={(e) => setForm({ ...form, litros: e.target.value })} placeholder={`Máx. ${Math.floor(faltan)}`} />
            </div>
            <div className="field">
              <label htmlFor="og-costo">Costo ($)</label>
              <input id="og-costo" className="input" type="number" inputMode="decimal" min="0" step="0.01" value={form.costo} onChange={(e) => setForm({ ...form, costo: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="og-km">Kilometraje</label>
              <input id="og-km" className="input" type="number" inputMode="numeric" min={a.kilometraje} value={form.kilometraje}
                placeholder={String(a.kilometraje)} onChange={(e) => setForm({ ...form, kilometraje: e.target.value })} />
            </div>
            <div className="field">
              <label htmlFor="og-estacion">Gasolinera</label>
              <input id="og-estacion" className="input" value={form.estacion} onChange={(e) => setForm({ ...form, estacion: e.target.value })} />
            </div>
          </div>
          {error && <p className="form-error">{error}</p>}
          {aviso && <p className="field-hint ok">{aviso}</p>}
          <button className="btn-primary" disabled={guardando || !form.litros}>{guardando ? 'Guardando…' : 'Registrar carga'}</button>
        </form>
      </div>

      <section className="panel">
        <h2 className="form-section-title titulo-icono">
          Mis cargas <span className="control-totales">{fmtLitros(ficha.litros_cargados)} · {fmtDinero(ficha.gasto_total)}</span>
        </h2>
        {!ficha.cargas.length ? <p className="muted">Todavía no hay cargas registradas.</p> : (
          <div className="table-wrap control-tabla">
            <table>
              <thead><tr><th>Fecha</th><th>Litros</th><th>Nivel</th><th>Costo</th><th>Km</th><th>Gasolinera</th></tr></thead>
              <tbody>
                {ficha.cargas.map((c) => (
                  <tr key={c.id}>
                    <td>{fmtFecha(c.created_at)}</td>
                    <td>{fmtLitros(c.litros)}</td>
                    <td>{Math.floor(c.combustible_antes)} % → {Math.floor(c.combustible_despues)} %</td>
                    <td>{fmtDinero(c.costo)}</td>
                    <td>{c.kilometraje != null ? c.kilometraje.toLocaleString('es-MX') : '—'}</td>
                    <td>{c.estacion || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
