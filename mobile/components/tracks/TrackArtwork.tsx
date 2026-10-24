/**
 * Square track artwork from the same endpoint the full player uses
 * (GET /tracks/{id}/artwork). Falls back to a lucide Music glyph when the
 * track has no id or the image fails to load. While playing, an accent
 * scrim with AudioLines sits over the art instead of replacing it.
 */
import { useState } from 'react';
import type { ReactElement } from 'react';
import { Image, StyleSheet, View } from 'react-native';
import { AudioLines, Music } from 'lucide-react-native';
import { getDefaultApiClient } from '@music-minion/shared';
import { artworkUrl } from '../../features/home/trackRow';

interface TrackArtworkProps {
  trackId: number | null;
  size?: number;
  isPlaying?: boolean;
}

export function TrackArtwork({ trackId, size = 44, isPlaying = false }: TrackArtworkProps): ReactElement {
  const [failedId, setFailedId] = useState<number | null>(null);
  const uri = trackId !== null && failedId !== trackId ? artworkUrl(getDefaultApiClient().getBaseUrl(), trackId) : null;
  const box = { width: size, height: size, borderRadius: Math.round(size / 7) };
  return (
    <View style={[styles.box, box]}>
      {uri ? (
        <Image
          source={{ uri }}
          style={StyleSheet.absoluteFill}
          resizeMode="cover"
          onError={() => setFailedId(trackId)}
        />
      ) : (
        <Music size={size * 0.42} color="#6B6B6B" />
      )}
      {isPlaying ? (
        <View style={[StyleSheet.absoluteFill, styles.playing]}>
          <AudioLines size={size * 0.46} color="#FFFFFF" strokeWidth={2.25} />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    backgroundColor: '#2A2A2A',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  playing: {
    backgroundColor: '#7C4DFFB3',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
