import { useState } from 'react';
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../ui/alert-dialog';

export interface NoteTarget {
  soundcloudId: string;
  title: string | null;
  note: string | null;
}

interface NoteDialogProps {
  target: NoteTarget | null;
  isSaving?: boolean;
  onSave: (soundcloudId: string, note: string) => void;
  onClose: () => void;
}

function NoteForm({
  target,
  isSaving,
  onSave,
}: {
  target: NoteTarget;
  isSaving: boolean;
  onSave: (soundcloudId: string, note: string) => void;
}): JSX.Element {
  const [draft, setDraft] = useState(target.note ?? '');
  const save = (): void => onSave(target.soundcloudId, draft);
  return (
    <>
      <AlertDialogHeader>
        <AlertDialogTitle>Note</AlertDialogTitle>
        <AlertDialogDescription className="truncate">{target.title ?? 'Untitled'}</AlertDialogDescription>
      </AlertDialogHeader>
      <textarea
        aria-label="Track note"
        autoFocus
        value={draft}
        maxLength={2000}
        rows={3}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) save();
        }}
        placeholder="What made it miss?"
        className="w-full resize-none rounded border border-obsidian-border bg-black/30 p-2 text-sm text-white placeholder:text-white/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-obsidian-accent"
      />
      <AlertDialogFooter>
        <AlertDialogCancel>Cancel</AlertDialogCancel>
        <button
          type="button"
          onClick={save}
          disabled={isSaving}
          className="rounded-lg bg-obsidian-accent/20 px-4 py-2 text-sm font-medium text-obsidian-accent hover:bg-obsidian-accent/30 disabled:opacity-50"
        >
          Save
        </button>
      </AlertDialogFooter>
    </>
  );
}

/** Small text field for a per-track note; saving an empty note deletes it. */
export function NoteDialog({ target, isSaving = false, onSave, onClose }: NoteDialogProps): JSX.Element {
  return (
    <AlertDialog open={target !== null} onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent className="border-obsidian-border bg-obsidian-surface">
        {/* Keyed so each opened track starts from its own saved note. */}
        {target && <NoteForm key={target.soundcloudId} target={target} isSaving={isSaving} onSave={onSave} />}
      </AlertDialogContent>
    </AlertDialog>
  );
}
