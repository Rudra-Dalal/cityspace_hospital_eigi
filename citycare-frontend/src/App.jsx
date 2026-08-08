import { Navigate, Route, Routes } from 'react-router-dom'
import Navbar from './components/Navbar'
import ProtectedRoute from './components/ProtectedRoute'
import { ROLE_HOME } from './components/ProtectedRoute'
import { getStoredAuth } from './api/client'

// Existing pages
import Book from './pages/Book'
import Dashboard from './pages/Dashboard'
import DoctorDashboard from './pages/DoctorDashboard'
import Login from './pages/Login'
import Signup from './pages/Signup'

// New pages
import AdminDashboard from './pages/AdminDashboard'
import ManagerDashboard from './pages/ManagerDashboard'

function HomeRedirect() {
  const auth = getStoredAuth()
  if (!auth?.user) return <Navigate to="/login" replace />
  const home = ROLE_HOME[auth.user.role] ?? '/login'
  return <Navigate to={home} replace />
}

export default function App() {
  return (
    <div className="min-h-screen">
      <Navbar />
      <main>
        <Routes>
          <Route path="/" element={<HomeRedirect />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />

          {/* Customer routes */}
          <Route element={<ProtectedRoute roles={['customer', 'patient']} />}>
            <Route path="/patient/dashboard" element={<Dashboard />} />
            <Route path="/patient/book" element={<Book />} />
            {/* Legacy aliases — keep old bookmarks working */}
            <Route path="/dashboard" element={<Navigate to="/patient/dashboard" replace />} />
            <Route path="/book" element={<Navigate to="/patient/book" replace />} />
          </Route>

          {/* Doctor routes */}
          <Route element={<ProtectedRoute roles={['doctor']} />}>
            <Route path="/doctor/dashboard" element={<DoctorDashboard />} />
            {/* Legacy alias */}
            <Route path="/doctor" element={<Navigate to="/doctor/dashboard" replace />} />
          </Route>

          {/* Hospital Manager routes */}
          <Route element={<ProtectedRoute roles={['hospital_manager', 'super_admin']} />}>
            <Route path="/manager/dashboard" element={<ManagerDashboard />} />
          </Route>

          {/* Super Admin routes */}
          <Route element={<ProtectedRoute roles={['super_admin']} />}>
            <Route path="/admin/dashboard" element={<AdminDashboard />} />
            <Route path="/admin/hospitals" element={<AdminDashboard tab="hospitals" />} />
            <Route path="/admin/users" element={<AdminDashboard tab="users" />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
