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
      <Route element={<Protected><Layout /></Protected>}>
        <Route index element={<Home />} />
        <Route path="configuracion" element={<SettingsPage />} />
        <Route path=":module/nuevo" element={<ModuleFormPage />} />
        <Route path=":module/:id" element={<RecordDetailPage />} />
        <Route path=":module" element={<ModulePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
