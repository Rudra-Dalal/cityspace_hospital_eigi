export default function FormInput({
  label,
  id,
  type = 'text',
  value,
  onChange,
  error,
  hint,
  required,
  as = 'input',
  children,
  ...rest
}) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, '-')
  const shared =
    'mt-1 w-full rounded-lg border border-clinic-300 bg-white px-3 py-2 text-sm text-clinic-900 shadow-sm outline-none transition focus:border-clinic-500 focus:ring-2 focus:ring-clinic-200'

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className="block text-sm font-medium text-clinic-800">
          {label}
          {required ? <span className="text-red-600"> *</span> : null}
        </label>
      )}
      {as === 'textarea' ? (
        <textarea id={inputId} className={shared} value={value} onChange={onChange} {...rest} />
      ) : as === 'select' ? (
        <select id={inputId} className={shared} value={value} onChange={onChange} {...rest}>
          {children}
        </select>
      ) : (
        <input id={inputId} type={type} className={shared} value={value} onChange={onChange} {...rest} />
      )}
      {hint && !error ? <p className="mt-1 text-xs text-clinic-600">{hint}</p> : null}
      {error ? <p className="mt-1 text-xs text-red-600">{error}</p> : null}
    </div>
  )
}
