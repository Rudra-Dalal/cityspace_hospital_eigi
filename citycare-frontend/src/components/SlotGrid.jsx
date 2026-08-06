export default function SlotGrid({ slots, selected, onSelect, loading, emptyMessage }) {
  if (loading) {
    return <p className="text-sm text-clinic-600">Loading available slots…</p>
  }

  if (!slots?.length) {
    return (
      <p className="rounded-lg border border-dashed border-clinic-300 bg-clinic-50 px-3 py-6 text-center text-sm text-clinic-700">
        {emptyMessage || 'No free slots for this date.'}
      </p>
    )
  }

  return (
    <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-6" role="listbox" aria-label="Available slots">
      {slots.map((slot) => {
        const isSelected = selected === slot
        return (
          <button
            key={slot}
            type="button"
            role="option"
            aria-selected={isSelected}
            onClick={() => onSelect(slot)}
            className={`rounded-full border px-3 py-2 text-sm font-medium transition ${
              isSelected
                ? 'border-clinic-600 bg-clinic-600 text-white shadow'
                : 'border-clinic-300 bg-white text-clinic-800 hover:border-clinic-500 hover:bg-clinic-50'
            }`}
          >
            {slot}
          </button>
        )
      })}
    </div>
  )
}
