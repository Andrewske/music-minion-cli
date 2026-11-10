import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { FEED_DECISION_MUTATION_KEY, isFeedSyncFailed, rateFeedItem } from '../api/feed';
import type { StoriesDecision, StoriesTrack } from '../api/stories';
import { FEED_QUERY_PREFIX } from '../components/feed/feedCache';
import { REVIEWED_QUERY_KEY } from '../components/feed/reviewed';
import { getListenStats } from '../stores/listenStore';
import { usePlayerStore } from '../stores/playerStore';
import { useStoriesStore } from '../stores/storiesStore';

interface VerdictVariables {
  track: StoriesTrack;
  decision: StoriesDecision;
}

/**
 * A verdict that advanced past the last unheard story clears `current`;
 * stop the rated track instead of letting it play under "caught up".
 */
function stopIfSessionFinished(localTrackId: number | null): void {
  const session = useStoriesStore.getState().session;
  const player = usePlayerStore.getState();
  if (!session || session.current !== null || localTrackId === null) return;
  if (player.currentTrack?.id === localTrackId && player.isPlaying) void player.pause();
}

/**
 * Keep / Not quite / Skip through POST /feed/{id}/rate (surface "stories").
 * The session updates optimistically (Not quite and Skip advance at once);
 * a failed write restores the previous verdict but does not rewind playback.
 */
export function useStoriesVerdict(): {
  decide: (track: StoriesTrack, decision: StoriesDecision) => void;
  pendingId: string | null;
} {
  const queryClient = useQueryClient();
  const dispatch = useStoriesStore((state) => state.dispatch);
  const mutation = useMutation({
    mutationKey: FEED_DECISION_MUTATION_KEY,
    mutationFn: ({ track, decision }: VerdictVariables) => {
      const listen = getListenStats(track.local_track_id);
      return rateFeedItem(track.soundcloud_id, decision, {
        surface: 'stories',
        listenSeconds: listen.listenSeconds,
        maxPositionMs: listen.maxPositionMs,
      });
    },
    onMutate: ({ track, decision }) => {
      dispatch({ type: 'verdict', soundcloudId: track.soundcloud_id, decision });
      stopIfSessionFinished(track.local_track_id);
      return { previousDecision: track.decision, previousLikeAction: track.sc_like_action };
    },
    onError: (_error, { track }, context) => {
      dispatch({ type: 'set-decision', soundcloudId: track.soundcloud_id, decision: context?.previousDecision ?? null });
      dispatch({
        type: 'set-sc-like',
        soundcloudId: track.soundcloud_id,
        scLiked: track.sc_liked,
        likeAction: context?.previousLikeAction ?? null,
      });
      toast.error(`Could not save the verdict for ${track.title ?? 'this track'}`);
    },
    onSuccess: (response, { track, decision }) => {
      dispatch({
        type: 'set-sc-like',
        soundcloudId: track.soundcloud_id,
        scLiked: response.sc_liked ?? track.sc_liked,
        likeAction: response.action_state.like,
      });
      if (isFeedSyncFailed(response.action_state)) toast.error('Kept locally; SoundCloud sync needs attention');
      else if (decision === 'keep') toast.success('Kept: SoundCloud sync queued');
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: FEED_QUERY_PREFIX });
      void queryClient.invalidateQueries({ queryKey: REVIEWED_QUERY_KEY });
    },
  });
  return {
    decide: (track, decision) => mutation.mutate({ track, decision }),
    pendingId: mutation.isPending ? mutation.variables?.track.soundcloud_id ?? null : null,
  };
}
