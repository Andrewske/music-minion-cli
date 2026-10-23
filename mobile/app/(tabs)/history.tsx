/**
 * History — playback history with stats.
 */
import type { ReactElement } from 'react';
import { View, Text, FlatList, ActivityIndicator } from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { getHistory, getStats } from '@music-minion/shared';
import type { HistoryEntry } from '@music-minion/shared';
import { describeListen, formatRelativeTime } from '../../features/history/historyFormat';

export default function HistoryScreen(): ReactElement {
  const { data: history, isLoading } = useQuery({
    queryKey: ['history'],
    queryFn: () => getHistory({ limit: 100 }),
    staleTime: 30_000,
  });

  const { data: stats } = useQuery({
    queryKey: ['history-stats'],
    queryFn: () => getStats(30),
    staleTime: 60_000,
  });

  return (
    <View className="flex-1 bg-background">
      {/* Header + stats */}
      <View className="px-4 pt-4 pb-3">
        <Text className="text-text-primary text-2xl font-bold mb-3">
          History
        </Text>

        {stats && (
          <View className="flex-row gap-4 mb-2">
            <View className="bg-surface rounded-lg px-4 py-3 flex-1 items-center">
              <Text className="text-text-primary text-lg font-bold font-mono">
                {stats.total_plays}
              </Text>
              <Text className="text-text-secondary text-xs">Plays</Text>
            </View>
            <View className="bg-surface rounded-lg px-4 py-3 flex-1 items-center">
              <Text className="text-text-primary text-lg font-bold font-mono">
                {Math.round(stats.total_minutes)}
              </Text>
              <Text className="text-text-secondary text-xs">Minutes</Text>
            </View>
            <View className="bg-surface rounded-lg px-4 py-3 flex-1 items-center">
              <Text className="text-text-primary text-lg font-bold font-mono">
                {stats.unique_tracks}
              </Text>
              <Text className="text-text-secondary text-xs">Unique</Text>
            </View>
          </View>
        )}
      </View>

      {isLoading ? (
        <View className="items-center py-8">
          <ActivityIndicator color="#7C4DFF" />
        </View>
      ) : (
        <FlatList
          data={history}
          keyExtractor={(item) => item.id.toString()}
          initialNumToRender={20}
          maxToRenderPerBatch={10}
          renderItem={({ item, index }: { item: HistoryEntry; index: number }) => (
            <View className="px-4 py-3 border-b border-neutral-800 flex-row items-center">
              <View className="flex-1 mr-3">
                <Text className="text-text-primary text-sm" numberOfLines={1}>
                  {item.track_title}
                </Text>
                <Text className="text-text-secondary text-xs" numberOfLines={1}>
                  {item.track_artist}
                </Text>
              </View>
              <View className="items-end">
                <Text className="text-text-secondary text-xs font-mono">
                  {describeListen(item, index === 0)}
                </Text>
                <Text className="text-neutral-600 text-xs">
                  {formatRelativeTime(item.started_at, Date.now())}
                </Text>
              </View>
            </View>
          )}
          ListEmptyComponent={
            <View className="items-center py-12">
              <Text className="text-text-secondary text-base">
                No history yet. Play some tracks!
              </Text>
            </View>
          }
        />
      )}
    </View>
  );
}
