import { useState } from 'react';
import { Check, ChevronDown, Pencil, Plus, Trash2, CircleCheckBig, AlertTriangle } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import { useOrganizerSessions } from '../../hooks/usePlaylistOrganizer';
import type { BucketSession, SessionSummary } from '../../api/buckets';
import { isDoneStatus, sessionLabel } from './sessionLabel';

interface SessionSwitcherProps {
  playlistId: number;
  session: BucketSession;
  /** Discovery playlists: finishing likes/dismisses tracks on SoundCloud. */
  isDiscovery: boolean;
  isBusy: boolean;
  onNew: () => void;
  onSwitch: (sessionId: string) => void;
  onRename: (sessionId: string, name: string | null) => void;
  onDelete: (sessionId: string) => void;
  onFinish: () => void;
}

/** Inline confirmation state: which destructive action is awaiting a second click. */
type Confirm = { kind: 'delete'; id: string; label: string } | { kind: 'finish' } | null;

const itemClass = 'text-white/80 focus:bg-white/10 focus:text-white cursor-pointer';

const countsText = (s: SessionSummary): string =>
  `${s.bucket_count} ${s.bucket_count === 1 ? 'bucket' : 'buckets'} · ${s.assigned_count}`;

export function SessionSwitcher(props: SessionSwitcherProps): JSX.Element {
  const { playlistId, session, isBusy } = props;
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState<Confirm>(null);
  const { sessions, isLoading } = useOrganizerSessions(playlistId, open);
  const current = sessions.find((s) => s.id === session.id);
  const others = sessions.filter((s) => s.id !== session.id);

  const handleOpenChange = (next: boolean): void => {
    setOpen(next);
    if (!next) setConfirm(null);
  };

  return (
    <DropdownMenu open={open} onOpenChange={handleOpenChange}>
      <DropdownMenuTrigger
        disabled={isBusy}
        className="inline-flex items-center gap-1 text-white/70 hover:text-white transition-colors disabled:opacity-50 outline-hidden focus-visible:text-white"
        aria-label="Switch organizer session"
      >
        <ChevronDown className="w-3 h-3" />
        <span className="max-w-[220px] truncate">{sessionLabel(session)}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        className="w-80 bg-obsidian-surface border-obsidian-border text-white/80"
      >
        <CurrentRow
          session={session}
          summary={current}
          confirm={confirm}
          setConfirm={setConfirm}
          onRename={props.onRename}
        />
        {isLoading && <div className="px-2 py-1.5 text-xs text-white/40">Loading sessions...</div>}
        {others.map((s) => (
          <OtherRow key={s.id} summary={s} confirm={confirm} setConfirm={setConfirm} onSwitch={props.onSwitch} />
        ))}
        {confirm?.kind === 'delete' && (
          <DeleteConfirm confirm={confirm} setConfirm={setConfirm} onDelete={props.onDelete} />
        )}
        <DropdownMenuSeparator className="bg-obsidian-border" />
        <DropdownMenuItem className={itemClass} onSelect={props.onNew}>
          <Plus className="w-4 h-4 mr-2 text-white/50" /> New session
        </DropdownMenuItem>
        <FinishItem isDiscovery={props.isDiscovery} confirm={confirm} setConfirm={setConfirm} onFinish={props.onFinish} />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

interface CurrentRowProps {
  session: BucketSession;
  summary: SessionSummary | undefined;
  confirm: Confirm;
  setConfirm: (c: Confirm) => void;
  onRename: (sessionId: string, name: string | null) => void;
}

function CurrentRow({ session, summary, setConfirm, onRename }: CurrentRowProps): JSX.Element {
  const [draft, setDraft] = useState<string | null>(null);
  const save = (): void => {
    if (draft === null) return;
    const name = draft.trim() || null;
    if (name !== session.name) onRename(session.id, name);
    setDraft(null);
  };

  if (draft !== null) {
    return (
      <div className="flex items-center gap-2 px-2 py-1.5">
        <Check className="w-4 h-4 text-obsidian-accent shrink-0" />
        <input
          autoFocus
          aria-label="Session name"
          value={draft}
          placeholder={sessionLabel({ name: null, created_at: session.created_at })}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={save}
          // Keep Radix menu typeahead/Escape from eating keystrokes while typing.
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === 'Enter') save();
            if (e.key === 'Escape') setDraft(null);
          }}
          className="flex-1 min-w-0 px-2 py-0.5 text-sm bg-black/30 border border-obsidian-border rounded-sm text-white placeholder:text-white/30 outline-hidden focus:border-obsidian-accent"
        />
      </div>
    );
  }

  return (
    <div className="flex items-center">
      <DropdownMenuItem
        className={`${itemClass} flex-1 min-w-0`}
        title="Rename session"
        onSelect={(e) => {
          e.preventDefault();
          setConfirm(null);
          setDraft(session.name ?? '');
        }}
      >
        <Check className="w-4 h-4 mr-2 text-obsidian-accent shrink-0" />
        <span className="truncate text-white">{sessionLabel(session)}</span>
        <Pencil className="w-3 h-3 ml-1.5 text-white/30 shrink-0" />
        {summary && <span className="ml-auto pl-2 text-xs text-white/40 shrink-0">{countsText(summary)}</span>}
      </DropdownMenuItem>
      <TrashItem id={session.id} label={sessionLabel(session)} setConfirm={setConfirm} />
    </div>
  );
}

interface OtherRowProps {
  summary: SessionSummary;
  confirm: Confirm;
  setConfirm: (c: Confirm) => void;
  onSwitch: (sessionId: string) => void;
}

function OtherRow({ summary, setConfirm, onSwitch }: OtherRowProps): JSX.Element {
  const label = sessionLabel(summary);
  return (
    <div className="flex items-center">
      <DropdownMenuItem className={`${itemClass} flex-1 min-w-0 pl-8`} onSelect={() => onSwitch(summary.id)}>
        <span className="truncate">{label}</span>
        {isDoneStatus(summary.status) && <span className="ml-1.5 text-xs text-white/40 shrink-0">(done)</span>}
        <span className="ml-auto pl-2 text-xs text-white/40 shrink-0">{countsText(summary)}</span>
      </DropdownMenuItem>
      <TrashItem id={summary.id} label={label} setConfirm={setConfirm} />
    </div>
  );
}

function TrashItem({ id, label, setConfirm }: { id: string; label: string; setConfirm: (c: Confirm) => void }): JSX.Element {
  return (
    <DropdownMenuItem
      aria-label={`Delete ${label}`}
      className="px-2 text-white/30 focus:bg-red-500/10 focus:text-red-400 cursor-pointer"
      onSelect={(e) => {
        e.preventDefault();
        setConfirm({ kind: 'delete', id, label });
      }}
    >
      <Trash2 className="w-3.5 h-3.5" />
    </DropdownMenuItem>
  );
}

interface DeleteConfirmProps {
  confirm: { kind: 'delete'; id: string; label: string };
  setConfirm: (c: Confirm) => void;
  onDelete: (sessionId: string) => void;
}

function DeleteConfirm({ confirm, setConfirm, onDelete }: DeleteConfirmProps): JSX.Element {
  return (
    <div className="mx-1 my-1 rounded-sm border border-red-500/30 bg-red-500/5 px-2 py-1.5">
      <div className="text-xs text-white/70">
        Delete <span className="text-white">{confirm.label}</span>? Its buckets are dropped and bucket emojis are removed from tracks.
      </div>
      <div className="flex justify-end gap-1 mt-1">
        <DropdownMenuItem className={`${itemClass} text-xs`} onSelect={(e) => { e.preventDefault(); setConfirm(null); }}>
          Cancel
        </DropdownMenuItem>
        <DropdownMenuItem
          className="text-xs text-red-400 focus:bg-red-500/20 focus:text-red-300 cursor-pointer"
          onSelect={() => onDelete(confirm.id)}
        >
          Delete
        </DropdownMenuItem>
      </div>
    </div>
  );
}

interface FinishItemProps {
  isDiscovery: boolean;
  confirm: Confirm;
  setConfirm: (c: Confirm) => void;
  onFinish: () => void;
}

function FinishItem({ isDiscovery, confirm, setConfirm, onFinish }: FinishItemProps): JSX.Element {
  const confirming = confirm?.kind === 'finish';
  return (
    <>
      <DropdownMenuItem
        className={itemClass}
        onSelect={(e) => {
          if (confirming) return onFinish();
          e.preventDefault();
          setConfirm({ kind: 'finish' });
        }}
      >
        <CircleCheckBig className="w-4 h-4 mr-2 text-white/50" />
        {confirming ? 'Click again to finish' : 'Finish session'}
      </DropdownMenuItem>
      {isDiscovery && (
        <div className="flex gap-1.5 px-2 pb-1.5 text-[11px] leading-snug text-amber-400/80">
          <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
          Finishing likes tracks in linked buckets on SoundCloud and dismisses (deletes) tracks in unlinked buckets.
        </div>
      )}
    </>
  );
}
