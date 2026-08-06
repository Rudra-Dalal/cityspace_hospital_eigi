import { Navigate, Outlet } from 'react-router-dom'
import { getStoredAuth } from '../api/client'

/**
 * role: 'patient' | 'doctor' | undefined (any authenticated user)
 */
export default function ProtectedRoute({ role }) {
  const auth = getStoredAuth()

  if (!auth?.token || !auth?.user) {
    return <Navigate to="/login" replace />
  }

  if (role === 'patient' && auth.user.role !== 'patient') {
    return <Navigate to="/doctor" replace />
  }

  if (role === 'doctor' && auth.user.role !== 'doctor') {
    return <Navigate to="/dashboard" replace />
  }

  return <Outlet />
}
