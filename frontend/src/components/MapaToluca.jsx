import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Minus, Plus, Maximize2 } from 'lucide-react'

// Mapa real con teselas de OpenStreetMap (estilo CARTO Voyager), sin librerías extra.
// Proyección Web Mercator: el mundo mide 256·2^zoom píxeles; las líneas se proyectan una
// vez por nivel de zoom y al arrastrar solo se mueve el dibujo.
//
// Props
//   lineas    [{ id, coords: [[lat, lng], …], color, ancho, opacidad, punteada, borde, titulo }]
//   marcadores [{ id, lat, lng, tipo: 'hospital' | 'emergencia' | 'ambulancia' | 'punto', etiqueta, icono }]
//   encuadre  [[lat, lng], …]  puntos que deben verse al cargar (se re-encuadra si cambian)
//   onClick   (lat, lng) => void   opcional

const TESELAS = ['a', 'b', 'c', 'd']
const ZOOM_MIN = 11
const ZOOM_MAX = 18
const TOLUCA = { lat: 19.285, lng: -99.65 }

const lng2x = (lng, z) => ((lng + 180) / 360) * 256 * 2 ** z
const lat2y = (lat, z) => {
  const s = Math.sin((lat * Math.PI) / 180)
  return (0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)) * 256 * 2 ** z
}
const x2lng = (x, z) => (x / (256 * 2 ** z)) * 360 - 180
const y2lat = (y, z) => {
  const n = Math.PI - (2 * Math.PI * y) / (256 * 2 ** z)
  return (180 / Math.PI) * Math.atan(0.5 * (Math.exp(n) - Math.exp(-n)))
}

function encuadrar(puntos, ancho, alto, margen = 48) {
  if (!puntos?.length || !ancho || !alto) return null
  const lats = puntos.map((p) => p[0])
  const lngs = puntos.map((p) => p[1])
  const n = Math.max(...lats), s = Math.min(...lats), e = Math.max(...lngs), o = Math.min(...lngs)
  let z = ZOOM_MAX
  for (; z > ZOOM_MIN; z--) {
    const w = lng2x(e, z) - lng2x(o, z)
    const h = lat2y(s, z) - lat2y(n, z)
    if (w <= ancho - margen * 2 && h <= alto - margen * 2) break
  }
  const cx = (lng2x(e, z) + lng2x(o, z)) / 2
  const cy = (lat2y(s, z) + lat2y(n, z)) / 2
  return { lat: y2lat(cy, z), lng: x2lng(cx, z), zoom: Math.min(z, 17) }
}

export default function MapaToluca({ lineas = [], marcadores = [], encuadre, onClick, alto = 460, etiquetaAccesible = 'Mapa de Toluca' }) {
  const caja = useRef(null)
  const [tam, setTam] = useState({ w: 0, h: 0 })
  const [vista, setVista] = useState({ ...TOLUCA, zoom: 13 })
  const arrastre = useRef(null)
  const retina = typeof window !== 'undefined' && window.devicePixelRatio > 1 ? '@2x' : ''

  // Tamaño del contenedor
  useEffect(() => {
    const el = caja.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setTam({ w: e.contentRect.width, h: e.contentRect.height }))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Encuadre automático cuando cambian los puntos importantes
  const claveEncuadre = JSON.stringify(encuadre ?? null)
  const encuadrarAhora = useCallback(() => {
    const v = encuadrar(encuadre, tam.w, tam.h)
    if (v) setVista(v)
  }, [claveEncuadre, tam.w, tam.h]) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(encuadrarAhora, [encuadrarAhora])

  const { lat, lng, zoom } = vista
  const cx = lng2x(lng, zoom)
  const cy = lat2y(lat, zoom)
  const origenX = cx - tam.w / 2
  const origenY = cy - tam.h / 2

  // Teselas visibles
  const teselas = []
  if (tam.w) {
    const n = 2 ** zoom
    for (let tx = Math.floor(origenX / 256); tx <= Math.floor((origenX + tam.w) / 256); tx++) {
      for (let ty = Math.floor(origenY / 256); ty <= Math.floor((origenY + tam.h) / 256); ty++) {
        if (ty < 0 || ty >= n) continue
        const x = ((tx % n) + n) % n
        teselas.push({
          key: `${zoom}-${tx}-${ty}`,
          src: `https://${TESELAS[(x + ty) % 4]}.basemaps.cartocdn.com/rastertiles/voyager/${zoom}/${x}/${ty}${retina}.png`,
          left: tx * 256 - origenX,
          top: ty * 256 - origenY,
        })
      }
    }
  }

  // Líneas proyectadas en píxeles del mundo (solo cambian con el zoom)
  const trazos = useMemo(() => lineas.map((l) => {
    let d = ''
    let px = null, py = null
    l.coords.forEach(([la, ln], i) => {
      const x = lng2x(ln, zoom), y = lat2y(la, zoom)
      if (i > 0 && i < l.coords.length - 1 && Math.abs(x - px) + Math.abs(y - py) < 1.5) return
      d += `${d ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`
      px = x; py = y
    })
    return { ...l, d }
  }), [lineas, zoom])

  const cambiarZoom = (delta, ancla) => {
    setVista((v) => {
      const z = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, v.zoom + delta))
      if (z === v.zoom) return v
      if (!ancla) return { ...v, zoom: z }
      // Mantener fijo el punto bajo el cursor
      const ox = lng2x(v.lng, v.zoom) - tam.w / 2 + ancla.x
      const oy = lat2y(v.lat, v.zoom) - tam.h / 2 + ancla.y
      const la = y2lat(oy, v.zoom), ln = x2lng(ox, v.zoom)
      const nx = lng2x(ln, z) - ancla.x + tam.w / 2
      const ny = lat2y(la, z) - ancla.y + tam.h / 2
      return { lat: y2lat(ny, z), lng: x2lng(nx, z), zoom: z }
    })
  }

  // Rueda del mouse: zoom (listener no pasivo para poder evitar el scroll de la página)
  useEffect(() => {
    const el = caja.current
    if (!el) return
    let acumulado = 0
    const onWheel = (e) => {
      e.preventDefault()
      acumulado += e.deltaY
      if (Math.abs(acumulado) < 60) return
      const r = el.getBoundingClientRect()
      cambiarZoom(acumulado < 0 ? 1 : -1, { x: e.clientX - r.left, y: e.clientY - r.top })
      acumulado = 0
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  })

  const onPointerDown = (e) => {
    if (e.target.closest('.mapa-controles, .mapa-credito')) return
    caja.current.setPointerCapture(e.pointerId)
    arrastre.current = { x: e.clientX, y: e.clientY, cx, cy, movio: false }
  }
  const onPointerMove = (e) => {
    const a = arrastre.current
    if (!a) return
    const dx = e.clientX - a.x, dy = e.clientY - a.y
    if (Math.abs(dx) + Math.abs(dy) > 4) a.movio = true
    if (a.movio) setVista((v) => ({ ...v, lat: y2lat(a.cy - dy, v.zoom), lng: x2lng(a.cx - dx, v.zoom) }))
  }
  const onPointerUp = (e) => {
    const a = arrastre.current
    arrastre.current = null
    if (a && !a.movio && onClick) {
      const r = caja.current.getBoundingClientRect()
      const x = origenX + (e.clientX - r.left), y = origenY + (e.clientY - r.top)
      onClick(y2lat(y, zoom), x2lng(x, zoom))
    }
  }

  return (
    <div
      ref={caja}
      className={`mapa${onClick ? ' clicable' : ''}`}
      style={{ height: alto }}
      role="application"
      aria-label={etiquetaAccesible}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={() => { arrastre.current = null }}
      onDoubleClick={(e) => {
        const r = caja.current.getBoundingClientRect()
        cambiarZoom(1, { x: e.clientX - r.left, y: e.clientY - r.top })
      }}
    >
      <div className="mapa-teselas" aria-hidden="true">
        {teselas.map((t) => (
          <img key={t.key} src={t.src} alt="" draggable="false" style={{ left: t.left, top: t.top }} onError={(e) => { e.currentTarget.style.visibility = 'hidden' }} />
        ))}
      </div>

      <svg className="mapa-lineas" width={tam.w} height={tam.h} aria-hidden="true">
        <g transform={`translate(${-origenX} ${-origenY})`}>
          {trazos.map((l) => l.borde && (
            <path key={`b-${l.id}`} d={l.d} className="borde" style={{ strokeWidth: (l.ancho ?? 4) + 4 }} />
          ))}
          {trazos.map((l) => (
            <path
              key={l.id}
              d={l.d}
              stroke={l.color}
              strokeWidth={l.ancho ?? 4}
              strokeOpacity={l.opacidad ?? 1}
              strokeDasharray={l.punteada ? '2 9' : undefined}
            >
              {l.titulo && <title>{l.titulo}</title>}
            </path>
          ))}
        </g>
      </svg>

      {marcadores.map((m) => {
        const x = lng2x(m.lng, zoom) - origenX
        const y = lat2y(m.lat, zoom) - origenY
        if (x < -40 || y < -40 || x > tam.w + 40 || y > tam.h + 40) return null
        return (
          <div key={m.id} className={`mapa-pin pin-${m.tipo}`} style={{ left: x, top: y }} title={m.etiqueta}>
            <span className="pin-icono" aria-hidden="true">{m.icono}</span>
            {m.etiqueta && <span className="pin-etiqueta">{m.etiqueta}</span>}
          </div>
        )
      })}

      <div className="mapa-controles">
        <button type="button" onClick={() => cambiarZoom(1)} aria-label="Acercar"><Plus size={16} /></button>
        <button type="button" onClick={() => cambiarZoom(-1)} aria-label="Alejar"><Minus size={16} /></button>
        {encuadre?.length > 0 && (
          <button type="button" onClick={encuadrarAhora} aria-label="Ver todo"><Maximize2 size={14} /></button>
        )}
      </div>
      <div className="mapa-credito">
        © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> · © <a href="https://carto.com/attributions" target="_blank" rel="noreferrer">CARTO</a>
      </div>
    </div>
  )
}
