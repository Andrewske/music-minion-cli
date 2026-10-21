import { useCallback, useRef, useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { saveFeedNote } from '../api/feed';
import type { NoteTarget } from '../components/feed/NoteDialog';
import { REVIEWED_QUERY_KEY } from '../components/feed/reviewed';

/** An opened note editor; `session` tells overlapping editors on any track apart. */
export interface NoteSession extends NoteTarget {
  session: number;
}

interface SaveVariables {
  soundcloudId: string;
  note: string;
  session: number;
}

export interface NoteEditor {
  target: NoteSession | null;
  isSaving: boolean;
  open: (target: NoteTarget) => void;
  close: () => void;
  save: (soundcloudId: string, note: string) => void;
}

/**
 * Note dialog state. A save closes only the editor session that submitted
 * it, so a slow response never closes (or discards) a draft opened later.
 */
export function useNoteEditor(): NoteEditor {
  const queryClient = useQueryClient();
  const sessionRef = useRef(0);
  const [target, setTarget] = useState<NoteSession | null>(null);
  const mutation = useMutation({
    mutationFn: ({ soundcloudId, note }: SaveVariables) => saveFeedNote(soundcloudId, note),
    onSuccess: (_response, { session }) => {
      setTarget((current) => (current?.session === session ? null : current));
      toast.success('Note saved');
    },
    onError: () => toast.error('Note failed to save'),
    onSettled: () => queryClient.invalidateQueries({ queryKey: REVIEWED_QUERY_KEY }),
  });
  const open = useCallback((next: NoteTarget): void => {
    sessionRef.current += 1;
    setTarget({ ...next, session: sessionRef.current });
  }, []);
  const close = useCallback((): void => setTarget(null), []);
  const save = (soundcloudId: string, note: string): void => {
    if (target) mutation.mutate({ soundcloudId, note, session: target.session });
  };
  const isSaving = mutation.isPending && target !== null && mutation.variables?.session === target.session;
  return { target, isSaving, open, close, save };
}
