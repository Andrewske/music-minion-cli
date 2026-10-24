/**
 * VerdictButtons: the Nope / Meh / Keep row. Three equal, full-width, 48dp
 * buttons with lucide icons and text labels. Stateless; the caller owns the
 * mutation and passes the current verdict back in.
 *
 *   <VerdictButtons selected={decision} keepActive={hearted} disabled={busy}
 *     onVerdict={(v) => decide(item, v)} testIDs={{ keep: 'feed-keep-7' }} />
 */
import type { ReactElement } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Heart, Meh, ThumbsDown } from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';
import type { FeedVerdict } from '@music-minion/shared';

interface VerdictSpec {
  verdict: FeedVerdict;
  label: string;
  icon: LucideIcon;
  /** Colours when this verdict is the active one. */
  activeBg: string;
  activeFg: string;
}

const VERDICTS: readonly VerdictSpec[] = [
  { verdict: 'nope', label: 'Nope', icon: ThumbsDown, activeBg: '#CF667926', activeFg: '#F28B9B' },
  { verdict: 'not_quite', label: 'Meh', icon: Meh, activeBg: '#FFFFFF1A', activeFg: '#E0E0E0' },
  { verdict: 'keep', label: 'Keep', icon: Heart, activeBg: '#7C4DFF', activeFg: '#FFFFFF' },
];

const IDLE_FG = '#BDBDBD';

export interface VerdictButtonsProps {
  selected: FeedVerdict | null;
  onVerdict: (verdict: FeedVerdict) => void;
  /** Disables all three (e.g. while a decision is saving). */
  disabled?: boolean;
  /** Keep can be active without being the selected verdict (already liked). Default: selected === 'keep'. */
  keepActive?: boolean;
  /** Disables Keep once kept, so a second tap can't re-queue the sync. */
  keepLocked?: boolean;
  testIDs?: Partial<Record<FeedVerdict, string>>;
  accessibilityHints?: Partial<Record<FeedVerdict, string>>;
}

export function VerdictButtons(props: VerdictButtonsProps): ReactElement {
  return (
    <View style={styles.row} accessibilityRole="toolbar" accessibilityLabel="Verdict">
      {VERDICTS.map((spec) => (
        <VerdictButton key={spec.verdict} spec={spec} {...props} />
      ))}
    </View>
  );
}

const isActive = (verdict: FeedVerdict, props: VerdictButtonsProps): boolean =>
  verdict === 'keep' ? props.keepActive ?? props.selected === 'keep' : props.selected === verdict;

function VerdictButton(props: VerdictButtonsProps & { spec: VerdictSpec }): ReactElement {
  const { spec, onVerdict, testIDs, accessibilityHints } = props;
  const active = isActive(spec.verdict, props);
  const disabled = (props.disabled ?? false) || (spec.verdict === 'keep' && (props.keepLocked ?? false));
  const fg = active ? spec.activeFg : IDLE_FG;
  const Icon = spec.icon;
  return (
    <Pressable
      onPress={() => onVerdict(spec.verdict)}
      disabled={disabled}
      testID={testIDs?.[spec.verdict]}
      accessibilityRole="button"
      accessibilityLabel={spec.label}
      accessibilityHint={accessibilityHints?.[spec.verdict]}
      accessibilityState={{ selected: active, disabled }}
      android_ripple={{ color: '#FFFFFF1F' }}
      // Static style: NativeWind's Pressable wrapper drops function styles.
      style={[styles.button, active && { backgroundColor: spec.activeBg, borderColor: spec.activeBg }, disabled && !active && styles.dim]}
    >
      <Icon size={18} color={fg} strokeWidth={2.25} fill={active && spec.verdict === 'keep' ? fg : 'none'} />
      <Text style={[styles.label, { color: fg }]}>{spec.label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: 8,
  },
  button: {
    flex: 1,
    minHeight: 48,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#2E2E2E',
    backgroundColor: '#262626',
    overflow: 'hidden',
  },
  dim: {
    opacity: 0.45,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
});
