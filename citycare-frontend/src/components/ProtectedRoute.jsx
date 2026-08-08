import { Navigate, Outlet } from 'react-router-dom'
import { getStoredAuth } from '../api/client'

// Role → home page mapping (mirrors backend roles)
export const ROLE_HOME = {
  super_admin:      '/admin/dashboard',
  hospital_manager: '/manager/dashboard',
  doctor:           '/doctor/dashboard',
  customer:         '/patient/dashboard',
  // Legacy aliases
  patient:          '/patient/dashboard',
}

/**
 * roles: string | string[] — the allowed role(s) for this route group.
 * Any unauthenticated user → /login
 * Wrong role → their own home page
 */
export default function ProtectedRoute({ roles }) {
  const auth = getStoredAuth()

  if (!auth?.token || !auth?.user) {
    return <Navigate to="/login" replace />
  }

  const userRole = auth.user.role
  const allowed = Array.isArray(roles) ? roles : [roles]

  if (allowed.length > 0 && !allowed.includes(userRole)) {
    const home = ROLE_HOME[userRole] ?? '/login'
    return <Navigate to={home} replace />
  }

  return <Outlet />
}
