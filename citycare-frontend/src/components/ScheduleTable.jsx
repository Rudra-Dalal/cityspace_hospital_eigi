export default function ScheduleTable({ rows, loading }) {
  if (loading) {
    return <p className="text-sm text-clinic-600">Loading schedule…</p>
  }

  if (!rows?.length) {
    return (
      <p className="rounded-lg border border-dashed border-clinic-300 bg-clinic-50 px-3 py-10 text-center text-sm text-clinic-700">
        No appointments for this date.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-clinic-200 bg-white">
      <table className="min-w-full text-left text-sm">
        <thead className="bg-clinic-100 text-clinic-800">
          <tr>
            <th className="px-3 py-2 font-semibold">Time</th>
            <th className="px-3 py-2 font-semibold">Patient</th>
            <th className="px-3 py-2 font-semibold">Reason</th>
            <th className="px-3 py-2 font-semibold">Temp</th>
            <th className="px-3 py-2 font-semibold">Symptoms</th>
            <th className="px-3 py-2 font-semibold">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-t border-clinic-100">
              <td className="whitespace-nowrap px-3 py-2 font-medium text-clinic-900">{row.slot}</td>
              <td className="px-3 py-2">{row.patient_name}</td>
              <td className="max-w-xs px-3 py-2">{row.reason}</td>
              <td className="px-3 py-2">{row.temperature != null ? `${row.temperature}°F` : '—'}</td>
              <td className="px-3 py-2">{row.symptoms?.length ? row.symptoms.join(', ') : '—'}</td>
              <td className="px-3 py-2 capitalize">{row.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
