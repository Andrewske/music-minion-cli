/**
 * Artist page — library tracks for one followed artist.
 * Liked / playlisted tracks pinned on top, then the rest by play count.
 */
import { useCallback } from 'react';
import {
  View,
  Text,
  Image,
  SectionList,
  Pressable,
  ActivityIndicator,
} from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { getArtist, getArtistLibraryTracks } from '@music-minion/shared';
import type { ArtistLibraryTrack, Track } from '@music-minion/shared';
import { usePlayerStore } from '../../stores/playerStore';

const formatDuration = (seconds: number | null): string => {
  if (seconds == null) return '-:--';
  const total = Math.floor(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
};

const formatFollowers = (n: number | null): string => {
  if (n == null) return '';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}m`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
};

const toTrack = (t: ArtistLibraryTrack): Track => ({
  id: t.id,
  title: t.title,
  artist: t.artist,
  duration: t.duration ?? undefined,
});

const isSaved = (t: ArtistLibraryTrack): boolean => t.is_liked || t.playlists.length > 0;

export default function ArtistScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const artistId = Number(id);
  const play = usePlayerStore((s) => s.play);
  const currentTrackId = usePlayerStore((s) => s.currentTrack?.id ?? null);

  const detailQuery = useQuery({
    queryKey: ['artists', 'detail', artistId],
    queryFn: () => getArtist(artistId),
    enabled: Number.isFinite(artistId),
  });
  const tracksQuery = useQuery({
    queryKey: ['artists', 'library-tracks', artistId],
    queryFn: () => getArtistLibraryTracks(artistId),
    enabled: Number.isFinite(artistId),
  });

  const tracks = tracksQuery.data ?? [];
  const saved = tracks.filter(isSaved);
  const rest = tracks.filter((t) => !isSaved(t));
  const sections = [
    ...(saved.length > 0 ? [{ title: `Liked & in playlists · ${saved.length}`, data: saved }] : []),
    ...(rest.length > 0 ? [{ title: `Library · ${rest.length}`, data: rest }] : []),
  ];

  const handlePlay = useCallback(
    (track: ArtistLibraryTrack): void => {
      // Sequential from the tapped row through the rest of the sorted list.
      const index = tracks.findIndex((t) => t.id === track.id);
      if (index === -1) return;
      const trackIds = tracks.slice(index).map((t) => t.id);
      play(toTrack(track), { type: 'feed', track_ids: trackIds, shuffle: false });
    },
    [tracks, play]
  );

  const artist = detailQuery.data?.artist;
  const isLoading = detailQuery.isLoading || tracksQuery.isLoading;
  const isError = detailQuery.isError || tracksQuery.isError;

  return (
    <View className="flex-1 bg-background">
      <View className="px-4 pt-12 pb-3">
        <Pressable onPress={() => router.back()} hitSlop={8} testID="artist-back">
          <Text className="text-text-secondary text-sm">← Back</Text>
        </Pressable>
      </View>

      {isLoading ? (
        <View className="items-center py-8">
          <ActivityIndicator color="#7C4DFF" />
        </View>
      ) : isError || !artist ? (
        <View className="items-center py-12">
          <Text className="text-text-secondary text-base">Failed to load artist.</Text>
        </View>
      ) : (
        <SectionList
          sections={sections}
          keyExtractor={(item) => item.id.toString()}
          stickySectionHeadersEnabled={false}
          contentContainerStyle={{ paddingBottom: 96 }}
          ListHeaderComponent={
            <View className="flex-row items-center px-4 pb-4">
              {artist.avatar_url ? (
                <Image
                  source={{ uri: artist.avatar_url }}
                  className="w-16 h-16 rounded-full"
                  resizeMode="cover"
                />
              ) : (
                <View className="w-16 h-16 rounded-full bg-neutral-800 items-center justify-center">
                  <Text className="text-text-secondary text-xl">♫</Text>
                </View>
              )}
              <View className="flex-1 ml-3">
                <Text className="text-text-primary text-xl font-bold" numberOfLines={1}>
                  {artist.display_name}
                </Text>
                <Text className="text-text-secondary text-xs mt-1" numberOfLines={2}>
                  {artist.follower_count != null &&
                    `${formatFollowers(artist.follower_count)} followers  ·  `}
                  {artist.library_track_count} in library  ·  {artist.sc_liked_count} liked
                </Text>
              </View>
            </View>
          }
          renderSectionHeader={({ section }) => (
            <Text className="text-primary text-xs uppercase tracking-widest px-4 pt-2 pb-2">
              {section.title}
            </Text>
          )}
          renderItem={({ item }) => {
            const playing = item.id === currentTrackId;
            return (
              <Pressable
                onPress={() => handlePlay(item)}
                className={`flex-row items-center px-3 py-2 mx-3 mb-2 rounded-lg ${
                  playing ? 'bg-primary/10 border border-primary/40' : 'bg-surface'
                }`}
                testID={`artist-track-${item.id}`}
              >
                <View className="flex-1 mr-2">
                  <Text
                    className={`text-sm ${playing ? 'text-primary' : 'text-text-primary'}`}
                    numberOfLines={1}
                  >
                    {item.title}
                  </Text>
                  {item.playlists.length > 0 && (
                    <Text className="text-text-secondary text-xs mt-0.5" numberOfLines={1}>
                      ♪ {item.playlists.map((p) => p.name).join(' · ')}
                    </Text>
                  )}
                </View>
                {item.is_liked && <Text className="text-base mr-2">💜</Text>}
                {item.play_count > 0 && (
                  <Text className="text-text-secondary text-xs mr-2">{item.play_count}×</Text>
                )}
                <Text className="text-text-secondary text-xs">
                  {formatDuration(item.duration)}
                </Text>
              </Pressable>
            );
          }}
          ListEmptyComponent={
            <View className="items-center py-12 px-6">
              <Text className="text-text-secondary text-base text-center">
                No tracks from this artist in your library yet.
              </Text>
            </View>
          }
        />
      )}
    </View>
  );
}
