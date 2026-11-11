interface KeepScoreBadgeProps {
  /** Jev keep probability (0-1); null renders nothing. */
  probability: number | null;
  modelVersion?: string | null;
  /** `overlay` sits on artwork: larger, on a dark backing so it reads over any image. */
  variant?: 'inline' | 'overlay';
  className?: string;
}

const scoreText = (percent: number, variant: 'inline' | 'overlay'): string =>
  percent >= 70 ? 'text-emerald-300'
  : percent >= 40 ? (variant === 'overlay' ? 'text-white/85' : 'text-white/60')
  : (variant === 'overlay' ? 'text-white/60' : 'text-white/35');

const VARIANT_CLASSES = {
  inline: 'px-1.5 py-0.5 text-[10px]',
  overlay: 'bg-black/75 px-2 py-1 text-sm font-semibold backdrop-blur-sm',
} as const;

const inlineBackground = (percent: number): string => (percent >= 70 ? 'bg-emerald-400/10' : 'bg-white/5');

/** Predicted keep probability as a percent, green from 70% up. */
export function KeepScoreBadge({ probability, modelVersion = null, variant = 'inline', className = '' }: KeepScoreBadgeProps): JSX.Element | null {
  if (probability === null) return null;
  const percent = Math.round(probability * 100);
  const background = variant === 'inline' ? inlineBackground(percent) : '';
  return (
    <span
      title={`Predicted keep probability${modelVersion ? ` (${modelVersion})` : ''}`}
      className={`shrink-0 rounded-sm font-sf-mono ${VARIANT_CLASSES[variant]} ${background} ${scoreText(percent, variant)} ${className}`}
    >
      {percent}%
    </span>
  );
}
