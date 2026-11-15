/**
 * Bucket session view — manage buckets and assign tracks.
 *
 * Tapping an unassigned track opens a bucket picker; nothing is assigned until
 * a bucket is chosen. Bucket tracks swipe left to remove. Every add or remove
 * shows an Undo snackbar that runs the opposite regular mutation (assign or
 * unassign), so linked playlists stay in sync.
 *
 * The header's Sessions button opens the session switcher (new / switch /
 * rename / delete). A switch loads the other session in place and updates the
 * route param and organizer store, so the screen never remounts.
 */
import { useState, useCallback, useMemo, useRef } from 'react';
import { View, Text, Pressable, TextInput, ActivityIndicator, FlatList } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import * as Haptics from 'expo-haptics';
import { Plus } from 'lucide-react-native';
import Toast from 'react-native-toast-message';
import { getSession, getPlaylistsByLibrary, lookupTracks } from '@music-minion/shared';
import type { Bucket, Playlist } from '@music-minion/shared';
import { usePlaylistOrganizer } from '../../../hooks/usePlaylistOrganizer';
import { BucketCard } from '../../../components/organizer/BucketCard';
import { BucketPickerSheet } from '../../../components/organizer/BucketPickerSheet';
import { SessionHeader } from '../../../components/organizer/SessionHeader';
import { ScreenHeader } from '../../../components/ScreenHeader';
import { SessionFooter } from '../../../components/organizer/SessionFooter';
import { SessionSwitcherSheet } from '../../../components/organizer/SessionSwitcherSheet';
import { useSessionSwitcher } from '../../../hooks/useSessionSwitcher';
import { UndoSnackbar } from '../../../components/organizer/UndoSnackbar';
import { useOrganizerUndo } from '../../../hooks/useOrganizerUndo';
import {
  buildTrackLabels,
  sessionCounts,
  sessionTrackIds,
  trackLabel,
} from '../../../features/organizer/organizerState';
import { undoForBuckets } from '../../../features/organizer/undoState';

const PICKER_HREF = '/organizer';

/** Close the sessions sheet before the action, so its toast lands on the screen. */
function closeThen(setOpen: (open: boolean) => void, action: () => Promise<void>): void {
  setOpen(false);
  void action();
}

/** Leave the session for the picker without stacking screens. */
function backToPicker(): void {
  router.dismissTo(PICKER_HREF);
}

interface PlaylistInfo {
  name: string;
  /** Discovery playlists: finishing a session likes/dismisses tracks on SoundCloud. */
  isDiscovery: boolean;
}

/** Name + discovery flag. The picker already cached the list, so this rarely fetches. */
function usePlaylistInfo(playlistId: number, paramName: string | undefined): PlaylistInfo {
  const { data: playlists } = useQuery({
    queryKey: ['playlists', 'local'],
    queryFn: () => getPlaylistsByLibrary('local'),
    enabled: !!playlistId,
  });
  const playlist = playlists?.find((p: Playlist) => p.id === playlistId);
  return { name: paramName ?? playlist?.name ?? 'Playlist', isDiscovery: Boolean(playlist?.discovery_source) };
}

export default function SessionScreen(): React.JSX.Element {
  const params = useLocalSearchParams<{ sessionId: string; playlistId?: string; playlistName?: string }>();
  const { sessionId } = params;
  const paramPlaylistId = params.playlistId ? Number(params.playlistId) : 0;
  const [newBucketName, setNewBucketName] = useState('');
  const [pickingTrackId, setPickingTrackId] = useState<number | null>(null);
  const [sessionsOpen, setSessionsOpen] = useState(false);

  // playlistId normally arrives as a param; fall back to fetching the session.
  const { data: sessionData, isLoading: sessionLoading } = useQuery({
    queryKey: ['organizer', 'session-raw', sessionId],
    queryFn: () => getSession(sessionId),
    enabled: !!sessionId && !paramPlaylistId,
  });
  const playlistId = paramPlaylistId || (sessionData?.playlist_id ?? 0);
  const { name: playlistName, isDiscovery } = usePlaylistInfo(playlistId, params.playlistName);
  const organizer = usePlaylistOrganizer({ playlistId, enabled: !!playlistId });
  const undo = useOrganizerUndo(organizer);
  const sessions = useSessionSwitcher({
    playlistId,
    playlistName,
    loaded: organizer.session,
    routeSessionId: sessionId,
    isDiscovery,
  });

  // Resolve names for every track in the session (unassigned + bucket tracks).
  // The id union doesn't change on assign/unassign, so this rarely refetches.
  const allTrackIds = useMemo(() => sessionTrackIds(organizer.session), [organizer.session]);
  const { data: trackNames, isSuccess: namesLoaded } = useQuery({
    queryKey: ['track-names', allTrackIds],
    queryFn: () => lookupTracks(allTrackIds),
    enabled: allTrackIds.length > 0,
    placeholderData: keepPreviousData,
    staleTime: 10 * 60 * 1000,
  });
  const labels = useMemo(() => buildTrackLabels(trackNames), [trackNames]);
  const getTrackLabel = useCallback(
    (trackId: number): string => trackLabel(labels, trackId, namesLoaded),
    [labels, namesLoaded]
  );
  const counts = sessionCounts(organizer.session);

  const handleCreateBucket = useCallback(async (): Promise<void> => {
    const name = newBucketName.trim();
    if (!name) return;
    try {
      await organizer.createBucket(name);
      setNewBucketName('');
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    } catch {
      Toast.show({ type: 'error', text1: 'Failed to create bucket' });
    }
  }, [newBucketName, organizer]);

  const handleApply = useCallback(async (): Promise<void> => {
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
      await organizer.applyOrder();
      Toast.show({ type: 'success', text1: 'Order applied!' });
    } catch {
      Toast.show({ type: 'error', text1: 'Failed to apply' });
    }
  }, [organizer]);

  const handleTrackPress = useCallback(
    (trackId: number): void => {
      if (organizer.buckets.length === 0) {
        Toast.show({ type: 'info', text1: 'Create a bucket first' });
        return;
      }
      setPickingTrackId(trackId);
    },
    [organizer.buckets.length]
  );

  // Synchronous in-flight guard: mutation.isPending is render-derived, so two
  // taps in the same tick would both read it as false and double-fire.
  const assigningRef = useRef(false);

  const { offer: offerUndo } = undo;

  const handleRemoveTrack = useCallback(
    async (bucket: Bucket, trackId: number): Promise<void> => {
      try {
        await organizer.unassignTrack(bucket.id, trackId);
        offerUndo({ kind: 'removed', bucketId: bucket.id, bucketName: bucket.name, trackId });
      } catch {
        Toast.show({ type: 'error', text1: 'Failed to remove', text2: 'The track is still in the bucket' });
      }
    },
    [organizer, offerUndo]
  );

  const handlePickBucket = useCallback(
    async (bucket: Bucket): Promise<void> => {
      const trackId = pickingTrackId;
      setPickingTrackId(null);
      if (trackId === null || assigningRef.current) return;
      assigningRef.current = true;
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      try {
        await organizer.assignTrack(bucket.id, trackId);
        offerUndo({ kind: 'added', bucketId: bucket.id, bucketName: bucket.name, trackId });
      } catch {
        Toast.show({ type: 'error', text1: 'Failed to assign' });
      } finally {
        assigningRef.current = false;
      }
    },
    [organizer, pickingTrackId, offerUndo]
  );

  if (sessionLoading || organizer.isLoading) {
    return (
      <View className="flex-1 bg-background">
        <ScreenHeader title={playlistName} onBack={backToPicker} backLabel="Back to playlists" backTestID="organizer-back-btn" />
        <View className="flex-1 justify-center items-center">
          <ActivityIndicator size="large" color="#7C4DFF" />
          <Text className="text-text-secondary mt-4">Loading session...</Text>
        </View>
      </View>
    );
  }

  const listHeader = (
    <View>
      <View className="px-4 flex-row gap-2 mb-4 mt-2">
        <TextInput
          testID="bucket-name-input"
          className="flex-1 bg-surface text-text-primary rounded-lg px-4 py-2 border border-neutral-700"
          placeholder="New bucket name..."
          placeholderTextColor="#666"
          value={newBucketName}
          onChangeText={setNewBucketName}
          onSubmitEditing={handleCreateBucket}
          returnKeyType="done"
        />
        <Pressable
          testID="create-bucket-btn"
          accessibilityRole="button"
          accessibilityLabel="Add bucket"
          className="bg-primary rounded-lg px-4 flex-row items-center gap-1"
          onPress={handleCreateBucket}
        >
          <Plus size={18} color="#FFFFFF" />
          <Text className="text-white font-semibold">Add</Text>
        </Pressable>
      </View>

      <View className="px-4">
        {organizer.buckets.map((bucket, index) => (
          <BucketCard
            key={bucket.id}
            bucket={bucket}
            getTrackLabel={getTrackLabel}
            onRemoveTrack={handleRemoveTrack}
            onMoveBucket={organizer.moveBucket}
            onShuffleBucket={organizer.shuffleBucket}
            onDeleteBucket={organizer.deleteBucket}
            isFirst={index === 0}
            isLast={index === organizer.buckets.length - 1}
          />
        ))}
        {organizer.buckets.length === 0 && (
          <Text className="text-text-secondary text-center py-8">No buckets yet. Add one above to start sorting.</Text>
        )}
      </View>

      {counts.unassigned > 0 && (
        <View className="px-4 mt-6 mb-2">
          <Text className="text-text-primary text-lg font-bold">Unassigned ({counts.unassigned})</Text>
          <Text className="text-text-secondary text-xs mt-1">Tap a track to choose its bucket</Text>
        </View>
      )}
    </View>
  );

  return (
    <View className="flex-1 bg-background">
      <SessionHeader
        playlistName={playlistName}
        session={organizer.session}
        counts={counts}
        onBack={backToPicker}
        onOpenSessions={organizer.session ? () => setSessionsOpen(true) : undefined}
        sessionsDisabled={sessions.isChanging}
      />
      <View className="flex-1">
        <FlatList
          data={organizer.unassignedTrackIds}
          keyExtractor={(id) => id.toString()}
          ListHeaderComponent={listHeader}
          contentContainerStyle={{ paddingBottom: 80 }}
          renderItem={({ item: trackId, index }) => (
            <Pressable
              testID={index === 0 ? 'track-row' : undefined}
              className="bg-surface rounded-lg px-4 py-3 mb-1 mx-4 active:opacity-70"
              onPress={() => handleTrackPress(trackId)}
            >
              <Text className="text-text-primary text-sm" numberOfLines={1}>
                {getTrackLabel(trackId)}
              </Text>
            </Pressable>
          )}
        />
        <UndoSnackbar action={undoForBuckets(undo.pending, organizer.buckets)} onUndo={undo.undo} />
      </View>
      <SessionFooter
        onApply={handleApply}
        onFinish={sessions.confirmFinish}
        isApplying={organizer.isApplying}
        isFinishing={sessions.isChanging}
      />
      <BucketPickerSheet
        visible={pickingTrackId !== null}
        trackLabel={pickingTrackId === null ? '' : getTrackLabel(pickingTrackId)}
        buckets={organizer.buckets}
        onPick={handlePickBucket}
        onClose={() => setPickingTrackId(null)}
      />
      {organizer.session ? (
        <SessionSwitcherSheet
          visible={sessionsOpen}
          playlistId={playlistId}
          session={organizer.session}
          isBusy={sessions.isChanging}
          onClose={() => setSessionsOpen(false)}
          onNew={() => closeThen(setSessionsOpen, sessions.newSession)}
          onSwitch={(id) => closeThen(setSessionsOpen, () => sessions.switchSession(id))}
          onRename={sessions.renameSession}
          onDelete={(id) => closeThen(setSessionsOpen, () => sessions.deleteSession(id))}
        />
      ) : null}
    </View>
  );
}
