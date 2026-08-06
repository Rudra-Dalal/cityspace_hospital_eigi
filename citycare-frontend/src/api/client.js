/**
 * Single API client wrapper — all backend calls go through here.
 */
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const AUTH_KEY = 'citycare_auth'

export function getStoredAuth() {
  try {
    const raw = localStorage.getItem(AUTH_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function setStoredAuth(auth) {
  localStorage.setItem(AUTH_KEY, JSON.stringify(auth))
}

export function clearStoredAuth() {
  localStorage.removeItem(AUTH_KEY)
}

/** Turn FastAPI detail (string or validation array) into readable text. */
export function formatApiDetail(detail, fallback = 'Something went wrong.') {
  if (!detail) return fallback
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === 'string') return item
        const loc = Array.isArray(item.loc) ? item.loc.filter((p) => p !== 'body').join('.') : ''
        const msg = item.msg || JSON.stringify(item)
        return loc ? `${loc}: ${msg}` : msg
      })
      .join(' · ')
  }
  if (typeof detail === 'object') return JSON.stringify(detail)
  return String(detail)
}

class ApiError extends Error {
  constructor(status, detail) {
    super(formatApiDetail(detail))
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request(path, { method = 'GET', body, token, authRedirect = true } = {}) {
  const headers = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const authToken = token ?? getStoredAuth()?.token
  if (authToken) headers.Authorization = `Bearer ${authToken}`

  let response
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Is the API running?')
  }

  let data = null
  const text = await response.text()
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = { detail: text }
    }
  }

  if (response.status === 401 && authRedirect) {
    clearStoredAuth()
    if (window.location.pathname !== '/login') {
      window.location.assign('/login')
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, data?.detail ?? 'Request failed')
  }

  return data
}

export const api = {
  signup: (payload) => request('/auth/signup', { method: 'POST', body: payload, authRedirect: false }),
  login: (payload) => request('/auth/login', { method: 'POST', body: payload, authRedirect: false }),
  doctorInfo: () => request('/doctor/info', { authRedirect: false }),
  freeSlots: (date) => request(`/appointments/free-slots?date=${encodeURIComponent(date)}`, { authRedirect: false }),
  book: (payload) => request('/appointments', { method: 'POST', body: payload }),
  myAppointments: () => request('/appointments/my'),
  doctorSchedule: (date) => request(`/doctor/schedule?date=${encodeURIComponent(date)}`),
  doctorStats: () => request('/doctor/stats'),
  cancel: (id) => request(`/appointments/${id}/cancel`, { method: 'PATCH' }),
}

export { ApiError, API_URL }
