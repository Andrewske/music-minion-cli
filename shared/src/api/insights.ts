import { getDefaultApiClient } from './client';

/** Feed Insights (#31): which features predict keeps vs nopes. */

export type InsightDimension = 'keyword' | 'genre' | 'tag' | 'reposter' | 'uploader' | 'duration' | 'age';
export type InsightSort = 'lift' | 'count';

export interface InsightTab {
  key: string;
  label: string;
  dimensions: InsightDimension[];
}

export const INSIGHT_TABS: readonly InsightTab[] = [
  { key: 'keywords', label: 'Keywords', dimensions: ['keyword'] },
  { key: 'genres', label: 'Genres', dimensions: ['genre'] },
  { key: 'tags', label: 'Tags', dimensions: ['tag'] },
  { key: 'reposters', label: 'Reposters', dimensions: ['reposter'] },
  { key: 'uploaders', label: 'Uploaders', dimensions: ['uploader'] },
  { key: 'other', label: 'Other', dimensions: ['duration', 'age'] },
];

export const INSIGHT_DIMENSION_LABELS: Record<InsightDimension, string> = {
  keyword: 'Title keyword',
  genre: 'Genre',
  tag: 'Tag',
  reposter: 'Reposter',
  uploader: 'Uploader',
  duration: 'Duration',
  age: 'Release age when reviewed',
};

export const DEFAULT_INSIGHT_MIN_COUNT = 8;

export interface InsightRow {
  value: string;
  seen: number;
  keeps: number;
  not_quites: number;
  nopes: number;
  /** Not quite counts as half a keep. */
  keep_pct: number | null;
  /** keep_pct minus the overall keep %, in percentage points. */
  lift: number;
}

export interface InsightsResponse {
  dimension: InsightDimension;
  min_count: number;
  overall: { seen: number; keep_pct: number };
  rows: InsightRow[];
}

export interface InsightTrack {
  soundcloud_id: string;
  decision: 'keep' | 'not_quite' | 'nope';
  decided_at: string;
  local_track_id: number | null;
  title: string | null;
  uploader: string | null;
  genre: string | null;
  tags: string[];
  reposters: string[];
  artwork_url: string | null;
  permalink_url: string | null;
  duration_ms: number;
  access: string | null;
  note: string | null;
}

export interface InsightTracksResponse {
  dimension: InsightDimension;
  value: string;
  total: number;
  items: InsightTrack[];
}

export async function getInsights(dimension: InsightDimension, minCount = DEFAULT_INSIGHT_MIN_COUNT): Promise<InsightsResponse> {
  const query = new URLSearchParams({ dimension, min_count: String(minCount) });
  return getDefaultApiClient().request<InsightsResponse>(`/insights?${query.toString()}`);
}

export async function getInsightTracks(dimension: InsightDimension, value: string): Promise<InsightTracksResponse> {
  const query = new URLSearchParams({ dimension, value });
  return getDefaultApiClient().request<InsightTracksResponse>(`/insights/tracks?${query.toString()}`);
}

/** Server order is by lift; 'count' re-sorts by times seen (ties by lift). */
export function sortInsightRows(rows: readonly InsightRow[], sort: InsightSort): InsightRow[] {
  if (sort === 'lift') return [...rows];
  return [...rows].sort((a, b) => b.seen - a.seen || b.lift - a.lift);
}

/** "+12.5 pts", "-3 pts", "0 pts". */
export function formatLift(lift: number): string {
  const rounded = Math.round(lift * 10) / 10;
  return `${rounded > 0 ? '+' : ''}${rounded} pts`;
}

export function formatKeepPct(pct: number | null): string {
  return pct === null ? '-' : `${Math.round(pct * 10) / 10}%`;
}
