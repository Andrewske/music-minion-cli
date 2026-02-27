import { useState } from 'react';
import type { PlaylistTrackEntry } from '../../types';
import type { Bucket } from '../../api/buckets';
import { BucketComponent } from './Bucket';
import { BucketEditDialog } from './BucketEditDialog';
import { Button } from '../ui/button';
import { useIsMobile } from '../../hooks/useIsMobile';

interface BucketListProps {
  buckets: Bucket[];
  allTracks: PlaylistTrackEntry[];
  activeBucketId: string | null;
  onCreateBucket: (name: string, emojiId?: string) => Promise<Bucket>;
  onMoveBucket: (bucketId: string, direction: 'up' | 'down') => Promise<void>;
  onShuffleBucket: (bucketId: string) => Promise<void>;
  onDeleteBucket: (bucketId: string) => Promise<void>;
  onUpdateBucket: (bucketId: string, updates: { name?: string; emoji_id?: string | null }) => Promise<void>;
  onReorderTracks: (bucketId: string, trackIds: number[]) => Promise<void>;
  onTrackClick: (trackId: number) => void;
}

export function BucketList({
  buckets,
  allTracks,
  activeBucketId,
  onCreateBucket,
  onMoveBucket,
  onShuffleBucket,
  onDeleteBucket,
  onUpdateBucket,
  onReorderTracks,
  onTrackClick,
}: BucketListProps): JSX.Element {
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  // Track which bucket is expanded on mobile (null = all collapsed)
  const [mobileExpandedBucketId, setMobileExpandedBucketId] = useState<string | null>(null);

  // Detect mobile viewport using shared hook
  const isMobile = useIsMobile();

  // Sort buckets by position
  const sortedBuckets = [...buckets].sort((a, b) => a.position - b.position);

  // Create track lookup map for O(1) access
  const trackMap = new Map<number, PlaylistTrackEntry>();
  for (const track of allTracks) {
    trackMap.set(track.id, track);
  }

  const handleCreateBucket = async (name: string, emojiId?: string): Promise<void> => {
    await onCreateBucket(name, emojiId);
    setIsDialogOpen(false);
  };

  return (
    <div className="space-y-3">
      {/* Bucket list */}
      {sortedBuckets.map((bucket, index) => (
        <BucketComponent
          key={bucket.id}
          bucket={bucket}
          tracks={bucket.track_ids.map((id) => trackMap.get(id)).filter((t): t is PlaylistTrackEntry => t !== undefined)}
          bucketIndex={index}
          totalBuckets={buckets.length}
          isActive={bucket.id === activeBucketId}
          onMove={(direction) => onMoveBucket(bucket.id, direction)}
          onShuffle={() => onShuffleBucket(bucket.id)}
          onDelete={() => onDeleteBucket(bucket.id)}
          onUpdate={(updates) => onUpdateBucket(bucket.id, updates)}
          onReorderTracks={(trackIds) => onReorderTracks(bucket.id, trackIds)}
          onTrackClick={onTrackClick}
          isMobile={isMobile}
          isMobileExpanded={mobileExpandedBucketId === bucket.id}
          onMobileToggle={() => {
            // Toggle: if already expanded, collapse; otherwise expand this one
            setMobileExpandedBucketId(
              mobileExpandedBucketId === bucket.id ? null : bucket.id
            );
          }}
        />
      ))}

      {/* Add bucket button */}
      <Button
        onClick={() => setIsDialogOpen(true)}
        variant="outline"
        className="w-full border-dashed border-white/20 text-white/60 hover:text-white/90 hover:border-white/40"
      >
        + Add Bucket
      </Button>

      {/* Create bucket dialog */}
      <BucketEditDialog
        open={isDialogOpen}
        onClose={() => setIsDialogOpen(false)}
        onSave={handleCreateBucket}
        mode="create"
      />
    </div>
  );
}
