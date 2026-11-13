import { ChevronDown, ChevronUp, NotebookPen } from 'lucide-react';
import { ApiError } from '../../api/client';
import { useTrackNotes, type NotesSaveStatus } from '../../hooks/useTrackNotes';

const STATUS_LABEL: Record<NotesSaveStatus, string> = {
  idle: '',
  pending: 'Editing…',
  saving: 'Saving…',
  saved: 'Saved',
  error: 'Save failed, retries on next edit or blur',
};

export function NotesToggle({ open, onToggle }: { open: boolean; onToggle: () => void }): JSX.Element {
  const Chevron = open ? ChevronUp : ChevronDown;
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className={`flex items-center gap-1 px-2 py-1 rounded-sm transition-colors ${
        open ? 'text-white/80 bg-white/10' : 'text-white/40 hover:text-white/70 hover:bg-white/5'
      }`}
    >
      <NotebookPen className="w-3.5 h-3.5" />
      Notes
      <Chevron className="w-3.5 h-3.5" />
    </button>
  );
}

function loadErrorMessage(error: Error): string {
  if (error instanceof ApiError && error.status === 404) {
    return `No notes for this track: ${error.message.toLowerCase()}.`;
  }
  return `Couldn't load notes: ${error.message}`;
}

/** The file's COMMENT tag, which Serato shows as Comment. Autosaves. */
export function TrackNotesPanel({ trackId }: { trackId: number }): JSX.Element {
  const { draft, setDraft, flush, status, isLoading, loadError } = useTrackNotes(trackId, true);

  if (loadError) {
    return <div className="mt-3 text-xs text-white/40">{loadErrorMessage(loadError)}</div>;
  }

  return (
    <div className="mt-3">
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={flush}
        disabled={isLoading}
        rows={4}
        placeholder={isLoading ? 'Loading…' : 'Notes (saved to the file comment Serato shows)'}
        className="w-full resize-y rounded-md bg-black/40 border border-white/10 focus:border-white/30 focus:outline-hidden p-2 text-sm text-white/90 placeholder:text-white/30"
      />
      <div
        className={`h-4 text-right text-[11px] ${status === 'error' ? 'text-red-400' : 'text-white/35'}`}
      >
        {STATUS_LABEL[status]}
      </div>
    </div>
  );
}
