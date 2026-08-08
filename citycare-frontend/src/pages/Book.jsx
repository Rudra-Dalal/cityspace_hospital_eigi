import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, formatApiDetail } from '../api/client'
import FormInput from '../components/FormInput'
import SlotGrid from '../components/SlotGrid'

const SYMPTOMS = ['fever', 'cough', 'cold', 'bodyache', 'headache', 'other']

function toIsoLocal(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function addDays(base, n) {
  const d = new Date(base)
  d.setDate(d.getDate() + n)
  return d
}

export default function Book() {
  const today = useMemo(() => new Date(), [])
  const minDate = toIsoLocal(today)
  const maxDate = toIsoLocal(addDays(today, 7))

  const [date, setDate] = useState(minDate)
  const [slots, setSlots] = useState([])
  const [slotsLoading, setSlotsLoading] = useState(false)
  const [slot, setSlot] = useState('')
  const [reason, setReason] = useState('')
  const [temperature, setTemperature] = useState('')
  const [symptoms, setSymptoms] = useState([])
  const [errors, setErrors] = useState({})
  const [apiError, setApiError] = useState('')
  const [conflictHint, setConflictHint] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(null)

  async function loadSlots(forDate) {
    setSlotsLoading(true)
    setApiError('')
    try {
      const data = await api.freeSlots(forDate)
      setSlots(data.free_slots || [])
      setSlot((prev) => (data.free_slots?.includes(prev) ? prev : ''))
    } catch (err) {
      setSlots([])
      setApiError(formatApiDetail(err.detail || err.message))
    } finally {
      setSlotsLoading(false)
    }
  }

  useEffect(() => {
    loadSlots(date)
  }, [date])

  function toggleSymptom(name) {
    setSymptoms((prev) => (prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name]))
  }

  function validate() {
    const next = {}
    if (!date) next.date = 'Pick a date'
    if (!slot) next.slot = 'Select a time slot'
    const nonWs = reason.replace(/\s+/g, '')
    if (nonWs.length < 10) next.reason = 'Reason needs at least 10 non-whitespace characters'
    if (temperature !== '') {
      const t = Number(temperature)
      if (Number.isNaN(t) || t < 95 || t > 110) next.temperature = 'Temperature must be between 95 and 110 °F'
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setApiError('')
    setConflictHint('')
    if (!validate()) return

    setLoading(true)
    try {
      const payload = {
        date,
        slot,
        reason: reason.trim(),
        symptoms,
      }
      if (temperature !== '') payload.temperature = Number(temperature)

      const booked = await api.book(payload)
      setSuccess(booked)
    } catch (err) {
      if (err.status === 409) {
        setConflictHint('That slot just got booked - please pick another')
        await loadSlots(date)
        setSlot('')
      } else {
        setApiError(formatApiDetail(err.detail || err.message))
      }
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className="page-wrap flex justify-center py-10">
        <div className="card-surface w-full max-w-lg space-y-4">
          <div className="success-banner">Appointment booked successfully.</div>
          <h1 className="font-display text-2xl font-bold text-clinic-900">Booking summary</h1>
          <dl className="space-y-2 text-sm text-clinic-800">
            <div className="flex justify-between gap-4">
              <dt className="text-clinic-600">Date</dt>
              <dd className="font-medium">{success.date}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-clinic-600">Slot</dt>
              <dd className="font-medium">{success.slot}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-clinic-600">Reason</dt>
              <dd className="max-w-[60%] text-right font-medium">{success.reason}</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-clinic-600">Status</dt>
              <dd className="font-medium capitalize">{success.status}</dd>
            </div>
          </dl>
          <div className="flex flex-wrap gap-2 pt-2">
            <Link to="/patient/dashboard" className="btn-primary">
              Back to dashboard
            </Link>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setSuccess(null)
                setReason('')
                setTemperature('')
                setSymptoms([])
                loadSlots(date)
              }}
            >
              Book another
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="page-wrap max-w-3xl space-y-6">
      <div>
        <h1 className="font-display text-3xl font-bold text-clinic-900">Book a slot</h1>
        <p className="mt-1 text-sm text-clinic-600">Choose a date within the next 7 days and an open time.</p>
      </div>

      {apiError && (
        <div className="error-banner" role="alert">
          {apiError}
        </div>
      )}
      {conflictHint && (
        <div className="error-banner" role="alert">
          {conflictHint}
        </div>
      )}

      <form className="card-surface space-y-5" onSubmit={handleSubmit} noValidate>
        <FormInput
          label="Date"
          type="date"
          required
          min={minDate}
          max={maxDate}
          value={date}
          onChange={(e) => setDate(e.target.value)}
          error={errors.date}
        />

        <div>
          <p className="mb-2 text-sm font-medium text-clinic-800">
            Available slots<span className="text-red-600"> *</span>
          </p>
          <SlotGrid slots={slots} selected={slot} onSelect={setSlot} loading={slotsLoading} />
          {errors.slot && <p className="mt-1 text-xs text-red-600">{errors.slot}</p>}
        </div>

        <FormInput
          label="Reason for visit"
          as="textarea"
          rows={3}
          required
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          error={errors.reason}
          hint="At least 10 meaningful characters"
        />

        <FormInput
          label="Temperature (°F)"
          type="number"
          step="0.1"
          min="95"
          max="110"
          value={temperature}
          onChange={(e) => setTemperature(e.target.value)}
          error={errors.temperature}
          hint="Optional — between 95 and 110"
        />

        <fieldset>
          <legend className="text-sm font-medium text-clinic-800">Symptoms</legend>
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {SYMPTOMS.map((name) => (
              <label key={name} className="flex items-center gap-2 rounded-lg border border-clinic-200 bg-clinic-50/50 px-3 py-2 text-sm capitalize">
                <input
                  type="checkbox"
                  checked={symptoms.includes(name)}
                  onChange={() => toggleSymptom(name)}
                  className="rounded border-clinic-400 text-clinic-600 focus:ring-clinic-400"
                />
                {name}
              </label>
            ))}
          </div>
        </fieldset>

        <button type="submit" className="btn-primary" disabled={loading || slotsLoading}>
          {loading ? 'Booking…' : 'Confirm booking'}
        </button>
      </form>
    </div>
  )
}
