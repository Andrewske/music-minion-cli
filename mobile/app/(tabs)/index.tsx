/**
 * Home / Track Browser — search tracks, tap to play.
 * FlatList with performance tuning for large libraries.
 */
import { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  FlatList,
  ActivityIndicator,
  Pressable,
} from 'react-native';
import { useQuery } from '@tanstack/react-query';
import { searchTracks } from '@music-minion/shared';
import type { Track } from '@music-minion/shared';
import { usePlayerStore } from '../../stores/playerStore';
import { TrackCard } from '../../components/tracks/TrackCard';

export default function HomeScreen() {
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { currentTrack, play } = usePlayerStore();

  const handleSearch = useCallback((text: string) => {
    setSearchQuery(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedQuery(text.trim());
    }, 300);
  }, []);

  // Search results
  const { data: searchResults, isLoading: searching } = useQuery({
    queryKey: ['track-search', debouncedQuery],
    queryFn: () => searchTracks(debouncedQuery, 50),
    enabled: debouncedQuery.length >= 2,
    staleTime: 10_000,
  });

  // Queue display when not searching
  const queue = usePlayerStore((s) => s.queue);
  const queueIndex = usePlayerStore((s) => s.queueIndex);

  const isSearching = debouncedQuery.length >= 2;
  const displayTracks: Track[] = isSearching
    ? (searchResults?.map((r) => ({
        id: r.id,
        title: r.title,
        artist: r.artist ?? undefined,
        album: r.album ?? undefined,
      })) ?? [])
    : queue;

  const handlePlayTrack = useCallback((track: Track, index: number) => {
    if (isSearching) {
      play(track, { type: 'search', query: debouncedQuery, track_ids: [track.id] });
    } else {
      play(track, { type: 'track', start_index: index });
    }
  }, [play, isSearching, debouncedQuery]);

  const clearSearch = useCallback(() => {
    setSearchQuery('');
    setDebouncedQuery('');
  }, []);

  return (
    <View className="flex-1 bg-background">
      {/* Search bar */}
      <View className="px-4 pt-12 pb-3">
        <View className="flex-row items-center bg-surface rounded-lg border border-neutral-700">
          <TextInput
            className="flex-1 text-text-primary px-4 py-3 text-base"
            placeholder="Search tracks..."
            placeholderTextColor="#666"
            value={searchQuery}
            onChangeText={handleSearch}
            autoCapitalize="none"
            autoCorrect={false}
            returnKeyType="search"
          />
          {searchQuery.length > 0 && (
            <Pressable className="px-3" onPress={clearSearch}>
              <Text className="text-text-secondary text-lg">✕</Text>
            </Pressable>
          )}
        </View>
      </View>

      {/* Section header */}
      <View className="px-4 py-2 flex-row justify-between items-center">
        <Text className="text-text-secondary text-sm">
          {isSearching
            ? `${displayTracks.length} results`
            : queue.length > 0
              ? `Queue · ${queueIndex + 1} / ${queue.length}`
              : 'No queue'}
        </Text>
        {searching && <ActivityIndicator size="small" color="#7C4DFF" />}
      </View>

      {/* Track list */}
      <FlatList
        data={displayTracks}
        keyExtractor={(item) => item.id.toString()}
        initialNumToRender={20}
        maxToRenderPerBatch={10}
        windowSize={10}
        renderItem={({ item, index }) => (
          <TrackCard
            track={item}
            isPlaying={currentTrack?.id === item.id}
            onPress={() => handlePlayTrack(item, index)}
          />
        )}
        ListEmptyComponent={
          <View className="items-center py-12">
            {isSearching && !searching ? (
              <>
                <Text className="text-text-secondary text-base mb-2">
                  No tracks match your search
                </Text>
                <Pressable onPress={clearSearch}>
                  <Text className="text-primary text-sm">Clear filters</Text>
                </Pressable>
              </>
            ) : !isSearching ? (
              <Text className="text-text-secondary text-base text-center px-8">
                Nothing playing.{'\n'}Search for tracks or start a playlist from Compare.
              </Text>
            ) : null}
          </View>
        }
      />
    </View>
  );
}
