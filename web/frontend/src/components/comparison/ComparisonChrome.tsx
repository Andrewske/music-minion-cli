import { Undo2 } from 'lucide-react';
import type { ComparisonProgress } from '../../types';
import type { ComparisonHistoryEntry } from '../../stores/comparisonStore';
import { AutoplayToggle } from '../AutoplayToggle';

function Kbd({ children }: { children: string }): JSX.Element {
  return <kbd className="px-1.5 py-0.5 rounded-sm bg-white/10 text-[10px] text-white/60">{children}</kbd>;
}

interface ComparisonHeaderProps {
  playlistName: string | undefined;
  progress: ComparisonProgress | null;
  sessionCount: number;
  canUndo: boolean;
  onUndo: () => void;
  onOpenStats: () => void;
}

const chipClass =
  'flex items-center gap-1.5 px-2 py-1 rounded-sm border border-obsidian-border text-xs text-white/60 hover:text-white/90 hover:bg-white/5 transition-colors disabled:opacity-40 disabled:hover:bg-transparent';

export function ComparisonHeader(props: ComparisonHeaderProps): JSX.Element {
  const { progress } = props;
  return (
    <header className="flex flex-wrap items-center gap-x-4 gap-y-2 pb-3 mb-4 border-b border-obsidian-border">
      <h1 className="font-semibold text-white/90 truncate">{props.playlistName ?? 'Comparison'}</h1>
      <div
        className="order-last sm:order-none basis-full sm:basis-auto flex-1 h-1 rounded-full bg-obsidian-border overflow-hidden"
        role="progressbar"
        aria-valuenow={progress?.percentage ?? 0}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className="h-full bg-obsidian-accent" style={{ width: `${progress?.percentage ?? 0}%` }} />
      </div>
      {progress && (
        <span className="text-xs text-white/50 tabular-nums" title={`${props.sessionCount} picks this session`}>
          {progress.compared.toLocaleString()} / {progress.total.toLocaleString()}
        </span>
      )}
      <div className="ml-auto flex items-center gap-3">
        <button type="button" className={chipClass} onClick={props.onUndo} disabled={!props.canUndo}>
          <Undo2 className="w-3.5 h-3.5" /> Undo <span className="hidden md:inline"><Kbd>Z</Kbd></span>
        </button>
        <button type="button" className={chipClass} onClick={props.onOpenStats}>Stats</button>
        <AutoplayToggle />
      </div>
    </header>
  );
}

function formatDelta(delta: number | null): string {
  return delta === null ? '' : `+${Math.round(delta)}`;
}

/** Recent picks, newest first: "+16 Winner › Loser". */
export function PickHistory({ history }: { history: ComparisonHistoryEntry[] }): JSX.Element | null {
  if (history.length === 0) return null;
  return (
    <div className="flex items-center gap-2 mt-4 text-xs text-white/35 overflow-hidden">
      <span className="shrink-0">Last picks</span>
      <ol className="flex gap-2 min-w-0 overflow-x-auto">
        {history.slice(0, 5).map((entry, i) => (
          <li
            key={`${entry.trackAId}-${entry.trackBId}-${i}`}
            className="shrink-0 px-2 py-0.5 rounded-sm border border-obsidian-border bg-obsidian-surface text-white/55 max-w-72 truncate"
            title={`${entry.winnerTitle} beat ${entry.loserTitle}`}
          >
            <span className="text-obsidian-accent mr-1.5 tabular-nums">{formatDelta(entry.ratingDelta)}</span>
            {entry.winnerTitle} <span className="text-white/30">›</span> {entry.loserTitle}
          </li>
        ))}
      </ol>
    </div>
  );
}

export function ShortcutHints(): JSX.Element {
  return (
    <div className="hidden md:flex flex-wrap gap-x-4 gap-y-1 mt-3 text-xs text-white/35">
      <span><Kbd>Space</Kbd> play/pause</span>
      <span><Kbd>Tab</Kbd> flip track, same spot</span>
      <span><Kbd>1</Kbd> / <Kbd>2</Kbd> pick</span>
      <span><Kbd>S</Kbd> skip pair</span>
      <span><Kbd>Z</Kbd> undo</span>
    </div>
  );
}
