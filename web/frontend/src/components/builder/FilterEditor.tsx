import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { Filter } from '../../api/builder';
import { validateFilter, getPlaceholder } from './filterUtils';
import { builderApi } from '../../api/builder';
import { EmojiPicker } from '../EmojiPicker';

function EmojiValuePicker({ value, onChange }: { value: string; onChange: (v: string) => void }): JSX.Element {
  const [showPicker, setShowPicker] = useState(false);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setShowPicker(true)}
        className="w-full bg-slate-700 rounded px-3 py-2 text-white text-left"
      >
        {value || 'Select emoji...'}
      </button>
      {showPicker && (
        <EmojiPicker
          onSelect={(emoji) => { onChange(emoji); setShowPicker(false); }}
          onClose={() => setShowPicker(false)}
        />
      )}
    </div>
  );
}

interface FilterEditorProps {
  initialFilter?: Filter;
  editingIndex: number | null;
  playlistId: number;
  onSave: (filter: Filter) => void;
  onCancel: () => void;
}

export default function FilterEditor({
  initialFilter,
  editingIndex,
  playlistId,
  onSave,
  onCancel
}: FilterEditorProps) {
  const [field, setField] = useState(initialFilter?.field || '');
  const [operator, setOperator] = useState(initialFilter?.operator || '');
  const [value, setValue] = useState(initialFilter?.value || '');
  const [validationError, setValidationError] = useState<string | null>(null);

  // Fetch candidates for genre extraction
  const { data: candidates } = useQuery({
    queryKey: ['builder-candidates', playlistId],
    queryFn: () => builderApi.getCandidates(playlistId, 1000), // Get more candidates for better genre coverage
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  // Extract unique genres with counts
  const uniqueGenres = useMemo(() => {
    if (!candidates?.candidates) return [];
    const genreMap = new Map<string, number>();
    candidates.candidates.forEach(track => {
      if (track.genre) {
        genreMap.set(track.genre, (genreMap.get(track.genre) || 0) + 1);
      }
    });
    return Array.from(genreMap.entries())
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [candidates]);

  // Handle field change with operator compatibility check
  const handleFieldChange = (newField: string) => {
    setField(newField);
    // Clear operator if it's incompatible with the new field
    if (newField && operator) {
      const isNumericField = ['year', 'bpm'].includes(newField);
      const isEmojiField = newField === 'emoji';
      const isNumericOperator = ['equals', 'not_equals', 'gt', 'gte', 'lt', 'lte'].includes(operator);
      const isTextOperator = ['contains', 'equals', 'not_equals', 'starts_with', 'ends_with'].includes(operator);
      const isEmojiOperator = ['has', 'not_has'].includes(operator);

      if (isEmojiField && !isEmojiOperator) {
        setOperator('');
      } else if (isNumericField && !isNumericOperator) {
        setOperator(''); // Clear incompatible operator
      } else if (!isNumericField && !isEmojiField && !isTextOperator) {
        setOperator('');
      }
    }
  };

  // Reset validation error when inputs change
  const resetValidationError = () => {
    if (validationError) {
      setValidationError(null);
    }
  };

  const handleSave = () => {
    const error = validateFilter(field, operator, value);
    if (error) {
      setValidationError(error);
      return;
    }

    onSave({
      field,
      operator,
      value,
      conjunction: initialFilter?.conjunction || 'AND'
    });
  };

  const isValid = field && operator && value && !validateFilter(field, operator, value);

  return (
    <div className="space-y-3">
      {/* Step 1: Field Selection */}
      <div className="bg-slate-800 rounded-lg p-3">
        <label htmlFor="field-select" className="text-xs text-gray-400 block mb-2">Field</label>
        <select
          id="field-select"
          value={field}
          onChange={(e) => {
            handleFieldChange(e.target.value);
            resetValidationError();
          }}
          className="w-full bg-slate-700 rounded px-3 py-2 text-white"
        >
          <option value="">Choose field...</option>
          <option value="title">Title</option>
          <option value="artist">Artist</option>
          <option value="album">Album</option>
          <option value="genre">Genre</option>
          <option value="year">Year</option>
          <option value="bpm">BPM</option>
          <option value="key">Key</option>
          <option value="emoji">Emoji</option>
        </select>
      </div>

      {/* Step 2: Operator Selection (Conditional) */}
      {field && ['title', 'artist', 'album', 'genre', 'key'].includes(field) && (
        <div className="bg-slate-800 rounded-lg p-3 mt-2">
          <label htmlFor="text-operator-select" className="text-xs text-gray-400 block mb-2">Condition</label>
          <select
            id="text-operator-select"
            value={operator}
            onChange={(e) => {
              setOperator(e.target.value);
              resetValidationError();
            }}
            className="w-full bg-slate-700 rounded px-3 py-2 text-white"
          >
            <option value="">Choose condition...</option>
            <option value="contains">contains (~)</option>
            <option value="equals">equals (=)</option>
            <option value="not_equals">not equals (≠)</option>
            <option value="starts_with">starts with</option>
            <option value="ends_with">ends with</option>
          </select>
        </div>
      )}

      {field && ['year', 'bpm'].includes(field) && (
        <div className="bg-slate-800 rounded-lg p-3 mt-2">
          <label htmlFor="numeric-operator-select" className="text-xs text-gray-400 block mb-2">Condition</label>
          <select
            id="numeric-operator-select"
            value={operator}
            onChange={(e) => {
              setOperator(e.target.value);
              resetValidationError();
            }}
            className="w-full bg-slate-700 rounded px-3 py-2 text-white"
          >
            <option value="">Choose condition...</option>
            <option value="equals">equals (=)</option>
            <option value="not_equals">not equals (≠)</option>
            <option value="gt">greater than (&gt;)</option>
            <option value="gte">greater or equal (≥)</option>
            <option value="lt">less than (&lt;)</option>
            <option value="lte">less or equal (≤)</option>
          </select>
        </div>
      )}

      {field === 'emoji' && (
        <div className="bg-slate-800 rounded-lg p-3 mt-2">
          <label htmlFor="emoji-operator-select" className="text-xs text-gray-400 block mb-2">Condition</label>
          <select
            id="emoji-operator-select"
            value={operator}
            onChange={(e) => {
              setOperator(e.target.value);
              resetValidationError();
            }}
            className="w-full bg-slate-700 rounded px-3 py-2 text-white"
          >
            <option value="">Choose condition...</option>
            <option value="has">has emoji</option>
            <option value="not_has">does not have emoji</option>
          </select>
        </div>
      )}

      {/* Step 3: Value Input (Conditional) */}
      {field === 'genre' && operator === 'equals' && (
        <div className="bg-slate-800 rounded-lg p-3 mt-2">
          <label htmlFor="genre-select" className="text-xs text-gray-400 block mb-2">Genre</label>
          <select
            id="genre-select"
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              resetValidationError();
            }}
            className="w-full bg-slate-700 rounded px-3 py-2 text-white"
          >
            <option value="">Choose genre...</option>
            {uniqueGenres.map(({ name, count }) => (
              <option key={name} value={name}>{name} ({count} tracks)</option>
            ))}
          </select>
        </div>
      )}

      {field === 'emoji' && operator && (
        <div className="bg-slate-800 rounded-lg p-3 mt-2">
          <label className="text-xs text-gray-400 block mb-2">Emoji</label>
          <EmojiValuePicker value={value} onChange={(v) => { setValue(v); resetValidationError(); }} />
        </div>
      )}

      {field && operator && field !== 'emoji' && !(field === 'genre' && operator === 'equals') && (
        <div className="bg-slate-800 rounded-lg p-3 mt-2">
          <label htmlFor="value-input" className="text-xs text-gray-400 block mb-2">Value</label>
          <input
            id="value-input"
            type={['year', 'bpm'].includes(field) ? 'number' : 'text'}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              resetValidationError();
            }}
            placeholder={getPlaceholder(field, operator)}
            className="w-full bg-slate-700 rounded px-3 py-2 text-white"
          />
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-2 mt-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={!isValid}
          className="flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded text-sm font-medium transition-colors"
        >
          {editingIndex !== null ? 'Update' : 'Add Filter'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded text-sm font-medium transition-colors"
        >
          Cancel
        </button>
      </div>

      {/* Validation Error Display */}
      {validationError && (
        <div className="mt-2 p-2 bg-red-900/50 border border-red-700 rounded text-xs text-red-300">
          {validationError}
        </div>
      )}
    </div>
  );
}