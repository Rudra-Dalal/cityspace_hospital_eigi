import { Link, NavLink, useNavigate } from 'react-router-dom'
import { clearStoredAuth, getStoredAuth } from '../api/client'
import { ROLE_HOME } from './ProtectedRoute'

export default function Navbar() {
  const navigate = useNavigate()
  const auth = getStoredAuth()
  const user = auth?.user

  function logout() {
    clearStoredAuth()
    navigate('/login')
  }

  const linkClass = ({ isActive }) =>
    `rounded-md px-3 py-1.5 text-sm font-medium transition ${
      isActive ? 'bg-clinic-600 text-white' : 'text-clinic-800 hover:bg-clinic-100'
    }`

  const homeUrl = user ? (ROLE_HOME[user.role] ?? '/') : '/'

  return (
    <header className="sticky top-0 z-40 border-b border-clinic-200/80 bg-white/90 backdrop-blur">
      <div className="page-wrap flex flex-wrap items-center justify-between gap-3 py-3">
        <Link to={homeUrl} className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-clinic-600 text-lg font-bold text-white">
            +
          </span>
          <div>
            <p className="font-display text-lg font-semibold leading-tight text-clinic-900">CityCare</p>
            <p className="text-xs text-clinic-600">Hospital Platform</p>
          </div>
        </Link>

        <nav className="flex flex-wrap items-center gap-1" aria-label="Main">
          {!user && (
            <>
              <NavLink to="/login" className={linkClass}>Login</NavLink>
              <NavLink to="/signup" className={linkClass}>Sign up</NavLink>
            </>
          )}

          {/* Customer */}
          {(user?.role === 'customer' || user?.role === 'patient') && (
            <>
              <NavLink to="/patient/dashboard" className={linkClass}>Dashboard</NavLink>
              <NavLink to="/patient/book" className={linkClass}>Book</NavLink>
            </>
          )}

          {/* Doctor */}
          {user?.role === 'doctor' && (
            <NavLink to="/doctor/dashboard" className={linkClass}>Schedule</NavLink>
          )}

          {/* Hospital Manager */}
          {user?.role === 'hospital_manager' && (
            <>
              <NavLink to="/manager/dashboard" className={linkClass}>Dashboard</NavLink>
            </>
          )}

          {/* Super Admin */}
          {user?.role === 'super_admin' && (
            <>
              <NavLink to="/admin/dashboard" className={linkClass}>Dashboard</NavLink>
              <NavLink to="/admin/hospitals" className={linkClass}>Hospitals</NavLink>
              <NavLink to="/admin/users" className={linkClass}>Users</NavLink>
            </>
          )}

          {user && (
            <div className="flex items-center gap-2 ml-2 pl-2 border-l border-clinic-200">
              <span className="text-xs text-clinic-600 hidden sm:block">
                {user.first_name} · <span className="capitalize">{user.role.replace('_', ' ')}</span>
              </span>
              <button type="button" onClick={logout} className="btn-secondary !py-1.5">
                Logout
              </button>
            </div>
          )}
        </nav>
      </div>
    </header>
  )
}
