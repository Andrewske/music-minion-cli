import { useEffect, useRef, useState } from 'react';
import { ExternalLink, Pause, Play } from 'lucide-react';
import type { CleanupRow, CleanupVerdict, CleanupView } from '../../api/cleanup';
import {
  CLEANUP_FIELDS,
  CLEANUP_SOURCES,
  cellChanged,
  cellTokens,
  draftFromView,
  groupWords,
  runsDisagree,
  viewFromDraft,
  type CleanupFieldSpec,
  type CleanupSource,
} from './cleanupView';

const GRID = 'sm:grid-cols-[5.5rem_repeat(3,minmax(0,1fr))]';
const SOURCE_TEXT: Record<CleanupSource, string> = { current: 'text-white/60', a: 'text-sky-300', b: 'text-teal-300' };

interface ActionSpec {
  verdict: CleanupVerdict | 'edit';
  label: string;
  shortcut: string;
  tone: string;
}

const CLEANUP_ACTIONS: readonly ActionSpec[] = [
  { verdict: 'model', label: 'Use A', shortcut: '1', tone: 'border-sky-400/40 text-sky-200 hover:bg-sky-400/10' },
  { verdict: 'alt', label: 'Use B', shortcut: '3', tone: 'border-teal-400/40 text-teal-200 hover:bg-teal-400/10' },
  { verdict: 'edit', label: 'Edit', shortcut: 'E', tone: 'border-fuchsia-400/40 text-fuchsia-200 hover:bg-fuchsia-400/10' },
  { verdict: 'gold', label: 'Keep current', shortcut: '2', tone: 'border-amber-400/40 text-amber-200 hover:bg-amber-400/10' },
  { verdict: 'unclear', label: 'Unclear', shortcut: 'U', tone: 'border-obsidian-border text-white/70 hover:bg-white/5' },
  { verdict: 'exclude', label: 'Skip', shortcut: 'X', tone: 'border-obsidian-border text-white/50 hover:bg-white/5' },
];

function Cell({ row, field, source }: { row: CleanupRow; field: CleanupFieldSpec; source: CleanupSource }): JSX.Element {
  const raw = cellTokens(row, field.key, source);
  const tokens = field.list ? raw : groupWords(raw);
  const changed = cellChanged(row, field.key, source);
  const label = CLEANUP_SOURCES.find((item) => item.key === source)?.label ?? source;
  return (
    <div
      data-testid={`cell-${field.key}-${source}`}
      data-changed={changed}
      className={`min-w-0 break-words rounded-md border px-3 py-2 text-sm ${changed ? 'border-amber-400/30 bg-amber-400/[0.04]' : 'border-obsidian-border bg-black/30'}`}
    >
      <span className={`mr-2 text-[10px] font-semibold uppercase tracking-wider sm:hidden ${SOURCE_TEXT[source]}`}>{label}</span>
      {tokens.length === 0 && <span className="italic text-white/30">none</span>}
      {tokens.map((token, index) => (
        <span key={`${token.text}-${index}`}>
          {index > 0 && (field.list ? <span className="text-white/30">; </span> : ' ')}
          {token.changed ? <mark className="rounded-sm bg-amber-400/20 px-0.5 text-amber-100">{token.text}</mark> : <span className="text-white/90">{token.text}</span>}
        </span>
      ))}
    </div>
  );
}

function Comparison({ row }: { row: CleanupRow }): JSX.Element {
  return (
    <div className="mt-4 space-y-3 sm:space-y-2">
      <div className={`hidden gap-2 sm:grid ${GRID}`}>
        <span />
        {CLEANUP_SOURCES.map((source) => (
          <span key={source.key} className={`text-[11px] font-semibold uppercase tracking-wider ${SOURCE_TEXT[source.key]}`}>{source.label}</span>
        ))}
      </div>
      {CLEANUP_FIELDS.map((field) => {
        const disagree = runsDisagree(row, field.key);
        return (
          <div key={field.key} className={`grid gap-1.5 sm:gap-2 ${GRID}`}>
            <div className={`text-xs sm:pt-2.5 ${disagree ? 'text-red-400' : 'text-white/50'}`}>
              {field.label}
              {disagree && <span className="ml-1 text-[10px] uppercase sm:block sm:ml-0">A ≠ B</span>}
            </div>
            {CLEANUP_SOURCES.map((source) => <Cell key={source.key} row={row} field={field} source={source.key} />)}
          </div>
        );
      })}
    </div>
  );
}

interface EditFormProps {
  initial: CleanupView;
  onSave: (view: CleanupView) => void;
  onCancel: () => void;
}

export function EditForm({ initial, onSave, onCancel }: EditFormProps): JSX.Element {
  const [draft, setDraft] = useState(() => draftFromView(initial));
  const submit = (event: React.FormEvent): void => {
    event.preventDefault();
    if (draft.title.trim()) onSave(viewFromDraft(draft));
  };
  return (
    <form onSubmit={submit} onKeyDown={(event) => event.key === 'Escape' && onCancel()} className="mt-4 space-y-3 rounded-md border border-fuchsia-400/30 bg-black/30 p-3">
      {CLEANUP_FIELDS.map((field, index) => (
        <label key={field.key} className="block text-xs text-white/60">
          {field.label}{field.list && <span className="text-white/30"> (separate names with ;)</span>}
          <input
            autoFocus={index === 0}
            value={draft[field.key]}
            onChange={(event) => setDraft({ ...draft, [field.key]: event.target.value })}
            className="mt-1 block w-full rounded-md border border-obsidian-border bg-black/50 px-3 py-2.5 text-base text-white focus:border-fuchsia-400/60 focus:outline-hidden sm:text-sm"
          />
        </label>
      ))}
      <div className="grid grid-cols-2 gap-2 sm:flex">
        <button type="submit" disabled={!draft.title.trim()} className="min-h-11 rounded-md bg-fuchsia-500/80 px-4 text-sm font-medium text-white hover:bg-fuchsia-500 disabled:opacity-40 sm:min-h-9">
          Save edit <kbd className="ml-1 hidden font-sf-mono text-[10px] opacity-70 sm:inline">⏎</kbd>
        </button>
        <button type="button" onClick={onCancel} className="min-h-11 rounded-md border border-obsidian-border px-4 text-sm text-white/70 hover:bg-white/5 sm:min-h-9">
          Cancel <kbd className="ml-1 hidden font-sf-mono text-[10px] opacity-70 sm:inline">Esc</kbd>
        </button>
      </div>
    </form>
  );
}

function Actions({ onAction }: { onAction: (verdict: ActionSpec['verdict']) => void }): JSX.Element {
  return (
    <div className="mt-4 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
      {CLEANUP_ACTIONS.map((action) => (
        <button key={action.verdict} type="button" onClick={() => onAction(action.verdict)}
          className={`min-h-11 rounded-md border px-3 text-sm font-medium transition-colors sm:min-h-9 ${action.tone}`}>
          <kbd className="mr-1.5 hidden font-sf-mono text-[10px] opacity-60 sm:inline">{action.shortcut}</kbd>
          {action.label}
        </button>
      ))}
    </div>
  );
}

function Header({ row, isPlaying, onPlay }: { row: CleanupRow; isPlaying: boolean; onPlay: () => void }): JSX.Element {
  const { raw } = row;
  const canPlay = row.track_id !== null;
  return (
    <div className="flex items-start gap-3">
      <button type="button" onClick={onPlay} disabled={!canPlay} aria-label={`${isPlaying ? 'Pause' : 'Play'} ${raw.title}`}
        title={canPlay ? 'Play (P)' : 'Not in the library yet; the next sync imports it'}
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-obsidian-accent text-black hover:bg-obsidian-accent/90 disabled:bg-white/10 disabled:text-white/30">
        {isPlaying ? <Pause className="h-5 w-5" /> : <Play className="ml-0.5 h-5 w-5" />}
      </button>
      <div className="min-w-0 flex-1">
        <h2 className="break-words text-base font-semibold text-white sm:text-lg">
          {raw.title}
          {row.unclear && <span className="ml-2 rounded-sm bg-amber-400/15 px-1.5 py-0.5 align-middle text-[10px] font-medium uppercase text-amber-300">Unclear</span>}
        </h2>
        <p className="flex flex-wrap items-center gap-x-3 text-sm text-white/60">
          {raw.uploader && <span>{raw.uploader}</span>}
          {raw.url && (
            <a href={raw.url} target="_blank" rel="noopener noreferrer" onClick={(event) => event.stopPropagation()} className="inline-flex items-center gap-1 text-obsidian-accent hover:underline">
              SoundCloud <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </p>
        <p className="break-all font-sf-mono text-[11px] text-white/30">{row.id}</p>
      </div>
    </div>
  );
}

export interface CleanupCardProps {
  row: CleanupRow;
  isActive: boolean;
  isEditing: boolean;
  isPlaying: boolean;
  onActivate: () => void;
  onDecide: (verdict: CleanupVerdict, expected?: CleanupView) => void;
  onEdit: (editing: boolean) => void;
  onPlay: () => void;
}

/** One pending track: SoundCloud context, Current / A / B, and the decision buttons. */
export function CleanupCard({ row, isActive, isEditing, isPlaying, onActivate, onDecide, onEdit, onPlay }: CleanupCardProps): JSX.Element {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    if (isActive) ref.current?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' });
  }, [isActive]);
  const onAction = (verdict: ActionSpec['verdict']): void => (verdict === 'edit' ? onEdit(true) : onDecide(verdict));
  return (
    <article ref={ref} onClick={onActivate} aria-label={row.raw.title} aria-current={isActive}
      className={`scroll-mt-4 rounded-lg border bg-obsidian-surface p-4 transition-colors sm:p-5 ${isActive ? 'border-obsidian-accent/50 ring-1 ring-obsidian-accent/30' : 'border-obsidian-border'}`}>
      <Header row={row} isPlaying={isPlaying} onPlay={onPlay} />
      {row.raw.description && (
        <details className="mt-3 rounded-md border border-obsidian-border bg-black/30 px-3 py-2">
          <summary className="cursor-pointer text-xs text-white/50">Description</summary>
          <pre className="mt-2 whitespace-pre-wrap break-words font-sf-mono text-xs leading-relaxed text-white/60">{row.raw.description}</pre>
        </details>
      )}
      <Comparison row={row} />
      <p className="mt-3 border-l-2 border-sky-400/50 pl-3 text-sm text-white/60">
        <span className="mr-2 font-sf-mono text-white/80">conf {row.confidence}</span>{row.notes || 'no notes'}
      </p>
      {isEditing
        ? <EditForm initial={row.a} onSave={(view) => onDecide('edited', view)} onCancel={() => onEdit(false)} />
        : <Actions onAction={onAction} />}
    </article>
  );
}
