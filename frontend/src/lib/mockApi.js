// Modo "solo frontend": simula el backend (login, tablas, estado de Spark) con
// datos guardados en localStorage, para poder trabajar en la interfaz sin
// levantar FastAPI ni Spark. Los mensajes de error imitan a los del backend
// real, para que el resto de la app no tenga que distinguir entre modos.
//
// Para volver a usar el backend real: en lib/api.js, cambia MOCK_API a false.

const PREFIX = 'emergexia.mock.'
const ADMIN = { username: 'admin', password: 'admin123', full_name: 'Yessica López', role: 'Administrador' }

const SEEDS = {
  doctors: [
    { id: 1, nombre: 'Dra. Laura Méndez', especialidad: 'Medicina de urgencias', telefono: '55 1234 5601', estado: 'Activo' },
    { id: 2, nombre: 'Dr. Carlos Ortega', especialidad: 'Cardiología', telefono: '55 1234 5602', estado: 'Activo' },
    { id: 3, nombre: 'Dra. Sofía Ramírez', especialidad: 'Traumatología', telefono: '55 1234 5603', estado: 'En guardia' },
    { id: 4, nombre: 'Dr. Andrés Villalobos', especialidad: 'Pediatría', telefono: '55 1234 5604', estado: 'Descanso' },
  ],
  ambulances: [
    { id: 1, placa: 'AMB-101', tipo: 'Avanzada', conductor: 'Jorge Salinas', estado: 'Libre' },
    { id: 2, placa: 'AMB-102', tipo: 'Básica', conductor: 'Marcos Herrera', estado: 'Ocupada' },
    { id: 3, placa: 'AMB-103', tipo: 'Avanzada', conductor: 'Elena Cruz', estado: 'Libre' },
    { id: 4, placa: 'AMB-104', tipo: 'Básica', conductor: 'Pablo Núñez', estado: 'En reparación' },
  ],
  emergencies: [
    { id: 1, folio: 'EMG-0001', descripcion: 'Accidente vehicular en Av. Reforma', prioridad: 'Alta', estado: 'En curso', ambulancia: 'AMB-102', creado: new Date().toISOString() },
    { id: 2, folio: 'EMG-0002', descripcion: 'Dolor torácico, adulto mayor', prioridad: 'Alta', estado: 'Asignada', ambulancia: 'AMB-101', creado: new Date().toISOString() },
    { id: 3, folio: 'EMG-0003', descripcion: 'Caída con posible fractura', prioridad: 'Media', estado: 'Pendiente', ambulancia: null, creado: new Date().toISOString() },
  ],
  operators: [
    { id: 1, nombre: 'Mariana Torres', turno: 'Matutino', extension: '201', estado: 'En línea' },
    { id: 2, nombre: 'Ricardo Paredes', turno: 'Vespertino', extension: '202', estado: 'En línea' },
    { id: 3, nombre: 'Daniela Ibarra', turno: 'Nocturno', extension: '203', estado: 'Desconectado' },
  ],
}

// Mismo mapeo que backend/app/routers/modules.py: ruta pública → tabla interna.
const TABLE_BY_PATH = { doctores: 'doctors', ambulancias: 'ambulances', emergencias: 'emergencies', operadores: 'operators' }

function loadTable(table) {
  const raw = localStorage.getItem(PREFIX + table)
  if (raw) {
    try { return JSON.parse(raw) } catch { /* datos corruptos: se reseeda abajo */ }
  }
  const seeded = SEEDS[table].map((row) => ({ ...row }))
  localStorage.setItem(PREFIX + table, JSON.stringify(seeded))
  return seeded
}

const saveTable = (table, rows) => localStorage.setItem(PREFIX + table, JSON.stringify(rows))

const nextId = (table) => loadTable(table).reduce((max, r) => Math.max(max, r.id), 0) + 1

function countBy(table, column) {
  return loadTable(table).reduce((acc, row) => {
    const key = row[column] || 'Sin dato'
    acc[key] = (acc[key] || 0) + 1
    return acc
  }, {})
}

// Token "de juguete": el usuario codificado en base64, nada de firmas ni expiración
// real. Es intencional: aquí no hay nada que proteger, solo se busca poder navegar
// la interfaz sin backend.
const encodeToken = (user) => 'mock.' + btoa(unescape(encodeURIComponent(JSON.stringify(user))))
function decodeToken(token) {
  try { return JSON.parse(decodeURIComponent(escape(atob(token.slice(5))))) } catch { return null }
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/** Misma forma que la API real, resuelta en el navegador. */
export async function mockApi(path, { method = 'GET', body } = {}, token) {
  await wait(180) // una pizca de latencia, para que las pantallas de carga se noten

  if (path === '/auth/login' && method === 'POST') {
    const okUser = body?.username?.trim().toLowerCase() === ADMIN.username
    if (!okUser || body?.password !== ADMIN.password) {
      throw new Error('Usuario o contraseña incorrectos.')
    }
    const user = { username: ADMIN.username, full_name: ADMIN.full_name, role: ADMIN.role }
    return { token: encodeToken(user), user }
  }

  if (path === '/auth/me') {
    const user = token?.startsWith('mock.') ? decodeToken(token) : null
    if (!user) throw new Error('Tu sesión expiró. Vuelve a iniciar sesión.')
    return user
  }

  if (path === '/spark/status') {
    return {
      connected: true,
      app_name: 'Emergexia (modo frontend)',
      app_id: 'mock-local',
      master: 'sin backend — datos en este navegador',
      version: '—',
      data_dir: 'localStorage',
    }
  }

  if (path === '/dashboard/summary') {
    return {
      doctores: countBy('doctors', 'estado'),
      ambulancias: countBy('ambulances', 'estado'),
      emergencias: countBy('emergencies', 'estado'),
      operadores: countBy('operators', 'estado'),
    }
  }

  const table = TABLE_BY_PATH[path.replace(/^\//, '').split('/')[0]]
  if (table) {
    if (method === 'GET') {
      const items = loadTable(table)
      return { total: items.length, items }
    }
    if (method === 'POST') {
      const rows = loadTable(table)
      const row = { id: nextId(table), ...body }
      if (table === 'emergencies') {
        row.folio = `EMG-${String(row.id).padStart(4, '0')}`
        row.creado = new Date().toISOString()
      }
      rows.push(row)
      saveTable(table, rows)
      return row
    }
  }

  throw new Error(`Ruta no implementada en modo frontend: ${method} ${path}`)
}
