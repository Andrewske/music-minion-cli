import { useState, Fragment } from 'react';
import type { Filter } from '../../api/builder';
import FilterItem from './FilterItem';
import ConjunctionToggle from './ConjunctionToggle';
import FilterEditor from './FilterEditor';

interface FilterPanelProps {
  filters: Filter[];
  onUpdate: (filters: Filter[]) => void;
  isUpdating: boolean;
  playlistId: number;
}

function FilterPanel({ filters, onUpdate, isUpdating, playlistId }: FilterPanelProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingFilter, setEditingFilter] = useState<Filter | undefined>(undefined);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const startAdding = () => {
    setIsEditing(true);
    setEditingIndex(null);
    setEditingFilter(undefined);
  };

  const startEditing = (index: number) => {
    setIsEditing(true);
    setEditingIndex(index);
    setEditingFilter(filters[index]);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditingIndex(null);
    setEditingFilter(undefined);
  };

  const handleSave = async (filter: Filter) => {
    try {
      const updatedFilters = editingIndex !== null
        ? filters.map((f, i) => i === editingIndex ? filter : f)
        : [...filters, filter];

      await onUpdate(updatedFilters);
      setIsEditing(false);
      setEditingIndex(null);
      setEditingFilter(undefined);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setToastMessage(`❌ Failed to save filter: ${errorMessage}`);
      setTimeout(() => setToastMessage(null), 5000);
    }
  };

  const handleDelete = async (index: number) => {
    try {
      const updatedFilters = filters.filter((_, i) => i !== index);
      await onUpdate(updatedFilters);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setToastMessage(`❌ Failed to delete filter: ${errorMessage}`);
      setTimeout(() => setToastMessage(null), 5000);
    }
  };

  const toggleConjunction = async (index: number) => {
    try {
      const updatedFilters = filters.map((f, i) =>
        i === index
          ? { ...f, conjunction: f.conjunction === 'AND' ? 'OR' as const : 'AND' as const }
          : f
      );
      await onUpdate(updatedFilters);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setToastMessage(`❌ Failed to toggle conjunction: ${errorMessage}`);
      setTimeout(() => setToastMessage(null), 5000);
    }
  };

  const handleClearAll = async () => {
    if (!confirm('Clear all filters? This will reset the candidate pool.')) {
      return;
    }
    try {
      await onUpdate([]);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setToastMessage(`❌ Failed to clear filters: ${errorMessage}`);
      setTimeout(() => setToastMessage(null), 5000);
    }
  };

  return (
    <>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Filters</h3>
        {filters.length > 0 && (
          <button
            type="button"
            onClick={handleClearAll}
            className="text-xs text-red-400 hover:text-red-300"
          >
            Clear All
          </button>
        )}
      </div>

      <div className="space-y-2 mb-4">
        {filters.map((filter, idx) => (
          <Fragment key={`${filter.field}-${filter.operator}-${filter.value}-${idx}`}>
            {idx > 0 && (
              <ConjunctionToggle
                conjunction={filter.conjunction}
                onChange={() => toggleConjunction(idx)}
                disabled={isUpdating}
              />
            )}
            <FilterItem
              filter={filter}
              onEdit={() => startEditing(idx)}
              onDelete={() => handleDelete(idx)}
              disabled={isUpdating}
            />
          </Fragment>
        ))}
      </div>

      {isEditing ? (
        <FilterEditor
          initialFilter={editingFilter}
          editingIndex={editingIndex}
          playlistId={playlistId}
          onSave={handleSave}
          onCancel={handleCancel}
        />
      ) : (
        <button
          type="button"
          onClick={startAdding}
          disabled={isUpdating}
          className="w-full py-2 border-2 border-dashed border-slate-700 rounded-lg hover:border-blue-500 text-sm text-gray-400 hover:text-blue-400 disabled:opacity-50"
        >
          + Add Filter
        </button>
      )}

      {filters.length === 0 && !isEditing && (
        <div className="text-center py-8 text-gray-500">
          <p className="text-sm mb-3">No filters active</p>
          <p className="text-xs">All tracks are candidates</p>
        </div>
      )}

      {toastMessage && (
        <div className="fixed top-4 right-4 bg-red-600 text-white px-4 py-2 rounded-lg shadow-lg z-50 max-w-sm">
          {toastMessage}
        </div>
      )}
    </>
  );
}

export default FilterPanel;