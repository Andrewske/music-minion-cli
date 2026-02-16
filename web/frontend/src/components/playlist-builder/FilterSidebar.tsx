import { useState, Fragment } from 'react';
import type { Filter } from '../../api/builder';
import { useFilterStore } from '../../stores/filterStore';

export function FilterSidebar(): JSX.Element {
  const { filters, setFilters, removeFilter, updateFilter, clearFilters, toggleConjunction } = useFilterStore();
  const [isEditing, setIsEditing] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingFilter, setEditingFilter] = useState<Filter | undefined>(undefined);

  const startAdding = (): void => {
    setIsEditing(true);
    setEditingIndex(null);
    setEditingFilter(undefined);
  };

  const startEditing = (idx: number): void => {
    setIsEditing(true);
    setEditingIndex(idx);
    setEditingFilter(filters[idx]);
  };

  const handleCancel = (): void => {
    setIsEditing(false);
    setEditingIndex(null);
    setEditingFilter(undefined);
  };

  const handleSave = (filter: Filter): void => {
    if (editingIndex !== null) {
      updateFilter(editingIndex, filter);
    } else {
      setFilters([...filters, filter]);
    }
    handleCancel();
  };

  const handleDelete = (idx: number): void => {
    removeFilter(idx);
  };

  const handleToggleConjunction = (idx: number): void => {
    toggleConjunction(idx);
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <span className="text-obsidian-accent text-xs tracking-[0.2em] uppercase">Filters</span>
        {filters.length > 0 && (
          <button
            onClick={() => confirm('Clear?') && clearFilters()}
            className="text-white/30 hover:text-white/60 text-xs"
          >
            Clear
          </button>
        )}
      </div>

      <div className="space-y-2 mb-6">
        {filters.map((filter, idx) => (
          <Fragment key={`${filter.field}-${idx}`}>
            {idx > 0 && (
              <button
                onClick={() => handleToggleConjunction(idx)}
                className="w-full py-1 text-white/20 hover:text-white/40 text-xs transition-colors"
              >
                {filter.conjunction}
              </button>
            )}
            <div className="group py-2 border-b border-obsidian-border hover:border-obsidian-accent/30 transition-colors">
              <div className="flex justify-between text-sm">
                <span className="text-white/60">
                  <span className="text-white/30">{filter.field}</span>
                  <span className="text-white/20 mx-2">{filter.operator}</span>
                  <span className="text-white">{filter.value}</span>
                </span>
                <div className="flex gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => startEditing(idx)} className="text-white/40 hover:text-obsidian-accent text-xs">
                    Edit
                  </button>
                  <button onClick={() => handleDelete(idx)} className="text-white/40 hover:text-red-400 text-xs">
                    x
                  </button>
                </div>
              </div>
            </div>
          </Fragment>
        ))}
      </div>

      {isEditing ? (
        <FilterEditor
          initialFilter={editingFilter}
          onSave={handleSave}
          onCancel={handleCancel}
        />
      ) : (
        <button
          onClick={startAdding}
          className="w-full py-2 border border-dashed border-obsidian-border hover:border-obsidian-accent/50
            text-white/30 hover:text-obsidian-accent transition-colors text-xs"
        >
          + Add
        </button>
      )}
    </div>
  );
}

interface FilterEditorProps {
  initialFilter?: Filter;
  onSave: (filter: Filter) => void;
  onCancel: () => void;
}

function FilterEditor({ initialFilter, onSave, onCancel }: FilterEditorProps): JSX.Element {
  const [field, setField] = useState(initialFilter?.field || '');
  const [operator, setOperator] = useState(initialFilter?.operator || '');
  const [value, setValue] = useState(initialFilter?.value || '');

  // For genre autocomplete, we'll use a placeholder empty array for now
  // In the future, this could fetch from a global genres endpoint
  const genres: string[] = [];
  const isNumeric = ['year', 'bpm'].includes(field);

  const inputClass = `w-full bg-black border border-obsidian-border px-3 py-2 text-white text-sm
    focus:border-obsidian-accent/50 focus:outline-none transition-colors`;

  const handleSave = (): void => {
    if (field && operator && value) {
      onSave({ field, operator, value, conjunction: initialFilter?.conjunction || 'AND' });
    }
  };

  return (
    <div className="space-y-4 py-4 border-t border-obsidian-border">
      <select
        value={field}
        onChange={(e) => { setField(e.target.value); setOperator(''); }}
        className={inputClass}
      >
        <option value="">Field</option>
        <option value="title">Title</option>
        <option value="artist">Artist</option>
        <option value="album">Album</option>
        <option value="genre">Genre</option>
        <option value="year">Year</option>
        <option value="bpm">BPM</option>
        <option value="key">Key</option>
      </select>

      {field && !isNumeric && (
        <select value={operator} onChange={(e) => setOperator(e.target.value)} className={inputClass}>
          <option value="">Condition</option>
          <option value="contains">contains</option>
          <option value="equals">equals</option>
          <option value="not_equals">does not equal</option>
          <option value="starts_with">starts with</option>
          <option value="ends_with">ends with</option>
        </select>
      )}

      {field && isNumeric && (
        <select value={operator} onChange={(e) => setOperator(e.target.value)} className={inputClass}>
          <option value="">Condition</option>
          <option value="equals">=</option>
          <option value="not_equals">does not equal</option>
          <option value="gt">&gt;</option>
          <option value="gte">&gt;=</option>
          <option value="lt">&lt;</option>
          <option value="lte">&lt;=</option>
        </select>
      )}

      {field === 'genre' && operator === 'equals' ? (
        <select value={value} onChange={(e) => setValue(e.target.value)} className={inputClass}>
          <option value="">Genre</option>
          {genres.map(g => <option key={g} value={g ?? ''}>{g}</option>)}
        </select>
      ) : field && operator && (
        <input
          type={isNumeric ? 'number' : 'text'}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Value"
          className={inputClass}
        />
      )}

      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={!field || !operator || !value}
          className="flex-1 py-2 border border-obsidian-accent text-obsidian-accent text-xs
            hover:bg-obsidian-accent hover:text-black disabled:opacity-30 transition-all"
        >
          {initialFilter ? 'Update' : 'Add'}
        </button>
        <button
          onClick={onCancel}
          className="flex-1 py-2 border border-obsidian-border text-white/40 text-xs hover:text-white transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
