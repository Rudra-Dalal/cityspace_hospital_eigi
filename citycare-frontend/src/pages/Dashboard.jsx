import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, formatApiDetail, getStoredAuth } from '../api/client'
import AppointmentCard from '../components/AppointmentCard'

export default function Dashboard() {
  const user = getStoredAuth()?.user
  const [clinic, setClinic] = useState(null)
  const [appointments, setAppointments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [cancellingId, setCancellingId] = useState(null)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const [info, mine] = await Promise.all([api.doctorInfo(), api.myAppointments()])
      setClinic(info)
      setAppointments(mine)
    } catch (err) {
      setError(formatApiDetail(err.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function handleCancel(appointment) {
    if (!window.confirm('Cancel this appointment? The slot will become available again.')) return
    setCancellingId(appointment.id)
    try {
      await api.cancel(appointment.id)
      await load()
    } catch (err) {
      setError(formatApiDetail(err.detail || err.message))
    } finally {
      setCancellingId(null)
    }
  }

  return (
    <div className="page-wrap space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold text-clinic-900">
            Hello, {user?.first_name || 'there'}
          </h1>
          <p className="mt-1 text-sm text-clinic-600">Your appointments at CityCare Clinic</p>
        </div>
        <Link to="/book" className="btn-primary">
          Book appointment
        </Link>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {clinic && (
        <section className="card-surface bg-gradient-to-br from-white to-clinic-100/60" aria-labelledby="clinic-heading">
          <h2 id="clinic-heading" className="font-display text-xl font-semibold text-clinic-900">
            {clinic.name}
          </h2>
          <p className="text-sm text-clinic-700">{clinic.qualification}</p>
          <p className="mt-2 text-sm text-clinic-800">
            {clinic.clinic_name} · {clinic.clinic_location}
          </p>
          <p className="mt-2 text-sm text-clinic-700">
            Morning {clinic.morning_hours} · Evening {clinic.evening_hours} · {clinic.slot_duration_minutes} min slots
          </p>
        </section>
      )}

      <section aria-labelledby="appointments-heading">
        <h2 id="appointments-heading" className="mb-3 font-display text-xl font-semibold text-clinic-900">
          My appointments
        </h2>

        {loading ? (
          <p className="text-sm text-clinic-600">Loading your appointments…</p>
        ) : appointments.length === 0 ? (
          <p className="rounded-xl border border-dashed border-clinic-300 bg-white/70 px-4 py-10 text-center text-sm text-clinic-700">
            You have no appointments yet.{' '}
            <Link to="/book" className="font-semibold text-clinic-700 underline-offset-2 hover:underline">
              Book your first visit
            </Link>
          </p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {appointments.map((appt) => (
              <AppointmentCard
                key={appt.id}
                appointment={appt}
                onCancel={handleCancel}
                cancelling={cancellingId === appt.id}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
