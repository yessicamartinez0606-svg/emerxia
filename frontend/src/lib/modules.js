import { Ambulance, BrainCircuit, CircleDot, CloudRain, Headset, History, Hospital, Route, Settings, Siren, TrafficCone, UserRound, House } from 'lucide-react'
import { ANIOS_VEHICULO, HOSPITALES, MARCAS_VEHICULO } from './flota.js'

export const HOME = { path: '/', label: 'Inicio', navIcon: House }

// Formato: correo con "@" y dominio; celular exactamente 10 dígitos (se aceptan espacios/guiones
// al escribir, pero al final deben quedar 10 números). El backend valida lo mismo — esto es solo
// para avisarle al usuario al momento, sin esperar a que el servidor lo rechace.
export const EMAIL_PATTERN = { re: /^[^\s@]+@[^\s@]+\.[^\s@]+$/, message: 'Escribe un correo válido, con "@" y dominio (ej. nombre@correo.com).' }
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
      { key: 'modelo', label: 'Modelo (API vPIC · NHTSA)', type: 'modeloApi', group: 'Vehículo',
        hint: 'Modelos reales que fabricó esa marca ese año, según la API pública de la NHTSA.' },
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
      {
        // Si se necesitan más de las que tiene libres el IMSS 220, las demás salen de otros hospitales.
        key: 'ambulancias_requeridas', label: 'Ambulancias necesarias', type: 'number', default: '1', group: 'Emergencia',
        hint: 'Si son más de las que hay libres en el Hospital IMSS 220, se piden a los hospitales más cercanos.',
      },
      { key: 'estado', label: 'Estado', options: ['Pendiente', 'Asignada', 'En curso', 'Cerrada'], group: 'Emergencia' },
      // Opcionales. Con los tres, el modelo de triaje (práctica 05) estima si es crítica.
      { key: 'saturacion_oxigeno', label: 'Saturación de oxígeno (SpO₂ %)', type: 'number', group: 'Signos vitales',
        hint: 'Opcional. Con saturación, frecuencia cardiaca y Glasgow, la IA estima si la emergencia es crítica.' },
      { key: 'frecuencia_cardiaca', label: 'Frecuencia cardiaca (latidos por minuto)', type: 'number', group: 'Signos vitales' },
      { key: 'escala_glasgow', label: 'Escala de Glasgow (3 a 15)', type: 'number', group: 'Signos vitales' },

      // Asignación: no se elige en el formulario. Al guardar, el sistema asigna solo las
      // ambulancias libres más cercanas y el operador es quien maneja la primera.
      {
        key: 'operador',
        label: 'Operador que atiende',
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
      { key: 'experiencia', label: 'Años de experiencia', type: 'number', group: 'Datos personales',
        hint: 'La IA lo usa para estimar si la ambulancia llegará a tiempo.' },
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
    // Pantalla propia (pages/RutasPage.jsx): búsqueda ciega y heurística (greedy, A*) sobre el espacio de estados.
    key: 'rutas',
    label: 'Rutas y tráfico',
    description: 'Encuentra la ruta de la ambulancia evitando el tráfico con búsqueda ciega y heurística (A*)',
    icon: TrafficCone,
    navIcon: Route,
    custom: true,
  },
  {
    // Pantalla propia (pages/TiempoLlegadaPage.jsx): árbol de regresión + clima de las zonas.
    key: 'llegada',
    label: 'Inteligencia artificial',
    description: 'Clima, tiempo de llegada, ¿llega a tiempo?, triaje, perfiles y despacho con algoritmo genético',
    icon: CloudRain,
    navIcon: BrainCircuit,
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
    key: 'configuracion',
    label: 'Configuración',
    description: 'Ajusta las preferencias del sistema y tu cuenta',
    icon: Settings,
    navIcon: Settings,
    custom: true,
  },
]

export const findModule = (key) => MODULES.find((m) => m.key === key)
