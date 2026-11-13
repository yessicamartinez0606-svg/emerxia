import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Activity, AlarmClock, ArrowLeft, ChevronDown, Hospital, Info, MapPin, Shapes, ShieldCheck, Sparkles, Timer,
} from 'lucide-react'
import { api } from '../lib/api.js'
import ClimaZonas from '../components/ClimaZonas.jsx'
import {
  COLOR_PERFIL, aTiempoEmergencia, estimarATiempo, estimarLlegada, estimarSegmentacion, estimarTriaje, llegadaEmergencia,
  modeloATiempo, modeloLlegada, modeloSegmentacion, modeloTriaje, pct, segmentacionEmergencia, triajeEmergencia, verOptimizacion,
} from '../lib/clima.js'
import ATiempoPanel from './ia/ATiempoPanel.jsx'
import DespachoPage from './DespachoPage.jsx'
import LlegadaPanel from './ia/LlegadaPanel.jsx'
import OptimizacionPanel from './ia/OptimizacionPanel.jsx'
import SegmentacionPanel from './ia/SegmentacionPanel.jsx'
import TriajePanel from './ia/TriajePanel.jsx'

// Asistente de despacho (modelos de inteligencia artificial), explicado para cualquier persona:
// cada herramienta responde una pregunta de la central, dice dónde aparece, se puede probar con
// datos sencillos y dice qué tan confiable es. Lo técnico queda dentro de «Ver detalles técnicos».
// Se abre desde cada emergencia en curso (/asistente?emergencia=ID) y llega lleno con sus datos.

const HERRAMIENTAS = [
  {
    key: 'llegada', icono: Timer, titulo: 'Tiempo de llegada', pregunta: '¿Cuánto tarda la ambulancia en llegar?',
    explicacion: 'Calcula en cuántos minutos llega la ambulancia según la distancia, la hora del día, si está lloviendo y la zona. Aprendió de servicios anteriores, por eso considera cosas que una cuenta simple no ve, como la hora pico.',
    donde: ['Reporte de cada emergencia («Llegada estimada»)', 'App del operador, en su emergencia'],
  },
  {
    key: 'a-tiempo', icono: AlarmClock, titulo: '¿Llega a tiempo?', pregunta: '¿Llegará en 15 minutos o menos?',
    explicacion: 'Antes de que salga la ambulancia avisa si probablemente llegará tarde, para pedir apoyo a otro hospital a tiempo. Se fija en la distancia, el tráfico, cuántas ambulancias hay libres y la experiencia del operador.',
    donde: ['Reporte de cada emergencia («¿Llega a tiempo?»)', 'App del operador'],
  },
  {
    key: 'triaje', icono: Activity, titulo: 'Prioridad del paciente', pregunta: '¿Qué emergencia atender primero?',
    explicacion: 'Con los signos vitales del paciente (oxigenación, pulso, nivel de conciencia y edad) estima si la emergencia es crítica. Así, cuando no alcanzan las ambulancias, las críticas se atienden primero.',
    donde: ['Inicio, en «Emergencias por atender» (las críticas suben)', 'Reporte de cada emergencia («Prioridad del paciente»)', 'Reparto automático de ambulancias'],
  },
  {
    key: 'perfiles', icono: Shapes, titulo: 'Tipo de servicio', pregunta: '¿Qué tan complicado será este servicio?',
    explicacion: 'Agrupa los servicios en tres tipos según la distancia, el tráfico, el tiempo y las ambulancias libres, y sugiere qué hacer con cada uno. Nadie le dijo cuáles eran los grupos: los descubrió sola comparando servicios parecidos.',
    donde: ['Reporte de cada emergencia («Tipo de servicio»)', 'App del operador'],
  },
  {
    key: 'despacho', icono: Hospital, titulo: 'Hospital de salida', pregunta: '¿De qué hospital conviene mandar la ambulancia?',
    explicacion: 'Marca un accidente en el mapa y el sistema prueba muchas combinaciones de hospitales (de dónde sale y a cuál regresa la ambulancia) hasta encontrar la ruta más corta, como si fuera evolucionando las mejores opciones.',
    donde: ['Aquí mismo, con la ubicación de la emergencia'],
  },
]

// Datos de la emergencia (si se abrió desde una): sus estimaciones ya calculadas.
function useEmergencia(id) {
  const [ctx, setCtx] = useState(null)
  useEffect(() => {
    if (!id) return
    const nada = () => null
    Promise.all([
      api('/emergencias').then((d) => (d.items || []).find((e) => String(e.id) === String(id)) || null).catch(nada),
      llegadaEmergencia(id).catch(nada), aTiempoEmergencia(id).catch(nada), triajeEmergencia(id).catch(nada),
      segmentacionEmergencia(id).catch(nada),
    ]).then(([em, llegada, aTiempo, triaje, perfil]) => setCtx({ em, llegada, aTiempo, triaje, perfil }))
  }, [id])
  return ctx
}

export default function TiempoLlegadaPage() {
  const [params] = useSearchParams()
  const emergenciaId = params.get('emergencia')
  const ctx = useEmergencia(emergenciaId)
  const [tab, setTab] = useState(() => {
    const pedida = params.get('tab')
    if (HERRAMIENTAS.some((h) => h.key === pedida)) return pedida
    try {
      const guardada = sessionStorage.getItem('ia.tab')
      return HERRAMIENTAS.some((h) => h.key === guardada) ? guardada : 'llegada'
    } catch { return 'llegada' }
  })
  const elegir = (k) => { setTab(k); try { sessionStorage.setItem('ia.tab', k) } catch { /* sin almacenamiento */ } }
  const h = HERRAMIENTAS.find((x) => x.key === tab)

  return (
    <section className="iah">
      <header className="view-head asistente-head">
        <div>
          {emergenciaId && (
            <Link to={`/emergencias/${emergenciaId}`} className="asistente-volver"><ArrowLeft size={15} aria-hidden="true" /> Volver a la emergencia</Link>
          )}
          <h1>Asistente de despacho{ctx?.em ? `: ${ctx.em.folio}` : ''}</h1>
          <p>
            {emergenciaId
              ? (ctx?.em ? `${ctx.em.descripcion} en ${ctx.em.direccion}. Las herramientas ya traen los datos de esta emergencia; puedes cambiarlos para comparar.` : 'Cargando los datos de la emergencia…')
              : 'Herramientas que aprendieron de servicios anteriores para ayudar a la central a decidir más rápido. Lo normal es abrirlo desde una emergencia en curso.'}
          </p>
        </div>
      </header>

      <div className="iah-herramientas" role="tablist" aria-label="Herramientas">
        {HERRAMIENTAS.map((x) => {
          const Icono = x.icono
          return (
            <button key={x.key} type="button" role="tab" aria-selected={tab === x.key} className={`iah-tool${tab === x.key ? ' on' : ''}`}
                    onClick={() => elegir(x.key)}>
              <span className="iah-tool-icono" aria-hidden="true"><Icono size={18} /></span>
              <span className="iah-tool-txt"><b>{x.titulo}</b><small>{x.pregunta}</small></span>
            </button>
          )
        })}
      </div>

      <p className="iah-aviso"><Info size={14} aria-hidden="true" /> Son herramientas de apoyo: aprendieron con datos de ejemplo y la decisión final siempre es de la central.</p>

      <Presentacion h={h} />

      {tab === 'llegada' && <Llegada ctx={ctx} />}
      {tab === 'a-tiempo' && <ATiempo ctx={ctx} />}
      {tab === 'triaje' && <Triaje ctx={ctx} />}
      {tab === 'perfiles' && <Perfiles ctx={ctx} />}
      {tab === 'despacho' && (emergenciaId && !ctx
        ? <div className="panel muted">Cargando la ubicación de la emergencia…</div>
        : <DespachoPage incrustado key={ctx?.em?.id ?? 'libre'}
            inicial={ctx?.em?.lat != null ? { lat: ctx.em.lat, lng: ctx.em.lng, texto: ctx.em.folio } : null} />)}
    </section>
  )
}

function Presentacion({ h }) {
  const Icono = h.icono
  return (
    <section className="panel iah-hero">
      <span className="iah-hero-icono" aria-hidden="true"><Icono size={24} /></span>
      <div className="iah-hero-txt">
        <h2>{h.pregunta}</h2>
        <p>{h.explicacion}</p>
        <div className="iah-donde">
          <span><MapPin size={13} aria-hidden="true" /> Dónde la ves:</span>
          {h.donde.map((d) => <em key={d}>{d}</em>)}
        </div>
      </div>
    </section>
  )
}

// ─────────────────────────── piezas comunes ───────────────────────────

function useCargar(fn) {
  const [d, setD] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => { fn().then(setD).catch((e) => setError(e.message)) }, []) // eslint-disable-line react-hooks/exhaustive-deps
  return [d, error]
}

function Prueba({ titulo = 'Pruébalo', descripcion, children }) {
  return (
    <section className="panel iah-prueba">
      <h3 className="iah-h3"><Sparkles size={15} aria-hidden="true" /> {titulo}</h3>
      {descripcion && <p className="iah-desc">{descripcion}</p>}
      {children}
    </section>
  )
}

function Resultado({ tono, titulo, detalle, cifra, cifraTexto }) {
  return (
    <div className={`iah-resultado ${tono}`} role="status">
      {cifra != null && <div className="iah-cifra"><b>{cifra}</b><span>{cifraTexto}</span></div>}
      <div>
        <strong>{titulo}</strong>
        {detalle && <p>{detalle}</p>}
      </div>
    </div>
  )
}

function Factores({ items, nota }) {
  if (!items?.length) return null
  const max = Math.max(...items.map((i) => i.peso))
  return (
    <section className="panel">
      <h3 className="iah-h3">¿En qué se fija más?</h3>
      <ul className="iah-factores">
        {items.map((i) => (
          <li key={i.factor}>
            <span>{i.factor}</span>
            <div className="iah-barra"><i style={{ width: `${(i.peso / max) * 100}%` }} /></div>
          </li>
        ))}
      </ul>
      {nota && <p className="iah-nota">{nota}</p>}
    </section>
  )
}

function Confianza({ grande, texto, nota }) {
  return (
    <section className="panel iah-confianza">
      <h3 className="iah-h3"><ShieldCheck size={15} aria-hidden="true" /> ¿Qué tan confiable es?</h3>
      <div className="iah-conf"><b>{grande}</b><p>{texto}</p></div>
      {nota && <p className="iah-nota">{nota}</p>}
    </section>
  )
}

function Tecnico({ children }) {
  return (
    <details className="iah-tecnico">
      <summary><ChevronDown size={16} aria-hidden="true" /> Ver detalles técnicos <small>Métricas, gráficas y cómo se entrenó el modelo</small></summary>
      <div className="iah-tecnico-cuerpo">{children}</div>
    </details>
  )
}

const hora12 = (h) => `${((h + 11) % 12) + 1}:00 ${h < 12 ? 'a. m.' : 'p. m.'}`
const NIVEL_TRAFICO = [
  { valor: 1.5, texto: 'Libre (de madrugada)' },
  { valor: 4.5, texto: 'Normal' },
  { valor: 7.5, texto: 'Pesado (hora pico)' },
  { valor: 9.5, texto: 'Muy pesado (lluvia u obras)' },
]
const NOMBRE_FACTOR = {
  'Hora exacta': 'Hora del día', 'Experiencia del operador': 'Experiencia del operador',
  'Ambulancias libres': 'Ambulancias libres', 'Nivel de tráfico': 'Tráfico',
}
const legible = (items) => (items || []).map((i) => ({ ...i, factor: NOMBRE_FACTOR[i.factor] || i.factor.replace('Zona ', 'Zona: ') }))

// ─────────────────────────── Tiempo de llegada ───────────────────────────

function Llegada({ ctx }) {
  const [ev, error] = useCargar(modeloLlegada)
  const [f, setF] = useState({ zona: 'Metepec', distancia_km: 7, hora: 8, fin_de_semana: false, lluvia: 'actual' })
  const [r, setR] = useState(null)
  useEffect(() => {
    const c = ctx?.llegada
    if (!c) return
    setF({ zona: c.zona, distancia_km: c.distancia_km, hora: c.hora, fin_de_semana: !!c.fin_de_semana, lluvia: c.lluvia ? 'si' : 'no' })
    setR(c)
  }, [ctx])
  const [msg, setMsg] = useState('')
  const cambiar = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))
  const calcular = async (e) => {
    e.preventDefault()
    setMsg('')
    try {
      setR(await estimarLlegada({ zona: f.zona, distancia_km: Number(f.distancia_km), hora: Number(f.hora), fin_de_semana: f.fin_de_semana,
        lluvia: f.lluvia === 'actual' ? null : f.lluvia === 'si' }))
    } catch (err) { setMsg(err.message) }
  }

  return (
    <>
      <ClimaZonas compacto puedeSimular />
      <div className="iah-grid">
        <Prueba descripcion="Escribe a dónde va la ambulancia y a qué hora sale.">
          <form className="iah-form" onSubmit={calcular}>
            <label>¿A qué zona va?
              <select value={f.zona} onChange={cambiar('zona')}>{(ev?.zonas || ['Metepec']).map((z) => <option key={z}>{z}</option>)}</select>
            </label>
            <label>Distancia desde el hospital (km)
              <input type="number" min="0.5" max="100" step="0.5" value={f.distancia_km} onChange={cambiar('distancia_km')} />
            </label>
            <label>Hora de salida
              <select value={f.hora} onChange={cambiar('hora')}>{Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{hora12(h)}</option>)}</select>
            </label>
            <label>¿Está lloviendo?
              <select value={f.lluvia} onChange={cambiar('lluvia')}>
                <option value="actual">Usar el clima de ahorita</option><option value="si">Sí</option><option value="no">No</option>
              </select>
            </label>
            <label className="check"><input type="checkbox" checked={f.fin_de_semana} onChange={cambiar('fin_de_semana')} /> Es fin de semana</label>
            <button className="btn-primary compact">Calcular</button>
          </form>
          {msg && <p className="form-error">{msg}</p>}
          {r && (
            <Resultado tono={r.cumple_meta ? 'bien' : 'mal'} cifra={`${Math.round(r.modelo_min)} min`} cifraTexto="tiempo estimado"
              titulo={r.cumple_meta ? `Llega dentro de la meta de ${r.meta_min} minutos` : `Tardaría más de ${r.meta_min} minutos: conviene mandar la unidad más cercana`}
              detalle={`${[r.hora_pico && 'Es hora pico', r.lluvia && 'está lloviendo'].filter(Boolean).join(' y ') || 'Sin hora pico ni lluvia'}. Una cuenta simple que solo usa la distancia diría ${Math.round(r.formula_min)} min.`} />
          )}
        </Prueba>
        <div className="iah-lado">
          {ev && <Confianza grande={`± ${Math.round(ev.calificacion.modelo.mae * 10) / 10} min`}
                            texto={`Es lo que se equivoca en promedio. Una cuenta simple (solo distancia) se equivoca por ${Math.round(ev.calificacion.formula.mae * 10) / 10} min.`} />}
          {ev && <Factores items={legible(ev.importancias)} nota="La distancia es lo que más pesa; la hora pico y la lluvia hacen que tarde más." />}
          {error && <p className="form-error">{error}</p>}
        </div>
      </div>
      <Tecnico><LlegadaPanel /></Tecnico>
    </>
  )
}

// ─────────────────────────── ¿Llega a tiempo? ───────────────────────────

function ATiempo({ ctx }) {
  const [ev, error] = useCargar(modeloATiempo)
  const [f, setF] = useState({ distancia_km: 9.5, nivel_trafico: 7.5, ambulancias_libres: 1, experiencia_operador: 3 })
  const [r, setR] = useState(null)
  useEffect(() => {
    const c = ctx?.aTiempo
    if (!c) return
    const cercano = NIVEL_TRAFICO.reduce((a, b) => (Math.abs(b.valor - c.datos.nivel_trafico) < Math.abs(a.valor - c.datos.nivel_trafico) ? b : a))
    setF({ ...c.datos, nivel_trafico: cercano.valor })
    setR(c)
  }, [ctx])
  const [msg, setMsg] = useState('')
  const cambiar = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const calcular = async (e) => {
    e.preventDefault()
    setMsg('')
    try { setR(await estimarATiempo(Object.fromEntries(Object.entries(f).map(([k, v]) => [k, Number(v)])))) } catch (err) { setMsg(err.message) }
  }
  const aciertos = ev ? Math.round(ev.prueba.exactitud * 100) : null

  return (
    <>
      <div className="iah-grid">
        <Prueba descripcion="Describe la emergencia como si la estuvieras asignando.">
          <form className="iah-form" onSubmit={calcular}>
            <label>Distancia al lugar (km)
              <input type="number" min="0.5" max="100" step="0.5" value={f.distancia_km} onChange={cambiar('distancia_km')} />
            </label>
            <label>¿Cómo está el tráfico?
              <select value={f.nivel_trafico} onChange={cambiar('nivel_trafico')}>{NIVEL_TRAFICO.map((n) => <option key={n.valor} value={n.valor}>{n.texto}</option>)}</select>
            </label>
            <label>Ambulancias libres en el hospital
              <input type="number" min="0" max="50" value={f.ambulancias_libres} onChange={cambiar('ambulancias_libres')} />
            </label>
            <label>Años de experiencia del operador
              <input type="number" min="0" max="50" step="1" value={f.experiencia_operador} onChange={cambiar('experiencia_operador')} />
            </label>
            <button className="btn-primary compact">Revisar</button>
          </form>
          {msg && <p className="form-error">{msg}</p>}
          {r && (
            <Resultado tono={r.llega_a_tiempo ? 'bien' : 'mal'} cifra={pct(r.probabilidad)} cifraTexto="probabilidad de llegar a tiempo"
              titulo={r.llega_a_tiempo ? 'Sí, llegará a tiempo' : 'Probablemente llegue tarde'}
              detalle={r.llega_a_tiempo ? `Debería llegar en ${r.umbral_min} minutos o menos.` : 'Considera pedir apoyo al hospital más cercano.'} />
          )}
        </Prueba>
        <div className="iah-lado">
          {ev && <Confianza grande={`${aciertos} de 100`} texto="emergencias de prueba las predijo bien (a tiempo o tarde)."
                            nota="Cuando se equivoca, lo más delicado es decir «llegará a tiempo» y que no sea así; por eso conviene revisar el aviso." />}
          {ev && <Factores items={legible(ev.importancias)} />}
          {error && <p className="form-error">{error}</p>}
        </div>
      </div>
      <Tecnico><ATiempoPanel sinSimulador /></Tecnico>
    </>
  )
}

// ─────────────────────────── Prioridad del paciente ───────────────────────────

function Triaje({ ctx }) {
  const [ev, error] = useCargar(modeloTriaje)
  const [opt] = useCargar(verOptimizacion)
  const [f, setF] = useState({ saturacion_oxigeno: 84, frecuencia_cardiaca: 132, escala_glasgow: 10, edad: 71 })
  const [r, setR] = useState(null)
  useEffect(() => {
    const c = ctx?.triaje
    if (!c || c.sin_signos) return
    setF(c.signos)
    setR(c)
  }, [ctx])
  const [msg, setMsg] = useState('')
  const cambiar = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const calcular = async (e) => {
    e.preventDefault()
    setMsg('')
    try { setR(await estimarTriaje(Object.fromEntries(Object.entries(f).map(([k, v]) => [k, Number(v)])))) } catch (err) { setMsg(err.message) }
  }
  const prueba = opt?.estado === 'listo' ? opt.prueba : ev?.prueba
  const aciertos = prueba ? Math.round(prueba.exactitud * 100) : null

  return (
    <>
      <div className="iah-grid">
        <Prueba descripcion={ctx?.triaje?.sin_signos ? 'Esta emergencia no tiene signos vitales capturados. Escríbelos aquí para probar, o captúralos al editar la emergencia.' : 'Escribe los signos vitales que reportan del paciente.'}>
          <form className="iah-form" onSubmit={calcular}>
            <label>Oxigenación (SpO₂ %)
              <input type="number" min="50" max="100" value={f.saturacion_oxigeno} onChange={cambiar('saturacion_oxigeno')} />
              <small>Normal: 95 a 100 %</small>
            </label>
            <label>Pulso (latidos por minuto)
              <input type="number" min="20" max="250" value={f.frecuencia_cardiaca} onChange={cambiar('frecuencia_cardiaca')} />
              <small>Normal en reposo: 60 a 100</small>
            </label>
            <label>Nivel de conciencia (Glasgow)
              <input type="number" min="3" max="15" value={f.escala_glasgow} onChange={cambiar('escala_glasgow')} />
              <small>15 = despierto y orientado · 3 = inconsciente</small>
            </label>
            <label>Edad
              <input type="number" min="0" max="120" value={f.edad} onChange={cambiar('edad')} />
            </label>
            <button className="btn-primary compact">Evaluar</button>
          </form>
          {msg && <p className="form-error">{msg}</p>}
          {r && (
            <Resultado tono={r.critica ? 'mal' : 'bien'} cifra={pct(r.probabilidad)} cifraTexto="probabilidad de que sea crítica"
              titulo={r.critica ? 'Crítica: atender de inmediato' : 'No crítica: puede esperar si no hay ambulancias'}
              detalle="Es un apoyo para ordenar la fila; no sustituye la valoración del personal médico." />
          )}
        </Prueba>
        <div className="iah-lado">
          {prueba && <Confianza grande={`${aciertos} de 100`} texto="pacientes de prueba los clasificó bien (crítico o no crítico)."
                                nota="Se probaron cientos de configuraciones y se quedó la más precisa. Si duda, la central debe tratarlo como crítico." />}
          <section className="panel">
            <h3 className="iah-h3">¿En qué se fija?</h3>
            <ul className="iah-lista">
              <li><b>Oxigenación baja</b> → más riesgo</li>
              <li><b>Pulso</b> muy bajo o muy alto → más riesgo</li>
              <li><b>Nivel de conciencia</b> bajo → más riesgo</li>
              <li><b>Edad</b> mayor → un poco más de riesgo</li>
            </ul>
          </section>
          {error && <p className="form-error">{error}</p>}
        </div>
      </div>
      <Tecnico>
        <TriajePanel sinSimulador />
        <OptimizacionPanel />
      </Tecnico>
    </>
  )
}

// ─────────────────────────── Tipo de servicio ───────────────────────────

function Perfiles({ ctx }) {
  const [ev, error] = useCargar(modeloSegmentacion)
  const [f, setF] = useState({ distancia_km: 12.5, nivel_trafico: 7.5, tiempo_respuesta_min: 25, ambulancias_libres: 1 })
  const [r, setR] = useState(null)
  useEffect(() => {
    const c = ctx?.perfil
    if (!c) return
    const cercano = NIVEL_TRAFICO.reduce((a, b) => (Math.abs(b.valor - c.datos.nivel_trafico) < Math.abs(a.valor - c.datos.nivel_trafico) ? b : a))
    setF({ ...c.datos, nivel_trafico: cercano.valor })
    setR(c)
  }, [ctx])
  const [msg, setMsg] = useState('')
  const cambiar = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }))
  const calcular = async (e) => {
    e.preventDefault()
    setMsg('')
    try { setR(await estimarSegmentacion(Object.fromEntries(Object.entries(f).map(([k, v]) => [k, Number(v)])))) } catch (err) { setMsg(err.message) }
  }

  return (
    <>
      {ev && (
        <div className="iah-perfiles">
          {ev.perfiles.map((p, i) => (
            <article key={p.perfil} className="panel iah-perfil" style={{ '--c': COLOR_PERFIL[p.perfil] }}>
              <span className="iah-perfil-nivel" aria-hidden="true">{[0, 1, 2].map((n) => <i key={n} className={n <= i ? 'on' : ''} />)}</span>
              <h3>{p.perfil}</h3>
              <p className="iah-perfil-dato">Unos <b>{Math.round(p.promedio.tiempo_respuesta_min)} min</b> · {Math.round(p.promedio.distancia_km)} km de distancia</p>
              <p className="iah-perfil-que">{p.estrategia}</p>
              <small>{p.servicios} de {ev.servicios} servicios son de este tipo</small>
            </article>
          ))}
        </div>
      )}
      {error && <p className="form-error">{error}</p>}
      <div className="iah-grid">
        <Prueba titulo="¿Qué tipo de servicio es?" descripcion="Escribe los datos del servicio y te dice a cuál de los tres tipos se parece.">
          <form className="iah-form" onSubmit={calcular}>
            <label>Distancia (km)
              <input type="number" min="0.5" max="100" step="0.5" value={f.distancia_km} onChange={cambiar('distancia_km')} />
            </label>
            <label>¿Cómo está el tráfico?
              <select value={f.nivel_trafico} onChange={cambiar('nivel_trafico')}>{NIVEL_TRAFICO.map((n) => <option key={n.valor} value={n.valor}>{n.texto}</option>)}</select>
            </label>
            <label>Minutos que tardaría
              <input type="number" min="1" max="180" step="1" value={f.tiempo_respuesta_min} onChange={cambiar('tiempo_respuesta_min')} />
            </label>
            <label>Ambulancias libres
              <input type="number" min="0" max="50" value={f.ambulancias_libres} onChange={cambiar('ambulancias_libres')} />
            </label>
            <button className="btn-primary compact">Ver tipo</button>
          </form>
          {msg && <p className="form-error">{msg}</p>}
          {r && <Resultado tono={r.nivel === 0 ? 'bien' : r.nivel === 1 ? 'medio' : 'mal'} titulo={r.perfil} detalle={r.estrategia} />}
        </Prueba>
        <div className="iah-lado">
          <section className="panel">
            <h3 className="iah-h3">¿Cómo encontró los tipos?</h3>
            <p className="iah-desc">Comparó {ev?.servicios ?? 500} servicios anteriores y juntó los que se parecían en distancia, tráfico, tiempo y ambulancias libres. Probó con 2, 3, 4 y más grupos; con <b>3</b> los grupos quedaron bien separados y cada uno tiene una acción clara.</p>
          </section>
        </div>
      </div>
      <Tecnico><SegmentacionPanel sinSimulador /></Tecnico>
    </>
  )
}
