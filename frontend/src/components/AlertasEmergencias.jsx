import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { BellRing, MessageSquare, Phone, Users, X } from 'lucide-react'
import { getToken } from '../lib/api.js'

// Avisos al instante en la central: en cuanto un usuario reporta una emergencia (o alguien
// más reporta la misma), aparece aquí con un sonido, sin recargar. El servidor se entera por
// los change streams de MongoDB (backend: routers/eventos.py) y lo manda por este flujo.
// También avisa al resto de la pantalla (evento «emergexia:emergencia») para que las listas
// se actualicen solas.

const MAX_AVISOS = 4

function sonar() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)()
    ;[0, 0.22].forEach((t) => {
      const o = ctx.createOscillator()
      const g = ctx.createGain()
      o.frequency.value = 880
      g.gain.setValueAtTime(0.0001, ctx.currentTime + t)
      g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + t + 0.02)
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + t + 0.18)
      o.connect(g).connect(ctx.destination)
      o.start(ctx.currentTime + t)
      o.stop(ctx.currentTime + t + 0.2)
    })
  } catch { /* sin audio (p. ej. el navegador lo bloquea hasta que la persona toca la página) */ }
}

// Lee el flujo text/event-stream con fetch (así puede llevar el token en el encabezado).
async function escuchar(señal, onEvento) {
  const res = await fetch('/api/eventos/emergencias', {
    headers: { Authorization: `Bearer ${getToken()}` }, signal: señal,
  })
  if (!res.ok || !res.body) throw new Error(`avisos: ${res.status}`)
  const lector = res.body.getReader()
  const dec = new TextDecoder()
  let resto = ''
  for (;;) {
    const { value, done } = await lector.read()
    if (done) break
    resto += dec.decode(value, { stream: true })
    const partes = resto.split('\n\n')
    resto = partes.pop()
    partes.forEach((p) => {
      const linea = p.split('\n').find((l) => l.startsWith('data: '))
      if (linea) {
        try { onEvento(JSON.parse(linea.slice(6))) } catch { /* evento mal formado: se ignora */ }
      }
    })
  }
}

export default function AlertasEmergencias() {
  const [avisos, setAvisos] = useState([])
  const [conectado, setConectado] = useState(false)
  const intentos = useRef(0)

  useEffect(() => {
    let vivo = true
    let control = new AbortController()
    const alEvento = (ev) => {
      if (ev.evento === 'listo') { setConectado(true); intentos.current = 0; return }
      if (ev.evento !== 'nueva' && ev.evento !== 'otro_reporte') return
      sonar()
      window.dispatchEvent(new CustomEvent('emergexia:emergencia', { detail: ev }))
      setAvisos((prev) => [{ ...ev, clave: `${ev.folio}-${ev.num_reportes}-${Date.now()}` }, ...prev].slice(0, MAX_AVISOS))
    }
    const conectar = async () => {
      while (vivo) {
        try {
          await escuchar(control.signal, alEvento)
        } catch { /* se cayó la conexión: se reintenta abajo */ }
        if (!vivo) break
        setConectado(false)
        // Reintento con espera creciente (2 s, 4 s, … hasta 30 s).
        const espera = Math.min(30000, 2000 * 2 ** intentos.current)
        intentos.current += 1
        await new Promise((r) => setTimeout(r, espera))
        control = new AbortController()
      }
    }
    conectar()
    return () => { vivo = false; control.abort() }
  }, [])

  const cerrar = (clave) => setAvisos((prev) => prev.filter((a) => a.clave !== clave))

  return (
    <div className="alertas" aria-live="assertive">
      {avisos.map((a) => (
        <div key={a.clave} className={`alerta-em ${(a.prioridad || '').toLowerCase()}`} role="alert">
          <span className="alerta-icono" aria-hidden="true">{a.evento === 'nueva' ? <BellRing size={18} /> : <Users size={18} />}</span>
          <div className="alerta-txt">
            <strong>
              {a.evento === 'nueva' ? 'Nueva emergencia' : `Otra persona reportó ${a.folio}`}
              {' · '}Prioridad {a.prioridad}
            </strong>
            <span>
              {a.folio} · {a.tipo}
              {a.reportante && <> · {a.canal === 'llamada' ? <Phone size={11} aria-hidden="true" /> : <MessageSquare size={11} aria-hidden="true" />} {a.canal === 'llamada' ? 'llamada' : 'mensaje'} de {a.reportante}</>}
            </span>
            <span className="alerta-dir">{a.direccion}</span>
            {a.prioridad_motivos?.length > 0 && <span className="alerta-alarma">{a.prioridad_motivos.join(' · ')}</span>}
            {a.evento === 'otro_reporte' && <span>Ya son {a.num_reportes} reportes.</span>}
            <Link to={`/emergencias/${a.id}`} className="btn-primary compact" onClick={() => cerrar(a.clave)}>Ver emergencia</Link>
          </div>
          <button type="button" className="alerta-cerrar" onClick={() => cerrar(a.clave)} aria-label="Cerrar aviso"><X size={15} /></button>
        </div>
      ))}
      <span className={`alertas-estado${conectado ? ' on' : ''}`} title={conectado ? 'Recibiendo avisos al instante' : 'Conectando los avisos…'}>
        <BellRing size={11} aria-hidden="true" /> {conectado ? 'Avisos al instante' : 'Conectando avisos…'}
      </span>
    </div>
  )
}
