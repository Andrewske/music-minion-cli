import { Image, Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';
import {
  getFeedEventAt,
  getFeedItemBestRank,
  getFeedItemDecision,
  getFeedItemUploader,
  isFeedSyncFailed,
  isFeedSyncPending,
} from '@music-minion/shared';
import type { FeedArtist, FeedDecision, FeedItem } from '@music-minion/shared';

const formatRelativeDate = (dateStr: string): string => {
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return '-';
  const days = Math.floor((Date.now() - date.getTime()) / 86_400_000);
  if (days < 1) return '<1d';
  if (days < 7) return `${days}d`;
  if (days < 30) return `${Math.floor(days / 7)}w`;
  return `${Math.floor(days / 30)}mo`;
};

const formatDuration = (ms: number): string => {
  const totalSec = Math.floor(ms / 1000);
  return `${Math.floor(totalSec / 60)}:${String(totalSec % 60).padStart(2, '0')}`;
};

function ArtistButton({ artist, prefix }: { artist: FeedArtist; prefix: string }) {
  const name = artist.display_name ?? artist.slug;
  if (artist.id === null || artist.id === undefined) {
    return <Text className="text-xs text-text-secondary">{prefix} {name}</Text>;
  }
  return (
    <Text
      onPress={() => router.push(`/artist/${artist.id}`)}
      accessibilityRole="link"
      accessibilityLabel={`${prefix} ${name}; open artist`}
      className="text-xs text-text-secondary underline"
      numberOfLines={1}
    >
      {prefix} {name}
    </Text>
  );
}

function SyncState({ item }: { item: FeedItem }) {
  const state = item.action_state;
  const failed = isFeedSyncFailed(state);
  if (!failed && !isFeedSyncPending(state)) return null;
  return (
    <Text
      accessibilityRole="alert"
      accessibilityLabel={failed ? `SoundCloud sync failed. ${state?.error ?? ''}` : 'SoundCloud sync pending'}
      className={`text-xs ${failed ? 'text-red-400' : 'text-amber-300'}`}
      numberOfLines={1}
    >
      {failed ? '⚠ SC sync failed' : '◷ SC sync pending'}
    </Text>
  );
}

interface FeedTrackCardProps {
  item: FeedItem;
  isPlaying: boolean;
  isUpdating?: boolean;
  onPlay: (item: FeedItem) => void;
  onDecide: (item: FeedItem, decision: FeedDecision) => void;
}

function DecisionButton({ label, glyph, active, disabled, onPress, testID }: {
  label: string;
  glyph: string;
  active: boolean;
  disabled: boolean;
  onPress: () => void;
  testID: string;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: active, disabled }}
      hitSlop={6}
      className={`min-h-11 min-w-11 items-center justify-center rounded ${active ? 'bg-primary/15' : ''}`}
      testID={testID}
    >
      <Text className={`text-base ${active ? 'text-primary' : 'text-neutral-400'}`}>{glyph}</Text>
    </Pressable>
  );
}

export function FeedTrackCard({ item, isPlaying, isUpdating = false, onPlay, onDecide }: FeedTrackCardProps) {
  const decision = getFeedItemDecision(item);
  const uploader = getFeedItemUploader(item);
  const firstReposter = item.reposters[0];
  const otherReposters = Math.max(0, item.reposter_count - (firstReposter ? 1 : 0));
  const bestRank = getFeedItemBestRank(item);
  const playable = item.access !== 'blocked';

  return (
    <View
      className={`mx-3 mb-2 rounded-lg border px-3 py-2 ${isPlaying ? 'border-primary/40 bg-primary/10' : 'border-transparent bg-surface'}`}
      testID={`feed-card-${item.soundcloud_id}`}
      accessibilityLabel={`${item.title ?? 'Untitled'} feed item`}
    >
      <View className="flex-row items-center">
        <Pressable
          onPress={() => playable && onPlay(item)}
          disabled={!playable}
          accessibilityRole="button"
          accessibilityLabel={`Play ${item.title ?? 'track'}`}
          accessibilityState={{ disabled: !playable }}
          className={`flex-1 flex-row items-center ${playable ? '' : 'opacity-40'}`}
          testID={`feed-play-${item.soundcloud_id}`}
        >
          {item.artwork_url ? (
            <Image source={{ uri: item.artwork_url }} accessibilityIgnoresInvertColors className="h-14 w-14 rounded" resizeMode="cover" />
          ) : (
            <View className="h-14 w-14 items-center justify-center rounded bg-neutral-800"><Text className="text-lg text-text-secondary">♫</Text></View>
          )}
          <View className="ml-3 flex-1">
            <Text className={`text-sm ${isPlaying ? 'text-primary' : 'text-text-primary'}`} numberOfLines={1}>{item.title ?? 'Untitled'}</Text>
            <View className="mt-0.5 flex-row items-center gap-2">
              <Text className="text-xs text-text-secondary">{formatRelativeDate(getFeedEventAt(item))} · {formatDuration(item.duration_ms)}</Text>
              {bestRank !== null && <Text className="rounded bg-neutral-800 px-1.5 py-0.5 text-xs text-text-secondary">#{bestRank}</Text>}
            </View>
          </View>
        </Pressable>
      </View>

      <View className="mt-2 gap-0.5">
        {item.sources.includes('release') && uploader && <ArtistButton artist={uploader} prefix="Uploaded by" />}
        {item.sources.includes('repost') && firstReposter && (
          <View className="flex-row items-center">
            <ArtistButton artist={firstReposter} prefix="Reposted by" />
            {otherReposters > 0 && <Text className="text-xs text-text-secondary"> +{otherReposters} other reposter{otherReposters === 1 ? '' : 's'}</Text>}
          </View>
        )}
      </View>

      <View className="mt-1 flex-row items-center justify-between">
        <View className="min-w-0 flex-1 pr-2"><SyncState item={item} /></View>
        <View className="flex-row items-center" accessibilityLabel="Feed decisions">
          <DecisionButton label="Nope; hide and count against this recommendation" glyph="👎" active={decision === 'nope'} disabled={isUpdating} onPress={() => onDecide(item, 'nope')} testID={`feed-nope-${item.soundcloud_id}`} />
          <DecisionButton label="Hide without affecting recommendations" glyph="◌" active={decision === 'hide'} disabled={isUpdating} onPress={() => onDecide(item, 'hide')} testID={`feed-hide-${item.soundcloud_id}`} />
          <DecisionButton label="Keep; like on SoundCloud and add to monthly playlist" glyph={decision === 'keep' ? '♥' : '♡'} active={decision === 'keep'} disabled={isUpdating || decision === 'keep'} onPress={() => onDecide(item, 'keep')} testID={`feed-keep-${item.soundcloud_id}`} />
        </View>
      </View>
    </View>
  );
}
