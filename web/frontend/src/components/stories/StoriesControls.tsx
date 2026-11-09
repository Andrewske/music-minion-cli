import type { ReactNode } from 'react';
import { Heart, Meh, SkipBack, SkipForward } from 'lucide-react';
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
  canGoPrevious: boolean;
  isUpdating: boolean;
  onDecide: (decision: StoriesDecision) => void;
  onPrevious: () => void;
}

/** Like (keeps playing), Not quite and Skip (advance), Previous (history). */
export function StoriesControls({ track, canGoPrevious, isUpdating, onDecide, onPrevious }: StoriesControlsProps): JSX.Element {
  const liked = track.decision === 'keep';
  return (
    <div role="group" aria-label="Story controls" className="flex flex-wrap items-center gap-2">
      <ControlButton label="Like; like on SoundCloud and add to monthly playlist" title="Like" active={liked} disabled={isUpdating || liked} onClick={() => onDecide('keep')}>
        <Heart className={`h-4 w-4 ${liked ? 'fill-current' : ''}`} />
      </ControlButton>
      <ControlButton label="Not quite; close but not a keep, play next" title="Not quite" active={track.decision === 'not_quite'} disabled={isUpdating} onClick={() => onDecide('not_quite')}>
        <Meh className="h-4 w-4" />
      </ControlButton>
      <ControlButton label="Skip; nope, play next" title="Skip" active={track.decision === 'nope'} disabled={isUpdating} onClick={() => onDecide('nope')}>
        <SkipForward className="h-4 w-4" />
      </ControlButton>
      <span className="flex-1" />
      <ControlButton label="Previous track" title="Previous" disabled={!canGoPrevious} onClick={onPrevious}>
        <SkipBack className="h-4 w-4" />
      </ControlButton>
    </div>
  );
}
