interface ConjunctionToggleProps {
  conjunction: 'AND' | 'OR';
  onChange: () => void;
  disabled?: boolean;
}

function ConjunctionToggle({ conjunction, onChange, disabled }: ConjunctionToggleProps) {
  return (
    <div className="flex justify-center py-1">
      <button
        type="button"
        onClick={onChange}
        disabled={disabled}
        className={`px-3 py-1 text-xs rounded-full font-medium transition-colors ${
          conjunction === 'AND'
            ? 'bg-slate-700 hover:bg-slate-600 text-gray-300'
            : 'bg-blue-600 hover:bg-blue-700 text-white'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        {conjunction}
      </button>
    </div>
  );
}

export default ConjunctionToggle;