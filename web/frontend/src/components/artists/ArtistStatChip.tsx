import type { ReactElement } from 'react';
import type { LucideIcon } from 'lucide-react';

// ---------------------------------------------------------------------------
// Chip key registry — consumed by chip-visibility store (task 16)
// ---------------------------------------------------------------------------

export const CHIP_KEYS = [
  'library',
  'reposts',
  'hit_rate',
  'first_loved',
  'feed_noise',
  'activity',
  'elo',
  'followers',
] as const;

export type ChipKey = typeof CHIP_KEYS[number];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface ArtistStatChipProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  tooltip?: string;
  accent?: boolean;
}

export function ArtistStatChip({
  icon: Icon,
  label,
  value,
  tooltip,
  accent = false,
}: ArtistStatChipProps): ReactElement {
  const colorClass = accent ? 'text-obsidian-accent' : 'text-white/70';

  const inner = (
    <span className={`inline-flex items-center gap-1 font-sf-mono text-xs ${colorClass}`}>
      <Icon size={12} className="shrink-0" />
      {label ? <span>{label} {value}</span> : <span>{value}</span>}
    </span>
  );

  if (tooltip) {
    return <span title={tooltip}>{inner}</span>;
  }

  return inner;
}
