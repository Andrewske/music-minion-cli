import type { ReactElement } from 'react';
import { Image, Pressable, Text, View } from 'react-native';
import { router } from 'expo-router';
import { CircleAlert, Clock, Music } from 'lucide-react-native';
import {
  getFeedEventAt,
  getFeedItemDecision,
  isFeedItemHearted,
  isFeedSyncFailed,
  isFeedSyncPending,
} from '@music-minion/shared';
import type { FeedDecision, FeedItem, FeedVerdict } from '@music-minion/shared';
import { VerdictButtons } from '../VerdictButtons';
import {
  artistName,
  feedAttributions,
  formatKeepScore,
  isLikelyKeep,
  type AttributionLine,
} from '../../features/feed/feedFormat';

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

const asVerdict = (decision: FeedDecision | null): FeedVerdict | null =>
  decision === 'hide' ? null : decision;

const VERDICT_HINTS: Partial<Record<FeedVerdict, string>> = {
  nope: 'Clear pass; counts against this recommendation',
  not_quite: 'Close, but not a keep',
  keep: 'Like on SoundCloud and add to the monthly playlist',
};

/** "Reposted by FESTIVILLAINZ #150 +5 others": name links to the artist, rank and count stay muted. */
function Attribution({ line }: { line: AttributionLine }): ReactElement {
  const { artist, prefix, rankLabel, othersLabel } = line;
  const name = artistName(artist);
  const linked = artist.id !== null && artist.id !== undefined;
  const spoken = [prefix, name, rankLabel ? `rank ${rankLabel.slice(1)}` : null, othersLabel].filter(Boolean).join(' ');
  return (
    <Text
      onPress={linked ? () => router.push(`/artist/${artist.id}`) : undefined}
      accessibilityRole={linked ? 'link' : 'text'}
      accessibilityLabel={linked ? `${spoken}; open artist` : spoken}
      className="text-xs text-text-secondary"
      numberOfLines={1}
    >
      {prefix}{' '}
      <Text className={`text-text-primary ${linked ? 'underline' : ''}`}>{name}</Text>
      {rankLabel ? <Text className="text-neutral-500">{` ${rankLabel}`}</Text> : null}
      {othersLabel ? <Text>{` ${othersLabel}`}</Text> : null}
    </Text>
  );
}

function SyncState({ item }: { item: FeedItem }): ReactElement | null {
  const state = item.action_state;
  const failed = isFeedSyncFailed(state);
  if (!failed && !isFeedSyncPending(state)) return null;
  const Icon = failed ? CircleAlert : Clock;
  return (
    <View
      className="mt-1 flex-row items-center gap-1"
      accessibilityRole="alert"
      accessibilityLabel={failed ? `SoundCloud sync failed. ${state?.error ?? ''}` : 'SoundCloud sync pending'}
    >
      <Icon size={12} color={failed ? '#F87171' : '#FCD34D'} strokeWidth={2.25} />
      <Text className={`text-xs ${failed ? 'text-red-400' : 'text-amber-300'}`} numberOfLines={1}>
        {failed ? 'SoundCloud sync failed' : 'SoundCloud sync pending'}
      </Text>
    </View>
  );
}

function Artwork({ uri }: { uri: string | null }): ReactElement {
  if (uri) {
    return <Image source={{ uri }} accessibilityIgnoresInvertColors className="h-14 w-14 rounded" resizeMode="cover" />;
  }
  return (
    <View className="h-14 w-14 items-center justify-center rounded bg-neutral-800">
      <Music size={22} color="#9E9E9E" strokeWidth={2} />
    </View>
  );
}

function MetaLine({ item }: { item: FeedItem }): ReactElement {
  const score = item.keep_probability;
  return (
    <Text className="mt-0.5 text-xs text-text-secondary" numberOfLines={1}>
      {formatRelativeDate(getFeedEventAt(item))} · {formatDuration(item.duration_ms)}
      {score !== null ? (
        <Text className={isLikelyKeep(score) ? 'font-semibold text-emerald-300' : ''} testID={`feed-score-${item.soundcloud_id}`}>
          {` · ${formatKeepScore(score)}`}
        </Text>
      ) : null}
    </Text>
  );
}

interface FeedTrackCardProps {
  item: FeedItem;
  isPlaying: boolean;
  isUpdating?: boolean;
  onPlay: (item: FeedItem) => void;
  onDecide: (item: FeedItem, decision: FeedVerdict) => void;
}

function PlayRow({ item, isPlaying, onPlay }: Pick<FeedTrackCardProps, 'item' | 'isPlaying' | 'onPlay'>): ReactElement {
  const playable = item.access !== 'blocked';
  return (
    <Pressable
      onPress={() => playable && onPlay(item)}
      disabled={!playable}
      accessibilityRole="button"
      accessibilityLabel={`Play ${item.title ?? 'track'}`}
      accessibilityState={{ disabled: !playable }}
      className={`flex-row items-center ${playable ? '' : 'opacity-40'}`}
      testID={`feed-play-${item.soundcloud_id}`}
    >
      <Artwork uri={item.artwork_url} />
      <View className="ml-3 flex-1">
        <Text className={`text-sm font-medium ${isPlaying ? 'text-primary' : 'text-text-primary'}`} numberOfLines={1}>{item.title ?? 'Untitled'}</Text>
        <MetaLine item={item} />
      </View>
    </Pressable>
  );
}

export function FeedTrackCard({ item, isPlaying, isUpdating = false, onPlay, onDecide }: FeedTrackCardProps): ReactElement {
  const decision = getFeedItemDecision(item);
  const id = item.soundcloud_id;
  return (
    <View
      className={`mx-3 mb-2 rounded-lg border px-3 pb-3 pt-2 ${isPlaying ? 'border-primary/40 bg-primary/10' : 'border-transparent bg-surface'}`}
      testID={`feed-card-${id}`}
      accessibilityLabel={`${item.title ?? 'Untitled'} feed item`}
    >
      <PlayRow item={item} isPlaying={isPlaying} onPlay={onPlay} />
      <View className="mt-2 gap-0.5">
        {feedAttributions(item).map((line) => <Attribution key={line.prefix} line={line} />)}
      </View>
      <SyncState item={item} />
      <View className="mt-3">
        <VerdictButtons
          selected={asVerdict(decision)}
          keepActive={isFeedItemHearted(item)}
          keepLocked={decision === 'keep'}
          disabled={isUpdating}
          onVerdict={(verdict) => onDecide(item, verdict)}
          testIDs={{ nope: `feed-nope-${id}`, not_quite: `feed-not-quite-${id}`, keep: `feed-keep-${id}` }}
          accessibilityHints={VERDICT_HINTS}
        />
      </View>
    </View>
  );
}
