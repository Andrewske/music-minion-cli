/**
 * Expandable bucket card — shows name, emoji, track count.
 * Tap to expand/collapse track list.
 * Swipe actions on tracks for unassign.
 */
import { useState, useCallback } from 'react';
import { View, Text, Pressable, FlatList, StyleSheet, Alert } from 'react-native';
import * as Haptics from 'expo-haptics';
import type { Bucket } from '@music-minion/shared';
import { TrackRow } from './TrackRow';

interface BucketCardProps {
  bucket: Bucket;
  trackTitles: Map<number, string>;
  onUnassignTrack: (bucketId: string, trackId: number) => void;
  onMoveBucket: (bucketId: string, direction: 'up' | 'down') => void;
  onShuffleBucket: (bucketId: string) => void;
  onDeleteBucket: (bucketId: string) => void;
  isFirst: boolean;
  isLast: boolean;
}

export function BucketCard({
  bucket,
  trackTitles,
  onUnassignTrack,
  onMoveBucket,
  onShuffleBucket,
  onDeleteBucket,
  isFirst,
  isLast,
}: BucketCardProps) {
  const [expanded, setExpanded] = useState(false);

  const handleToggle = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setExpanded((prev) => !prev);
  }, []);

  const handleDelete = useCallback(() => {
    Alert.alert(
      'Delete Bucket',
      `Delete "${bucket.name}"? Tracks will become unassigned.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => onDeleteBucket(bucket.id),
        },
      ]
    );
  }, [bucket.id, bucket.name, onDeleteBucket]);

  const handleShuffle = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    onShuffleBucket(bucket.id);
  }, [bucket.id, onShuffleBucket]);

  return (
    <View style={styles.card}>
      {/* Header */}
      <Pressable style={styles.header} onPress={handleToggle}>
        <View style={styles.headerLeft}>
          <Text style={styles.emoji}>
            {bucket.emoji_id ?? '📁'}
          </Text>
          <View style={styles.headerInfo}>
            <Text style={styles.name} numberOfLines={1}>
              {bucket.name}
            </Text>
            {bucket.linked_playlist_name && (
              <Text style={styles.linkedPlaylist} numberOfLines={1}>
                → {bucket.linked_playlist_name}
              </Text>
            )}
          </View>
        </View>
        <View style={styles.headerRight}>
          <Text style={styles.trackCount}>
            {bucket.track_ids.length}
          </Text>
          <Text style={styles.chevron}>
            {expanded ? '▼' : '▶'}
          </Text>
        </View>
      </Pressable>

      {/* Expanded content */}
      {expanded && (
        <View style={styles.expandedContent}>
          {/* Actions row */}
          <View style={styles.actions}>
            <Pressable
              style={[styles.actionBtn, isFirst && styles.actionDisabled]}
              onPress={() => onMoveBucket(bucket.id, 'up')}
              disabled={isFirst}
            >
              <Text style={styles.actionText}>↑ Up</Text>
            </Pressable>
            <Pressable
              style={[styles.actionBtn, isLast && styles.actionDisabled]}
              onPress={() => onMoveBucket(bucket.id, 'down')}
              disabled={isLast}
            >
              <Text style={styles.actionText}>↓ Down</Text>
            </Pressable>
            <Pressable style={styles.actionBtn} onPress={handleShuffle}>
              <Text style={styles.actionText}>🔀 Shuffle</Text>
            </Pressable>
            <Pressable style={[styles.actionBtn, styles.deleteBtn]} onPress={handleDelete}>
              <Text style={[styles.actionText, styles.deleteText]}>🗑</Text>
            </Pressable>
          </View>

          {/* Track list */}
          {bucket.track_ids.length === 0 ? (
            <Text style={styles.emptyText}>No tracks assigned</Text>
          ) : (
            <FlatList
              data={bucket.track_ids}
              keyExtractor={(id) => id.toString()}
              scrollEnabled={false}
              renderItem={({ item: trackId }) => (
                <TrackRow
                  trackId={trackId}
                  title={trackTitles.get(trackId) ?? `Track #${trackId}`}
                  onUnassign={() => onUnassignTrack(bucket.id, trackId)}
                />
              )}
            />
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#1E1E1E',
    borderRadius: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#333',
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    gap: 12,
  },
  emoji: {
    fontSize: 24,
  },
  headerInfo: {
    flex: 1,
  },
  name: {
    color: '#E0E0E0',
    fontSize: 16,
    fontWeight: '600',
  },
  linkedPlaylist: {
    color: '#7C4DFF',
    fontSize: 12,
    marginTop: 2,
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  trackCount: {
    color: '#9E9E9E',
    fontSize: 14,
    fontFamily: 'monospace',
    backgroundColor: '#2A2A2A',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 8,
    overflow: 'hidden',
  },
  chevron: {
    color: '#666',
    fontSize: 12,
  },
  expandedContent: {
    borderTopWidth: 1,
    borderTopColor: '#333',
  },
  actions: {
    flexDirection: 'row',
    paddingHorizontal: 12,
    paddingVertical: 8,
    gap: 8,
  },
  actionBtn: {
    backgroundColor: '#2A2A2A',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  actionDisabled: {
    opacity: 0.3,
  },
  actionText: {
    color: '#9E9E9E',
    fontSize: 12,
  },
  deleteBtn: {
    marginLeft: 'auto',
    backgroundColor: '#3E1E1E',
  },
  deleteText: {
    color: '#CF6679',
  },
  emptyText: {
    color: '#666',
    fontSize: 13,
    textAlign: 'center',
    paddingVertical: 16,
  },
});
