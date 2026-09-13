import { useCallback, useMemo } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
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
  FEED_PAGE_SIZE,
  FEED_RANK_PRESETS,
  getFeed,
  hasPendingFeedSync,
  isFeedSyncFailed,
  materializeFeedItem,
  mergeFeedDecisionResponse,
  rateFeedItem,
} from '@music-minion/shared';
import type {
  FeedDecision,
  FeedItem,
  FeedPage,
  FeedRankPreset,
  FeedSource,
  Track,
} from '@music-minion/shared';
import { usePlayerStore } from '../../stores/playerStore';
import { FeedTrackCard } from '../../components/feed/FeedTrackCard';
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

function FilterChip({
  label,
  active,
  onPress,
  testID,
}: {
  label: string;
  active: boolean;
  onPress: () => void;
  testID: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      testID={testID}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      accessibilityLabel={`Show ${label}`}
      className={`min-h-10 justify-center rounded-full border px-3 ${
        active ? 'border-primary bg-primary/15' : 'border-neutral-700'
      }`}
    >
      <Text className={`text-xs ${active ? 'text-primary' : 'text-text-secondary'}`}>
        {label}
      </Text>
    </Pressable>
  );
}

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
      hasPendingFeedSync((query.state.data as InfiniteData<FeedPage> | undefined)?.pages)
        ? 5_000
        : false,
  });
  const items = useMemo(
    () => feedQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [feedQuery.data]
  );

  const decisionMutation = useMutation({
    mutationFn: ({ item, decision }: { item: FeedItem; decision: FeedDecision }) =>
      rateFeedItem(item.soundcloud_id, decision, {
        surface: 'mobile',
        modelVersion: item.prediction_model_version ?? undefined,
      }),
    onMutate: async ({ item, decision }) => {
      await queryClient.cancelQueries({ queryKey: feedQueryKey });
      const previous = queryClient.getQueryData<InfiniteData<FeedPage>>(feedQueryKey);
      queryClient.setQueryData<InfiniteData<FeedPage>>(feedQueryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          pages: old.pages.map((page) => ({
            ...page,
            items: optimisticallyDecideFeedItems(
              page.items,
              item.soundcloud_id,
              decision
            ),
          })),
        };
      });
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) queryClient.setQueryData(feedQueryKey, context.previous);
      Toast.show({ type: 'error', text1: 'Decision failed', text2: 'Your previous choice was restored.' });
    },
    onSuccess: (response, { item, decision }) => {
      queryClient.setQueryData<InfiniteData<FeedPage>>(feedQueryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          pages: old.pages.map((page) => ({
            ...page,
            items: page.items.map((candidate) =>
              candidate.soundcloud_id === item.soundcloud_id
                ? mergeFeedDecisionResponse(candidate, response)
                : candidate
            ),
          })),
        };
      });
      if (isFeedSyncFailed(response.action_state)) {
        Toast.show({ type: 'error', text1: 'Kept locally', text2: 'SoundCloud sync needs attention.' });
      } else if (decision === 'keep') {
        Toast.show({ type: 'success', text1: 'Kept', text2: 'SoundCloud sync queued.' });
      }
    },
  });

  const handlePlay = useCallback(
    async (item: FeedItem): Promise<void> => {
      let localTrackId = item.local_track_id;
      if (localTrackId === null) {
        try {
          const materialized = await materializeFeedItem(item.soundcloud_id);
          localTrackId = materialized.local_track_id;
          queryClient.setQueriesData<InfiniteData<FeedPage>>(
            { queryKey: ['feed'] },
            (old) => old && ({
              ...old,
              pages: old.pages.map((page) => ({
                ...page,
                items: page.items.map((candidate) =>
                  candidate.soundcloud_id === item.soundcloud_id
                    ? { ...candidate, local_track_id: materialized.local_track_id }
                    : candidate
                ),
              })),
            })
          );
        } catch {
          Toast.show({ type: 'error', text1: 'Could not prepare track for playback' });
          return;
        }
      }
      const index = items.findIndex((candidate) => candidate.soundcloud_id === item.soundcloud_id);
      const trackIds = items
        .slice(Math.max(0, index))
        .map((candidate) =>
          candidate.soundcloud_id === item.soundcloud_id
            ? localTrackId
            : candidate.local_track_id
        )
        .filter((id): id is number => id !== null);
      await play(toTrack(item, localTrackId), { type: 'feed', track_ids: trackIds, shuffle: false });
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
      <View className="pb-3 pt-12">
        <Text className="mb-3 px-4 text-2xl font-bold text-text-primary">Feed</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerClassName="gap-2 px-4">
          {(['all', 'releases', 'reposts'] as const).map((value) => (
            <FilterChip key={value} label={value === 'all' ? 'All' : value === 'releases' ? 'Releases' : 'Reposts'} active={source === value} onPress={() => setSource(value)} testID={`feed-source-${value}`} />
          ))}
        </ScrollView>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerClassName="mt-2 gap-2 px-4" accessibilityLabel="Rank filters">
          <FilterChip label="All ranks" active={maxRank === undefined} onPress={() => setMaxRank()} testID="feed-rank-all" />
          {FEED_RANK_PRESETS.map((rank) => (
            <FilterChip key={rank} label={`Top ${rank}`} active={maxRank === rank} onPress={() => setMaxRank(rank)} testID={`feed-rank-${rank}`} />
          ))}
          <FilterChip label="In library" active={inLibrary} onPress={toggleInLibrary} testID="feed-filter-library" />
        </ScrollView>
      </View>

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
