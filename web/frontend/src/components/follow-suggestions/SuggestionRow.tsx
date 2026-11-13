import { useState } from 'react';
import type { FormEvent, ReactElement } from 'react';
import { ChevronDown, ChevronRight, Tag, UserRound } from 'lucide-react';
import { Button } from '../ui/button';
import type { Suggestion } from '../../api/followSuggestions';
import { AccountRow, Chip, FollowActions } from './AccountRow';
import { ROLE_LABEL, ageLabel, scoreChips } from './format';

export interface SuggestionHandlers {
  followDisabled: boolean;
  /** True while a mutation on this account is in flight: its row's actions wait. */
  isBusy: (account: { key: string; soundcloud_user_id: string | null }) => boolean;
  onFollow: (soundcloudUserId: string) => void;
  onDismiss: (key: string) => void;
  onSetLabel: (key: string, isLabel: boolean) => void;
  /** Resolves once the name is linked; rejects (after a toast) to keep the form open. */
  onLink: (key: string, url: string) => Promise<unknown>;
}

function LinkForm({ name, onSubmit, onCancel }: { name: string; onSubmit: (url: string) => Promise<unknown>; onCancel: () => void }): ReactElement {
  const [url, setUrl] = useState('');
  const [saving, setSaving] = useState(false);
  const submit = (e: FormEvent): void => {
    e.preventDefault();
    setSaving(true);
    onSubmit(url.trim()).then(onCancel, () => setSaving(false));
  };
  return (
    <form onSubmit={submit} className="mt-2 ml-0 sm:ml-[52px] flex items-center gap-2">
      <input
        autoFocus
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        aria-label={`SoundCloud link for ${name}`}
        placeholder="https://soundcloud.com/artist"
        className="flex-1 min-w-0 h-8 px-2 bg-transparent border border-obsidian-border font-sf-mono text-xs text-white placeholder:text-white/30 focus:outline-none focus:border-obsidian-accent"
      />
      <Button type="submit" size="sm" variant="outline" disabled={saving || url.trim() === ''}>Link</Button>
      <Button type="button" size="sm" variant="ghost" className="text-white/50" onClick={onCancel}>Cancel</Button>
    </form>
  );
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
  const [linking, setLinking] = useState(false);
  const labelText = suggestion.is_label ? 'Not a label' : 'This is a label';
  const LabelIcon = suggestion.is_label ? UserRound : Tag;
  const busy = handlers.isBusy(suggestion);
  const details = (
    <>
      {scoreChips(suggestion).map((c) => <Chip key={c}>{c}</Chip>)}
      {suggestion.tracks.length > 0 && <TracksToggle count={suggestion.tracks.length} open={open} onToggle={() => setOpen((o) => !o)} />}
    </>
  );
  const actions = (
    <>
      <FollowActions account={suggestion} followDisabled={handlers.followDisabled} busy={busy} onFollow={handlers.onFollow} onDismiss={handlers.onDismiss} onStartLink={() => setLinking(true)} />
      <Button size="icon" variant="ghost" aria-label={labelText} title={suggestion.is_label ? 'Not a label: move to artists' : 'This is a label: move to labels'} className="h-8 w-8 text-white/50" disabled={busy} onClick={() => handlers.onSetLabel(suggestion.key, !suggestion.is_label)}>
        <LabelIcon className="w-4 h-4" />
      </Button>
    </>
  );
  return (
    <AccountRow account={suggestion} details={details} actions={actions} quiet={suggestion.is_label}>
      {linking && <LinkForm name={suggestion.display_name} onSubmit={(url) => handlers.onLink(suggestion.key, url)} onCancel={() => setLinking(false)} />}
      {open && <TrackList suggestion={suggestion} />}
    </AccountRow>
  );
}
