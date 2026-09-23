import { Ambulance, CircleDot, Headset, Settings, Siren, Stethoscope, UserRound, House } from 'lucide-react'

export const HOME = { path: '/', label: 'Inicio', navIcon: House }

// Formato: correo con "@" y dominio; celular exactamente 10 dígitos (se aceptan espacios/guiones
// al escribir, pero al final deben quedar 10 números). El backend valida lo mismo — esto es solo
// para avisarle al usuario al momento, sin esperar a que el servidor lo rechace.
export const EMAIL_PATTERN = { re: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: 'Escribe un correo válido, con "@" y dominio (ej. nombre@correo.com).' }
export const CELULAR_PATTERN = { re: /^\d{10}$/, message: 'El celular debe tener exactamente 10 dígitos (ej. 5512345678).', normalize: (v) => v.replace(/[\s()-]/g, '') }

// Cada módulo alimenta: tarjeta de inicio, menú lateral, tabla y formulario.
export const MODULES = [
  {
    key: 'doctores',
    label: 'Doctores',
    description: 'Gestiona el personal médico y sus especialidades',
    icon: Stethoscope,
    navIcon: UserRound,
    singular: 'doctor',
    nuevo: 'Nuevo',
    columns: [
      { key: 'nombre', label: 'Nombre' },
      { key: 'especialidad', label: 'Especialidad' },
      { key: 'celular', label: 'Celular' },
      { key: 'turno', label: 'Turno' },
      { key: 'estado', label: 'Estado', badge: true },
    ],
    fields: [
      // Datos personales
      { key: 'nombres', label: 'Nombre(s)', required: true, group: 'Datos personales' },
      { key: 'apellidos', label: 'Apellidos', required: true, group: 'Datos personales' },
      { key: 'fecha_nacimiento', label: 'Fecha de nacimiento', type: 'date', group: 'Datos personales' },
      { key: 'direccion', label: 'Dirección', group: 'Datos personales' },
      { key: 'celular', label: 'Celular (10 dígitos)', required: true, type: 'tel', pattern: CELULAR_PATTERN, group: 'Datos personales' },
      { key: 'correo', label: 'Correo electrónico', required: true, type: 'email', pattern: EMAIL_PATTERN, group: 'Datos personales' },
      { key: 'contacto_emergencia', label: 'Contacto de emergencia', group: 'Datos personales' },

      // Datos profesionales
      { key: 'especialidad', label: 'Especialidad', required: true, group: 'Datos profesionales' },
      { key: 'cedula_profesional', label: 'Cédula profesional', required: true, group: 'Datos profesionales' },
      { key: 'turno', label: 'Turno', options: ['Matutino', 'Vespertino', 'Nocturno'], group: 'Datos profesionales' },
      { key: 'estado', label: 'Estado', options: ['Activo', 'En guardia', 'Descanso'], group: 'Datos profesionales' },

      // Verificación: igual que Operadores, la foto de referencia se compara
      // por reconocimiento facial antes de asignar al doctor a una emergencia.
      {
        key: 'foto',
        label: 'Foto de referencia (rostro)',
        type: 'photo',
        required: true,
        group: 'Verificación',
        hint: 'Se usa para verificar por reconocimiento facial que es el mismo doctor antes de asignarlo a una emergencia.',
      },
    ],
  },
  {
    key: 'ambulancias',
    label: 'Ambulancias',
    description: 'Administra la flota de ambulancias y su disponibilidad',
    icon: Ambulance,
    navIcon: Ambulance,
    singular: 'ambulancia',
    nuevo: 'Nueva',
    columns: [
      { key: 'placa', label: 'Placa' },
      { key: 'tipo', label: 'Tipo' },
      { key: 'conductor', label: 'Conductor' },
      { key: 'estado', label: 'Estado', badge: true },
    ],
    fields: [
      { key: 'placa', label: 'Placa', required: true },
      { key: 'tipo', label: 'Tipo', options: ['Básica', 'Avanzada'] },
      { key: 'conductor', label: 'Conductor' },
      { key: 'estado', label: 'Estado', options: ['Disponible', 'En servicio', 'Mantenimiento'] },
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
    columns: [
      { key: 'folio', label: 'Folio' },
      { key: 'paciente_nombre', label: 'Paciente' },
      { key: 'descripcion', label: 'Descripción' },
      { key: 'prioridad', label: 'Prioridad', badge: true },
      { key: 'doctor', label: 'Doctor' },
      { key: 'operador', label: 'Operador' },
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
      { key: 'estado', label: 'Estado', options: ['Pendiente', 'Asignada', 'En curso', 'Cerrada'], group: 'Emergencia' },

      // Asignación: se elige de las bases de datos reales, no se escribe a mano
      {
        key: 'doctor',
        label: 'Doctor que atiende',
        group: 'Asignación',
        source: 'doctores',
        optionValue: (r) => r.nombre,
        optionLabel: (r) => `${r.nombre} · ${r.especialidad}${r.estado === 'Descanso' ? ' (descanso)' : ''}`,
        allowEmpty: true,
        emptyLabel: 'Sin doctor asignado',
        // Igual que con el operador: antes de asignarlo se compara por
        // reconocimiento facial contra la foto de referencia del doctor.
        requireFaceVerification: true,
      },
      {
        key: 'operador',
        label: 'Operador que atiende',
        group: 'Asignación',
        source: 'operadores',
        optionValue: (r) => r.nombre,
        optionLabel: (r) => `${r.nombre} · turno ${r.turno}${r.estado === 'Desconectado' ? ' (desconectado)' : ''}`,
        allowEmpty: true,
        emptyLabel: 'Sin operador asignado',
        // Antes de asignarlo, se le pide al despachador tomar una foto del
        // operador y se compara por reconocimiento facial contra la foto
        // con la que ese operador se registró. Se vuelve a pedir al marcar
        // la emergencia como "En curso" (salida de la ambulancia).
        requireFaceVerification: true,
      },
      {
        key: 'ambulancia',
        label: 'Ambulancia asignada',
        group: 'Asignación',
        source: 'ambulancias',
        optionValue: (r) => r.placa,
        optionLabel: (r) => `${r.placa} · ${r.tipo} (${r.estado})`,
        allowEmpty: true,
        emptyLabel: 'Sin ambulancia asignada',
      },
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
    columns: [
      { key: 'nombre', label: 'Nombre' },
      { key: 'turno', label: 'Turno' },
      { key: 'extension', label: 'Extensión' },
      { key: 'estado', label: 'Estado', badge: true },
    ],
    fields: [
      { key: 'nombres', label: 'Nombre(s)', required: true, group: 'Datos personales' },
      { key: 'apellidos', label: 'Apellidos', required: true, group: 'Datos personales' },
      { key: 'celular', label: 'Celular (10 dígitos)', required: true, type: 'tel', pattern: CELULAR_PATTERN, group: 'Datos personales' },
      { key: 'correo', label: 'Correo electrónico', required: true, type: 'email', pattern: EMAIL_PATTERN, group: 'Datos personales' },
      { key: 'turno', label: 'Turno', options: ['Matutino', 'Vespertino', 'Nocturno'], group: 'Datos personales' },
      { key: 'extension', label: 'Extensión', group: 'Datos personales' },
      { key: 'estado', label: 'Estado', options: ['En línea', 'Desconectado'], group: 'Datos personales' },
      {
        key: 'foto',
        label: 'Foto de referencia (rostro)',
        type: 'photo',
        required: true,
        hint: 'Se usa para verificar por reconocimiento facial que es el mismo operador antes de que salga una ambulancia.',
      },
    ],
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
