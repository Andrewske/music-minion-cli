/**
 * Playback error banner — surfaces store.playbackError (failed control
 * POSTs while offline, dead tracks, circuit breaker) with Retry + dismiss.
 *
 * Reads the store directly (not usePlayer) so mounting it never registers
 * player side-effects. Rendered above the PlayerBar and inside NowPlaying.
 */
import { View, Text, Pressable, StyleSheet } from 'react-native';
import * as Haptics from 'expo-haptics';
import { usePlayerStore } from '../../stores/playerStore';

export function PlaybackErrorBanner() {
  const playbackError = usePlayerStore((s) => s.playbackError);
  const retryPlayback = usePlayerStore((s) => s.retryPlayback);
  const setPlaybackError = usePlayerStore((s) => s.setPlaybackError);

  if (!playbackError) return null;

  const handleRetry = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    retryPlayback();
  };

  const handleDismiss = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setPlaybackError(null);
  };

  return (
    <View testID="playback-error-banner" style={styles.banner}>
      <Text style={styles.message} numberOfLines={2}>
        {playbackError}
      </Text>
      <Pressable
        testID="playback-error-retry"
        style={styles.retryBtn}
        onPress={handleRetry}
        hitSlop={8}
      >
        <Text style={styles.retryText}>Retry</Text>
      </Pressable>
      <Pressable
        testID="playback-error-dismiss"
        style={styles.dismissBtn}
        onPress={handleDismiss}
        hitSlop={8}
      >
        <Text style={styles.dismissText}>✕</Text>
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
    gap: 12,
  },
  message: {
    flex: 1,
    color: '#CF6679',
    fontSize: 13,
  },
  retryBtn: {
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
    width: 28,
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dismissText: {
    color: '#9E9E9E',
    fontSize: 14,
  },
});
