import { FLAG_REASON_LABELS, formatConfidence, type FlaggedItem } from '../../api/feedFilters';

type DescribedFlag = Pick<FlaggedItem, 'reason' | 'source' | 'rule_name'> & { confidence?: number | null };

/**
 * "Live mix / set · Longer than 15 min" for rule flags, "… · agent 87%" for
 * agent flags, the reason alone for user flags.
 */
export function describeFlag(item: DescribedFlag): string {
  const reason = FLAG_REASON_LABELS[item.reason];
  if (item.source === 'rule') return `${reason} · ${item.rule_name ?? 'deleted rule'}`;
  if (item.source === 'agent') {
    const confidence = formatConfidence(item.confidence ?? null);
    return confidence ? `${reason} · agent ${confidence}` : `${reason} · agent`;
  }
  return reason;
}

/** m:ss, or h:mm:ss for the hour-long sets these rules mostly catch. */
export function formatFlagDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const hours = Math.floor(totalSec / 3600);
  const minutes = Math.floor((totalSec % 3600) / 60);
  const seconds = String(totalSec % 60).padStart(2, '0');
  return hours > 0 ? `${hours}:${String(minutes).padStart(2, '0')}:${seconds}` : `${minutes}:${seconds}`;
}

/** The server's validation message (e.g. an invalid regex), or a fallback. */
export function ruleErrorMessage(error: unknown, fallback: string): string {
  const message = error instanceof Error ? error.message : '';
  return message && !message.startsWith('[object') ? message : fallback;
}
