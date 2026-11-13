import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './lib/auth.jsx'
import Layout from './components/Layout.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'
import ForgotPassword from './pages/ForgotPassword.jsx'
import ResetPassword from './pages/ResetPassword.jsx'
import Home from './pages/Home.jsx'
import ModulePage from './pages/ModulePage.jsx'
import ModuleFormPage from './pages/ModuleFormPage.jsx'
import RecordDetailPage from './pages/RecordDetailPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import OperatorValidationPage from './pages/OperatorValidationPage.jsx'
import RutasPage from './pages/RutasPage.jsx'
import HistorialPage from './pages/HistorialPage.jsx'
import TiempoLlegadaPage from './pages/TiempoLlegadaPage.jsx'
import { ClipboardList, Fuel, History, Route as RouteIcon, Siren, Truck } from 'lucide-react'
import PortalLayout from './components/PortalLayout.jsx'
import MiTurno from './pages/operador/MiTurno.jsx'
import Gasolina from './pages/operador/Gasolina.jsx'
import MiHistorial from './pages/operador/MiHistorial.jsx'
import Reportar from './pages/usuario/Reportar.jsx'
import MisReportes from './pages/usuario/MisReportes.jsx'

function Protected({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="splash">Cargando…</div>
  return user ? children : <Navigate to="/login" replace />
}

function PublicOnly({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="splash">Cargando…</div>
  return user ? <Navigate to="/" replace /> : children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
      <Route path="/registro" element={<PublicOnly><Register /></PublicOnly>} />
      <Route path="/recuperar" element={<PublicOnly><ForgotPassword /></PublicOnly>} />
      <Route path="/restablecer" element={<PublicOnly><ResetPassword /></PublicOnly>} />
      <Route path="/*" element={<Protected><PorPerfil /></Protected>} />
    </Routes>
  )
}

// Cada perfil ve su propia aplicación (los permisos también se revisan en el backend).
const NAV_OPERADOR = [
  { to: '/', label: 'Mi turno', icon: Truck },
  { to: '/gasolina', label: 'Gasolina', icon: Fuel },
  { to: '/rutas', label: 'Rutas y tráfico', icon: RouteIcon },
  { to: '/historial', label: 'Historial', icon: History },
]
const NAV_USUARIO = [
  { to: '/', label: 'Reportar', icon: Siren },
  { to: '/mis-reportes', label: 'Mis reportes', icon: ClipboardList },
]

function PorPerfil() {
  const { user } = useAuth()
  if (user.role === 'Operador') {
    return (
      <Routes>
        <Route element={<PortalLayout nav={NAV_OPERADOR} etiqueta="Operador" />}>
          <Route index element={<MiTurno />} />
          <Route path="gasolina" element={<Gasolina />} />
          <Route path="rutas" element={<RutasPage />} />
          <Route path="historial" element={<MiHistorial />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    )
  }
  if (user.role === 'Usuario') {
    return (
      <Routes>
        <Route element={<PortalLayout nav={NAV_USUARIO} etiqueta="Reportes" />}>
          <Route index element={<Reportar />} />
          <Route path="mis-reportes" element={<MisReportes />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    )
  }
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="configuracion" element={<SettingsPage />} />
        <Route path="rutas" element={<RutasPage />} />
        {/* El despacho ahora es una pestaña de Inteligencia artificial. */}
        <Route path="despacho" element={<Navigate to="/llegada?tab=despacho" replace />} />
        <Route path="historial" element={<HistorialPage />} />
        <Route path="llegada" element={<TiempoLlegadaPage />} />
        <Route path="operadores/validar/:emergenciaId" element={<OperatorValidationPage />} />
        <Route path=":module/nuevo" element={<ModuleFormPage />} />
        <Route path=":module/:id" element={<RecordDetailPage />} />
        <Route path=":module" element={<ModulePage />} />
      </Route>
    </Routes>
  )
}
