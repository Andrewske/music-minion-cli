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
        className={`px-3 py-1 text-xs border font-medium transition-colors ${
          conjunction === 'AND'
            ? 'border-obsidian-border text-white/40 hover:border-white/40 hover:text-white/60'
            : 'border-obsidian-accent text-obsidian-accent hover:bg-obsidian-accent/10'
        } disabled:opacity-50 disabled:cursor-not-allowed`}
      >
        {conjunction}
      </button>
    </div>
  );
}

export default ConjunctionToggle;