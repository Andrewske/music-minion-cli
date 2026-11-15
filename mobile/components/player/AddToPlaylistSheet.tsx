/**
 * "Add to playlist" sheet for the full player: the shared PlaylistPicker over
 * every manual playlist the track can join (POST /playlists/{id}/tracks/{id}).
 *
 *   ───
 *   Add to playlist
 *   Track title
 *   [search …] [Recent | A–Z | Size]
 *   rows: name / "12 tracks · soundcloud" or "Already added"
 */
import { useMemo } from 'react';
import type { ReactElement } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { UseMutationResult } from '@tanstack/react-query';
import Toast from 'react-native-toast-message';
import { addTrackToPlaylist, getAllPlaylists, getTrackPlaylists } from '@music-minion/shared';
import type { Track } from '@music-minion/shared';
import { PlaylistPicker } from '../PlaylistPicker';
import type { PickerPlaylist } from '../../features/playlists/playlistPicker';
import { addablePlaylists, playlistTargetSubtitle } from '../../features/player/playlistTargets';

interface AddToPlaylistSheetProps {
  track: Track;
  visible: boolean;
  onClose: () => void;
}

export function AddToPlaylistSheet({ track, visible, onClose }: AddToPlaylistSheetProps): ReactElement {
  const { bottom } = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <Pressable testID="add-to-playlist-scrim" style={styles.scrim} onPress={onClose} accessibilityLabel="Close add to playlist" />
      <View testID="add-to-playlist-sheet" style={[styles.sheet, { paddingBottom: bottom }]}>
        <View style={styles.handle} />
        <Text style={styles.title}>Add to playlist</Text>
        <Text style={styles.subtitle} numberOfLines={1}>{track.title}</Text>
        {visible ? <AddToPlaylistBody track={track} onDone={onClose} /> : null}
      </View>
    </Modal>
  );
}

/** Mounted only while open, so the playlist queries run on demand. */
function AddToPlaylistBody({ track, onDone }: { track: Track; onDone: () => void }): ReactElement {
  const playlists = useQuery({ queryKey: ['playlists', 'all'], queryFn: getAllPlaylists, staleTime: 60_000 });
  const containing = useQuery({ queryKey: ['track-playlists', track.id], queryFn: () => getTrackPlaylists(track.id) });
  const added = useMemo(() => new Set((containing.data ?? []).map((p) => p.id)), [containing.data]);
  const add = useAddMutation(track, onDone);
  const onSelect = (playlist: PickerPlaylist): void => {
    if (added.has(playlist.id)) {
      Toast.show({ type: 'info', text1: `Already in ${playlist.name}` });
      return;
    }
    add.mutate(playlist);
  };
  return (
    <PlaylistPicker
      playlists={addablePlaylists(playlists.data ?? [], track)}
      isLoading={playlists.isLoading}
      error={playlists.error}
      searchPlaceholder="Search playlists"
      subtitle={(p) => playlistTargetSubtitle(p, added)}
      onSelect={onSelect}
      busyId={add.isPending ? (add.variables?.id ?? null) : null}
      emptyText="No playlists this track can join."
      optionTestID="add-to-playlist-option"
    />
  );
}

function useAddMutation(track: Track, onDone: () => void): UseMutationResult<void, Error, PickerPlaylist> {
  const queryClient = useQueryClient();
  return useMutation<void, Error, PickerPlaylist>({
    mutationFn: (playlist) => addTrackToPlaylist(playlist.id, track.id),
    onSuccess: (_data, playlist) => {
      Toast.show({ type: 'success', text1: `Added to ${playlist.name}`, text2: track.title });
      void queryClient.invalidateQueries({ queryKey: ['track-playlists', track.id] });
      void queryClient.invalidateQueries({ queryKey: ['playlists'] });
      onDone();
    },
    onError: (err) => {
      Toast.show({ type: 'error', text1: "Couldn't add track", text2: err.message });
    },
  });
}

const styles = StyleSheet.create({
  scrim: { flex: 1, backgroundColor: '#00000099' },
  sheet: {
    height: '82%',
    backgroundColor: '#161616',
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    paddingTop: 8,
  },
  handle: { alignSelf: 'center', width: 36, height: 4, borderRadius: 2, backgroundColor: '#3A3A3A', marginBottom: 12 },
  title: { color: '#E0E0E0', fontSize: 18, fontWeight: '600', paddingHorizontal: 20 },
  subtitle: { color: '#9E9E9E', fontSize: 13, paddingHorizontal: 20, marginTop: 2, marginBottom: 12 },
});
