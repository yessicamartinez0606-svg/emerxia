import { useEffect, useState } from 'react'
import { api } from './api.js'

export const slug = (v) =>
  String(v).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, '-')

// Claves habituales bajo las que puede venir guardada una foto en MongoDB,
// aunque el módulo no declare un campo tipo "photo" en modules.js.
export const PHOTO_KEYS = ['foto', 'photo', 'imagen', 'foto_perfil', 'avatar']

// Foto de un registro: usa el campo que el módulo declara como tipo "photo"
// (p. ej. Operadores/Doctores) o, si el documento trae una foto guardada bajo
// otra clave habitual, esa. Se usa tanto en la tabla como en el perfil, para
// que un mismo ícono/avatar se vea igual en toda la app.
export function getPhoto(mod, item) {
  const declaredPhotoField = mod.fields.find((f) => f.type === 'photo')
  return (
    (declaredPhotoField && item[declaredPhotoField.key]) ||
    PHOTO_KEYS.map((k) => item[k]).find(Boolean) ||
    null
  )
}

export function emptyForm(fields) {
  return Object.fromEntries(fields.map((f) => [f.key, f.options ? f.options[0] : '']))
}

// Campos con `source` no traen una lista fija: se llenan leyendo otra colección
// (p. ej. "operador" lee /api/operadores, "ambulancia" lee /api/ambulancias),
// así el formulario siempre refleja lo que de verdad hay en la base de datos.
export function useSourcedOptions(fields) {
  const [options, setOptions] = useState({})
  const [loading, setLoading] = useState({})
  const sourced = fields.filter((f) => f.source)

  useEffect(() => {
    sourced.forEach((f) => {
      setLoading((prev) => ({ ...prev, [f.key]: true }))
      api(`/${f.source}`)
        .then((d) => {
          const rows = d.items ?? []
          setOptions((prev) => ({
            ...prev,
            // se guarda también la fila completa ("raw") para poder leer campos
            // que no van en el <option>, como la foto de referencia del operador
            [f.key]: rows.map((r) => ({ value: f.optionValue(r), label: f.optionLabel(r), raw: r })),
          }))
        })
        .catch(() => setOptions((prev) => ({ ...prev, [f.key]: null })))
        .finally(() => setLoading((prev) => ({ ...prev, [f.key]: false })))
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fields])

  return { options, loading }
}
