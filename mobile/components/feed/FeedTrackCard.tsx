/**
 * Compact feed row: artwork, title/artist/date, -1/0/+1 rating buttons.
 * No waveform on mobile (web-only).
 */
import { View, Text, Image, Pressable } from 'react-native';
import { router } from 'expo-router';
import type { FeedItem, FeedRating } from '@music-minion/shared';

const formatRelativeDate = (dateStr: string): string => {
  const date = new Date(dateStr);
  if (isNaN(date.getTime())) return '-';
  const days = Math.floor((Date.now() - date.getTime()) / 86400000);
  if (days < 1) return '<1d';
  if (days < 7) return `${days}d`;
  if (days < 30) return `${Math.floor(days / 7)}w`;
  return `${Math.floor(days / 30)}mo`;
};

const formatDuration = (ms: number): string => {
  const totalSec = Math.floor(ms / 1000);
  return `${Math.floor(totalSec / 60)}:${String(totalSec % 60).padStart(2, '0')}`;
};

interface FeedTrackCardProps {
  item: FeedItem;
  isPlaying: boolean;
  onPlay: (item: FeedItem) => void;
  onRate: (item: FeedItem, value: FeedRating) => void;
}

export function FeedTrackCard({
  item,
  isPlaying,
  onPlay,
  onRate,
}: FeedTrackCardProps) {
  const playable = item.local_track_id !== null;
  const liked = item.status === 'liked';

  return (
    <View
      className={`flex-row items-center px-3 py-2 mx-3 mb-2 rounded-lg ${
        isPlaying ? 'bg-primary/10 border border-primary/40' : 'bg-surface'
      }`}
      testID={`feed-card-${item.id}`}
    >
      <Pressable
        onPress={() => playable && onPlay(item)}
        disabled={!playable}
        className={`flex-row items-center flex-1 mr-2 ${playable ? '' : 'opacity-40'}`}
        testID={`feed-play-${item.id}`}
      >
        {item.artwork_url ? (
          <Image
            source={{ uri: item.artwork_url }}
            className="w-14 h-14 rounded"
            resizeMode="cover"
          />
        ) : (
          <View className="w-14 h-14 rounded bg-neutral-800 items-center justify-center">
            <Text className="text-text-secondary text-lg">♫</Text>
          </View>
        )}
        <View className="flex-1 ml-3">
          <Text
            className={`text-sm ${isPlaying ? 'text-primary' : 'text-text-primary'}`}
            numberOfLines={1}
          >
            {item.title ?? 'Untitled'}
          </Text>
          <Text className="text-text-secondary text-xs mt-0.5" numberOfLines={1}>
            <Text
              onPress={() => router.push(`/artist/${item.artist.id}`)}
              suppressHighlighting
              className="underline"
              testID={`feed-artist-${item.id}`}
            >
              {item.artist.display_name ?? item.artist.slug}
            </Text>
            {'  ·  '}
            {formatRelativeDate(item.uploaded_at)}
            {'  ·  '}
            {formatDuration(item.duration_ms)}
          </Text>
        </View>
      </Pressable>

      <View className="flex-row items-center">
        <Pressable
          onPress={() => onRate(item, -1)}
          hitSlop={6}
          className="p-2"
          testID={`feed-rate-down-${item.id}`}
        >
          <Text className="text-base text-neutral-500">👎</Text>
        </Pressable>
        <Pressable
          onPress={() => onRate(item, 0)}
          hitSlop={6}
          className="p-2"
          testID={`feed-rate-hide-${item.id}`}
        >
          <Text className="text-base text-neutral-500">🚫</Text>
        </Pressable>
        <Pressable
          onPress={() => !liked && onRate(item, 1)}
          hitSlop={6}
          className="p-2"
          testID={`feed-rate-up-${item.id}`}
        >
          <Text className={`text-base ${liked ? '' : 'opacity-40'}`}>
            {liked ? '💜' : '🤍'}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}
