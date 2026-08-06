import { Link, NavLink, useNavigate } from 'react-router-dom'
import { clearStoredAuth, getStoredAuth } from '../api/client'

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

  return (
    <header className="sticky top-0 z-40 border-b border-clinic-200/80 bg-white/90 backdrop-blur">
      <div className="page-wrap flex flex-wrap items-center justify-between gap-3 py-3">
        <Link to={user?.role === 'doctor' ? '/doctor' : user ? '/dashboard' : '/'} className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-clinic-600 text-lg font-bold text-white">
            +
          </span>
          <div>
            <p className="font-display text-lg font-semibold leading-tight text-clinic-900">CityCare Clinic</p>
            <p className="text-xs text-clinic-600">Dharampeth, Nagpur</p>
          </div>
        </Link>

        <nav className="flex flex-wrap items-center gap-1" aria-label="Main">
          {!user && (
            <>
              <NavLink to="/login" className={linkClass}>
                Login
              </NavLink>
              <NavLink to="/signup" className={linkClass}>
                Sign up
              </NavLink>
            </>
          )}
          {user?.role === 'patient' && (
            <>
              <NavLink to="/dashboard" className={linkClass}>
                Dashboard
              </NavLink>
              <NavLink to="/book" className={linkClass}>
                Book
              </NavLink>
            </>
          )}
          {user?.role === 'doctor' && (
            <NavLink to="/doctor" className={linkClass}>
              Schedule
            </NavLink>
          )}
          {user && (
            <button type="button" onClick={logout} className="btn-secondary ml-1 !py-1.5">
              Logout
            </button>
          )}
        </nav>
      </div>
    </header>
  )
}
