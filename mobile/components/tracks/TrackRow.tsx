/**
 * TrackRow — the shared list row for Home and History:
 *   [art 44] Title             [trailing]
 *            Subtitle
 * Static styles only: NativeWind's Pressable wrapper drops function styles,
 * so press feedback is android_ripple.
 */
import type { ReactElement, ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { TrackArtwork } from './TrackArtwork';

export interface TrackRowProps {
  artworkId: number | null;
  title: string;
  subtitle: string;
  trailing?: ReactNode;
  isPlaying?: boolean;
  onPress?: () => void;
  onLongPress?: () => void;
  testID?: string;
}

export function TrackRow(props: TrackRowProps): ReactElement {
  const { artworkId, title, subtitle, trailing, isPlaying = false, onPress, onLongPress, testID } = props;
  return (
    <Pressable
      testID={testID}
      style={[styles.row, isPlaying && styles.rowPlaying]}
      onPress={onPress}
      onLongPress={onLongPress}
      disabled={!onPress && !onLongPress}
      delayLongPress={350}
      android_ripple={{ color: '#FFFFFF14' }}
      accessibilityRole={onPress ? 'button' : undefined}
      accessibilityHint={onLongPress ? 'Long press for more actions' : undefined}
    >
      <TrackArtwork trackId={artworkId} isPlaying={isPlaying} />
      <View style={styles.info}>
        <Text style={[styles.title, isPlaying && styles.titlePlaying]} numberOfLines={1}>
          {title}
        </Text>
        <Text style={styles.subtitle} numberOfLines={1}>
          {subtitle}
        </Text>
      </View>
      {trailing ? <View style={styles.trailing}>{trailing}</View> : null}
    </Pressable>
  );
}

export const trackRowText = StyleSheet.create({
  meta: {
    color: '#9E9E9E',
    fontSize: 12,
    fontVariant: ['tabular-nums'],
  },
  metaDim: {
    color: '#6B6B6B',
    fontSize: 11,
    fontVariant: ['tabular-nums'],
  },
});

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 64,
    paddingHorizontal: 16,
    paddingVertical: 10,
    gap: 12,
  },
  rowPlaying: {
    backgroundColor: '#7C4DFF14',
  },
  info: {
    flex: 1,
  },
  title: {
    color: '#E0E0E0',
    fontSize: 15,
    fontWeight: '500',
  },
  titlePlaying: {
    color: '#B39DFF',
  },
  subtitle: {
    color: '#9E9E9E',
    fontSize: 13,
    marginTop: 2,
  },
  trailing: {
    alignItems: 'flex-end',
    gap: 3,
  },
});
