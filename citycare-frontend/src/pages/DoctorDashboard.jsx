import { useEffect, useMemo, useState } from 'react'
import { api, formatApiDetail, getStoredAuth } from '../api/client'
import FormInput from '../components/FormInput'
import ScheduleTable from '../components/ScheduleTable'
import StatCard from '../components/StatCard'

function toIsoLocal(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export default function DoctorDashboard() {
  const user = getStoredAuth()?.user
  const today = useMemo(() => toIsoLocal(new Date()), [])
  const [date, setDate] = useState(today)
  const [stats, setStats] = useState(null)
  const [rows, setRows] = useState([])
  const [loadingStats, setLoadingStats] = useState(true)
  const [loadingSchedule, setLoadingSchedule] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    async function loadStats() {
      setLoadingStats(true)
      try {
        const data = await api.doctorStats()
        if (!cancelled) setStats(data)
      } catch (err) {
        if (!cancelled) setError(formatApiDetail(err.detail || err.message))
      } finally {
        if (!cancelled) setLoadingStats(false)
      }
    }
    loadStats()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function loadSchedule() {
      setLoadingSchedule(true)
      setError('')
      try {
        const data = await api.doctorSchedule(date)
        if (!cancelled) setRows(data)
      } catch (err) {
        if (!cancelled) {
          setRows([])
          setError(formatApiDetail(err.detail || err.message))
        }
      } finally {
        if (!cancelled) setLoadingSchedule(false)
      }
    }
    loadSchedule()
    return () => {
      cancelled = true
    }
  }, [date])

  return (
    <div className="page-wrap space-y-6">
      <div>
        <h1 className="font-display text-3xl font-bold text-clinic-900">
          Doctor dashboard
        </h1>
        <p className="mt-1 text-sm text-clinic-600">
          Welcome, Dr. {user?.last_name || user?.first_name}. Review clinic activity and today&apos;s schedule.
        </p>
      </div>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      <section className="grid gap-3 sm:grid-cols-3" aria-label="Clinic statistics">
        <StatCard
          label="Total patients"
          value={loadingStats ? '…' : stats?.total_patients ?? '—'}
          hint="Registered patient accounts"
        />
        <StatCard
          label="Today's visits"
          value={loadingStats ? '…' : stats?.today_visits ?? '—'}
          hint="Booked appointments for today"
        />
        <StatCard
          label="Upcoming visits"
          value={loadingStats ? '…' : stats?.upcoming_visits ?? '—'}
          hint="Booked from today onward"
        />
      </section>

      <section className="space-y-3" aria-labelledby="schedule-heading">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 id="schedule-heading" className="font-display text-xl font-semibold text-clinic-900">
            Day schedule
          </h2>
          <div className="w-full max-w-xs">
            <FormInput
              label="Select date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>
        </div>
        <ScheduleTable rows={rows} loading={loadingSchedule} />
      </section>
    </div>
  )
}
