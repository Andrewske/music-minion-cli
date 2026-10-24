/**
 * Expandable bucket card: name, linked playlist, track count.
 * Tap to expand; the expanded card has move / shuffle / delete actions and
 * the track list, where each row swipes left to remove (see TrackRow).
 */
import { useState, useCallback } from 'react';
import type { ReactElement } from 'react';
import { View, Text, Pressable, StyleSheet, Alert } from 'react-native';
import * as Haptics from 'expo-haptics';
import { ArrowDown, ArrowUp, ChevronDown, ChevronRight, ListMusic, Shuffle, Trash2 } from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';
import type { Bucket } from '@music-minion/shared';
import { TrackRow } from './TrackRow';

const MUTED = '#9E9E9E';
const DANGER = '#CF6679';

interface BucketCardProps {
  bucket: Bucket;
  getTrackLabel: (trackId: number) => string;
  onRemoveTrack: (bucket: Bucket, trackId: number) => void;
  onMoveBucket: (bucketId: string, direction: 'up' | 'down') => void;
  onShuffleBucket: (bucketId: string) => void;
  onDeleteBucket: (bucketId: string) => void;
  isFirst: boolean;
  isLast: boolean;
}

export function BucketCard(props: BucketCardProps): ReactElement {
  const [expanded, setExpanded] = useState(false);

  const handleToggle = useCallback((): void => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setExpanded((prev) => !prev);
  }, []);

  return (
    <View style={styles.card}>
      <BucketHeader bucket={props.bucket} expanded={expanded} onToggle={handleToggle} />
      {expanded && (
        <View style={styles.expandedContent}>
          <BucketActions {...props} />
          <BucketTracks bucket={props.bucket} getTrackLabel={props.getTrackLabel} onRemoveTrack={props.onRemoveTrack} />
        </View>
      )}
    </View>
  );
}

function BucketHeader({ bucket, expanded, onToggle }: { bucket: Bucket; expanded: boolean; onToggle: () => void }): ReactElement {
  const Chevron = expanded ? ChevronDown : ChevronRight;
  return (
    <Pressable
      testID="bucket-card-header"
      accessibilityRole="button"
      accessibilityState={{ expanded }}
      android_ripple={{ color: '#FFFFFF14' }}
      style={styles.header}
      onPress={onToggle}
    >
      <View style={styles.headerInfo}>
        <Text style={styles.name} numberOfLines={1}>{bucket.name}</Text>
        {bucket.linked_playlist_name ? (
          <View style={styles.linkedRow}>
            <ListMusic size={12} color="#B39DFF" />
            <Text style={styles.linkedPlaylist} numberOfLines={1}>{bucket.linked_playlist_name}</Text>
          </View>
        ) : null}
      </View>
      <Text style={styles.trackCount}>{bucket.track_ids.length}</Text>
      <Chevron size={18} color="#666" />
    </Pressable>
  );
}

function BucketActions({ bucket, onMoveBucket, onShuffleBucket, onDeleteBucket, isFirst, isLast }: BucketCardProps): ReactElement {
  const handleShuffle = (): void => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    onShuffleBucket(bucket.id);
  };
  const handleDelete = (): void => {
    Alert.alert('Delete bucket', `Delete "${bucket.name}"? Its tracks go back to Unassigned.`, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => onDeleteBucket(bucket.id) },
    ]);
  };
  return (
    <View style={styles.actions}>
      <ActionButton icon={ArrowUp} label="Up" onPress={() => onMoveBucket(bucket.id, 'up')} disabled={isFirst} />
      <ActionButton icon={ArrowDown} label="Down" onPress={() => onMoveBucket(bucket.id, 'down')} disabled={isLast} />
      <ActionButton icon={Shuffle} label="Shuffle" onPress={handleShuffle} />
      <View style={styles.spacer} />
      <ActionButton icon={Trash2} label="Delete bucket" onPress={handleDelete} danger iconOnly />
    </View>
  );
}

interface ActionButtonProps {
  icon: LucideIcon;
  label: string;
  onPress: () => void;
  disabled?: boolean;
  danger?: boolean;
  /** Show only the icon; `label` still names it for TalkBack. */
  iconOnly?: boolean;
}

function ActionButton({ icon: Icon, label, onPress, disabled, danger, iconOnly }: ActionButtonProps): ReactElement {
  const color = danger ? DANGER : MUTED;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: Boolean(disabled) }}
      android_ripple={{ color: '#FFFFFF1F' }}
      style={[styles.actionBtn, danger && styles.deleteBtn, disabled && styles.actionDisabled]}
      onPress={onPress}
      disabled={disabled}
    >
      <Icon size={16} color={color} />
      {iconOnly ? null : <Text style={[styles.actionText, { color }]}>{label}</Text>}
    </Pressable>
  );
}

type BucketTracksProps = Pick<BucketCardProps, 'bucket' | 'getTrackLabel' | 'onRemoveTrack'>;

function BucketTracks({ bucket, getTrackLabel, onRemoveTrack }: BucketTracksProps): ReactElement {
  if (bucket.track_ids.length === 0) {
    return <Text style={styles.emptyText}>No tracks yet. Tap an unassigned track to add it here.</Text>;
  }
  // Plain map: this card renders inside the session FlatList header,
  // and nesting a VirtualizedList there breaks virtualization.
  return (
    <View>
      <Text style={styles.hint}>Swipe a track left to remove it</Text>
      {bucket.track_ids.map((trackId, index) => (
        <TrackRow
          key={trackId}
          testID={index === 0 ? 'bucket-track-row' : undefined}
          title={getTrackLabel(trackId)}
          onRemove={() => onRemoveTrack(bucket, trackId)}
        />
      ))}
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
    gap: 10,
    minHeight: 56,
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  headerInfo: {
    flex: 1,
  },
  linkedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 2,
  },
  name: {
    color: '#E0E0E0',
    fontSize: 16,
    fontWeight: '600',
  },
  linkedPlaylist: {
    color: '#B39DFF',
    fontSize: 12,
    flexShrink: 1,
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
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    minHeight: 40,
    minWidth: 40,
    justifyContent: 'center',
    backgroundColor: '#2A2A2A',
    paddingHorizontal: 12,
    borderRadius: 8,
    overflow: 'hidden',
  },
  actionDisabled: {
    opacity: 0.3,
  },
  actionText: {
    fontSize: 13,
  },
  spacer: {
    flex: 1,
  },
  deleteBtn: {
    backgroundColor: '#3E1E1E',
  },
  hint: {
    color: '#666',
    fontSize: 12,
    paddingHorizontal: 16,
    paddingBottom: 6,
  },
  emptyText: {
    color: '#666',
    fontSize: 13,
    textAlign: 'center',
    paddingVertical: 16,
    paddingHorizontal: 16,
  },
});
