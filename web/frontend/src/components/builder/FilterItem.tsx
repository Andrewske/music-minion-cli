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
    <div className="flex items-center justify-between bg-slate-800 rounded-lg p-2 group">
      <div className="flex items-center gap-2 text-sm">
        <span className="px-2 py-0.5 bg-blue-600 rounded text-xs font-medium">
          {filter.field}
        </span>
        <span className="text-gray-400">{operatorSymbol}</span>
        <span className="text-white">
          {isNumeric ? filter.value : `"${filter.value}"`}
        </span>
      </div>

      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button
          type="button"
          onClick={onEdit}
          disabled={disabled}
          className="p-1 hover:bg-slate-700 rounded text-gray-400 hover:text-blue-400"
          title="Edit filter"
        >
          ✏️
        </button>
        <button
          type="button"
          onClick={onDelete}
          disabled={disabled}
          className="p-1 hover:bg-slate-700 rounded text-gray-400 hover:text-red-400"
          title="Delete filter"
        >
          ×
        </button>
      </div>
    </div>
  );
}

export default FilterItem;