/**
 * Playback error banner — surfaces store.playbackError (failed control
 * POSTs while offline, dead tracks, circuit breaker) with Retry + dismiss.
 *
 * Reads the store directly (not usePlayer) so mounting it never registers
 * player side-effects. Rendered above the PlayerBar and inside NowPlaying.
 */
import type { ReactElement } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import * as Haptics from 'expo-haptics';
import { CircleAlert, RotateCcw, X } from 'lucide-react-native';
import { usePlayerStore } from '../../stores/playerStore';

export function PlaybackErrorBanner(): ReactElement | null {
  const playbackError = usePlayerStore((s) => s.playbackError);
  const retryPlayback = usePlayerStore((s) => s.retryPlayback);
  const setPlaybackError = usePlayerStore((s) => s.setPlaybackError);

  if (!playbackError) return null;

  const handleRetry = (): void => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    retryPlayback();
  };

  const handleDismiss = (): void => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setPlaybackError(null);
  };

  return (
    <View testID="playback-error-banner" style={styles.banner}>
      <CircleAlert size={18} color="#CF6679" strokeWidth={2} />
      <Text style={styles.message} numberOfLines={2}>
        {playbackError}
      </Text>
      <Pressable
        testID="playback-error-retry"
        accessibilityRole="button"
        accessibilityLabel="Retry playback"
        android_ripple={{ color: '#FFFFFF33' }}
        style={styles.retryBtn}
        onPress={handleRetry}
        hitSlop={8}
      >
        <RotateCcw size={14} color="#FFFFFF" strokeWidth={2.25} />
        <Text style={styles.retryText}>Retry</Text>
      </Pressable>
      <Pressable
        testID="playback-error-dismiss"
        accessibilityRole="button"
        accessibilityLabel="Dismiss error"
        android_ripple={{ color: '#FFFFFF1F', borderless: true, radius: 18 }}
        style={styles.dismissBtn}
        onPress={handleDismiss}
        hitSlop={8}
      >
        <X size={18} color="#9E9E9E" strokeWidth={2} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#2A1A1D',
    borderTopWidth: 1,
    borderTopColor: '#5A2A33',
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 10,
  },
  message: {
    flex: 1,
    color: '#CF6679',
    fontSize: 13,
  },
  retryBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    overflow: 'hidden',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: '#7C4DFF',
  },
  retryText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '600',
  },
  dismissBtn: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
