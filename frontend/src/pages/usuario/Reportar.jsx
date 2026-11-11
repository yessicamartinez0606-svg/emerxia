import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, Crosshair, MessageSquare, Phone, Search } from 'lucide-react'
import MapaToluca from '../../components/MapaToluca.jsx'
import { useAuth } from '../../lib/auth.jsx'
import { buscarDireccion, enviarReporte, tiposEmergencia } from '../../lib/portal.js'

// Reportar una emergencia: por mensaje (formulario) o por llamada (se registra la ubicación
// y se marca a la central). El lugar se marca en el mapa, con el GPS o escribiendo la dirección.

const TOLUCA = [[19.25, -99.72], [19.33, -99.58]]

export default function Reportar() {
  const { user } = useAuth()
  const [catalogo, setCatalogo] = useState({ tipos: [], telefono_central: '911' })
  const [canal, setCanal] = useState('mensaje')
  const [tipo, setTipo] = useState('')
  const [punto, setPunto] = useState(null)        // { lat, lng, texto }
  const [direccion, setDireccion] = useState('')
  const [buscando, setBuscando] = useState(false)
  const [form, setForm] = useState({ descripcion: '', referencias: '', paciente_nombre: '', paciente_edad: '', telefono: user?.telefono ?? '', personas: 1 })
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const [listo, setListo] = useState(null)

  useEffect(() => { tiposEmergencia().then(setCatalogo).catch(() => {}) }, [])

  const miUbicacion = () => {
    setError('')
    if (!navigator.geolocation) { setError('Tu navegador no permite usar la ubicación. Marca el lugar en el mapa.'); return }
    navigator.geolocation.getCurrentPosition(
      (p) => setPunto({ lat: p.coords.latitude, lng: p.coords.longitude, texto: 'Mi ubicación' }),
      () => setError('No se pudo obtener tu ubicación. Revisa el permiso o marca el lugar en el mapa.'),
      { enableHighAccuracy: true, timeout: 10000 },
    )
  }

  const buscar = async (e) => {
    e.preventDefault()
    if (direccion.trim().length < 5) return
    setBuscando(true)
    setError('')
    try {
      const r = await buscarDireccion(direccion.trim())
      setPunto({ lat: r.lat, lng: r.lng, texto: direccion.trim() })
    } catch (err) {
      setError(err.message)
    } finally {
      setBuscando(false)
    }
  }

  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    setError('')
    try {
      const r = await enviarReporte({
        canal, tipo, ...form, personas: Number(form.personas) || 1,
        lat: punto?.lat ?? null, lng: punto?.lng ?? null,
        direccion: punto?.texto && punto.texto !== 'Mi ubicación' && punto.texto !== 'Punto marcado' ? punto.texto : direccion.trim(),
      })
      setListo(r)
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  if (listo) {
    return (
      <section className="panel us-listo">
        <CheckCircle2 size={34} aria-hidden="true" />
        <h1>Reporte enviado · {listo.folio}</h1>
        <p>La central ya recibió tu emergencia en <strong>{listo.direccion}</strong>. Te avisaremos aquí cuando salga la ambulancia.</p>
        {canal === 'llamada' && (
          <a className="btn-primary us-llamar" href={`tel:${catalogo.telefono_central}`}>
            <Phone size={17} /> Llamar al {catalogo.telefono_central}
          </a>
        )}
        <p className="muted">Si no se abre la llamada, marca al {catalogo.telefono_central} desde tu teléfono.</p>
        <div className="us-listo-acciones">
          <Link className="btn-ghost tall" to="/mis-reportes">Ver cómo va</Link>
          <button type="button" className="btn-ghost tall" onClick={() => { setListo(null); setPunto(null); setTipo('') }}>Reportar otra</button>
        </div>
      </section>
    )
  }

  const listoParaEnviar = tipo && (punto || direccion.trim().length >= 5)

  return (
    <form className="us-reportar" onSubmit={enviar}>
      <header className="view-head">
        <div>
          <h1>Reportar una emergencia</h1>
          <p>Si hay peligro inmediato, llama al {catalogo.telefono_central}.</p>
        </div>
      </header>

      <div className="us-canales" role="radiogroup" aria-label="Cómo quieres reportar">
        <button type="button" role="radio" aria-checked={canal === 'mensaje'} className={`us-canal${canal === 'mensaje' ? ' on' : ''}`} onClick={() => setCanal('mensaje')}>
          <MessageSquare size={22} aria-hidden="true" />
          <strong>Por mensaje</strong>
          <span>Llena los datos y la central te contacta</span>
        </button>
        <button type="button" role="radio" aria-checked={canal === 'llamada'} className={`us-canal${canal === 'llamada' ? ' on' : ''}`} onClick={() => setCanal('llamada')}>
          <Phone size={22} aria-hidden="true" />
          <strong>Por llamada</strong>
          <span>Mandamos tu ubicación y llamas a la central</span>
        </button>
      </div>

      <section className="panel us-paso">
        <h2 className="us-titulo"><span>1</span> ¿Dónde es?</h2>
        <div className="us-ubicacion">
          <button type="button" className="btn-ghost tall" onClick={miUbicacion}><Crosshair size={15} /> Usar mi ubicación</button>
          <div className="us-buscar">
            <Search size={15} aria-hidden="true" />
            <label htmlFor="us-dir" className="sr-only">Dirección</label>
            <input id="us-dir" placeholder="Calle, número, colonia y municipio" value={direccion}
              onChange={(e) => setDireccion(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') buscar(e) }} />
            <button type="button" className="btn-ghost" onClick={buscar} disabled={buscando || direccion.trim().length < 5}>{buscando ? 'Buscando…' : 'Buscar'}</button>
          </div>
        </div>
        <MapaToluca
          alto={320}
          onClick={(lat, lng) => setPunto({ lat, lng, texto: 'Punto marcado' })}
          marcadores={punto ? [{ id: 'p', lat: punto.lat, lng: punto.lng, tipo: 'emergencia', etiqueta: punto.texto }] : []}
          encuadre={punto ? [[punto.lat - 0.004, punto.lng - 0.004], [punto.lat + 0.004, punto.lng + 0.004]] : TOLUCA}
          etiquetaAccesible="Toca el mapa para marcar dónde es la emergencia"
        />
        <p className="field-hint">{punto ? 'Lugar marcado. Si no es exacto, toca otro punto del mapa.' : 'Toca el mapa en el lugar exacto de la emergencia.'}</p>
        <div className="field">
          <label htmlFor="us-ref">Referencias (opcional)</label>
          <input id="us-ref" className="input" placeholder="Ej. frente a la farmacia, portón verde" value={form.referencias} onChange={(e) => setForm({ ...form, referencias: e.target.value })} />
        </div>
      </section>

      <section className="panel us-paso">
        <h2 className="us-titulo"><span>2</span> ¿Qué pasó?</h2>
        <div className="us-tipos" role="radiogroup" aria-label="Tipo de emergencia">
          {catalogo.tipos.map((t) => (
            <button key={t} type="button" role="radio" aria-checked={tipo === t} className={`us-tipo${tipo === t ? ' on' : ''}`} onClick={() => setTipo(t)}>{t}</button>
          ))}
        </div>
        <div className="us-campos">
          <div className="field">
            <label htmlFor="us-personas">Personas afectadas</label>
            <input id="us-personas" className="input" type="number" min="1" max="50" value={form.personas} onChange={(e) => setForm({ ...form, personas: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="us-tel">Teléfono para contactarte</label>
            <input id="us-tel" className="input" inputMode="tel" value={form.telefono} onChange={(e) => setForm({ ...form, telefono: e.target.value })} placeholder="10 dígitos" />
          </div>
          <div className="field">
            <label htmlFor="us-pac">Nombre del paciente (si lo sabes)</label>
            <input id="us-pac" className="input" value={form.paciente_nombre} onChange={(e) => setForm({ ...form, paciente_nombre: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="us-edad">Edad aproximada</label>
            <input id="us-edad" className="input" inputMode="numeric" value={form.paciente_edad} onChange={(e) => setForm({ ...form, paciente_edad: e.target.value })} />
          </div>
        </div>
        {canal === 'mensaje' && (
          <div className="field">
            <label htmlFor="us-desc">Cuéntanos qué pasa</label>
            <textarea id="us-desc" className="input" rows={3} value={form.descripcion} onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
              placeholder="¿Está consciente? ¿Respira? ¿Sangra?" />
          </div>
        )}
      </section>

      {error && <p className="form-error">{error}</p>}
      <div className="us-enviar">
        <button className="btn-primary" disabled={enviando || !listoParaEnviar}>
          {canal === 'llamada' ? <><Phone size={17} /> {enviando ? 'Enviando…' : 'Enviar ubicación y llamar'}</> : <><MessageSquare size={17} /> {enviando ? 'Enviando…' : 'Enviar reporte'}</>}
        </button>
        {!listoParaEnviar && <span className="muted">Marca el lugar y elige qué pasó.</span>}
      </div>
    </form>
  )
}
