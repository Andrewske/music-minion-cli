import type { ReactNode } from 'react';
import { Check, Meh, ThumbsDown } from 'lucide-react';
import type { StoriesDecision, StoriesTrack } from '../../api/stories';

interface ControlButtonProps {
  label: string;
  title: string;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}

function ControlButton({ label, title, active = false, disabled = false, onClick, children }: ControlButtonProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      aria-pressed={active}
      className={`flex min-h-10 items-center justify-center gap-1.5 rounded-sm px-3 py-2 text-xs font-medium transition-colors focus-visible:outline-solid focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-obsidian-accent disabled:cursor-default disabled:opacity-40 ${
        active ? 'bg-obsidian-accent/15 text-obsidian-accent' : 'bg-white/5 text-white/70 hover:bg-white/10 hover:text-white'
      }`}
    >
      {children}
      <span>{title}</span>
    </button>
  );
}

interface StoriesControlsProps {
  track: StoriesTrack;
  isUpdating: boolean;
  onDecide: (decision: StoriesDecision) => void;
}

/** Keep (keeps playing), Not quite and Nope (advance). Active state is the MM verdict only. */
export function StoriesControls({ track, isUpdating, onDecide }: StoriesControlsProps): JSX.Element {
  const kept = track.decision === 'keep';
  return (
    <div role="group" aria-label="Story controls" className="flex flex-wrap items-center gap-2">
      <ControlButton label="Keep; like on SoundCloud and add to monthly playlist" title="Keep" active={kept} disabled={isUpdating || kept} onClick={() => onDecide('keep')}>
        <Check className="h-4 w-4" />
      </ControlButton>
      <ControlButton label="Not quite; close but not a keep, play next" title="Not quite" active={track.decision === 'not_quite'} disabled={isUpdating} onClick={() => onDecide('not_quite')}>
        <Meh className="h-4 w-4" />
      </ControlButton>
      <ControlButton label="Nope; clear pass, play next" title="Nope" active={track.decision === 'nope'} disabled={isUpdating} onClick={() => onDecide('nope')}>
        <ThumbsDown className="h-4 w-4" />
      </ControlButton>
    </div>
  );
}
