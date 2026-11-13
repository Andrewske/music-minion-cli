import type { ReactElement } from 'react';
import type { FollowingCount } from '../../api/followSuggestions';

const LOW_SLOTS = 25;

/** "1,945 / 2,000 following": SoundCloud stops follows at the limit. */
export function FollowingMeter({ following }: { following: FollowingCount }): ReactElement {
  const left = following.limit - following.count;
  const tone = left <= 0 ? 'text-red-400' : left <= LOW_SLOTS ? 'text-amber-400' : 'text-white/50';
  const note = left <= 0 ? 'at the limit: unfollow someone first' : `${left.toLocaleString()} left`;
  return (
    <p data-testid="following-meter" className={`mb-3 font-sf-mono text-xs ${tone}`}>
      Following {following.count.toLocaleString()} / {following.limit.toLocaleString()} on SoundCloud · {note}
    </p>
  );
}

interface ViewTabsProps<V extends string> {
  view: V;
  /** Tab label counts; null hides a tab (its section has nothing to show). */
  counts: Record<V, number | null>;
  labels: Record<V, string>;
  onChange: (v: V) => void;
}

export function ViewTabs<V extends string>({ view, counts, labels, onChange }: ViewTabsProps<V>): ReactElement {
  const views = (Object.keys(labels) as V[]).filter((v) => counts[v] != null);
  return (
    <div role="tablist" className="mb-4 flex flex-wrap gap-1 border-b border-obsidian-border">
      {views.map((v) => (
        <button
          key={v}
          type="button"
          role="tab"
          aria-selected={view === v}
          onClick={() => onChange(v)}
          className={`px-3 py-2 -mb-px border-b-2 font-inter text-sm ${view === v ? 'border-obsidian-accent text-white' : 'border-transparent text-white/50 hover:text-white/80'}`}
        >
          {labels[v]} <span className="font-sf-mono text-[11px] text-white/40">{counts[v]}</span>
        </button>
      ))}
    </div>
  );
}
