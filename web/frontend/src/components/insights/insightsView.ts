import { INSIGHT_TABS, type InsightRow, type InsightTab } from '../../api/insights';

export const INSIGHTS_QUERY_KEY = ['insights'] as const;
export const MAX_MIN_COUNT = 1000;

export interface LiftBar {
  /** Which half of the centered track the bar fills. */
  side: 'up' | 'down' | 'none';
  /** Share of that half, 0-100. */
  widthPct: number;
}

/** Largest |lift| in the table, so bars are comparable within one table. */
export function maxAbsLift(rows: readonly InsightRow[]): number {
  return rows.reduce((max, row) => Math.max(max, Math.abs(row.lift)), 0);
}

export function liftBar(lift: number, maxAbs: number): LiftBar {
  if (lift === 0 || maxAbs <= 0) return { side: 'none', widthPct: 0 };
  return { side: lift > 0 ? 'up' : 'down', widthPct: Math.min(100, (Math.abs(lift) / maxAbs) * 100) };
}

export function tabByKey(key: string | undefined): InsightTab {
  return INSIGHT_TABS.find((tab) => tab.key === key) ?? INSIGHT_TABS[0];
}

/** A whole number between 1 and MAX_MIN_COUNT, or undefined. */
export function parseMinCount(value: unknown): number | undefined {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > MAX_MIN_COUNT) return undefined;
  return parsed;
}
