import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Ambulance, HeartPulse, MapPin, Phone, Siren, Stethoscope, UserRound, Users } from 'lucide-react'
import { ESTADO_INFO, fmtHoraCorta } from '../../lib/flota.js'
import { portalParamedico } from '../../lib/portal.js'

// «Mi turno» del paramédico: la emergencia a la que lo mandó la central (paciente, dirección,
// avance) y con quién va. La ambulancia no se elige: es la de la emergencia. Los signos
// vitales y la atención se capturan en «Salud» (pages/paramedico/Salud.jsx).
// Se actualiza solo cada 30 s.

const AVANCE = [
  { label: 'Salida', campo: 'hora_salida' },
  { label: 'En el lugar', campo: 'hora_llegada' },
  { label: 'Traslado', campo: 'hora_traslado' },
  { label: 'Cerrada', campo: 'hora_cierre' },
]

export function usePortalParamedico() {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const cargar = () => portalParamedico().then((d) => { setDatos(d); setError('') }).catch((e) => setError(e.message))
    cargar()
    const t = setInterval(cargar, 30000)
    return () => clearInterval(t)
  }, [])
  return [datos, setDatos, error]
}

export default function MiAtencion() {
  const [datos, , error] = usePortalParamedico()
  if (error && !datos) return <p className="form-error">{error}</p>
  if (!datos) return <p className="muted">Cargando tu turno…</p>

  const pm = datos.paramedico
  const em = datos.emergencia
  return (
    <div className="op-turno">
      <section className="op-saludo">
        {datos.foto ? <img src={datos.foto} alt="" /> : <span className="avatar pm-avatar"><Stethoscope size={22} /></span>}
        <div>
          <h1>Hola, {pm.nombre.split(' ')[0]}</h1>
          <p>{pm.nivel} · Turno {pm.turno}{pm.cedula ? ` · Cédula ${pm.cedula}` : ''}</p>
        </div>
      </section>

      {error && <p className="form-error">{error}</p>}

      {em ? (
        <section className="panel op-emergencia">
          <div className="op-em-head">
            <span className="op-em-alerta"><Siren size={18} aria-hidden="true" /></span>
            <div>
              <span className="op-eyebrow">Tu emergencia · {em.folio}</span>
              <h2>{em.descripcion}</h2>
            </div>
            <span className={`badge b-${(em.prioridad || '').toLowerCase()}`}>Prioridad {em.prioridad}</span>
          </div>

          <dl className="op-em-datos">
            <div><dt><UserRound size={13} /> Paciente</dt><dd>{em.paciente_nombre}{em.paciente_edad ? `, ${em.paciente_edad} años` : ''}{em.paciente_sexo && em.paciente_sexo !== 'Otro' ? ` · ${em.paciente_sexo}` : ''}</dd></div>
            <div><dt><MapPin size={13} /> Dirección</dt><dd>{em.direccion}</dd></div>
            {em.paciente_telefono && <div><dt><Phone size={13} /> Teléfono</dt><dd><a href={`tel:${em.paciente_telefono}`}>{em.paciente_telefono}</a></dd></div>}
            {em.hospital_destino && <div><dt><Ambulance size={13} /> Hospital destino</dt><dd>{em.hospital_destino}</dd></div>}
          </dl>

          {em.prioridad_motivos?.length > 0 && (
            <p className="rd-alarma"><strong>Señales de alarma que reportaron:</strong> {em.prioridad_motivos.join(' · ')}</p>
          )}

          <ol className="op-pasos">
            {AVANCE.map((p) => (
              <li key={p.campo} className={em[p.campo] ? 'hecho' : ''}>
                <span className="op-paso-punto" aria-hidden="true" />
                <span>{p.label}</span>
                <small>{em[p.campo] ? fmtHoraCorta(em[p.campo]) : ''}</small>
              </li>
            ))}
          </ol>

          <Link to="/salud" className="btn-primary pm-ir-salud"><HeartPulse size={17} /> Anotar signos vitales y atención</Link>
        </section>
      ) : (
        <section className="panel op-sin-emergencia">
          <Siren size={22} aria-hidden="true" />
          <div>
            <strong>Sin emergencia por ahora</strong>
            <p>Cuando la central te mande a una emergencia (mirando a la cámara para confirmar que eres tú), aquí aparecen el paciente, la dirección y tu ambulancia. Esta pantalla se actualiza sola.</p>
          </div>
        </section>
      )}

      {em && <MiEquipo datos={datos} />}
    </div>
  )
}

function MiEquipo({ datos }) {
  const a = datos.ambulancia
  const info = a ? (ESTADO_INFO[a.estado] ?? ESTADO_INFO.Libre) : null
  return (
    <section className="panel op-ambulancia">
      <h2 className="form-section-title titulo-icono"><Users size={15} /> Con quién vas</h2>
      {a ? (
        <div className="op-amb-fila">
          <div className="op-amb-placa">
            <strong>{a.placa}</strong>
            <span>{a.tipo} · {a.hospital}{a.vehiculo ? ` · ${a.vehiculo}` : ''}</span>
          </div>
          <span className="flota-chip op-chip" style={{ color: info.color, background: info.fondo }}>{a.estado}</span>
        </div>
      ) : <p className="muted">La central todavía no asigna la ambulancia de esta emergencia.</p>}
      <dl className="op-em-datos">
        <div>
          <dt><Ambulance size={13} /> Operador (maneja)</dt>
          <dd>{datos.conductor ? <>{datos.conductor.nombre}{datos.conductor.celular ? <> · <a href={`tel:${datos.conductor.celular}`}>{datos.conductor.celular}</a></> : null}</> : 'Sin operador todavía'}</dd>
        </div>
        <div>
          <dt><Stethoscope size={13} /> Otro paramédico</dt>
          <dd>{datos.companeros.length ? datos.companeros.map((c) => `${c.nombre} (${c.nivel})`).join(', ') : 'Falta que la central confirme al segundo'}</dd>
        </div>
      </dl>
    </section>
  )
}
