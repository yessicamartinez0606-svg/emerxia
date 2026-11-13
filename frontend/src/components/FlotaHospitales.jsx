import { Fragment, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, DownloadCloud, Fuel, Gauge, Hospital, MapPin, Siren, Truck, UserRound, X } from 'lucide-react'
import { ESTADOS, ESTADO_INFO, HOSPITAL_BASE, colorGasolina, importarFlotaReal, obtenerHospitales } from '../lib/flota.js'

// Flota por hospital: una tarjeta por cada hospital registrado (app/genetico.py) con su
// resumen; al dar clic se abre el detalle con sus ambulancias. Va arriba de la tabla del
// módulo Ambulancias.

const CLAVE = 'emergexia.flota.hospital'

// Institución de cada hospital, para la etiqueta de color de la tarjeta.
function institucion(nombre) {
  if (/IMSS/i.test(nombre)) return { texto: 'IMSS', clase: 'imss' }
  if (/ISSSTE/i.test(nombre)) return { texto: 'ISSSTE', clase: 'issste' }
  if (/Cruz Roja/i.test(nombre)) return { texto: 'Cruz Roja', clase: 'cruz-roja' }
  if (/Municipal/i.test(nombre)) return { texto: 'Municipal', clase: 'municipal' }
  return { texto: 'Estatal', clase: 'estatal' }
}

const promedio = (xs) => (xs.length ? xs.reduce((s, x) => s + x, 0) / xs.length : null)
const fmtKm = (km) => `${Math.round(km).toLocaleString('es-MX')} km`

export default function FlotaHospitales({ recarga = 0, onCambio }) {
  const [datos, setDatos] = useState(null)
  const [error, setError] = useState('')
  const [elegido, setElegido] = useState(() => {
    try { return localStorage.getItem(CLAVE) || null } catch { return null }
  })
  const [filtro, setFiltro] = useState('Todas')
  const [importando, setImportando] = useState(false)
  const [aviso, setAviso] = useState(null)
  const detalle = useRef(null)
  const grid = useRef(null)
  const [columnas, setColumnas] = useState(4)

  // Cuántas tarjetas caben por fila, para abrir el detalle justo debajo de la fila elegida.
  useLayoutEffect(() => {
    const el = grid.current
    if (!el) return undefined
    const medir = () => setColumnas(Math.max(1, getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean).length))
    medir()
    const ro = new ResizeObserver(medir)
    ro.observe(el)
    return () => ro.disconnect()
  }, [datos])

  useEffect(() => {
    setError('')
    obtenerHospitales().then(setDatos).catch((e) => setError(e.message))
  }, [recarga])

  const elegir = (id) => {
    const nuevo = id === elegido ? null : id
    setElegido(nuevo)
    setFiltro('Todas')
    try { nuevo ? localStorage.setItem(CLAVE, nuevo) : localStorage.removeItem(CLAVE) } catch { /* sin almacenamiento */ }
    if (nuevo) setTimeout(() => detalle.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 60)
  }

  // Marca, modelo y año reales (API vPIC) para las que no tienen, y las que faltan en cada hospital.
  const importar = async () => {
    setImportando(true)
    setAviso(null)
    try {
      const r = await importarFlotaReal()
      setAviso({ kind: r.fuente.startsWith('Respaldo') ? 'warn' : 'ok', text: r.mensaje })
      onCambio?.()
    } catch (e) {
      setAviso({ kind: 'warn', text: e.message })
    } finally {
      setImportando(false)
    }
  }

  if (error) return <p className="form-error">No se pudo cargar la flota: {error}</p>
  if (!datos) return <div className="panel flota-cargando muted">Cargando hospitales y ambulancias…</div>

  const minimo = datos.combustible_minimo
  const todas = datos.hospitales.flatMap((h) => h.ambulancias)
  const sinVehiculo = todas.filter((a) => !a.vehiculo).length
  const listas = datos.hospitales.reduce((s, h) => s + h.listas, 0)
  const hosp = datos.hospitales.find((h) => h.id === elegido)

  return (
    <section className="fh" aria-label="Ambulancias por hospital">
      <div className="panel fh-resumen">
        <div className="fh-total">
          <span className="fh-total-num">{datos.totales.total}</span>
          <span className="fh-total-txt">
            <strong>ambulancias</strong>
            <small>{datos.hospitales.length} hospitales · {listas} listas para salir</small>
          </span>
        </div>
        <ul className="fh-estados">
          {ESTADOS.map((e) => (
            <li key={e} style={{ '--c': ESTADO_INFO[e].color }}>
              <i aria-hidden="true" /> <b>{datos.totales[e]}</b> {e}
            </li>
          ))}
        </ul>
        <button type="button" className="btn-ghost tall fh-importar" onClick={importar} disabled={importando}
                title="Consulta la API vPIC de la NHTSA (marca, modelo y año reales) y completa la flota de cada hospital">
          <DownloadCloud size={15} /> {importando ? 'Consultando la API…' : sinVehiculo ? `Datos reales (${sinVehiculo} sin vehículo)` : 'Completar flota con datos reales'}
        </button>
      </div>

      {aviso && <p className={`notice ${aviso.kind}`} role="status">{aviso.text}</p>}

      <div className="fh-grid" ref={grid}>
        {datos.hospitales.map((h, i) => {
          const inst = institucion(h.nombre)
          const total = h.ambulancias.length
          const gas = promedio(h.ambulancias.map((a) => a.combustible_pct))
          const abierto = h.id === elegido
          // El detalle va después de la última tarjeta de la fila del hospital elegido.
          const iElegido = datos.hospitales.findIndex((x) => x.id === elegido)
          const finDeFila = Math.min(datos.hospitales.length - 1, Math.floor(iElegido / columnas) * columnas + columnas - 1)
          return (
            <Fragment key={h.id}>
            <button type="button" className={`fh-card${abierto ? ' abierto' : ''}${total ? '' : ' vacio'}`}
                    aria-expanded={abierto} aria-controls="fh-detalle" onClick={() => elegir(h.id)}>
              <span className="fh-card-top">
                <span className={`fh-inst ${inst.clase}`}>{inst.texto}</span>
                {h.nombre === HOSPITAL_BASE && <span className="fh-base">Base</span>}
              </span>
              <span className="fh-nombre">{h.nombre}</span>
              <span className="fh-lugar"><MapPin size={12} aria-hidden="true" /> {h.municipio}</span>

              <span className="fh-cifras">
                <span className="fh-num"><b>{total}</b> <small>{total === 1 ? 'ambulancia' : 'ambulancias'}</small></span>
                <span className={`fh-listas${total && !h.listas ? ' ninguna' : ''}`}>{total ? `${h.listas} lista${h.listas === 1 ? '' : 's'} para salir` : 'Sin ambulancias'}</span>
              </span>

              <span className="fh-barra" aria-hidden="true">
                {total > 0 && ESTADOS.map((e) => h.conteo[e] > 0 && (
                  <i key={e} style={{ flex: h.conteo[e], background: ESTADO_INFO[e].color }} title={`${e}: ${h.conteo[e]}`} />
                ))}
              </span>

              <span className="fh-pie">
                <span className="fh-gas">
                  <Fuel size={12} aria-hidden="true" /> {gas == null ? '—' : `${Math.round(gas)} % promedio`}
                </span>
                <span className="fh-ver">{abierto ? 'Ocultar' : 'Ver ambulancias'} <ChevronRight size={14} aria-hidden="true" /></span>
              </span>
            </button>
            {hosp && i === finDeFila && (
              <DetalleHospital refDetalle={detalle} h={hosp} minimo={minimo} filtro={filtro} setFiltro={setFiltro}
                               onCerrar={() => elegir(hosp.id)} />
            )}
            </Fragment>
          )
        })}
      </div>
    </section>
  )
}

function DetalleHospital({ h, minimo, filtro, setFiltro, onCerrar, refDetalle }) {
  const inst = institucion(h.nombre)
  const lista = h.ambulancias.filter((a) => filtro === 'Todas' || a.estado === filtro)
  return (
    <section id="fh-detalle" ref={refDetalle} className="panel fh-detalle" aria-label={`Ambulancias de ${h.nombre}`}>
      <header className="fh-detalle-head">
        <span className="fh-detalle-icono" aria-hidden="true"><Hospital size={20} /></span>
        <div className="fh-detalle-titulo">
          <span className={`fh-inst ${inst.clase}`}>{inst.texto}</span>
          <h2>{h.nombre}</h2>
          <p><MapPin size={13} aria-hidden="true" /> {h.municipio} · {h.ambulancias.length} ambulancia(s) · {h.listas} lista(s) para salir</p>
        </div>
        <button type="button" className="fh-cerrar" onClick={onCerrar} aria-label="Cerrar detalle"><X size={18} /></button>
      </header>

      {h.ambulancias.length > 0 && (
        <div className="fh-filtros" role="group" aria-label="Filtrar por estatus">
          {['Todas', ...ESTADOS].map((e) => {
            const n = e === 'Todas' ? h.ambulancias.length : h.conteo[e]
            if (e !== 'Todas' && !n) return null
            return (
              <button key={e} type="button" className={filtro === e ? 'on' : ''} aria-pressed={filtro === e}
                      style={e !== 'Todas' ? { '--c': ESTADO_INFO[e].color } : undefined} onClick={() => setFiltro(e)}>
                {e !== 'Todas' && <i aria-hidden="true" />}{e} <b>{n}</b>
              </button>
            )
          })}
        </div>
      )}

      {h.ambulancias.length === 0 ? (
        <div className="fh-sin">
          <Truck size={26} aria-hidden="true" />
          <p>Este hospital todavía no tiene ambulancias registradas.</p>
          <small>Agrégalas con «Nueva ambulancia» o con «Completar flota con datos reales».</small>
        </div>
      ) : (
        <ul className="fh-ambs">
          {lista.map((a) => {
            const info = ESTADO_INFO[a.estado]
            return (
              <li key={a.id}>
                <Link to={`/ambulancias/${a.id}`} className="fh-amb" style={{ '--c': info.color }}>
                  <span className="fh-amb-top">
                    <span className="fh-placa">{a.placa}</span>
                    <span className="fh-chip" style={{ color: info.color, background: info.fondo }}>{a.estado}</span>
                  </span>
                  <span className="fh-vehiculo">
                    <Truck size={14} aria-hidden="true" />
                    <span>{a.vehiculo || <em>Sin datos del vehículo</em>}</span>
                    <span className={`fh-tipo ${a.tipo === 'Avanzada' ? 'avanzada' : ''}`}>{a.tipo}</span>
                  </span>
                  <dl className="fh-datos">
                    <div><dt><UserRound size={12} aria-hidden="true" /> Conductor</dt><dd className={a.conductor ? '' : 'falta'}>{a.conductor || 'Sin conductor'}</dd></div>
                    <div><dt><Gauge size={12} aria-hidden="true" /> Kilometraje</dt><dd>{fmtKm(a.kilometraje)}</dd></div>
                    {a.emergencia_actual && <div className="ancho"><dt><Siren size={12} aria-hidden="true" /> Atendiendo</dt><dd>{a.emergencia_actual}</dd></div>}
                  </dl>
                  <span className="fh-gasolina" title={`Gasolina: ${a.combustible_pct} %`}>
                    <Fuel size={13} aria-hidden="true" />
                    <span className="barra"><span style={{ width: `${a.combustible_pct}%`, background: colorGasolina(a.combustible_pct, minimo) }} /></span>
                    <span className={`pct${a.combustible_bajo ? ' bajo' : ''}`}>{Math.floor(a.combustible_pct)} %</span>
                  </span>
                  <span className="fh-abrir">Abrir ficha <ChevronRight size={13} aria-hidden="true" /></span>
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
