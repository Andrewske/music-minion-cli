import { useState } from 'react';
import type { ReactElement } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { Suggestion } from '../../api/followSuggestions';
import { AccountRow, Chip, FollowActions } from './AccountRow';
import { ROLE_LABEL, ageLabel, scoreChips } from './format';

export interface SuggestionHandlers {
  followDisabled: boolean;
  onFollow: (soundcloudUserId: string) => void;
  onDismiss: (key: string) => void;
  onSetLabel: (key: string, isLabel: boolean) => void;
}

function TrackList({ suggestion }: { suggestion: Suggestion }): ReactElement {
  return (
    <ul className="mt-2 ml-0 sm:ml-[52px] space-y-1">
      {suggestion.tracks.map((t) => (
        <li key={`${t.soundcloud_id}-${t.role}`} className="flex items-baseline gap-2 text-xs min-w-0">
          <span className="font-sf-mono text-[10px] text-white/40 w-24 shrink-0">{ROLE_LABEL[t.role]}</span>
          <span className="text-white/80 truncate">
            {t.artist} – {t.title}
          </span>
          {t.liked_at && <span className="font-sf-mono text-[10px] text-white/30 shrink-0">{ageLabel(t.liked_at)}</span>}
        </li>
      ))}
    </ul>
  );
}

function TracksToggle({ count, open, onToggle }: { count: number; open: boolean; onToggle: () => void }): ReactElement {
  const Icon = open ? ChevronDown : ChevronRight;
  return (
    <button type="button" aria-expanded={open} onClick={onToggle} className="inline-flex items-center gap-0.5 font-sf-mono text-[11px] text-obsidian-accent">
      <Icon className="w-3 h-3" /> {count} track{count === 1 ? '' : 's'}
    </button>
  );
}

export function SuggestionRow({ suggestion, handlers }: { suggestion: Suggestion; handlers: SuggestionHandlers }): ReactElement {
  const [open, setOpen] = useState(false);
  const labelText = suggestion.is_label ? 'Not a label' : 'This is a label';
  const details = (
    <>
      {scoreChips(suggestion).map((c) => <Chip key={c}>{c}</Chip>)}
      {suggestion.tracks.length > 0 && <TracksToggle count={suggestion.tracks.length} open={open} onToggle={() => setOpen((o) => !o)} />}
    </>
  );
  const actions = (
    <>
      <FollowActions account={suggestion} followDisabled={handlers.followDisabled} onFollow={handlers.onFollow} onDismiss={handlers.onDismiss} />
      <button type="button" onClick={() => handlers.onSetLabel(suggestion.key, !suggestion.is_label)} className="text-[11px] text-white/40 hover:text-white/70 underline-offset-2 hover:underline">
        {labelText}
      </button>
    </>
  );
  return (
    <AccountRow account={suggestion} details={details} actions={actions} quiet={suggestion.is_label}>
      {open && <TrackList suggestion={suggestion} />}
    </AccountRow>
  );
}
