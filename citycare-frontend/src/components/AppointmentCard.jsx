export default function AppointmentCard({ appointment, onCancel, cancelling }) {
  const booked = appointment.status === 'booked'

  return (
    <article className="card-surface flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-display text-lg font-semibold text-clinic-900">
            {appointment.date} · {appointment.slot}
          </p>
          <p className="mt-1 text-sm text-clinic-700">{appointment.reason}</p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${
            booked ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'
          }`}
        >
          {appointment.status}
        </span>
      </div>

      <div className="flex flex-wrap gap-3 text-xs text-clinic-600">
        {appointment.temperature != null && <span>Temp: {appointment.temperature}°F</span>}
        {appointment.symptoms?.length > 0 && <span>Symptoms: {appointment.symptoms.join(', ')}</span>}
      </div>

      {booked && onCancel && (
        <button
          type="button"
          className="btn-secondary self-start !py-1.5 text-xs"
          disabled={cancelling}
          onClick={() => onCancel(appointment)}
        >
          {cancelling ? 'Cancelling…' : 'Cancel appointment'}
        </button>
      )}
    </article>
  )
}
