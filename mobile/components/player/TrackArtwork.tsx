/**
 * Track artwork from the backend, with a lucide note on a dark tile when the
 * image is missing or fails to load.
 */
import { memo, useState } from 'react';
import type { ReactElement } from 'react';
import { View, Image, StyleSheet } from 'react-native';
import { Music } from 'lucide-react-native';
import { getDefaultApiClient } from '@music-minion/shared';

/** Backend artwork URL — baseUrl already includes the `/api` prefix. */
export function getArtworkUrl(trackId: number): string {
  return `${getDefaultApiClient().getBaseUrl()}/tracks/${trackId}/artwork`;
}

interface TrackArtworkProps {
  trackId: number;
  size: number;
  radius: number;
  label?: string;
}

/**
 * Memoized: props are primitives, so a parent re-render (e.g. a player
 * state change) doesn't rebuild the Image or its fresh `source` object.
 */
export const TrackArtwork = memo(function TrackArtwork({ trackId, size, radius, label }: TrackArtworkProps): ReactElement {
  const [failedId, setFailedId] = useState<number | null>(null);
  const box = { width: size, height: size, borderRadius: radius };
  if (failedId === trackId) {
    return (
      <View style={[styles.tile, box]} accessibilityLabel={label}>
        <Music size={Math.round(size * 0.4)} color="#555" strokeWidth={1.75} />
      </View>
    );
  }
  return (
    <Image
      source={{ uri: getArtworkUrl(trackId) }}
      style={[styles.tile, box]}
      resizeMode="cover"
      accessibilityLabel={label}
      onError={() => setFailedId(trackId)}
    />
  );
});

const styles = StyleSheet.create({
  tile: {
    backgroundColor: '#1E1E1E',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
