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
import { FLAG_REASONS, FLAG_REASON_LABELS, type FlagReason } from '../../api/feedFilters';

export interface FlagTarget {
  soundcloudId: string;
  title: string | null;
}

interface FlagDialogProps {
  target: FlagTarget | null;
  isSaving?: boolean;
  onFlag: (soundcloudId: string, reason: FlagReason, note: string) => void;
  onClose: () => void;
}

function ReasonChips({ value, onChange }: { value: FlagReason; onChange: (reason: FlagReason) => void }): JSX.Element {
  return (
    <fieldset role="radiogroup" aria-label="Reason" className="flex flex-wrap gap-1.5">
      <legend className="sr-only">Reason</legend>
      {FLAG_REASONS.map((reason) => (
        <button
          key={reason}
          type="button"
          role="radio"
          aria-checked={value === reason}
          onClick={() => onChange(reason)}
          className={`rounded-full border px-3 py-1.5 text-xs ${
            value === reason ? 'border-obsidian-accent text-obsidian-accent' : 'border-obsidian-border text-white/60 hover:text-white'
          }`}
        >
          {FLAG_REASON_LABELS[reason]}
        </button>
      ))}
    </fieldset>
  );
}

function FlagForm({
  target,
  isSaving,
  onFlag,
}: {
  target: FlagTarget;
  isSaving: boolean;
  onFlag: FlagDialogProps['onFlag'];
}): JSX.Element {
  const [reason, setReason] = useState<FlagReason>('live_mix');
  const [note, setNote] = useState('');
  return (
    <>
      <AlertDialogHeader>
        <AlertDialogTitle>Not for feed</AlertDialogTitle>
        <AlertDialogDescription className="truncate">
          {target.title ?? 'Untitled'}: hidden from the feed without counting against the artist.
        </AlertDialogDescription>
      </AlertDialogHeader>
      <ReasonChips value={reason} onChange={setReason} />
      <textarea
        aria-label="Flag note"
        value={note}
        maxLength={2000}
        rows={2}
        onChange={(event) => setNote(event.target.value)}
        placeholder="Optional note"
        className="w-full resize-none rounded-sm border border-obsidian-border bg-black/30 p-2 text-sm text-white placeholder:text-white/30 focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-obsidian-accent"
      />
      <AlertDialogFooter>
        <AlertDialogCancel>Cancel</AlertDialogCancel>
        <button
          type="button"
          onClick={() => onFlag(target.soundcloudId, reason, note)}
          disabled={isSaving}
          className="rounded-lg bg-obsidian-accent/20 px-4 py-2 text-sm font-medium text-obsidian-accent hover:bg-obsidian-accent/30 disabled:opacity-50"
        >
          Hide from feed
        </button>
      </AlertDialogFooter>
    </>
  );
}

/** Reason chips plus an optional note; flagging is not a verdict. */
export function FlagDialog({ target, isSaving = false, onFlag, onClose }: FlagDialogProps): JSX.Element {
  return (
    <AlertDialog open={target !== null} onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent className="border-obsidian-border bg-obsidian-surface">
        {target && <FlagForm key={target.soundcloudId} target={target} isSaving={isSaving} onFlag={onFlag} />}
      </AlertDialogContent>
    </AlertDialog>
  );
}
