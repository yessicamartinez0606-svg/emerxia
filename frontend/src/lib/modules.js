import { Ambulance, CircleDot, Headset, History, Hospital, HeartPulse, KeyRound, Route, Settings, Siren, Stethoscope, TrafficCone, UserRound, House } from 'lucide-react'
import { ANIOS_VEHICULO, HOSPITALES, MARCAS_VEHICULO, fmtFecha } from './flota.js'

// Para mostrar en la ficha campos que no son texto simple (`format` en un campo).
const fecha = (v) => (v ? fmtFecha(v) : '')
const listaParamedicos = (v) => (Array.isArray(v) && v.length
  ? v.map((p) => (typeof p === 'string' ? p : `${p.nombre}${p.nivel ? ` (${p.nivel})` : ''}`)).join(', ')
  : '')

export const HOME = { path: '/', label: 'Inicio', navIcon: House }

// Formato: correo con "@" y dominio; celular exactamente 10 dígitos (se aceptan espacios/guiones
// al escribir, pero al final deben quedar 10 números). El backend valida lo mismo — esto es solo
// para avisarle al usuario al momento, sin esperar a que el servidor lo rechace.
export const EMAIL_PATTERN = { re: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: 'Escribe un correo válido, con "@" y dominio (ej. nombre@correo.com).' }
export const USUARIO_PATTERN = { re: /^[a-z0-9._-]{3,40}$/, message: 'El usuario debe tener de 3 a 40 caracteres: letras sin acento, números, punto, guion o guion bajo (sin espacios).', normalize: (v) => v.toLowerCase() }
export const PASSWORD_PATTERN = { re: /^.{6,}$/, message: 'La contraseña debe tener al menos 6 caracteres.' }

// Usuario y contraseña con los que entra un operador o un paramédico. La contraseña se guarda
// cifrada en su cuenta (no en el registro) y no se vuelve a mostrar: en su ficha, el
// Administrador puede cambiarla (components/AccesoSistema.jsx).
const CAMPOS_ACCESO = [
  { key: 'usuario', label: 'Usuario para entrar', required: true, pattern: USUARIO_PATTERN, group: 'Acceso al sistema',
    hint: 'Con el que entrará. Sin espacios ni acentos, ej. maria.lopez' },
  { key: 'password', label: 'Contraseña', type: 'password', required: true, pattern: PASSWORD_PATTERN, group: 'Acceso al sistema',
    hideInDetail: true, hint: 'Mínimo 6 caracteres. Entrégasela en persona. Después solo el Administrador puede cambiarla.' },
]

export const CELULAR_PATTERN = { re: /^\d{10}$/, message: 'El celular debe tener exactamente 10 dígitos (ej. 5512345678).', normalize: (v) => v.replace(/[\s()-]/g, '') }

// Cada módulo alimenta: tarjeta de inicio, menú lateral, tabla y formulario.
export const MODULES = [
  {
    key: 'ambulancias',
    label: 'Ambulancias',
    description: 'Administra la flota de ambulancias y su disponibilidad',
    icon: Ambulance,
    navIcon: Ambulance,
    singular: 'ambulancia',
    nuevo: 'Nueva',
    eliminar: true,   // solo el Administrador (RecordDetailPage y tarjetas de FlotaHospitales)
    editar: true,     // /ambulancias/:id/editar (ModuleFormPage)
    // Sin tabla: las ambulancias se ven por hospital (components/FlotaHospitales.jsx).
    sinTabla: true,
    columns: [
      { key: 'placa', label: 'Placa' },
      { key: 'vehiculo', label: 'Vehículo' },
      { key: 'tipo', label: 'Tipo' },
      { key: 'hospital', label: 'Hospital' },
      { key: 'conductor', label: 'Conductor' },
      { key: 'combustible_pct', label: 'Gasolina (%)' },
      { key: 'estado', label: 'Estatus', badge: true },
    ],
    fields: [
      { key: 'placa', label: 'Placa', required: true, group: 'Ambulancia' },
      { key: 'tipo', label: 'Tipo', options: ['Básica', 'Avanzada'], group: 'Ambulancia' },
      { key: 'hospital', label: 'Hospital donde está', options: HOSPITALES, group: 'Ambulancia' },
      // "Ocupada" no se elige aquí: la pone el sistema al asignarla a una emergencia.
      { key: 'estado', label: 'Estatus', options: ['Libre', 'En reparación', 'Fuera de servicio'], group: 'Ambulancia' },
      {
        // El conductor es un operador: es quien registra la gasolina de esta ambulancia.
        key: 'conductor',
        label: 'Conductor (operador)',
        group: 'Ambulancia',
        source: 'operadores',
        optionValue: (r) => r.nombre,
        optionLabel: (r) => `${r.nombre} · turno ${r.turno}`,
        allowEmpty: true,
        emptyLabel: 'Sin conductor',
      },
      // Vehículo real: la marca y el año consultan la API vPIC de la NHTSA y el modelo se elige
      // de lo que responde; al elegirlo se llenan el tanque y el rendimiento de su ficha técnica.
      { key: 'marca', label: 'Marca', options: MARCAS_VEHICULO, group: 'Vehículo' },
      { key: 'anio', label: 'Año', options: ANIOS_VEHICULO, group: 'Vehículo' },
      { key: 'modelo', label: 'Modelo', type: 'modeloApi', group: 'Vehículo',
        hint: 'Solo aparecen los modelos que de verdad fabricó esa marca ese año.' },
      { key: 'tanque_litros', label: 'Capacidad del tanque (L)', type: 'number', default: '80', group: 'Gasolina' },
      { key: 'rendimiento_km_l', label: 'Rendimiento (km por litro)', type: 'number', default: '6', group: 'Gasolina' },
      { key: 'combustible_pct', label: 'Gasolina actual (%)', type: 'number', default: '100', group: 'Gasolina' },
      { key: 'kilometraje', label: 'Kilometraje (odómetro)', type: 'number', default: '0', group: 'Gasolina' },
    ],
  },
  {
    key: 'emergencias',
    label: 'Emergencias',
    description: 'Atiende y da seguimiento a las emergencias',
    icon: Siren,
    navIcon: CircleDot,
    singular: 'emergencia',
    nuevo: 'Nueva',
    // Al guardar, las ambulancias y el operador se asignan solos (backend: routers/flota.py →
    // asignar_automatico) y se abre el reporte de la emergencia con el resultado.
    afterSave: (saved) => `/emergencias/${saved.id}`,
    columns: [
      { key: 'folio', label: 'Folio' },
      { key: 'paciente_nombre', label: 'Paciente' },
      { key: 'descripcion', label: 'Descripción' },
      // mensaje / llamada si la reportó una persona desde su perfil de Usuario.
      { key: 'canal', label: 'Reportada por' },
      { key: 'prioridad', label: 'Prioridad', badge: true },
      { key: 'operador', label: 'Conductor' },
      { key: 'ambulancia', label: 'Ambulancia' },
      { key: 'estado', label: 'Estado', badge: true },
    ],
    fields: [
      // Datos del paciente
      { key: 'paciente_nombre', label: 'Nombre completo del paciente', required: true, group: 'Paciente' },
      { key: 'paciente_edad', label: 'Edad', group: 'Paciente' },
      { key: 'paciente_sexo', label: 'Sexo', options: ['Masculino', 'Femenino', 'Otro'], group: 'Paciente' },
      { key: 'paciente_telefono', label: 'Teléfono de contacto (10 dígitos)', type: 'tel', pattern: CELULAR_PATTERN, group: 'Paciente' },
      { key: 'direccion', label: 'Dirección / ubicación de la emergencia', required: true, group: 'Paciente' },

      // Datos de la emergencia
      { key: 'descripcion', label: 'Descripción de la emergencia', required: true, group: 'Emergencia' },
      { key: 'prioridad', label: 'Prioridad', options: ['Alta', 'Media', 'Baja'], group: 'Emergencia' },
      {
        // Si se necesitan más de las que tiene libres el IMSS 220, las demás salen de otros hospitales.
        key: 'ambulancias_requeridas', label: 'Ambulancias necesarias', type: 'number', default: '1', group: 'Emergencia',
        hint: 'Si son más de las que hay libres en el Hospital IMSS 220, se piden a los hospitales más cercanos.',
      },
      { key: 'estado', label: 'Estado', options: ['Pendiente', 'Asignada', 'En curso', 'Cerrada'], group: 'Emergencia' },
      // Opcionales. Con los tres, el modelo de triaje (práctica 05) estima si es crítica.
      { key: 'saturacion_oxigeno', label: 'Saturación de oxígeno (SpO₂ %)', type: 'number', group: 'Signos vitales',
        hint: 'Opcional. Con saturación, frecuencia cardiaca y Glasgow, el sistema te avisa si el paciente parece grave.' },
      { key: 'frecuencia_cardiaca', label: 'Frecuencia cardiaca (latidos por minuto)', type: 'number', group: 'Signos vitales' },
      { key: 'escala_glasgow', label: 'Escala de Glasgow (3 a 15)', type: 'number', group: 'Signos vitales' },
      // Los captura el paramédico desde su portal (pages/paramedico/MiAtencion.jsx).
      { key: 'presion_arterial', label: 'Presión arterial', group: 'Signos vitales', hideInForm: true },
      { key: 'temperatura', label: 'Temperatura (°C)', group: 'Signos vitales', hideInForm: true },
      { key: 'glucosa', label: 'Glucosa (mg/dL)', group: 'Signos vitales', hideInForm: true },
      { key: 'atendio_paramedico', label: 'Paramédico que atendió', group: 'Atención prehospitalaria', hideInForm: true },
      { key: 'observaciones_paramedico', label: 'Atención brindada', group: 'Atención prehospitalaria', hideInForm: true },

      // Asignación: no se elige en el formulario. Al guardar, el sistema asigna solo las
      // ambulancias libres más cercanas y el operador es quien maneja la primera.
      {
        // El conductor de la ambulancia ES el operador (lo dice la ficha de cada ambulancia).
        key: 'operador',
        label: 'Conductor (operador)',
        group: 'Asignación',
        source: 'operadores',
        optionValue: (r) => r.nombre,
        optionLabel: (r) => `${r.nombre} · turno ${r.turno}${r.estado === 'Desconectado' ? ' (desconectado)' : ''}`,
        allowEmpty: true,
        emptyLabel: 'Sin operador asignado',
        // No se elige en el formulario: es quien maneja la primera ambulancia asignada.
        // El campo se sigue mostrando en el perfil y en la tabla.
        hideInForm: true,
      },
      {
        key: 'ambulancia',
        label: 'Ambulancia(s) asignada(s)',
        group: 'Asignación',
        source: 'ambulancias',
        optionValue: (r) => r.placa,
        optionLabel: (r) => `${r.placa} · ${r.tipo} (${r.estado})`,
        allowEmpty: true,
        emptyLabel: 'Sin ambulancia asignada',
        // Se asignan solas al guardar (pueden ser varias, de varios hospitales).
        hideInForm: true,
      },
      // Los 2 paramédicos que confirma la central con su rostro (ParamedicosEmergencia).
      { key: 'paramedicos', label: 'Paramédicos', group: 'Asignación', hideInForm: true, format: listaParamedicos },

      // Lo que marca el operador desde su perfil (Mi turno): aparece aquí al momento.
      { key: 'hora_salida', label: 'Salió del hospital', group: 'Seguimiento del operador', hideInForm: true, format: fecha },
      { key: 'hora_llegada', label: 'Llegó al lugar', group: 'Seguimiento del operador', hideInForm: true, format: fecha },
      { key: 'hora_traslado', label: 'Traslado al hospital', group: 'Seguimiento del operador', hideInForm: true, format: fecha },
      { key: 'hospital_destino', label: 'Hospital destino', group: 'Seguimiento del operador', hideInForm: true },
      { key: 'hora_cierre', label: 'Emergencia cerrada', group: 'Seguimiento del operador', hideInForm: true, format: fecha },
      { key: 'km_recorridos', label: 'Km recorridos', group: 'Seguimiento del operador', hideInForm: true,
        format: (v) => (v == null || v === '' ? '' : `${v} km`) },
      { key: 'observaciones', label: 'Notas del operador', group: 'Seguimiento del operador', hideInForm: true },
    ],
  },
  {
    key: 'operadores',
    label: 'Operadores',
    description: 'Gestiona el equipo de operadores y sus turnos',
    icon: Headset,
    navIcon: UserRound,
    singular: 'operador',
    nuevo: 'Nuevo',
    eliminar: true,
    columns: [
      { key: 'nombre', label: 'Nombre' },
      { key: 'turno', label: 'Turno' },
      { key: 'extension', label: 'Extensión' },
      { key: 'usuario', label: 'Usuario' },
      { key: 'estado', label: 'Estado', badge: true },
    ],
    // Tiene cuenta propia: usuario y contraseña (además de entrar con su rostro).
    credenciales: true,
    fields: [
      { key: 'nombres', label: 'Nombre(s)', required: true, group: 'Datos personales' },
      { key: 'apellidos', label: 'Apellidos', required: true, group: 'Datos personales' },
      { key: 'celular', label: 'Celular (10 dígitos)', required: true, type: 'tel', pattern: CELULAR_PATTERN, group: 'Datos personales' },
      { key: 'correo', label: 'Correo electrónico', required: true, type: 'email', pattern: EMAIL_PATTERN, group: 'Datos personales' },
      { key: 'turno', label: 'Turno', options: ['Matutino', 'Vespertino', 'Nocturno'], group: 'Datos personales' },
      { key: 'extension', label: 'Extensión', group: 'Datos personales' },
      { key: 'estado', label: 'Estado', options: ['En línea', 'Desconectado'], group: 'Datos personales' },
      { key: 'experiencia', label: 'Años de experiencia', type: 'number', group: 'Datos personales',
        hint: 'Ayuda a calcular si la ambulancia llegará a tiempo.' },
      {
        key: 'foto',
        label: 'Foto de referencia (rostro)',
        type: 'photo',
        required: true,
        hint: 'Con esta foto el operador puede entrar mirando a la cámara, y se confirma que es él antes de que salga la ambulancia.',
      },
      ...CAMPOS_ACCESO,
    ],
  },
  {
    key: 'paramedicos',
    label: 'Paramédicos',
    description: 'Gestiona a los paramédicos (TUM) y su acceso. Van 2 por emergencia, en la ambulancia de esa emergencia',
    icon: Stethoscope,
    navIcon: HeartPulse,
    singular: 'paramédico',
    nuevo: 'Nuevo',
    eliminar: true,
    credenciales: true,
    columns: [
      { key: 'nombre', label: 'Nombre' },
      { key: 'nivel', label: 'Nivel' },
      { key: 'emergencia_actual', label: 'Emergencia actual' },
      { key: 'ambulancia', label: 'Ambulancia' },
      { key: 'turno', label: 'Turno' },
      { key: 'usuario', label: 'Usuario' },
      { key: 'estado', label: 'Estado', badge: true },
    ],
    fields: [
      { key: 'nombres', label: 'Nombre(s)', required: true, group: 'Datos personales' },
      { key: 'apellidos', label: 'Apellidos', required: true, group: 'Datos personales' },
      { key: 'celular', label: 'Celular (10 dígitos)', required: true, type: 'tel', pattern: CELULAR_PATTERN, group: 'Datos personales' },
      { key: 'correo', label: 'Correo electrónico', required: true, type: 'email', pattern: EMAIL_PATTERN, group: 'Datos personales' },
      { key: 'tipo_sangre', label: 'Tipo de sangre', options: ['', 'O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-'], group: 'Datos personales' },
      { key: 'contacto_emergencia', label: 'Contacto de emergencia (nombre y teléfono)', group: 'Datos personales' },
      { key: 'nivel', label: 'Nivel', options: ['TUM Básico', 'TUM Intermedio', 'TUM Avanzado', 'Paramédico'], group: 'Servicio' },
      { key: 'cedula', label: 'Cédula o número de certificación', group: 'Servicio' },
      { key: 'turno', label: 'Turno', options: ['Matutino', 'Vespertino', 'Nocturno'], group: 'Servicio' },
      { key: 'estado', label: 'Estado', options: ['En servicio', 'Fuera de turno', 'Baja'], group: 'Servicio' },
      {
        key: 'foto',
        label: 'Foto de su rostro',
        type: 'photo',
        required: true,
        hint: 'Con esta foto el paramédico puede entrar mirando a la cámara, sin escribir su contraseña.',
      },
      ...CAMPOS_ACCESO,
    ],
  },
  {
    // Pantalla propia (pages/RutasPage.jsx): búsqueda ciega y heurística (greedy, A*) sobre el espacio de estados.
    key: 'rutas',
    label: 'Rutas y tráfico',
    description: 'La ruta más rápida para la ambulancia, evitando el tráfico',
    icon: TrafficCone,
    navIcon: Route,
    custom: true,
  },
  {
    // Pantalla propia (pages/HistorialPage.jsx): movimientos de la flota.
    key: 'historial',
    label: 'Historial',
    description: 'Movimientos de las ambulancias: estatus, emergencias, conductores y gasolina',
    icon: History,
    navIcon: History,
    custom: true,
  },
  {
    // Pantalla propia (pages/CuentasPage.jsx): el Administrador crea las cuentas de la central.
    key: 'cuentas',
    label: 'Cuentas',
    description: 'Crea y administra las cuentas de la central; revisa todas las del sistema',
    icon: KeyRound,
    navIcon: KeyRound,
    custom: true,
    soloAdmin: true,
  },
  {
    key: 'configuracion',
    label: 'Configuración',
    description: 'Ajusta las preferencias del sistema y tu cuenta',
    icon: Settings,
    navIcon: Settings,
    custom: true,
  },
]

export const findModule = (key) => MODULES.find((m) => m.key === key)
