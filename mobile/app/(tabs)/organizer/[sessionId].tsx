/**
 * Bucket session view — manage buckets and assign tracks.
 */
import { useState, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  Pressable,
  FlatList,
  TextInput,
  Alert,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import * as Haptics from 'expo-haptics';
import Toast from 'react-native-toast-message';
import { getSession, getPlaylistTracks } from '@music-minion/shared';
import type { BucketSession } from '@music-minion/shared';
import { usePlaylistOrganizer } from '../../../hooks/usePlaylistOrganizer';
import { BucketCard } from '../../../components/organizer/BucketCard';

export default function SessionScreen() {
  const { sessionId } = useLocalSearchParams<{ sessionId: string }>();
  const [newBucketName, setNewBucketName] = useState('');

  // Fetch session to get playlistId
  const { data: sessionData, isLoading: sessionLoading } = useQuery({
    queryKey: ['organizer', 'session-raw', sessionId],
    queryFn: () => getSession(sessionId),
    enabled: !!sessionId,
  });

  const playlistId = sessionData?.playlist_id ?? 0;

  const organizer = usePlaylistOrganizer({
    playlistId,
    enabled: !!playlistId,
  });

  // Fetch track titles for display
  const { data: trackData } = useQuery({
    queryKey: ['playlist-tracks', playlistId],
    queryFn: () => getPlaylistTracks(playlistId),
    enabled: !!playlistId,
  });

  const trackTitles = useMemo(() => {
    const map = new Map<number, string>();
    trackData?.tracks?.forEach((t) => {
      map.set(t.id, `${t.artist ?? 'Unknown'} — ${t.title}`);
    });
    return map;
  }, [trackData]);

  const handleCreateBucket = useCallback(async () => {
    const name = newBucketName.trim();
    if (!name) return;
    try {
      await organizer.createBucket(name);
      setNewBucketName('');
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    } catch (err) {
      Toast.show({ type: 'error', text1: 'Failed to create bucket' });
    }
  }, [newBucketName, organizer]);

  const handleApply = useCallback(async () => {
    try {
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
      await organizer.applyOrder();
      Toast.show({ type: 'success', text1: 'Order applied!' });
    } catch {
      Toast.show({ type: 'error', text1: 'Failed to apply' });
    }
  }, [organizer]);

  const handleDiscard = useCallback(() => {
    Alert.alert(
      'Discard Session',
      'Discard all bucket assignments? This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Discard',
          style: 'destructive',
          onPress: async () => {
            try {
              await organizer.discardSession();
              router.back();
            } catch {
              Toast.show({ type: 'error', text1: 'Failed to discard' });
            }
          },
        },
      ]
    );
  }, [organizer]);

  const handleFinalize = useCallback(async () => {
    try {
      await organizer.finalizeSession();
      Toast.show({ type: 'success', text1: 'Session finalized' });
      router.back();
    } catch {
      Toast.show({ type: 'error', text1: 'Failed to finalize' });
    }
  }, [organizer]);

  // Assign track to first available bucket on tap
  const handleAssignTrack = useCallback(async (trackId: number) => {
    if (organizer.buckets.length === 0) {
      Toast.show({ type: 'info', text1: 'Create a bucket first' });
      return;
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    try {
      await organizer.assignTrack(organizer.buckets[0].id, trackId);
    } catch {
      Toast.show({ type: 'error', text1: 'Failed to assign' });
    }
  }, [organizer]);

  if (sessionLoading || organizer.isLoading) {
    return (
      <View className="flex-1 bg-background justify-center items-center">
        <ActivityIndicator size="large" color="#7C4DFF" />
        <Text className="text-text-secondary mt-4">Loading session...</Text>
      </View>
    );
  }

  return (
    <ScrollView className="flex-1 bg-background" contentContainerStyle={{ paddingBottom: 120 }}>
      {/* Header */}
      <View className="px-4 pt-12 pb-4">
        <View className="flex-row items-center justify-between mb-2">
          <Pressable onPress={() => router.back()}>
            <Text className="text-primary text-base">← Back</Text>
          </Pressable>
          <Text className="text-text-secondary text-sm">
            {organizer.buckets.length} buckets · {organizer.unassignedTrackIds.length} unassigned
          </Text>
        </View>
      </View>

      {/* Create bucket input */}
      <View className="px-4 flex-row gap-2 mb-4">
        <TextInput
          className="flex-1 bg-surface text-text-primary rounded-lg px-4 py-2 border border-neutral-700"
          placeholder="New bucket name..."
          placeholderTextColor="#666"
          value={newBucketName}
          onChangeText={setNewBucketName}
          onSubmitEditing={handleCreateBucket}
          returnKeyType="done"
        />
        <Pressable
          className="bg-primary rounded-lg px-4 justify-center"
          onPress={handleCreateBucket}
        >
          <Text className="text-white font-semibold">+ Add</Text>
        </Pressable>
      </View>

      {/* Bucket list */}
      <View className="px-4">
        {organizer.buckets.map((bucket, index) => (
          <BucketCard
            key={bucket.id}
            bucket={bucket}
            trackTitles={trackTitles}
            onUnassignTrack={organizer.unassignTrack}
            onMoveBucket={organizer.moveBucket}
            onShuffleBucket={organizer.shuffleBucket}
            onDeleteBucket={organizer.deleteBucket}
            isFirst={index === 0}
            isLast={index === organizer.buckets.length - 1}
          />
        ))}

        {organizer.buckets.length === 0 && (
          <Text className="text-text-secondary text-center py-8">
            No buckets yet. Tap + Add to create one.
          </Text>
        )}
      </View>

      {/* Unassigned tracks */}
      {organizer.unassignedTrackIds.length > 0 && (
        <View className="px-4 mt-6">
          <Text className="text-text-primary text-lg font-bold mb-2">
            Unassigned ({organizer.unassignedTrackIds.length})
          </Text>
          <Text className="text-text-secondary text-xs mb-3">
            Tap a track to assign it to the first bucket
          </Text>
          {organizer.unassignedTrackIds.slice(0, 50).map((trackId) => (
            <Pressable
              key={trackId}
              className="bg-surface rounded-lg px-4 py-3 mb-1 active:opacity-70"
              onPress={() => handleAssignTrack(trackId)}
            >
              <Text className="text-text-primary text-sm" numberOfLines={1}>
                {trackTitles.get(trackId) ?? `Track #${trackId}`}
              </Text>
            </Pressable>
          ))}
          {organizer.unassignedTrackIds.length > 50 && (
            <Text className="text-text-secondary text-center py-2 text-xs">
              + {organizer.unassignedTrackIds.length - 50} more tracks
            </Text>
          )}
        </View>
      )}

      {/* Session controls */}
      <View className="px-4 mt-8 gap-3">
        <Pressable
          className="bg-primary rounded-lg py-4 items-center"
          onPress={handleApply}
          disabled={organizer.isApplying}
        >
          {organizer.isApplying ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text className="text-white text-base font-bold">Apply Order</Text>
          )}
        </Pressable>

        <View className="flex-row gap-3">
          <Pressable
            className="flex-1 bg-surface rounded-lg py-3 items-center border border-neutral-700"
            onPress={handleFinalize}
            disabled={organizer.isFinalizing}
          >
            <Text className="text-text-primary text-sm font-medium">Finalize</Text>
          </Pressable>

          <Pressable
            className="flex-1 bg-surface rounded-lg py-3 items-center border border-red-900"
            onPress={handleDiscard}
          >
            <Text className="text-error text-sm font-medium">Discard</Text>
          </Pressable>
        </View>
      </View>
    </ScrollView>
  );
}
