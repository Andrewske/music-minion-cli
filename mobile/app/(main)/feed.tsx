import { useCallback, useMemo } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  Text,
  View,
} from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query';
import Toast from 'react-native-toast-message';
import {
  FEED_DECISION_MUTATION_KEY,
  FEED_PAGE_SIZE,
  getFeed,
  getFeedRefetchInterval,
  isFeedSyncFailed,
  prepareFeedQueue,
  applyMaterializedIds,
  type PreparedFeedQueue,
  rateFeedItem,
  type FeedVerdict,
  type FeedItem,
  type FeedPage,
  type FeedRankPreset,
  type FeedSource,
  type Track,
} from '@music-minion/shared';
import { usePlayerStore } from '../../stores/playerStore';
import { FeedTrackCard } from '../../components/feed/FeedTrackCard';
import { FeedFilterRow } from '../../components/feed/FeedFilterRow';
import { ScreenHeader } from '../../components/ScreenHeader';
import {
  optimisticallyDecideFeedItems,
  parseFeedScreenState,
} from '../../features/feed/feedState';

const toTrack = (item: FeedItem, localTrackId = item.local_track_id): Track => {
  const artist = item.uploader ?? item.artist ?? item.reposters[0];
  return {
    id: localTrackId as number,
    title: item.title ?? 'Untitled',
    artist: artist?.display_name ?? artist?.slug ?? 'Unknown artist',
    duration: item.duration_ms / 1000,
  };
};

export default function FeedScreen() {
  const params = useLocalSearchParams<{
    source?: string | string[];
    maxRank?: string | string[];
    inLibrary?: string | string[];
  }>();
  const { source, maxRank, inLibrary } = parseFeedScreenState(params);
  const queryClient = useQueryClient();
  const play = usePlayerStore((state) => state.play);
  const currentTrackId = usePlayerStore((state) => state.currentTrack?.id ?? null);
  const feedQueryKey = ['feed', { source, maxRank, inLibrary }] as const;

  const feedQuery = useInfiniteQuery({
    queryKey: feedQueryKey,
    queryFn: ({ pageParam }) =>
      getFeed({
        cursor: pageParam,
        limit: FEED_PAGE_SIZE,
        source,
        maxRank,
        inLibrary,
      }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    refetchInterval: (query) =>
      getFeedRefetchInterval(
        (query.state.data as InfiniteData<FeedPage> | undefined)?.pages,
        queryClient.isMutating({ mutationKey: FEED_DECISION_MUTATION_KEY })
      ),
  });
  const items = useMemo(
    () => feedQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [feedQuery.data]
  );

  const decisionMutation = useMutation({
    mutationKey: FEED_DECISION_MUTATION_KEY,
    mutationFn: ({ item, decision }: { item: FeedItem; decision: FeedVerdict }) =>
      rateFeedItem(item.soundcloud_id, decision, {
        surface: 'mobile',
        modelVersion: item.prediction_model_version ?? undefined,
      }),
    onMutate: async ({ item }) => {
      await queryClient.cancelQueries({ queryKey: feedQueryKey });
      const previous = queryClient.getQueryData<InfiniteData<FeedPage>>(feedQueryKey);
      queryClient.setQueryData<InfiniteData<FeedPage>>(feedQueryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          pages: old.pages.map((page) => ({
            ...page,
            items: optimisticallyDecideFeedItems(page.items, item.soundcloud_id),
          })),
        };
      });
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(feedQueryKey, context.previous);
      Toast.show({ type: 'error', text1: 'Decision failed', text2: 'Your previous choice was restored.' });
    },
    onSuccess: (response, { decision }) => {
      if (isFeedSyncFailed(response.action_state)) {
        Toast.show({ type: 'error', text1: 'Kept locally', text2: 'SoundCloud sync needs attention.' });
      } else if (decision === 'keep') {
        Toast.show({ type: 'success', text1: 'Kept', text2: 'SoundCloud sync queued.' });
      }
    },
    onSettled: () => {
      // Replaces any poll that read before the decision committed.
      if (queryClient.isMutating({ mutationKey: FEED_DECISION_MUTATION_KEY }) === 1) {
        void queryClient.invalidateQueries({ queryKey: feedQueryKey });
      }
    },
  });

  const handlePlay = useCallback(
    async (item: FeedItem): Promise<void> => {
      let queue: PreparedFeedQueue;
      try {
        queue = await prepareFeedQueue(items, item);
      } catch {
        Toast.show({ type: 'error', text1: 'Could not prepare track for playback' });
        return;
      }
      const localTrackId = item.local_track_id ?? queue.materialized[item.soundcloud_id];
      if (localTrackId === undefined) {
        Toast.show({ type: 'error', text1: 'Could not prepare track for playback' });
        return;
      }
      if (Object.keys(queue.materialized).length > 0) {
        queryClient.setQueriesData<InfiniteData<FeedPage>>(
          { queryKey: ['feed'] },
          (old) => old && ({
            ...old,
            pages: old.pages.map((page) => ({
              ...page,
              items: page.items.map((candidate) => applyMaterializedIds(candidate, queue.materialized)),
            })),
          })
        );
      }
      // No shuffle override: the player bar's shuffle toggle decides.
      await play(toTrack(item, localTrackId), { type: 'feed', track_ids: queue.trackIds });
    },
    [items, play, queryClient]
  );

  const setSource = (value: FeedSource): void => {
    router.setParams({ source: value === 'all' ? undefined : value });
  };
  const setMaxRank = (value?: FeedRankPreset): void => {
    router.setParams({ maxRank: value ? String(value) : undefined });
  };
  const toggleInLibrary = (): void => {
    router.setParams({ inLibrary: inLibrary ? undefined : 'true' });
  };

  return (
    <View className="flex-1 bg-background">
      <ScreenHeader title="Feed" />
      <FeedFilterRow
        source={source}
        maxRank={maxRank}
        inLibrary={inLibrary}
        onSource={setSource}
        onMaxRank={setMaxRank}
        onToggleInLibrary={toggleInLibrary}
      />

      {feedQuery.isLoading ? (
        <View className="items-center py-8" accessibilityRole="progressbar" accessibilityLabel="Loading feed"><ActivityIndicator color="#7C4DFF" /></View>
      ) : feedQuery.isError ? (
        <View className="items-center gap-3 py-12" accessibilityRole="alert">
          <Text className="text-base text-text-secondary">Failed to load feed.</Text>
          <Pressable onPress={() => void feedQuery.refetch()} accessibilityRole="button" className="rounded border border-neutral-700 px-4 py-2"><Text className="text-text-primary">Try again</Text></Pressable>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.soundcloud_id}
          initialNumToRender={16}
          maxToRenderPerBatch={12}
          updateCellsBatchingPeriod={40}
          windowSize={9}
          removeClippedSubviews
          keyboardShouldPersistTaps="handled"
          onEndReached={() => {
            if (feedQuery.hasNextPage && !feedQuery.isFetchingNextPage) void feedQuery.fetchNextPage();
          }}
          onEndReachedThreshold={0.6}
          refreshControl={<RefreshControl refreshing={feedQuery.isRefetching} onRefresh={() => void feedQuery.refetch()} tintColor="#7C4DFF" />}
          renderItem={({ item }) => (
            <FeedTrackCard
              item={item}
              isPlaying={item.local_track_id !== null && item.local_track_id === currentTrackId}
              isUpdating={decisionMutation.isPending && decisionMutation.variables?.item.soundcloud_id === item.soundcloud_id}
              onPlay={(target) => void handlePlay(target)}
              onDecide={(target, decision) => decisionMutation.mutate({ item: target, decision })}
            />
          )}
          ListFooterComponent={feedQuery.isFetchingNextPage ? <View className="py-4" accessibilityRole="progressbar" accessibilityLabel="Loading more tracks"><ActivityIndicator color="#7C4DFF" /></View> : null}
          ListEmptyComponent={<View className="items-center px-6 py-12"><Text className="text-center text-base text-text-secondary">No tracks for these filters.</Text></View>}
        />
      )}
    </View>
  );
}
