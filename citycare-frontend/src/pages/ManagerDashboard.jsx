import { useEffect, useState } from 'react'
import { api, formatApiDetail } from '../api/client'

function StatCard({ label, value }) {
  return (
    <div className="card-surface flex flex-col gap-1 border-l-4 border-clinic-500">
      <p className="text-sm text-clinic-600">{label}</p>
      <p className="text-3xl font-bold text-clinic-900">{value ?? '—'}</p>
    </div>
  )
}

export default function ManagerDashboard() {
  const [hospital,     setHospital]     = useState(null)
  const [doctors,      setDoctors]      = useState([])
  const [appointments, setAppointments] = useState([])
  const [loading,      setLoading]      = useState(false)
  const [error,        setError]        = useState('')
  const [tab,          setTab]          = useState('overview')

  async function loadAll() {
    setLoading(true)
    try {
      const [h, d, a] = await Promise.all([
        api.managerHospital(),
        api.managerDoctors(),
        api.managerAppointments(),
      ])
      setHospital(h)
      setDoctors(d)
      setAppointments(a)
    } catch (err) {
      setError(formatApiDetail(err.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadAll() }, [])

  const today = new Date().toISOString().split('T')[0]
  const todayAppts   = appointments.filter((a) => a.date === today && a.status === 'booked').length
  const bookedCount  = appointments.filter((a) => a.status === 'booked').length
  const cancelledCount = appointments.filter((a) => a.status === 'cancelled').length

  return (
    <div className="page-wrap py-8">
      <div className="mb-6">
        <h1 className="font-display text-3xl font-bold text-clinic-900">
          {hospital?.name ?? 'Hospital Manager'}
        </h1>
        <p className="text-clinic-600 mt-1">
          {hospital ? `${hospital.address}, ${hospital.city}` : 'Loading hospital info…'}
        </p>
      </div>

      {error && <div className="error-banner mb-4">{error}</div>}

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <StatCard label="Doctors"           value={doctors.length} />
        <StatCard label="Today's Bookings"  value={todayAppts} />
        <StatCard label="Total Booked"      value={bookedCount} />
        <StatCard label="Cancelled"         value={cancelledCount} />
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-clinic-200 mb-6">
        {['overview', 'doctors', 'appointments'].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition capitalize ${
              tab === t
                ? 'border-clinic-600 text-clinic-900'
                : 'border-transparent text-clinic-500 hover:text-clinic-700'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {loading && <p className="text-clinic-600">Loading…</p>}

      {/* Overview */}
      {tab === 'overview' && hospital && (
        <div className="card-surface max-w-lg space-y-3">
          <h2 className="font-semibold text-clinic-900 text-lg mb-2">Hospital Profile</h2>
          {[
            ['Name',    hospital.name],
            ['Address', hospital.address],
            ['City',    hospital.city],
            ['State',   hospital.state],
            ['Phone',   hospital.contact_phone],
            ['Email',   hospital.contact_email],
            ['Status',  hospital.status],
          ].map(([k, v]) => (
            <div key={k} className="flex justify-between text-sm">
              <span className="text-clinic-600 font-medium w-24">{k}</span>
              <span className="text-clinic-900 flex-1">{v}</span>
            </div>
          ))}
        </div>
      )}

      {/* Doctors */}
      {tab === 'doctors' && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-clinic-200 text-left text-clinic-600">
                <th className="py-2 pr-4">Name</th>
                <th className="py-2 pr-4">Email</th>
                <th className="py-2">Mobile</th>
              </tr>
            </thead>
            <tbody>
              {doctors.map((d) => (
                <tr key={d.id} className="border-b border-clinic-100 hover:bg-clinic-50">
                  <td className="py-2 pr-4 font-medium text-clinic-900">
                    Dr. {d.first_name} {d.last_name}
                  </td>
                  <td className="py-2 pr-4 text-clinic-600">{d.email}</td>
                  <td className="py-2 text-clinic-600">{d.mobile}</td>
                </tr>
              ))}
              {doctors.length === 0 && (
                <tr><td colSpan={3} className="py-6 text-center text-clinic-400">No doctors assigned.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Appointments */}
      {tab === 'appointments' && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-clinic-200 text-left text-clinic-600">
                <th className="py-2 pr-4">Date</th>
                <th className="py-2 pr-4">Slot</th>
                <th className="py-2 pr-4">Reason</th>
                <th className="py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {appointments.map((a) => (
                <tr key={a.id} className="border-b border-clinic-100 hover:bg-clinic-50">
                  <td className="py-2 pr-4 font-medium text-clinic-900">{a.date}</td>
                  <td className="py-2 pr-4 text-clinic-600">{a.slot}</td>
                  <td className="py-2 pr-4 text-clinic-600 max-w-xs truncate">{a.reason}</td>
                  <td className="py-2">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                      a.status === 'booked'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {a.status}
                    </span>
                  </td>
                </tr>
              ))}
              {appointments.length === 0 && (
                <tr><td colSpan={4} className="py-6 text-center text-clinic-400">No appointments yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
