import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, Loader2 } from 'lucide-react';
import { getPendingCleanup, type CleanupRow, type CleanupVerdict, type CleanupView } from '../../api/cleanup';
import { useCleanupDecision } from '../../hooks/useCleanupDecision';
import { useReviewShortcuts } from '../../hooks/useReviewShortcuts';
import { usePlayerStore } from '../../stores/playerStore';
import { CleanupCard } from './CleanupCard';
import { CLEANUP_PENDING_KEY, toText } from './cleanupView';

/** Play a row through the global player, or toggle it if it's already loaded. */
function usePlayCleanupRow(): { playingId: number | null; toggle: (row: CleanupRow) => void } {
  const currentTrack = usePlayerStore((state) => state.currentTrack);
  const isPlaying = usePlayerStore((state) => state.isPlaying);
  const { play, pause, resume } = usePlayerStore.getState();
  const toggle = (row: CleanupRow): void => {
    const trackId = row.track_id;
    if (trackId === null) return;
    if (currentTrack?.id === trackId) {
      void (isPlaying ? pause() : resume());
      return;
    }
    const track = { id: trackId, title: row.current.title, artist: toText(row.current.credited_artists) };
    void play(track, { type: 'track', track_ids: [trackId] });
  };
  return { playingId: isPlaying ? currentTrack?.id ?? null : null, toggle };
}

/** The row to focus once `id` leaves the list: the next one, else the previous. */
function neighbourOf(rows: CleanupRow[], id: string): string | null {
  const index = rows.findIndex((row) => row.id === id);
  return rows[index + 1]?.id ?? rows[index - 1]?.id ?? null;
}

function EmptyState(): JSX.Element {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-obsidian-border bg-obsidian-surface px-6 py-16 text-center">
      <CheckCircle2 className="h-8 w-8 text-obsidian-accent" />
      <p className="text-lg font-medium text-white">Nothing to review</p>
      <p className="max-w-sm text-sm text-white/50">Tracks show up here when the nightly cleanup's two runs disagree or hedge.</p>
    </div>
  );
}

function Intro({ count }: { count: number }): JSX.Element {
  return (
    <div className="space-y-1">
      <h1 className="text-2xl font-bold text-white sm:text-3xl">Tag review</h1>
      <p className="text-sm text-white/60">
        {count} {count === 1 ? 'track' : 'tracks'} the nightly cleanup couldn't settle. Each decision writes the file right away (with a backup).
      </p>
      <p className="hidden text-xs text-white/40 sm:block">
        <kbd className="font-sf-mono">J</kbd>/<kbd className="font-sf-mono">K</kbd> move · <kbd className="font-sf-mono">1</kbd> A · <kbd className="font-sf-mono">3</kbd> B · <kbd className="font-sf-mono">2</kbd> keep current · <kbd className="font-sf-mono">E</kbd> edit · <kbd className="font-sf-mono">U</kbd> unclear · <kbd className="font-sf-mono">X</kbd> skip · <kbd className="font-sf-mono">P</kbd> play
      </p>
    </div>
  );
}

/** Clear the metadata-cleanup pending queue: one card per track. */
export function TagReviewPage(): JSX.Element {
  const pendingQuery = useQuery({ queryKey: CLEANUP_PENDING_KEY, queryFn: getPendingCleanup, refetchOnWindowFocus: true });
  const decision = useCleanupDecision();
  const player = usePlayCleanupRow();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const rows = pendingQuery.data?.rows ?? [];
  const active = rows.find((row) => row.id === activeId) ?? rows[0] ?? null;

  const decide = (row: CleanupRow, verdict: CleanupVerdict, expected?: CleanupView): void => {
    setActiveId(neighbourOf(rows, row.id));
    setEditingId(null);
    decision.mutate({ id: row.id, verdict, expected });
  };
  const move = (delta: 1 | -1): void => {
    const index = rows.findIndex((row) => row.id === active?.id);
    const next = rows[Math.min(rows.length - 1, Math.max(0, index + delta))];
    if (next) setActiveId(next.id);
  };
  useReviewShortcuts({
    move,
    decide: (verdict) => active && decide(active, verdict),
    edit: () => active && setEditingId(active.id),
    play: () => active && player.toggle(active),
  }, editingId === null);

  if (pendingQuery.isLoading) {
    return <div className="flex justify-center py-24 text-white/40" role="status" aria-label="Loading tag review"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  }
  return (
    <div className="min-h-screen bg-black px-3 py-5 sm:p-6">
      <div className="mx-auto max-w-5xl space-y-4">
        <Intro count={rows.length} />
        {pendingQuery.isError && <p role="alert" className="text-sm text-red-400">Failed to load the review queue.</p>}
        {!pendingQuery.isError && rows.length === 0 && <EmptyState />}
        {rows.map((row) => (
          <CleanupCard
            key={row.id}
            row={row}
            isActive={row.id === active?.id}
            isEditing={row.id === editingId}
            isPlaying={row.track_id !== null && row.track_id === player.playingId}
            onActivate={() => setActiveId(row.id)}
            onDecide={(verdict, expected) => decide(row, verdict, expected)}
            onEdit={(editing) => setEditingId(editing ? row.id : null)}
            onPlay={() => player.toggle(row)}
          />
        ))}
      </div>
    </div>
  );
}
