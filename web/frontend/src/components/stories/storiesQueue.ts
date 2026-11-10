/**
 * Pure session logic for the Stories page: which artist is active, which
 * track plays next, what Previous returns to, and which artists are still
 * shown. The page dispatches actions; nothing here touches the player or API.
 *
 * Playback is requested by bumping `playNonce`: whenever a transition wants
 * `current` to start playing, the nonce increments and the page plays it.
 */
import type { FeedActionStatus } from '../../api/feed';
import type { StoriesArtist, StoriesDecision, StoriesResponse, StoriesTrack } from '../../api/stories';

export const STORIES_QUERY_KEY = ['stories'] as const;

/** Seconds of real playback that make a track "listened" on this page. */
export const LISTENED_THRESHOLD_MS = 5_000;

export interface StoryRef {
  artistId: number;
  soundcloudId: string;
}

export interface StoriesSession {
  generatedAt: string;
  /** Snapshot of the server response, patched locally (listened, verdicts, local ids). */
  artists: readonly StoriesArtist[];
  activeArtistId: number | null;
  /** The track this page last started, or null when nothing was started. */
  current: StoryRef | null;
  /** Play stack for Previous; the top is `current` while it is set. */
  history: readonly StoryRef[];
  /** Incremented whenever `current` should (re)start playing. */
  playNonce: number;
}

export type StoriesAction =
  | { type: 'select-artist'; artistId: number }
  | { type: 'play-track'; artistId: number; soundcloudId: string }
  | { type: 'advance' }
  | { type: 'previous' }
  | { type: 'track-ended'; soundcloudId: string }
  | { type: 'mark-listened'; soundcloudId: string }
  | { type: 'verdict'; soundcloudId: string; decision: StoriesDecision }
  | { type: 'set-decision'; soundcloudId: string; decision: StoriesDecision | null }
  | { type: 'set-sc-like'; soundcloudId: string; scLiked: boolean; likeAction: FeedActionStatus }
  | { type: 'materialized'; soundcloudId: string; localTrackId: number };

function findPlayingRef(artists: readonly StoriesArtist[], localTrackId: number | null): StoryRef | null {
  if (localTrackId === null) return null;
  for (const artist of artists) {
    const track = artist.tracks.find((candidate) => candidate.local_track_id === localTrackId);
    if (track) return { artistId: artist.discovery_artist_id, soundcloudId: track.soundcloud_id };
  }
  return null;
}

/**
 * A fresh session. When a story is already playing (Reload mid-track), it
 * becomes `current` without bumping playNonce, so end detection and the
 * 5-second reporter keep tracking it and nothing replays. A rebuild passes
 * the old session's playNonce on: the autoplay effect fires on any change,
 * so resetting it to 0 would restart whatever is playing.
 */
export function createSession(
  response: StoriesResponse,
  playingLocalTrackId: number | null = null,
  playNonce = 0
): StoriesSession {
  const playing = findPlayingRef(response.artists, playingLocalTrackId);
  return {
    generatedAt: response.generated_at,
    artists: response.artists,
    activeArtistId: playing?.artistId ?? response.artists[0]?.discovery_artist_id ?? null,
    current: playing,
    history: playing ? [playing] : [],
    playNonce,
  };
}

const sameRef = (a: StoryRef | null | undefined, b: StoryRef | null | undefined): boolean =>
  !!a && !!b && a.artistId === b.artistId && a.soundcloudId === b.soundcloudId;

export const unheardCount = (artist: StoriesArtist): number =>
  artist.tracks.filter((track) => !track.listened).length;

export const totalUnheard = (session: StoriesSession): number =>
  session.artists.reduce((sum, artist) => sum + unheardCount(artist), 0);

export const findArtist = (session: StoriesSession, artistId: number | null): StoriesArtist | null =>
  session.artists.find((artist) => artist.discovery_artist_id === artistId) ?? null;

export function findTrack(session: StoriesSession, ref: StoryRef | null): StoriesTrack | null {
  if (!ref) return null;
  const artist = findArtist(session, ref.artistId);
  return artist?.tracks.find((track) => track.soundcloud_id === ref.soundcloudId) ?? null;
}

/**
 * The left-hand list: artists with unheard tracks, plus the active artist even
 * when finished. So an artist drops out once the user leaves it fully heard,
 * and Previous can bring a dropped artist back while it is active.
 */
export const visibleArtists = (session: StoriesSession): StoriesArtist[] =>
  session.artists.filter(
    (artist) => artist.discovery_artist_id === session.activeArtistId || unheardCount(artist) > 0
  );

/** Nothing unheard anywhere and nothing started: show the caught-up state. */
export const isCaughtUp = (session: StoriesSession): boolean =>
  session.current === null && totalUnheard(session) === 0;

/**
 * The track the centre column shows: the playing track when it belongs to the
 * active artist, otherwise the active artist's first unheard (or first) track.
 */
export function focusTrack(session: StoriesSession): StoriesTrack | null {
  const artist = findArtist(session, session.activeArtistId);
  if (!artist) return null;
  if (session.current?.artistId === artist.discovery_artist_id) {
    const playing = findTrack(session, session.current);
    if (playing) return playing;
  }
  return artist.tracks.find((track) => !track.listened) ?? artist.tracks[0] ?? null;
}

/** Next unheard track after `anchorId` in list order, wrapping; never the anchor itself. */
export function nextUnheardInArtist(artist: StoriesArtist, anchorId: string | null): StoriesTrack | null {
  const index = artist.tracks.findIndex((track) => track.soundcloud_id === anchorId);
  const ordered = [...artist.tracks.slice(index + 1), ...artist.tracks.slice(0, Math.max(0, index))];
  return ordered.find((track) => !track.listened && track.soundcloud_id !== anchorId) ?? null;
}

/** First artist after `fromArtistId` in list order (wrapping) that still has unheard tracks. */
export function nextArtistWithUnheard(session: StoriesSession, fromArtistId: number | null): StoriesArtist | null {
  const index = session.artists.findIndex((artist) => artist.discovery_artist_id === fromArtistId);
  const ordered = [...session.artists.slice(index + 1), ...session.artists.slice(0, Math.max(0, index))];
  return ordered.find((artist) => artist.discovery_artist_id !== fromArtistId && unheardCount(artist) > 0) ?? null;
}

/** Patch one track everywhere it appears: listened and verdicts are global per track. */
export function updateTrack(
  session: StoriesSession,
  soundcloudId: string,
  patch: Partial<Pick<StoriesTrack, 'listened' | 'decision' | 'local_track_id' | 'sc_liked' | 'sc_like_action'>>
): StoriesSession {
  const patchTracks = (tracks: StoriesTrack[]): StoriesTrack[] =>
    tracks.map((track) => (track.soundcloud_id === soundcloudId ? { ...track, ...patch } : track));
  return {
    ...session,
    artists: session.artists.map((artist) =>
      artist.tracks.some((track) => track.soundcloud_id === soundcloudId)
        ? { ...artist, tracks: patchTracks(artist.tracks) }
        : artist
    ),
  };
}

/** Make `ref` current and active, ask the page to play it, and record it for Previous. */
export function startTrack(session: StoriesSession, ref: StoryRef): StoriesSession {
  const top = session.history[session.history.length - 1];
  return {
    ...session,
    activeArtistId: ref.artistId,
    current: ref,
    history: sameRef(top, ref) ? session.history : [...session.history, ref],
    playNonce: session.playNonce + 1,
  };
}

/**
 * Next unheard track of the active artist after `anchorId`; when the artist
 * is done, the first unheard track of the next artist. Nothing left anywhere:
 * playback stops and `current` clears. Callers that mark a track listened
 * pass it as the anchor, since marking it moves the focus elsewhere.
 */
export function advanceFrom(session: StoriesSession, anchorId: string | null): StoriesSession {
  const artist = findArtist(session, session.activeArtistId);
  const sameArtistNext = artist ? nextUnheardInArtist(artist, anchorId) : null;
  if (artist && sameArtistNext) {
    return startTrack(session, { artistId: artist.discovery_artist_id, soundcloudId: sameArtistNext.soundcloud_id });
  }
  const nextArtist = nextArtistWithUnheard(session, session.activeArtistId);
  const firstUnheard = nextArtist?.tracks.find((track) => !track.listened);
  if (!nextArtist || !firstUnheard) return { ...session, current: null };
  return startTrack(session, { artistId: nextArtist.discovery_artist_id, soundcloudId: firstUnheard.soundcloud_id });
}

/** Advance from whatever the centre column is showing. */
export const advance = (session: StoriesSession): StoriesSession =>
  advanceFrom(session, focusTrack(session)?.soundcloud_id ?? null);

/** History without the current entry: what Previous would return to is its top. */
function previousStack(session: StoriesSession): readonly StoryRef[] {
  const top = session.history[session.history.length - 1];
  return sameRef(top, session.current) ? session.history.slice(0, -1) : session.history;
}

export const canGoPrevious = (session: StoriesSession): boolean => previousStack(session).length > 0;

/** Step back through the play history, switching back to that track's artist. */
export function previous(session: StoriesSession): StoriesSession {
  const stack = previousStack(session);
  const target = stack[stack.length - 1];
  if (!target) return session;
  return {
    ...session,
    history: stack,
    current: target,
    activeArtistId: target.artistId,
    playNonce: session.playNonce + 1,
  };
}

/** Clicking an artist: play its first unheard track, or just show it when all are heard. */
export function selectArtist(session: StoriesSession, artistId: number): StoriesSession {
  const artist = findArtist(session, artistId);
  if (!artist) return session;
  if (session.current?.artistId === artistId) return { ...session, activeArtistId: artistId };
  const firstUnheard = artist.tracks.find((track) => !track.listened);
  if (!firstUnheard) return { ...session, activeArtistId: artistId };
  return startTrack(session, { artistId, soundcloudId: firstUnheard.soundcloud_id });
}

/**
 * Keep keeps playing; Not quite and Skip advance. Every verdict counts as
 * listened. A keep queues the SoundCloud like, so its heart shows pending
 * until the server says the like landed; other verdicts cancel that job.
 */
export function applyVerdict(session: StoriesSession, soundcloudId: string, decision: StoriesDecision): StoriesSession {
  const likeAction: FeedActionStatus = decision === 'keep' ? 'pending' : null;
  const rated = updateTrack(session, soundcloudId, { decision, listened: true, sc_like_action: likeAction });
  return decision === 'keep' ? rated : advanceFrom(rated, soundcloudId);
}

function trackEnded(session: StoriesSession, soundcloudId: string): StoriesSession {
  if (session.current?.soundcloudId !== soundcloudId) return session;
  return advanceFrom(updateTrack(session, soundcloudId, { listened: true }), soundcloudId);
}

export function storiesReducer(session: StoriesSession, action: StoriesAction): StoriesSession {
  switch (action.type) {
    case 'select-artist': return selectArtist(session, action.artistId);
    case 'play-track': return startTrack(session, { artistId: action.artistId, soundcloudId: action.soundcloudId });
    case 'advance': return advance(session);
    case 'previous': return previous(session);
    case 'track-ended': return trackEnded(session, action.soundcloudId);
    case 'mark-listened': return updateTrack(session, action.soundcloudId, { listened: true });
    case 'verdict': return applyVerdict(session, action.soundcloudId, action.decision);
    case 'set-decision': return updateTrack(session, action.soundcloudId, { decision: action.decision });
    case 'set-sc-like':
      return updateTrack(session, action.soundcloudId, { sc_liked: action.scLiked, sc_like_action: action.likeAction });
    case 'materialized': return updateTrack(session, action.soundcloudId, { local_track_id: action.localTrackId });
    default: {
      const exhaustive: never = action;
      return exhaustive;
    }
  }
}

/** POST /listened once: only for a track not already listened that has played long enough. */
export const shouldReportListen = (track: StoriesTrack | null, playedMs: number): track is StoriesTrack =>
  track !== null && !track.listened && playedMs >= LISTENED_THRESHOLD_MS;

/**
 * The page plays each story as a one-track queue, so when it finishes (or the
 * player bar's Next is pressed) the server runs off the end of the queue and
 * the player's current track goes from the story's id to null. A switch to a
 * different track is someone playing something else, not an end.
 */
export const isStoryTrackEnd = (
  previousTrackId: number | null,
  nextTrackId: number | null,
  storyTrackId: number | null
): boolean => storyTrackId !== null && previousTrackId === storyTrackId && nextTrackId === null;

/** The library id of the track this page started, once materialized. */
export const currentLocalTrackId = (session: StoriesSession | null): number | null =>
  session ? findTrack(session, session.current)?.local_track_id ?? null : null;

/**
 * The story to highlight as playing: `current` while it is loaded in the
 * player, or still materializing (no local id yet). Null once the player has
 * moved on to something this page did not start.
 */
export function playingStoryId(session: StoriesSession, playerTrackId: number | null): string | null {
  const track = findTrack(session, session.current);
  if (!track) return null;
  return track.local_track_id === null || track.local_track_id === playerTrackId ? track.soundcloud_id : null;
}
