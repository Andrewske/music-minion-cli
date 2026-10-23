/**
 * Playlist Organizer — playlist picker.
 * Select a playlist to start/resume a bucket session. The last opened session
 * gets a "Resume" shortcut at the top.
 */
import { View, Text, Pressable, FlatList, ActivityIndicator } from 'react-native';
import { router } from 'expo-router';
import { useQuery, useMutation } from '@tanstack/react-query';
import { getPlaylistsByLibrary, createOrResumeSession } from '@music-minion/shared';
import type { Playlist } from '@music-minion/shared';
import Toast from 'react-native-toast-message';
import { useOrganizerStore } from '../../../stores/organizerStore';
import type { ActiveOrganizerSession } from '../../../stores/organizerStore';

/** Open a session. The [sessionId] screen is single-instance (see _layout), so this never stacks. */
function openSession(active: ActiveOrganizerSession): void {
  router.push({
    pathname: '/(tabs)/organizer/[sessionId]',
    params: {
      sessionId: active.sessionId,
      playlistId: String(active.playlistId),
      playlistName: active.playlistName,
    },
  });
}

export default function OrganizerPickerScreen(): React.JSX.Element {
  const { data: playlists, isLoading, error } = useQuery({
    queryKey: ['playlists', 'local'],
    queryFn: () => getPlaylistsByLibrary('local'),
  });

  const activeSession = useOrganizerStore((s) => s.activeSession);
  const setActiveSession = useOrganizerStore((s) => s.setActiveSession);

  const startSession = useMutation({
    mutationFn: (playlist: Playlist) => createOrResumeSession(playlist.id),
    onSuccess: (session, playlist) => {
      const active = { sessionId: session.id, playlistId: playlist.id, playlistName: playlist.name };
      setActiveSession(active);
      openSession(active);
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
        <Text className="text-error text-lg mb-2">Can&apos;t reach server</Text>
        <Text className="text-text-secondary text-center">
          Is Tailscale running?
        </Text>
      </View>
    );
  }

  return (
    <View className="flex-1 bg-background pt-4">
      <View className="px-4 mb-6">
        <Text className="text-text-primary text-2xl font-bold mb-1">
          Organize
        </Text>
        <Text className="text-text-secondary text-base">
          Pick a playlist to organize into buckets
        </Text>
      </View>

      {activeSession && (
        <Pressable
          testID="organizer-resume-btn"
          className="mx-4 mb-4 bg-primary rounded-lg px-4 py-4 flex-row items-center active:opacity-80"
          onPress={() => openSession(activeSession)}
        >
          <View className="flex-1 mr-4">
            <Text className="text-white text-xs uppercase opacity-80">Resume</Text>
            <Text className="text-white text-base font-bold" numberOfLines={1}>
              {activeSession.playlistName}
            </Text>
          </View>
          <Text className="text-white text-lg">→</Text>
        </Pressable>
      )}

      <FlatList
        data={playlists?.filter((p: Playlist) => p.track_count > 0) ?? []}
        keyExtractor={(item) => item.id.toString()}
        contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 32 }}
        renderItem={({ item, index }) => (
          <Pressable
            testID={index === 0 ? 'organizer-playlist-option' : undefined}
            className="bg-surface rounded-lg px-4 py-4 mb-2 flex-row justify-between items-center active:opacity-70"
            onPress={() => startSession.mutate(item)}
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
            {startSession.isPending && startSession.variables?.id === item.id && (
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
