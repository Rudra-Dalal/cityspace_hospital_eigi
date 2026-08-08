import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, formatApiDetail, setStoredAuth } from '../api/client'
import FormInput from '../components/FormInput'
import { ROLE_HOME } from '../components/ProtectedRoute'

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState('')
  const [loading, setLoading] = useState(false)

  function validate() {
    const next = {}
    if (!email.trim()) next.email = 'Email is required'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) next.email = 'Enter a valid email'
    if (!password) next.password = 'Password is required'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setApiError('')
    if (!validate()) return

    setLoading(true)
    try {
      const data = await api.login({ email: email.trim(), password })
      setStoredAuth({ token: data.access_token, user: data.user })
      const home = ROLE_HOME[data.user.role] ?? '/patient/dashboard'
      navigate(home, { replace: true })
    } catch (err) {
      setApiError(formatApiDetail(err.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-wrap flex justify-center py-10">
      <div className="card-surface w-full max-w-md">
        <h1 className="font-display text-2xl font-bold text-clinic-900">Welcome back</h1>
        <p className="mt-1 text-sm text-clinic-600">Sign in to CityCare Clinic</p>

        {apiError && (
          <div className="error-banner mt-4" role="alert">
            {apiError}
          </div>
        )}

        <form className="mt-6 space-y-4" onSubmit={handleSubmit} noValidate>
          <FormInput
            label="Email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={errors.email}
          />
          <FormInput
            label="Password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.password}
          />
          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-clinic-700">
          New patient?{' '}
          <Link to="/signup" className="font-semibold text-clinic-700 underline-offset-2 hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  )
}
