import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, ScanFace, ShieldCheck } from 'lucide-react'
import { api } from '../lib/api.js'
import { slug } from '../lib/moduleHelpers.js'
import FaceCapture from '../components/FaceCapture.jsx'

// Ventana del operador: a la que se llega solos justo después de registrar una
// emergencia (ver `afterSave` del módulo Emergencias en lib/modules.js). Aquí el
// operador que va a atenderla se identifica por Face ID: su rostro se compara
// contra la foto de referencia de todos los operadores registrados y, si
// coincide con alguno, ese operador queda asignado a la emergencia.
export default function OperatorValidationPage() {
  const { emergenciaId } = useParams()
  const [emergency, setEmergency] = useState(null)   // null = cargando, false = no existe
  const [operators, setOperators] = useState(null)   // null = cargando o con error
  const [loadError, setLoadError] = useState('')
  const [faceOpen, setFaceOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [validated, setValidated] = useState(null)   // operador ya validado en esta pantalla
  const autoOpened = useRef(false)

  useEffect(() => {
    setLoadError('')
    Promise.all([api('/emergencias'), api('/operadores')])
      .then(([em, op]) => {
        setEmergency((em.items ?? []).find((r) => String(r.id) === String(emergenciaId)) ?? false)
        setOperators(op.items ?? [])
      })
      .catch((e) => setLoadError(e.message))
  }, [emergenciaId])

  const candidates = useMemo(
    () => (operators ?? []).map((o) => ({ ...o, label: o.nombre })),
    [operators],
  )
  const withPhoto = candidates.filter((c) => c.foto).length

  // Al llegar desde el registro, la cámara se abre sola (si la emergencia aún no
  // tiene operador). Si se cancela, el botón de la pantalla permite reintentar.
  useEffect(() => {
    if (autoOpened.current || !emergency || !operators) return
    autoOpened.current = true
    if (!emergency.operador && withPhoto > 0) setFaceOpen(true)
  }, [emergency, operators, withPhoto])

  const onFaceSuccess = async (_photo, result) => {
    const operator = result.candidate
    setFaceOpen(false)
    setSaving(true)
    setSaveError('')
    try {
      const wasEnCurso = emergency.estado === 'En curso'
      const changes = { operador: operator.nombre }
      if (emergency.estado === 'Pendiente') changes.estado = 'Asignada'
      const updated = await api(`/emergencias/${emergency.id}`, { method: 'PATCH', body: changes })
      setEmergency(updated)
      setValidated(operator)
      // Bitácora de auditoría: no debe bloquear el flujo si falla.
      api('/verificaciones', {
        method: 'POST',
        body: {
          operador: operator.nombre,
          contexto: wasEnCurso ? 'salida' : 'asignacion',
          coincide: true,
          distancia: result.distance,
          emergencia_folio: emergency.folio,
        },
      }).catch(() => {})
    } catch (err) {
      setSaveError(`Se validó el rostro de ${operator.nombre}, pero no se pudo asignar a la emergencia: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  if (loadError) {
    return (
      <section className="record-screen">
        <p className="form-error">{loadError}</p>
      </section>
    )
  }
  if (emergency === null) {
    return <section className="record-screen"><p className="muted pad">Cargando emergencia…</p></section>
  }
  if (emergency === false) {
    return (
      <section className="record-screen">
        <Link to="/emergencias" className="btn-back" aria-label="Volver a emergencias"><ArrowLeft size={18} /></Link>
        <p className="muted pad">No se encontró esta emergencia. Puede que el id no sea correcto.</p>
      </section>
    )
  }

  const assigned = validated?.nombre ?? emergency.operador
  const summary = [
    ['Paciente', emergency.paciente_nombre],
    ['Ubicación', emergency.direccion],
    ['Descripción', emergency.descripcion],
    ['Doctor', emergency.doctor],
    ['Teléfono', emergency.paciente_telefono],
  ]

  return (
    <section className="record-screen">
      <header className="record-screen-head">
        <Link to="/emergencias" className="btn-back" aria-label="Volver a emergencias">
          <ArrowLeft size={18} />
        </Link>
        <span className="record-screen-icon"><ScanFace size={22} strokeWidth={1.8} /></span>
        <div className="record-screen-title">
          <span className="record-screen-eyebrow">Operadores</span>
          <h1>Validación de operador</h1>
          <p>Confirma con Face ID quién atiende la emergencia {emergency.folio}.</p>
        </div>
      </header>

      <p className="notice ok" role="status">
        ✓ Emergencia {emergency.folio} registrada.{' '}
        {assigned ? `Operador asignado: ${assigned}.` : 'Falta validar al operador que la atiende.'}
      </p>

      <div className="panel form-section">
        <h2 className="form-section-title">Resumen de la emergencia</h2>
        <div className="validation-badges">
          {emergency.prioridad && <span className={`badge b-${slug(emergency.prioridad)}`}>Prioridad {emergency.prioridad}</span>}
          {emergency.estado && <span className={`badge b-${slug(emergency.estado)}`}>{emergency.estado}</span>}
        </div>
        <dl className="kv profile-kv">
          {summary.filter(([, v]) => v).map(([k, v]) => (
            <Fragment key={k}><dt>{k}</dt><dd>{v}</dd></Fragment>
          ))}
        </dl>
      </div>

      <div className="panel form-section">
        <h2 className="form-section-title">Face ID del operador</h2>

        {assigned ? (
          <div className="validation-done">
            <span className="validation-done-icon"><ShieldCheck size={26} strokeWidth={1.8} /></span>
            <div>
              <strong>{assigned}</strong>
              <p className="muted">
                {validated
                  ? 'Identidad verificada por reconocimiento facial y asignado a esta emergencia.'
                  : 'Ya tiene operador asignado. Puedes validar a otro si cambia quien la atiende.'}
              </p>
            </div>
          </div>
        ) : (
          <p className="muted validation-lead">
            El operador que atenderá la emergencia debe mirar a la cámara. Su rostro se compara contra la foto
            con la que se registró y, si coincide, queda asignado automáticamente.
          </p>
        )}

        {operators === null && <p className="field-hint warn">No se pudo cargar la lista de operadores.</p>}
        {operators && operators.length === 0 && (
          <p className="field-hint warn">No hay operadores registrados todavía — agrega uno primero en el módulo de Operadores.</p>
        )}
        {operators && operators.length > 0 && withPhoto === 0 && (
          <p className="field-hint warn">Ningún operador tiene foto de referencia. Agrégala en el módulo de Operadores.</p>
        )}
        {saveError && <p className="form-error validation-error">{saveError}</p>}

        <div className="validation-actions">
          <button
            type="button"
            className="btn-primary compact"
            onClick={() => setFaceOpen(true)}
            disabled={saving || withPhoto === 0}
          >
            <ScanFace size={16} /> {saving ? 'Asignando…' : assigned ? 'Validar de nuevo' : 'Validar con Face ID'}
          </button>
          {assigned ? (
            <>
              <Link to={`/emergencias/${emergency.id}`} className="btn-ghost tall">Ver emergencia</Link>
              <Link to="/emergencias" className="btn-ghost tall">Ir a emergencias <ArrowRight size={15} /></Link>
            </>
          ) : (
            <Link to="/emergencias" className="btn-ghost tall">Validar más tarde</Link>
          )}
        </div>
      </div>

      <FaceCapture
        open={faceOpen}
        mode="identify"
        title={`Validar operador · ${emergency.folio}`}
        candidates={candidates}
        onSuccess={onFaceSuccess}
        onCancel={() => setFaceOpen(false)}
      />
    </section>
  )
}
