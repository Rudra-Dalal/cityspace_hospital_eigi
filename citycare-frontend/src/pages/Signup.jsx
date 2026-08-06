import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, formatApiDetail, setStoredAuth } from '../api/client'
import FormInput from '../components/FormInput'

const MOBILE_RE = /^\+91[6-9]\d{9}$/

export default function Signup() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    mobile: '+91',
    password: '',
    confirm: '',
  })
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState('')
  const [loading, setLoading] = useState(false)

  function update(field) {
    return (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }))
  }

  function validate() {
    const next = {}
    if (!form.first_name.trim()) next.first_name = 'First name is required'
    if (!form.last_name.trim()) next.last_name = 'Last name is required'
    if (!form.email.trim()) next.email = 'Email is required'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) next.email = 'Enter a valid email'
    if (!MOBILE_RE.test(form.mobile.trim())) {
      next.mobile = 'Use +91 followed by a 10-digit Indian mobile number'
    }
    if (form.password.length < 8) next.password = 'Password must be at least 8 characters'
    if (form.password !== form.confirm) next.confirm = 'Passwords do not match'
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setApiError('')
    if (!validate()) return

    setLoading(true)
    try {
      await api.signup({
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        email: form.email.trim(),
        mobile: form.mobile.trim(),
        password: form.password,
      })
      const data = await api.login({ email: form.email.trim(), password: form.password })
      setStoredAuth({ token: data.access_token, user: data.user })
      navigate(data.user.role === 'doctor' ? '/doctor' : '/dashboard', { replace: true })
    } catch (err) {
      setApiError(formatApiDetail(err.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page-wrap flex justify-center py-10">
      <div className="card-surface w-full max-w-lg">
        <h1 className="font-display text-2xl font-bold text-clinic-900">Create patient account</h1>
        <p className="mt-1 text-sm text-clinic-600">Sign up to book appointments at CityCare Clinic</p>

        {apiError && (
          <div className="error-banner mt-4" role="alert">
            {apiError}
          </div>
        )}

        <form className="mt-6 grid gap-4 sm:grid-cols-2" onSubmit={handleSubmit} noValidate>
          <FormInput label="First name" required value={form.first_name} onChange={update('first_name')} error={errors.first_name} />
          <FormInput label="Last name" required value={form.last_name} onChange={update('last_name')} error={errors.last_name} />
          <div className="sm:col-span-2">
            <FormInput label="Email" type="email" required value={form.email} onChange={update('email')} error={errors.email} />
          </div>
          <div className="sm:col-span-2">
            <FormInput
              label="Mobile"
              required
              value={form.mobile}
              onChange={update('mobile')}
              error={errors.mobile}
              hint="Format: +9198XXXXXXXX"
            />
          </div>
          <FormInput
            label="Password"
            type="password"
            required
            value={form.password}
            onChange={update('password')}
            error={errors.password}
          />
          <FormInput
            label="Confirm password"
            type="password"
            required
            value={form.confirm}
            onChange={update('confirm')}
            error={errors.confirm}
          />
          <div className="sm:col-span-2">
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? 'Creating account…' : 'Sign up'}
            </button>
          </div>
        </form>

        <p className="mt-4 text-center text-sm text-clinic-700">
          Already registered?{' '}
          <Link to="/login" className="font-semibold text-clinic-700 underline-offset-2 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
