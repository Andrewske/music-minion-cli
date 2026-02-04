interface TimeInputProps {
  value: string; // "HH:MM"
  onChange: (value: string) => void;
  label: string;
  error?: string;
}

export function TimeInput({
  value,
  onChange,
  label,
  error,
}: TimeInputProps): JSX.Element {
  return (
    <div className="flex flex-col">
      <label className="text-sm text-slate-400 mb-1 font-medium">
        {label}
      </label>
      <input
        type="time"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`
          bg-slate-800 border rounded-lg px-3 py-2 text-white
          focus:outline-none focus:ring-2 focus:ring-emerald-500
          ${error ? 'border-red-500' : 'border-slate-700'}
        `}
      />
      {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
    </div>
  );
}
