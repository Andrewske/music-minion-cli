/**
 * MatchingReview — Review SC track match candidates stored in match_candidates table.
 *
 * Displays pending candidates with local track vs SC track side-by-side.
 * Users can Accept (links soundcloud_id) or Reject each row.
 * Supports score-range filtering and pagination.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getMatchingCandidates,
  getMatchingStats,
  acceptCandidate,
  rejectCandidate,
  type MatchCandidate,
  type MatchCandidateStats,
} from '../../api/soundcloud';

// ============================================================================
// Helpers
// ============================================================================

function scoreBadgeClass(score: number): string {
  if (score >= 0.8) return 'bg-green-500/20 text-green-400 border-green-500/30';
  if (score >= 0.7) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
  if (score >= 0.6) return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
  return 'bg-red-500/20 text-red-400 border-red-500/30';
}

function ScoreBadge({ score }: { score: number }): JSX.Element {
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded border text-xs font-mono font-medium ${scoreBadgeClass(score)}`}
    >
      {(score * 100).toFixed(0)}%
    </span>
  );
}

// ============================================================================
// Progress bar
// ============================================================================

interface ProgressBarProps {
  stats: MatchCandidateStats;
}

function ProgressBar({ stats }: ProgressBarProps): JSX.Element {
  const reviewed = stats.accepted + stats.rejected;
  const pct = stats.total > 0 ? Math.round((reviewed / stats.total) * 100) : 0;

  return (
    <div className="p-4 bg-slate-800 border border-slate-700 rounded-lg space-y-2">
      <div className="flex justify-between text-sm">
        <span className="text-white/60">
          <span className="text-white font-medium">{reviewed}</span> of{' '}
          <span className="text-white font-medium">{stats.total}</span> reviewed
        </span>
        <div className="flex gap-4 text-xs">
          <span className="text-green-400">{stats.accepted} accepted</span>
          <span className="text-red-400">{stats.rejected} rejected</span>
          <span className="text-white/40">{stats.pending} pending</span>
        </div>
      </div>
      <div className="w-full bg-slate-700 rounded-full h-2">
        <div
          className="bg-obsidian-accent h-2 rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ============================================================================
// Score filter
// ============================================================================

interface ScoreFilterProps {
  minScore: number;
  maxScore: number;
  onMinChange: (v: number) => void;
  onMaxChange: (v: number) => void;
}

function ScoreFilter({ minScore, maxScore, onMinChange, onMaxChange }: ScoreFilterProps): JSX.Element {
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="text-white/60 whitespace-nowrap">Score range:</span>
      <div className="flex items-center gap-2">
        <input
          type="number"
          min={0}
          max={1}
          step={0.05}
          value={minScore}
          onChange={(e) => onMinChange(Math.min(parseFloat(e.target.value) || 0, maxScore))}
          className="w-20 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-white text-xs focus:ring-1 focus:ring-obsidian-accent focus:border-transparent"
        />
        <span className="text-white/40">–</span>
        <input
          type="number"
          min={0}
          max={1}
          step={0.05}
          value={maxScore}
          onChange={(e) => onMaxChange(Math.max(parseFloat(e.target.value) || 1, minScore))}
          className="w-20 px-2 py-1 bg-slate-800 border border-slate-700 rounded text-white text-xs focus:ring-1 focus:ring-obsidian-accent focus:border-transparent"
        />
      </div>
    </div>
  );
}

// ============================================================================
// Candidate row
// ============================================================================

interface CandidateRowProps {
  candidate: MatchCandidate;
  onAccept: (id: number) => void;
  onReject: (id: number) => void;
  isPending: boolean;
}

function CandidateRow({ candidate, onAccept, onReject, isPending }: CandidateRowProps): JSX.Element {
  return (
    <tr className="border-b border-slate-700/50 hover:bg-slate-800/40 transition-colors">
      {/* Local track */}
      <td className="py-3 pr-4">
        <div className="font-medium text-white truncate max-w-[200px]">
          {candidate.local_track.title ?? <span className="text-white/30 italic">Unknown</span>}
        </div>
        <div className="text-xs text-slate-400 truncate max-w-[200px]">
          {candidate.local_track.artist ?? '—'}
        </div>
      </td>

      {/* SC track */}
      <td className="py-3 pr-4">
        <div className="font-medium text-white truncate max-w-[200px]">
          {candidate.sc_track.title ?? <span className="text-white/30 italic">Unknown</span>}
        </div>
        <div className="text-xs text-slate-400 truncate max-w-[200px]">
          {candidate.sc_track.artist ?? '—'}
        </div>
      </td>

      {/* Score */}
      <td className="py-3 pr-4">
        <div className="flex flex-col gap-1">
          <ScoreBadge score={candidate.score} />
          {candidate.scoring_path && (
            <span className="text-[10px] text-white/30 font-mono truncate max-w-[120px]">
              {candidate.scoring_path}
            </span>
          )}
        </div>
      </td>

      {/* Actions */}
      <td className="py-3">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onAccept(candidate.id)}
            disabled={isPending}
            className="px-3 py-1.5 bg-green-700 hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-medium rounded transition-colors"
          >
            Accept
          </button>
          <button
            type="button"
            onClick={() => onReject(candidate.id)}
            disabled={isPending}
            className="px-3 py-1.5 bg-slate-700 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs font-medium rounded transition-colors"
          >
            Reject
          </button>
        </div>
      </td>
    </tr>
  );
}

// ============================================================================
// Pagination
// ============================================================================

interface PaginationProps {
  page: number;
  pageSize: number;
  count: number;
  onPageChange: (page: number) => void;
}

function Pagination({ page, pageSize, count, onPageChange }: PaginationProps): JSX.Element {
  const hasPrev = page > 1;
  const hasNext = count === pageSize; // if we got a full page, there may be more

  return (
    <div className="flex items-center justify-between text-sm text-white/60">
      <span>Page {page}</span>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onPageChange(page - 1)}
          disabled={!hasPrev}
          className="px-3 py-1 bg-slate-800 border border-slate-700 rounded disabled:opacity-40 hover:bg-slate-700 transition-colors text-white text-xs"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={() => onPageChange(page + 1)}
          disabled={!hasNext}
          className="px-3 py-1 bg-slate-800 border border-slate-700 rounded disabled:opacity-40 hover:bg-slate-700 transition-colors text-white text-xs"
        >
          Next
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// Main component
// ============================================================================

const PAGE_SIZE = 20;

export function MatchingReview(): JSX.Element {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [minScore, setMinScore] = useState(0.0);
  const [maxScore, setMaxScore] = useState(1.0);
  // Track which candidate IDs have an in-flight mutation
  const [pendingIds, setPendingIds] = useState<Set<number>>(new Set());

  const candidatesKey = ['matching-candidates', page, PAGE_SIZE, minScore, maxScore] as const;

  const { data: candidates = [], isLoading, isError } = useQuery({
    queryKey: candidatesKey,
    queryFn: () => getMatchingCandidates({ page, pageSize: PAGE_SIZE, minScore, maxScore }),
  });

  const { data: stats } = useQuery({
    queryKey: ['matching-stats'],
    queryFn: getMatchingStats,
  });

  const handleMutationStart = (id: number): void => {
    setPendingIds((prev) => new Set([...prev, id]));
  };

  const handleMutationEnd = (id: number): void => {
    setPendingIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  };

  const invalidate = (): void => {
    queryClient.invalidateQueries({ queryKey: ['matching-candidates'] });
    queryClient.invalidateQueries({ queryKey: ['matching-stats'] });
  };

  const acceptMutation = useMutation({
    mutationFn: (id: number) => acceptCandidate(id),
    onMutate: (id) => handleMutationStart(id),
    onSettled: (_data, _err, id) => {
      handleMutationEnd(id);
      invalidate();
    },
  });

  const rejectMutation = useMutation({
    mutationFn: (id: number) => rejectCandidate(id),
    onMutate: (id) => handleMutationStart(id),
    onSettled: (_data, _err, id) => {
      handleMutationEnd(id);
      invalidate();
    },
  });

  const handleFilterChange = (newMin: number, newMax: number): void => {
    setMinScore(newMin);
    setMaxScore(newMax);
    setPage(1);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-white">Track Matching Review</h2>
        <p className="text-white/60 text-sm mt-1">
          Review candidate matches between your local library and SoundCloud tracks.
          Accepting a match links the local track so it can be streamed from SoundCloud.
        </p>
      </div>

      {/* Progress */}
      {stats && <ProgressBar stats={stats} />}

      {/* Filters */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <ScoreFilter
          minScore={minScore}
          maxScore={maxScore}
          onMinChange={(v) => handleFilterChange(v, maxScore)}
          onMaxChange={(v) => handleFilterChange(minScore, v)}
        />
        {stats && (
          <span className="text-xs text-white/40">
            {stats.pending} pending candidates
          </span>
        )}
      </div>

      {/* Table */}
      <div className="bg-obsidian-surface border border-obsidian-border rounded-lg overflow-hidden">
        {isLoading && (
          <div className="flex items-center justify-center py-16 text-white/40 text-sm">
            Loading candidates…
          </div>
        )}

        {isError && (
          <div className="p-6 text-red-400 text-sm">
            Failed to load candidates. Check that the backend is running.
          </div>
        )}

        {!isLoading && !isError && candidates.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 gap-2">
            <div className="text-white/60 text-sm">No pending candidates in this score range.</div>
            {minScore > 0 || maxScore < 1 ? (
              <button
                type="button"
                onClick={() => handleFilterChange(0, 1)}
                className="text-xs text-obsidian-accent hover:underline"
              >
                Clear filters
              </button>
            ) : null}
          </div>
        )}

        {!isLoading && !isError && candidates.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-700 bg-slate-800/50">
                  <th className="px-4 py-3 pr-4 font-medium">Local Track</th>
                  <th className="px-4 py-3 pr-4 font-medium">SC Match</th>
                  <th className="px-4 py-3 pr-4 font-medium">Score</th>
                  <th className="px-4 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((candidate) => (
                  <CandidateRow
                    key={candidate.id}
                    candidate={candidate}
                    onAccept={(id) => acceptMutation.mutate(id)}
                    onReject={(id) => rejectMutation.mutate(id)}
                    isPending={pendingIds.has(candidate.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pagination */}
      {!isLoading && candidates.length > 0 && (
        <Pagination
          page={page}
          pageSize={PAGE_SIZE}
          count={candidates.length}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
