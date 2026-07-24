/**
 * SoundCloud Feed — newest uploads from followed artists, newest first.
 * Infinite scroll, sequential no-shuffle playback, -1/0/+1 triage.
 */
import { useCallback, useState } from 'react';
import {
  View,
  Text,
  FlatList,
  Pressable,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query';
import { getFeed, rateFeedItem } from '@music-minion/shared';
import type { FeedItem, FeedPage, FeedRating, Track } from '@music-minion/shared';
import { usePlayerStore } from '../../stores/playerStore';
import { FeedTrackCard } from '../../components/feed/FeedTrackCard';

const PAGE_SIZE = 30;

const toTrack = (item: FeedItem): Track => ({
  id: item.local_track_id as number,
  title: item.title ?? 'Untitled',
  artist: item.artist.display_name ?? item.artist.slug,
  duration: item.duration_ms / 1000,
});

export default function FeedScreen() {
  const queryClient = useQueryClient();
  const play = usePlayerStore((s) => s.play);
  const currentTrackId = usePlayerStore((s) => s.currentTrack?.id ?? null);
  const [top200, setTop200] = useState(false);
  const [inLibrary, setInLibrary] = useState(false);

  const feedQueryKey = ['feed', { top200, inLibrary }] as const;

  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    isError,
    refetch,
    isRefetching,
  } = useInfiniteQuery({
    queryKey: feedQueryKey,
    queryFn: ({ pageParam }) =>
      getFeed({ cursor: pageParam, limit: PAGE_SIZE, top200, inLibrary }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  });

  const items = data?.pages.flatMap((p) => p.items) ?? [];

  const rateMutation = useMutation({
    mutationFn: ({ item, value }: { item: FeedItem; value: FeedRating }) =>
      rateFeedItem(item.id, value),
    onMutate: async ({ item, value }) => {
      await queryClient.cancelQueries({ queryKey: feedQueryKey });
      const previous =
        queryClient.getQueryData<InfiniteData<FeedPage>>(feedQueryKey);
      queryClient.setQueryData<InfiniteData<FeedPage>>(feedQueryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          pages: old.pages.map((page) => ({
            ...page,
            items:
              value === 1
                ? page.items.map((i) =>
                    i.id === item.id ? { ...i, status: 'liked' as const } : i
                  )
                : page.items.filter((i) => i.id !== item.id),
          })),
        };
      });
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(feedQueryKey, context.previous);
      }
    },
  });

  const handlePlay = useCallback(
    (item: FeedItem): void => {
      const index = items.findIndex((i) => i.id === item.id);
      if (index === -1 || item.local_track_id === null) return;
      // Sequential from the tapped row, shuffle forced off.
      const trackIds = items
        .slice(index)
        .filter((i) => i.local_track_id !== null)
        .map((i) => i.local_track_id as number);
      play(toTrack(item), { type: 'feed', track_ids: trackIds, shuffle: false });
    },
    [items, play]
  );

  const FilterChip = ({
    label,
    active,
    onPress,
    testID,
  }: {
    label: string;
    active: boolean;
    onPress: () => void;
    testID: string;
  }) => (
    <Pressable
      onPress={onPress}
      testID={testID}
      className={`px-3 py-1.5 rounded-full border ${
        active ? 'bg-primary/15 border-primary' : 'border-neutral-700'
      }`}
    >
      <Text className={`text-xs ${active ? 'text-primary' : 'text-text-secondary'}`}>
        {label}
      </Text>
    </Pressable>
  );

  return (
    <View className="flex-1 bg-background">
      <View className="px-4 pt-12 pb-3">
        <Text className="text-text-primary text-2xl font-bold mb-3">Feed</Text>
        <View className="flex-row gap-2">
          <FilterChip
            label="Top 200"
            active={top200}
            onPress={() => setTop200((v) => !v)}
            testID="feed-filter-top200"
          />
          <FilterChip
            label="In library"
            active={inLibrary}
            onPress={() => setInLibrary((v) => !v)}
            testID="feed-filter-library"
          />
        </View>
      </View>

      {isLoading ? (
        <View className="items-center py-8">
          <ActivityIndicator color="#7C4DFF" />
        </View>
      ) : isError ? (
        <View className="items-center py-12">
          <Text className="text-text-secondary text-base">Failed to load feed.</Text>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => item.id.toString()}
          initialNumToRender={20}
          maxToRenderPerBatch={10}
          windowSize={10}
          onEndReached={() => {
            if (hasNextPage && !isFetchingNextPage) fetchNextPage();
          }}
          onEndReachedThreshold={0.5}
          refreshControl={
            <RefreshControl
              refreshing={isRefetching}
              onRefresh={refetch}
              tintColor="#7C4DFF"
            />
          }
          renderItem={({ item }: { item: FeedItem }) => (
            <FeedTrackCard
              item={item}
              isPlaying={
                item.local_track_id !== null &&
                item.local_track_id === currentTrackId
              }
              onPlay={handlePlay}
              onRate={(target, value) => rateMutation.mutate({ item: target, value })}
            />
          )}
          ListFooterComponent={
            isFetchingNextPage ? (
              <View className="py-4">
                <ActivityIndicator color="#7C4DFF" />
              </View>
            ) : null
          }
          ListEmptyComponent={
            <View className="items-center py-12 px-6">
              <Text className="text-text-secondary text-base text-center">
                No uploads yet{top200 || inLibrary ? ' for these filters' : ''}.
                Sync the feed from the web app to fetch the latest.
              </Text>
            </View>
          }
        />
      )}
    </View>
  );
}
