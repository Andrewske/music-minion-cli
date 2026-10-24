/**
 * Comparison screen — swipe-to-vote flow.
 *
 * Flow: playlist picker → startComparison → tap cards to listen → swipe/tap vote
 * → recordComparison → next pair. Vote lock prevents double-submits while
 * the POST is in flight.
 * Portrait locked (handled via app.json orientation per-screen in future).
 */
import { useState, useCallback, useRef, type ReactNode } from 'react';
import { View, Text, Pressable } from 'react-native';
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
import { SessionHeader } from '../../components/comparison/SessionHeader';
import { ScreenHeader } from '../../components/ScreenHeader';
import { PlaylistPicker } from '../../components/PlaylistPicker';
import { PartyPopper } from 'lucide-react-native';
import { useComparisonPlayback } from '../../hooks/useComparisonPlayback';
import { selectComparablePlaylists } from '../../features/comparison/comparisonState';

type ScreenState =
  | { phase: 'picking' }
  | { phase: 'comparing'; playlistId: number; playlistName: string; pair: ComparisonPair }
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
    mutationFn: (playlist: Playlist) => startComparison(playlist.id),
    onSuccess: (response, playlist) => {
      if (response.pair) {
        setScreen({
          phase: 'comparing',
          playlistId: playlist.id,
          playlistName: playlist.name,
          pair: response.pair,
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
        setScreen({ ...screen, pair: response.pair });
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

  const handleSelectPlaylist = useCallback((playlist: Playlist) => {
    startMutation.mutate(playlist);
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
    return (
      <CompareFrame>
        <PlaylistPicker
          playlists={selectComparablePlaylists(playlists)}
          isLoading={playlistsLoading}
          error={playlistsError}
          searchPlaceholder="Find a playlist to rank"
          subtitle={compareSubtitle}
          onSelect={handleSelectPlaylist}
          busyId={startMutation.isPending ? (startMutation.variables?.id ?? null) : null}
          emptyText={'No manual playlists with 2+ tracks.\nCreate one in the web app.'}
          optionTestID="comparison-playlist-option"
        />
      </CompareFrame>
    );
  }

  // === COMPLETION ===
  if (screen.phase === 'complete') {
    return (
      <CompareFrame>
        <View className="flex-1 justify-center items-center px-6">
          <View className="mb-4">
            <PartyPopper size={44} color="#7C4DFF" strokeWidth={1.75} />
          </View>
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
      </CompareFrame>
    );
  }

  // === COMPARING ===
  return (
    <ComparingView
      playlistName={screen.playlistName}
      pair={screen.pair}
      voteCount={voteCount}
      voting={recordMutation.isPending}
      onVoteA={handleVoteA}
      onVoteB={handleVoteB}
      onExit={handleReset}
    />
  );
}

/** Picker row subtitle: size first, then the description if there is one. */
function compareSubtitle(playlist: Playlist): string {
  const size = `${playlist.track_count} tracks`;
  return playlist.description ? `${size} · ${playlist.description}` : size;
}

/** Picker / loading / done states: the Compare header over the body. */
function CompareFrame({ children }: { children: ReactNode }): React.JSX.Element {
  return (
    <View className="flex-1 bg-background">
      <ScreenHeader title="Compare" />
      {children}
    </View>
  );
}

interface ComparingViewProps {
  playlistName: string;
  pair: ComparisonPair;
  voteCount: number;
  voting: boolean;
  onVoteA: () => void;
  onVoteB: () => void;
  onExit: () => void;
}

/**
 * One-screen session: header, two flex cards, vote buttons pinned at the
 * bottom. No ScrollView and no bottom offsets: this screen's container
 * already ends above the root-level PlayerBar (which pads itself for the
 * bottom inset), so flex layout keeps the buttons visible.
 */
function ComparingView({
  playlistName,
  pair,
  voteCount,
  voting,
  onVoteA,
  onVoteB,
  onExit,
}: ComparingViewProps): React.JSX.Element {
  const { playStateFor, toggle, playingElsewhere } = useComparisonPlayback(pair);

  return (
    <View testID="comparison-session" className="flex-1 bg-background">
      <SessionHeader playlistName={playlistName} voteCount={voteCount} onExit={onExit} />

      <View className="flex-1 pb-3">
        <SwipeableComparisonCard
          track={pair.track_a}
          label="A"
          onVote={onVoteA}
          onPress={() => toggle(pair.track_a)}
          playState={playStateFor(pair.track_a.id)}
          playingElsewhere={playingElsewhere}
          disabled={voting}
        />
        <View className="items-center py-1">
          <Text className="text-text-secondary font-bold text-xs tracking-widest">VS</Text>
        </View>
        <SwipeableComparisonCard
          track={pair.track_b}
          label="B"
          onVote={onVoteB}
          onPress={() => toggle(pair.track_b)}
          playState={playStateFor(pair.track_b.id)}
          playingElsewhere={playingElsewhere}
          disabled={voting}
        />
      </View>

      <View className="pb-3">
        <VoteButtons
          trackATitle={pair.track_a.title}
          trackBTitle={pair.track_b.title}
          onVoteA={onVoteA}
          onVoteB={onVoteB}
          disabled={voting}
        />
      </View>
    </View>
  );
}
