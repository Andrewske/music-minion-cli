/**
 * Comparison screen — swipe-to-vote flow.
 *
 * Flow: playlist picker → startComparison → swipe cards → recordComparison → next pair
 * Optimistic: show next pair immediately, fire POST in background.
 * Portrait locked (handled via app.json orientation per-screen in future).
 */
import { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  Pressable,
  FlatList,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Toast from 'react-native-toast-message';
import {
  getPlaylistsByLibrary,
  startComparison,
  recordComparison,
} from '@music-minion/shared';
import type {
  Playlist,
  ComparisonPair,
  ComparisonProgress,
  RecordComparisonRequest,
} from '@music-minion/shared';
import { SwipeableComparisonCard } from '../../components/comparison/SwipeableComparisonCard';
import { VoteButtons } from '../../components/comparison/VoteButtons';
import { StreakCounter } from '../../components/comparison/StreakCounter';
import { ProgressBar } from '../../components/comparison/ProgressBar';

type ScreenState =
  | { phase: 'picking' }
  | { phase: 'comparing'; playlistId: number; pair: ComparisonPair; progress: ComparisonProgress }
  | { phase: 'complete'; progress: ComparisonProgress };

export default function ComparisonScreen() {
  const queryClient = useQueryClient();
  const [screen, setScreen] = useState<ScreenState>({ phase: 'picking' });
  const [voteCount, setVoteCount] = useState(0);
  const pendingVoteRef = useRef(false);

  // Playlist list
  const { data: playlists, isLoading: playlistsLoading, error: playlistsError } = useQuery({
    queryKey: ['playlists', 'local'],
    queryFn: () => getPlaylistsByLibrary('local'),
  });

  // Start comparison mutation
  const startMutation = useMutation({
    mutationFn: (playlistId: number) => startComparison(playlistId),
    onSuccess: (response, playlistId) => {
      if (response.pair) {
        setScreen({
          phase: 'comparing',
          playlistId,
          pair: response.pair,
          progress: response.progress,
        });
      } else {
        setScreen({ phase: 'complete', progress: response.progress });
      }
    },
    onError: (error) => {
      Toast.show({
        type: 'error',
        text1: 'Failed to start',
        text2: error instanceof Error ? error.message : 'Try again',
      });
    },
  });

  // Record vote mutation — optimistic
  const recordMutation = useMutation({
    mutationFn: (request: RecordComparisonRequest) => recordComparison(request),
    onSuccess: (response) => {
      pendingVoteRef.current = false;
      if (response.pair && screen.phase === 'comparing') {
        setScreen({
          phase: 'comparing',
          playlistId: screen.playlistId,
          pair: response.pair,
          progress: response.progress,
        });
      } else {
        setScreen({ phase: 'complete', progress: response.progress });
      }
      setVoteCount((c) => c + 1);
    },
    onError: (error) => {
      pendingVoteRef.current = false;
      Toast.show({
        type: 'error',
        text1: 'Vote failed',
        text2: error instanceof Error ? error.message : 'Try again',
      });
    },
  });

  const handleSelectPlaylist = useCallback((playlistId: number) => {
    startMutation.mutate(playlistId);
  }, [startMutation]);

  const handleVote = useCallback((winnerId: number) => {
    if (screen.phase !== 'comparing' || pendingVoteRef.current) return;
    pendingVoteRef.current = true;

    recordMutation.mutate({
      playlist_id: screen.playlistId,
      track_a_id: screen.pair.track_a.id,
      track_b_id: screen.pair.track_b.id,
      winner_id: winnerId,
    });
  }, [screen, recordMutation]);

  const handleVoteA = useCallback(() => {
    if (screen.phase === 'comparing') handleVote(screen.pair.track_a.id);
  }, [screen, handleVote]);

  const handleVoteB = useCallback(() => {
    if (screen.phase === 'comparing') handleVote(screen.pair.track_b.id);
  }, [screen, handleVote]);

  const handleReset = useCallback(() => {
    setScreen({ phase: 'picking' });
    setVoteCount(0);
    queryClient.invalidateQueries({ queryKey: ['playlists'] });
  }, [queryClient]);

  // === PLAYLIST PICKER ===
  if (screen.phase === 'picking') {
    if (playlistsLoading) {
      return (
        <View className="flex-1 bg-background justify-center items-center">
          <ActivityIndicator size="large" color="#7C4DFF" />
          <Text className="text-text-secondary mt-4">Loading playlists...</Text>
        </View>
      );
    }

    if (playlistsError) {
      return (
        <View className="flex-1 bg-background justify-center items-center px-6">
          <Text className="text-error text-lg mb-2">Can't reach server</Text>
          <Text className="text-text-secondary text-center mb-4">
            {playlistsError instanceof Error ? playlistsError.message : 'Connection failed'}
          </Text>
          <Text className="text-text-secondary text-sm text-center">
            Is Tailscale running?
          </Text>
        </View>
      );
    }

    const localPlaylists = playlists?.filter((p: Playlist) => p.track_count >= 2) ?? [];

    return (
      <View className="flex-1 bg-background pt-12">
        <View className="px-4 mb-6">
          <Text className="text-text-primary text-2xl font-bold mb-1">
            Compare
          </Text>
          <Text className="text-text-secondary text-base">
            Pick a playlist to start ranking tracks
          </Text>
        </View>

        {startMutation.isPending && (
          <View className="px-4 mb-4">
            <ActivityIndicator color="#7C4DFF" />
          </View>
        )}

        <FlatList
          data={localPlaylists}
          keyExtractor={(item) => item.id.toString()}
          contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 32 }}
          renderItem={({ item, index }) => (
            <Pressable
              testID={index === 0 ? 'comparison-playlist-option' : undefined}
              className="bg-surface rounded-lg px-4 py-4 mb-2 flex-row justify-between items-center active:opacity-70"
              onPress={() => handleSelectPlaylist(item.id)}
              disabled={startMutation.isPending}
            >
              <View className="flex-1 mr-4">
                <Text className="text-text-primary text-base font-medium">
                  {item.name}
                </Text>
                {item.description ? (
                  <Text className="text-text-secondary text-sm mt-1" numberOfLines={1}>
                    {item.description}
                  </Text>
                ) : null}
              </View>
              <Text className="text-text-secondary text-sm">
                {item.track_count} tracks
              </Text>
            </Pressable>
          )}
          ListEmptyComponent={
            <Text className="text-text-secondary text-center mt-8">
              No playlists with 2+ tracks.{'\n'}Create one in the web app.
            </Text>
          }
        />
      </View>
    );
  }

  // === COMPLETION ===
  if (screen.phase === 'complete') {
    return (
      <View className="flex-1 bg-background justify-center items-center px-6">
        <Text className="text-4xl mb-4">🎉</Text>
        <Text className="text-text-primary text-2xl font-bold mb-2">
          All caught up!
        </Text>
        <Text className="text-text-secondary text-base text-center mb-2">
          All tracks have been compared
        </Text>
        {screen.progress && (
          <Text className="text-text-secondary text-sm font-mono mb-6">
            {screen.progress.compared} / {screen.progress.total} comparisons
          </Text>
        )}
        {voteCount > 0 && (
          <Text className="text-text-secondary text-sm mb-6">
            You made {voteCount} votes this session
          </Text>
        )}
        <Pressable
          className="bg-primary rounded-lg px-8 py-4"
          onPress={handleReset}
        >
          <Text className="text-white text-base font-semibold">
            Pick another playlist
          </Text>
        </Pressable>
      </View>
    );
  }

  // === COMPARING ===
  const { pair, progress } = screen;

  return (
    <ScrollView
      className="flex-1 bg-background"
      contentContainerStyle={{ paddingTop: 48, paddingBottom: 120 }}
      showsVerticalScrollIndicator={false}
    >
      {/* Progress */}
      <ProgressBar progress={progress} />

      {/* Streak counter */}
      <StreakCounter voteCount={voteCount} />

      {/* Track A */}
      <SwipeableComparisonCard
        track={pair.track_a}
        label="A"
        onVote={handleVoteA}
        disabled={recordMutation.isPending}
      />

      {/* VS divider */}
      <View className="items-center py-3">
        <View className="w-12 h-12 rounded-full bg-surface border-2 border-neutral-700 items-center justify-center">
          <Text className="text-text-secondary font-bold text-sm tracking-widest">
            VS
          </Text>
        </View>
      </View>

      {/* Track B */}
      <SwipeableComparisonCard
        track={pair.track_b}
        label="B"
        onVote={handleVoteB}
        disabled={recordMutation.isPending}
      />

      {/* Vote buttons (tap fallback) */}
      <View className="mt-6">
        <VoteButtons
          trackATitle={pair.track_a.title}
          trackBTitle={pair.track_b.title}
          onVoteA={handleVoteA}
          onVoteB={handleVoteB}
          disabled={recordMutation.isPending}
        />
      </View>

      {/* Session info */}
      <View className="items-center mt-6">
        <Pressable onPress={handleReset}>
          <Text className="text-text-secondary text-sm underline">
            Pick different playlist
          </Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}
