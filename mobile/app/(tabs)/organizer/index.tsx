/**
 * Playlist Organizer — playlist picker.
 * Select a playlist to start/resume a bucket session.
 */
import { View, Text, Pressable, FlatList, ActivityIndicator } from 'react-native';
import { router } from 'expo-router';
import { useQuery, useMutation } from '@tanstack/react-query';
import { getPlaylistsByLibrary, createOrResumeSession } from '@music-minion/shared';
import type { Playlist } from '@music-minion/shared';
import Toast from 'react-native-toast-message';

export default function OrganizerPickerScreen() {
  const { data: playlists, isLoading, error } = useQuery({
    queryKey: ['playlists', 'local'],
    queryFn: () => getPlaylistsByLibrary('local'),
  });

  const startSession = useMutation({
    mutationFn: (playlistId: number) => createOrResumeSession(playlistId),
    onSuccess: (session, playlistId) => {
      router.push(`/(tabs)/organizer/${session.id}?playlistId=${playlistId}`);
    },
    onError: (err) => {
      Toast.show({
        type: 'error',
        text1: 'Failed to start session',
        text2: err instanceof Error ? err.message : 'Try again',
      });
    },
  });

  if (isLoading) {
    return (
      <View className="flex-1 bg-background justify-center items-center">
        <ActivityIndicator size="large" color="#7C4DFF" />
      </View>
    );
  }

  if (error) {
    return (
      <View className="flex-1 bg-background justify-center items-center px-6">
        <Text className="text-error text-lg mb-2">Can't reach server</Text>
        <Text className="text-text-secondary text-center">
          Is Tailscale running?
        </Text>
      </View>
    );
  }

  return (
    <View className="flex-1 bg-background pt-12">
      <View className="px-4 mb-6">
        <Text className="text-text-primary text-2xl font-bold mb-1">
          Organize
        </Text>
        <Text className="text-text-secondary text-base">
          Pick a playlist to organize into buckets
        </Text>
      </View>

      <FlatList
        data={playlists?.filter((p: Playlist) => p.track_count > 0) ?? []}
        keyExtractor={(item) => item.id.toString()}
        contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 32 }}
        renderItem={({ item }) => (
          <Pressable
            className="bg-surface rounded-lg px-4 py-4 mb-2 flex-row justify-between items-center active:opacity-70"
            onPress={() => startSession.mutate(item.id)}
            disabled={startSession.isPending}
          >
            <View className="flex-1 mr-4">
              <Text className="text-text-primary text-base font-medium">
                {item.name}
              </Text>
              <Text className="text-text-secondary text-xs mt-1">
                {item.type === 'smart' ? 'Smart' : 'Manual'} · {item.track_count} tracks
              </Text>
            </View>
            {startSession.isPending && startSession.variables === item.id && (
              <ActivityIndicator size="small" color="#7C4DFF" />
            )}
          </Pressable>
        )}
        ListEmptyComponent={
          <Text className="text-text-secondary text-center mt-8">
            No playlists yet. Create one in the web app.
          </Text>
        }
      />
    </View>
  );
}
