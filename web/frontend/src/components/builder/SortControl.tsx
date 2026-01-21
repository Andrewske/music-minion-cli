import type { SortField, SortDirection } from '../../hooks/useBuilderSession';

interface SortControlProps {
  sortField: SortField;
  sortDirection: SortDirection;
  onSortFieldChange: (field: SortField) => void;
  onSortDirectionChange: (direction: SortDirection) => void;
}

const SORT_OPTIONS = [
  { value: 'artist', label: 'Artist' },
  { value: 'title', label: 'Title' },
  { value: 'year', label: 'Year' },
  { value: 'bpm', label: 'BPM' },
  { value: 'elo_rating', label: 'Rating' }
] as const;

export function SortControl({
  sortField,
  sortDirection,
  onSortFieldChange,
  onSortDirectionChange
}: SortControlProps) {
  const toggleDirection = () => {
    onSortDirectionChange(sortDirection === 'asc' ? 'desc' : 'asc');
  };

  const directionIcon = sortDirection === 'asc' ? '↑' : '↓';
  const directionLabel = (sortField === 'artist' || sortField === 'title')
    ? (sortDirection === 'asc' ? 'A→Z' : 'Z→A')
    : directionIcon;

  return (
    <div className="flex items-center gap-2 text-sm">
      <span>Sort:</span>
      <select
        value={sortField}
        onChange={(e) => onSortFieldChange(e.target.value as SortField)}
        className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-white"
      >
        {SORT_OPTIONS.map(option => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={toggleDirection}
        className="px-2 py-1 bg-slate-700 hover:bg-slate-600 rounded text-white"
        title={`Sort ${sortDirection === 'asc' ? 'ascending' : 'descending'}`}
      >
        {directionLabel}
      </button>
    </div>
  );
}