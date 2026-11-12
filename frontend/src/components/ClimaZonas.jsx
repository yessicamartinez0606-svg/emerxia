import { useEffect, useState } from 'react'
import { Cloud, CloudFog, CloudLightning, CloudRain, CloudSun, RefreshCw, Sun, Umbrella } from 'lucide-react'
import { fmtActualizado, simularLluvia, tipoCielo, verClima } from '../lib/clima.js'

const ICONO = { sol: Sun, nublado: CloudSun, niebla: CloudFog, lluvia: CloudRain, tormenta: CloudLightning, nada: Cloud }

// Clima de cada zona y cuánto se frena el tránsito por la lluvia.
// puedeSimular: el personal de la central puede simular lluvia para una demostración.
export default function ClimaZonas({ puedeSimular = false, compacto = false, onCambio }) {
  const [clima, setClima] = useState(null)
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState('')

  const cargar = () => verClima().then((c) => { setClima(c); setError('') }).catch((e) => setError(e.message))
  useEffect(() => {
    cargar()
    const t = setInterval(cargar, 5 * 60 * 1000)
    return () => clearInterval(t)
  }, [])

  const alternar = async (z) => {
    setOcupado(z.id)
    try {
      // Simulado con lluvia → quitar simulación; real → simular lo contrario de lo que hay.
      const sim = clima.simulacion?.[z.id]
      const r = await simularLluvia(z.id, sim === undefined ? !z.lluvia : null)
      setClima(r)
      onCambio?.(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setOcupado('')
    }
  }

  if (error && !clima) return <section className="panel clima"><p className="form-error">No se pudo consultar el clima: {error}</p></section>
  if (!clima) return <section className="panel clima muted">Consultando el clima de las zonas…</section>

  const hayLluvia = clima.con_lluvia.length > 0
  return (
    <section className={`panel clima${compacto ? ' compacto' : ''}`}>
      <header className="clima-head">
        <div>
          <h2 className="form-section-title titulo-icono"><Umbrella size={15} /> Clima y tránsito por zona</h2>
          <p className={`clima-mensaje${hayLluvia ? ' alerta' : ''}`}>{clima.mensaje}</p>
        </div>
        <button type="button" className="btn-ghost icon" title="Actualizar" aria-label="Actualizar clima" onClick={cargar}><RefreshCw size={14} /></button>
      </header>

      <ul className="clima-zonas">
        {clima.zonas.map((z) => {
          const Icono = ICONO[tipoCielo(z)]
          return (
            <li key={z.id} className={z.lluvia ? 'llueve' : ''}>
              <Icono size={compacto ? 20 : 24} aria-hidden="true" className="clima-icono" />
              <div className="clima-dato">
                <strong>{z.nombre}</strong>
                <span>{z.descripcion}{z.temperatura != null ? ` · ${Math.round(z.temperatura)} °C` : ''}</span>
                <em className={z.retraso_pct ? 'lento' : 'normal'}>
                  {z.retraso_pct ? `Tránsito ${z.retraso_pct} % más lento` : 'Tránsito normal'}
                  {z.simulado && <b className="clima-sim">simulado</b>}
                </em>
              </div>
              {puedeSimular && (
                <button type="button" className="btn-ghost clima-btn" disabled={ocupado === z.id} onClick={() => alternar(z)}>
                  {z.simulado ? 'Quitar simulación' : z.lluvia ? 'Simular despejado' : 'Simular lluvia'}
                </button>
              )}
            </li>
          )
        })}
      </ul>

      <p className="clima-fuente">
        Fuente: {clima.fuente}{clima.actualizado ? ` · actualizado ${fmtActualizado(clima.actualizado)}` : ''}
        {clima.error ? ` · ${clima.error}` : ''} · con lluvia la ambulancia va al 75 % de su velocidad; con tormenta, al 60 %.
      </p>
    </section>
  )
}
