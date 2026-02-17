import type { Filter } from '../../api/builder';
import { getOperatorSymbol } from './filterUtils';

interface FilterItemProps {
  filter: Filter;
  onEdit: () => void;
  onDelete: () => void;
  disabled?: boolean;
}

function FilterItem({ filter, onEdit, onDelete, disabled }: FilterItemProps) {
  const operatorSymbol = getOperatorSymbol(filter.operator);
  const isNumeric = ['year', 'bpm'].includes(filter.field);

  return (
    <div className="flex items-center justify-between border border-obsidian-border p-2 group hover:bg-white/5 transition-colors">
      <div className="flex items-center gap-2 text-sm">
        <span className="px-2 py-0.5 border border-obsidian-accent text-obsidian-accent text-xs font-medium">
          {filter.field}
        </span>
        <span className="text-white/40">{operatorSymbol}</span>
        <span className="text-white">
          {isNumeric ? filter.value : `"${filter.value}"`}
        </span>
      </div>

      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          type="button"
          onClick={onEdit}
          disabled={disabled}
          className="p-1 hover:bg-white/10 text-white/40 hover:text-obsidian-accent transition-colors"
          title="Edit filter"
        >
          ✏️
        </button>
        <button
          type="button"
          onClick={onDelete}
          disabled={disabled}
          className="p-1 hover:bg-white/10 text-white/40 hover:text-red-400 transition-colors"
          title="Delete filter"
        >
          ×
        </button>
      </div>
    </div>
  );
}

export default FilterItem;