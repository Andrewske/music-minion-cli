import { useCallback, useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getTrackNotes, saveTrackNotes } from '../api/tracks';

export const NOTES_AUTOSAVE_MS = 800;

export type NotesSaveStatus = 'idle' | 'pending' | 'saving' | 'saved' | 'error';

interface PendingSave {
  trackId: number;
  notes: string;
}

/** Edits and save status are tagged with their track so a track change resets them for free. */
interface Tagged<T> {
  trackId: number;
  value: T;
}

export function trackNotesQueryKey(trackId: number | null): readonly ['trackNotes', number | null] {
  return ['trackNotes', trackId] as const;
}

function forTrack<T>(tagged: Tagged<T> | null, trackId: number | null, fallback: T): T {
  return tagged && tagged.trackId === trackId ? tagged.value : fallback;
}

interface UseTrackNotesResult {
  draft: string;
  setDraft: (notes: string) => void;
  flush: () => void;
  status: NotesSaveStatus;
  isLoading: boolean;
  loadError: Error | null;
}

/**
 * Autosaving notes for one track. Edits save NOTES_AUTOSAVE_MS after typing
 * stops; flush() (on blur) and a track change save any pending edit at once,
 * so switching tracks mid-sentence never drops what was typed.
 */
export function useTrackNotes(trackId: number | null, enabled: boolean): UseTrackNotesResult {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: trackNotesQueryKey(trackId),
    queryFn: () => getTrackNotes(trackId as number),
    enabled: enabled && trackId !== null,
    retry: false,
    staleTime: 30_000,
  });
  const [edit, setEdit] = useState<Tagged<string> | null>(null);
  const [status, setStatus] = useState<Tagged<NotesSaveStatus> | null>(null);
  const pendingRef = useRef<PendingSave | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const chainRef = useRef<Promise<void>>(Promise.resolve());

  // Saves run one at a time so an older write can't land after a newer one.
  // A failed save goes back to pending (unless newer text replaced it), so
  // the next blur or edit retries it.
  const save = useCallback(
    (pending: PendingSave): void => {
      const mark = (value: NotesSaveStatus): void => setStatus({ trackId: pending.trackId, value });
      mark('saving');
      chainRef.current = chainRef.current
        .then(() => saveTrackNotes(pending.trackId, pending.notes))
        .then((saved) => {
          queryClient.setQueryData(trackNotesQueryKey(pending.trackId), saved);
          if (pendingRef.current === null) mark('saved');
        })
        .catch(() => {
          pendingRef.current ??= pending;
          mark('error');
        });
    },
    [queryClient],
  );

  const flush = useCallback((): void => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = null;
    const pending = pendingRef.current;
    pendingRef.current = null;
    if (pending) save(pending);
  }, [save]);

  // Track change or unmount: save the previous track's pending edit.
  useEffect(() => flush, [trackId, flush]);

  const setDraft = useCallback(
    (notes: string): void => {
      if (trackId === null) return;
      setEdit({ trackId, value: notes });
      setStatus({ trackId, value: 'pending' });
      pendingRef.current = { trackId, notes };
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(flush, NOTES_AUTOSAVE_MS);
    },
    [trackId, flush],
  );

  return {
    draft: forTrack(edit, trackId, query.data?.notes ?? ''),
    setDraft,
    flush,
    status: forTrack(status, trackId, 'idle'),
    isLoading: query.isLoading,
    loadError: query.error,
  };
}
