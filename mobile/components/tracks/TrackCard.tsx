/**
 * Track card — Home row for a library Track: artwork, title, artist
 * (album only when it isn't a month bucket), rating + duration.
 * Tap to play, long-press opens the track action sheet.
 */
import type { ReactElement } from 'react';
import { Text } from 'react-native';
import * as Haptics from 'expo-haptics';
import type { Track } from '@music-minion/shared';
import { trackRowSubtitle } from '../../features/home/trackRow';
import { TrackRow, trackRowText } from './TrackRow';

interface TrackCardProps {
  track: Track;
  isPlaying?: boolean;
  onPress: () => void;
  onLongPress?: () => void;
  testID?: string;
}

const formatDuration = (seconds?: number): string => {
  if (!seconds) return '';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
};

function Trailing({ track }: { track: Track }): ReactElement {
  const tag = track.emojis?.[0];
  const rating = track.elo_rating != null ? String(Math.round(track.elo_rating)) : null;
  const top = [tag, rating].filter((v): v is string => Boolean(v)).join(' ');
  return (
    <>
      {top ? <Text style={trackRowText.meta}>{top}</Text> : null}
      <Text style={trackRowText.metaDim}>{formatDuration(track.duration)}</Text>
    </>
  );
}

export function TrackCard({ track, isPlaying, onPress, onLongPress, testID }: TrackCardProps): ReactElement {
  const handleLongPress = onLongPress
    ? (): void => {
        void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
        onLongPress();
      }
    : undefined;

  return (
    <TrackRow
      testID={testID}
      artworkId={track.id}
      title={track.title}
      subtitle={trackRowSubtitle(track)}
      trailing={<Trailing track={track} />}
      isPlaying={isPlaying}
      onPress={onPress}
      onLongPress={handleLongPress}
    />
  );
}
