/**
 * Side-effect glue between the pure Stories session (stores/storiesStore.ts)
 * and the global player: starting tracks, noticing when they end, and
 * reporting 5-second listens. Mounted once, app-wide, by
 * components/stories/StoriesPlaybackBridge.tsx.
 */
import { useCallback, useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { markStoryListened } from '../api/stories';
import {
  currentLocalTrackId,
  findTrack,
  isStoryTrackEnd,
  shouldReportListen,
  type StoryRef,
} from '../components/stories/storiesQueue';
import { resolveLocalTrackId, rowToTrack } from '../lib/feedPlayback';
import { useListenStore } from '../stores/listenStore';
import { usePlayerStore } from '../stores/playerStore';
import { useStoriesStore } from '../stores/storiesStore';

const PREPARE_FAILED = 'Could not prepare this SoundCloud track for playback';

function reportListen(soundcloudId: string): void {
  markStoryListened(soundcloudId).catch(() => toast.error('Could not save that this track was heard'));
}

const isStillCurrent = (ref: StoryRef): boolean => {
  const current = useStoriesStore.getState().session?.current;
  return current?.artistId === ref.artistId && current.soundcloudId === ref.soundcloudId;
};

/**
 * Play a story through the global player as a ONE-track queue: the player's
 * own queue auto-advance then has nothing to advance to, and this page
 * decides what plays next.
 */
export function usePlayStory(): (ref: StoryRef) => Promise<void> {
  const play = usePlayerStore((state) => state.play);
  return useCallback(
    async (ref: StoryRef): Promise<void> => {
      const { session, dispatch } = useStoriesStore.getState();
      const track = session ? findTrack(session, ref) : null;
      if (!track) return;
      const localTrackId = await resolveLocalTrackId(track);
      if (localTrackId === null) {
        toast.error(PREPARE_FAILED);
        return;
      }
      if (track.local_track_id === null) dispatch({ type: 'materialized', soundcloudId: ref.soundcloudId, localTrackId });
      // A later click won the race while this one was materializing.
      if (!isStillCurrent(ref)) return;
      void play(rowToTrack(track, localTrackId), { type: 'feed', track_ids: [localTrackId], shuffle: false });
    },
    [play]
  );
}

/** Plays `current` whenever the session bumps playNonce. Never replays on remount. */
export function useStoriesAutoplay(): void {
  const playNonce = useStoriesStore((state) => state.session?.playNonce ?? 0);
  const handledNonce = useRef(playNonce);
  const playStory = usePlayStory();
  useEffect(() => {
    if (playNonce === handledNonce.current) return;
    handledNonce.current = playNonce;
    const current = useStoriesStore.getState().session?.current;
    if (current) void playStory(current);
  }, [playNonce, playStory]);
}

/** Natural end (or player-bar Next) of a story track advances the session. */
export function useStoriesTrackEnd(): void {
  useEffect(
    () =>
      usePlayerStore.subscribe((state, previousState) => {
        const { session, dispatch } = useStoriesStore.getState();
        const ended = isStoryTrackEnd(
          previousState.currentTrack?.id ?? null,
          state.currentTrack?.id ?? null,
          currentLocalTrackId(session)
        );
        if (!ended || !session?.current) return;
        // Also fires on stream errors and player-bar Next, so only a real
        // 5-second listen reaches the server. The local track-ended patch
        // still stops the session looping back to a broken track.
        const track = findTrack(session, session.current);
        const playedMs = track?.local_track_id ? useListenStore.getState().tallies[track.local_track_id]?.listenedMs ?? 0 : 0;
        if (shouldReportListen(track, playedMs)) reportListen(track.soundcloud_id);
        dispatch({ type: 'track-ended', soundcloudId: session.current.soundcloudId });
      }),
    []
  );
}

/** After 5s of real playback, mark the current story listened (optimistic) and POST once. */
export function useStoriesListenReporter(): void {
  const track = useStoriesStore((state) => (state.session ? findTrack(state.session, state.session.current) : null));
  const localTrackId = track?.local_track_id ?? null;
  const playedMs = useListenStore((state) =>
    localTrackId === null ? 0 : state.tallies[localTrackId]?.listenedMs ?? 0
  );
  const dispatch = useStoriesStore((state) => state.dispatch);
  useEffect(() => {
    if (!shouldReportListen(track, playedMs)) return;
    dispatch({ type: 'mark-listened', soundcloudId: track.soundcloud_id });
    reportListen(track.soundcloud_id);
  }, [track, playedMs, dispatch]);
}
