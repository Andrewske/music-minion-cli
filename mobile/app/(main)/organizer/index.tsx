/**
 * Playlist Organizer — playlist picker.
 * Select a playlist to start/resume a bucket session (shared PlaylistPicker).
 * The last opened session gets a "Resume" shortcut above the list.
 */
import type { ReactNode } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { ChevronRight } from 'lucide-react-native';
import { ScreenHeader } from '../../../components/ScreenHeader';
import { PlaylistPicker } from '../../../components/PlaylistPicker';
import { router } from 'expo-router';
import { useQuery, useMutation } from '@tanstack/react-query';
import { getPlaylistsByLibrary, createOrResumeSession } from '@music-minion/shared';
import type { Playlist } from '@music-minion/shared';
import Toast from 'react-native-toast-message';
import { useOrganizerStore } from '../../../stores/organizerStore';
import type { ActiveOrganizerSession } from '../../../stores/organizerStore';
import { organizeSubtitle, selectOrganizablePlaylists } from '../../../features/organizer/organizerState';

/** Open a session. The [sessionId] screen is single-instance (see _layout), so this never stacks. */
function openSession(active: ActiveOrganizerSession): void {
  router.push({
    pathname: '/organizer/[sessionId]',
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

  return (
    <OrganizeFrame>
      <PlaylistPicker
        playlists={selectOrganizablePlaylists(playlists)}
        isLoading={isLoading}
        error={error}
        searchPlaceholder="Find a playlist to organize"
        subtitle={organizeSubtitle}
        onSelect={(playlist) => startSession.mutate(playlist)}
        busyId={startSession.isPending ? (startSession.variables?.id ?? null) : null}
        emptyText="No playlists yet. Create one in the web app."
        optionTestID="organizer-playlist-option"
        header={activeSession ? <ResumeCard session={activeSession} /> : null}
      />
    </OrganizeFrame>
  );
}

/** Shortcut back into the last opened session. */
function ResumeCard({ session }: { session: ActiveOrganizerSession }): React.JSX.Element {
  return (
    <Pressable
      testID="organizer-resume-btn"
      accessibilityRole="button"
      accessibilityLabel={`Resume ${session.playlistName}`}
      android_ripple={{ color: '#FFFFFF26' }}
      style={styles.resume}
      onPress={() => openSession(session)}
    >
      <View style={styles.resumeText}>
        <Text style={styles.resumeLabel}>Resume</Text>
        <Text style={styles.resumeName} numberOfLines={1}>{session.playlistName}</Text>
      </View>
      <ChevronRight size={22} color="#FFFFFF" />
    </Pressable>
  );
}

function OrganizeFrame({ children }: { children: ReactNode }): React.JSX.Element {
  return (
    <View className="flex-1 bg-background">
      <ScreenHeader title="Organize" />
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  resume: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 64,
    marginHorizontal: 16,
    marginBottom: 10,
    paddingHorizontal: 16,
    borderRadius: 12,
    backgroundColor: '#7C4DFF',
    overflow: 'hidden',
  },
  resumeText: { flex: 1, marginRight: 12 },
  resumeLabel: { color: '#FFFFFFCC', fontSize: 12, fontWeight: '500' },
  resumeName: { color: '#FFFFFF', fontSize: 16, fontWeight: '700', marginTop: 1 },
});
