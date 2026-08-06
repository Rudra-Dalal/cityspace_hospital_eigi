import { Navigate, Route, Routes } from 'react-router-dom'
import Navbar from './components/Navbar'
import ProtectedRoute from './components/ProtectedRoute'
import { getStoredAuth } from './api/client'
import Book from './pages/Book'
import Dashboard from './pages/Dashboard'
import DoctorDashboard from './pages/DoctorDashboard'
import Login from './pages/Login'
import Signup from './pages/Signup'

function HomeRedirect() {
  const auth = getStoredAuth()
  if (!auth?.user) return <Navigate to="/login" replace />
  return <Navigate to={auth.user.role === 'doctor' ? '/doctor' : '/dashboard'} replace />
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

          <Route element={<ProtectedRoute role="patient" />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/book" element={<Book />} />
          </Route>

          <Route element={<ProtectedRoute role="doctor" />}>
            <Route path="/doctor" element={<DoctorDashboard />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
