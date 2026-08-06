export default function StatCard({ label, value, hint }) {
  return (
    <div className="card-surface">
      <p className="text-sm font-medium text-clinic-600">{label}</p>
      <p className="mt-2 font-display text-3xl font-bold text-clinic-900">{value}</p>
      {hint ? <p className="mt-1 text-xs text-clinic-500">{hint}</p> : null}
    </div>
  )
}
