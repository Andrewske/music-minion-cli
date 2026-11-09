import { describe, expect, it } from 'vitest';
import { makeArtist, makeResponse, makeTrack } from './storiesFixtures';
import {
  canGoPrevious,
  createSession,
  currentLocalTrackId,
  focusTrack,
  isCaughtUp,
  isStoryTrackEnd,
  nextUnheardInArtist,
  playingStoryId,
  shouldReportListen,
  storiesReducer,
  visibleArtists,
  type StoriesAction,
  type StoriesSession,
} from './storiesQueue';

/** A: a1, a2 (heard), a3. B: b1. C: c1 (heard) — so C only appears via cross-artist listening. */
const baseSession = (): StoriesSession =>
  createSession(
    makeResponse([
      makeArtist(1, [makeTrack('a1'), makeTrack('a2', { listened: true }), makeTrack('a3')]),
      makeArtist(2, [makeTrack('b1')]),
      makeArtist(3, [makeTrack('shared'), makeTrack('c1', { listened: true })]),
    ])
  );

const run = (session: StoriesSession, ...actions: StoriesAction[]): StoriesSession =>
  actions.reduce(storiesReducer, session);

const current = (session: StoriesSession): string | null => session.current?.soundcloudId ?? null;
const visibleIds = (session: StoriesSession): number[] => visibleArtists(session).map((a) => a.discovery_artist_id);

describe('createSession', () => {
  it('keeps a rebuilt session\'s playNonce so autoplay does not replay the adopted track', () => {
    const rebuilt = createSession(makeResponse([makeArtist(1, [makeTrack('a1', { local_track_id: 7 })])]), 7, 4);
    expect(rebuilt.playNonce).toBe(4);
    expect(rebuilt.current).toEqual({ artistId: 1, soundcloudId: 'a1' });
  });


  it('selects the first artist and starts nothing', () => {
    const session = baseSession();
    expect(session.activeArtistId).toBe(1);
    expect(session.current).toBeNull();
    expect(session.playNonce).toBe(0);
    expect(focusTrack(session)?.soundcloud_id).toBe('a1');
  });

  it('handles an empty response as caught up', () => {
    const session = createSession(makeResponse([]));
    expect(session.activeArtistId).toBeNull();
    expect(isCaughtUp(session)).toBe(true);
  });

  it('adopts the story that is already playing without replaying it', () => {
    const response = makeResponse([
      makeArtist(1, [makeTrack('a1')]),
      makeArtist(2, [makeTrack('b1'), makeTrack('b2', { local_track_id: 77 })]),
    ]);
    const session = createSession(response, 77);
    expect(session.activeArtistId).toBe(2);
    expect(session.current).toEqual({ artistId: 2, soundcloudId: 'b2' });
    expect(session.history).toEqual([{ artistId: 2, soundcloudId: 'b2' }]);
    expect(session.playNonce).toBe(0);
  });

  it('ignores a playing track that is not a story', () => {
    const session = createSession(makeResponse([makeArtist(1, [makeTrack('a1')])]), 999);
    expect(session.current).toBeNull();
    expect(session.activeArtistId).toBe(1);
  });
});

describe('advance', () => {
  it('skips listened tracks within the artist', () => {
    const session = run(baseSession(), { type: 'play-track', artistId: 1, soundcloudId: 'a1' }, { type: 'advance' });
    expect(current(session)).toBe('a3');
    expect(session.playNonce).toBe(2);
  });

  it('wraps to earlier unheard tracks before leaving the artist', () => {
    const session = run(baseSession(), { type: 'play-track', artistId: 1, soundcloudId: 'a3' }, { type: 'advance' });
    expect(current(session)).toBe('a1');
  });

  it('moves to the first unheard track of the next artist once the artist is done', () => {
    const session = run(
      baseSession(),
      { type: 'play-track', artistId: 1, soundcloudId: 'a1' },
      { type: 'mark-listened', soundcloudId: 'a1' },
      { type: 'mark-listened', soundcloudId: 'a3' },
      { type: 'advance' }
    );
    expect(session.activeArtistId).toBe(2);
    expect(current(session)).toBe('b1');
  });

  it('never auto-queues a track heard under another artist', () => {
    const session = run(
      createSession(
        makeResponse([
          makeArtist(1, [makeTrack('a1'), makeTrack('shared')]),
          makeArtist(2, [makeTrack('shared')]),
          makeArtist(3, [makeTrack('c1')]),
        ])
      ),
      { type: 'play-track', artistId: 1, soundcloudId: 'shared' },
      { type: 'mark-listened', soundcloudId: 'shared' },
      { type: 'mark-listened', soundcloudId: 'a1' },
      { type: 'advance' }
    );
    expect(session.activeArtistId).toBe(3);
    expect(current(session)).toBe('c1');
  });

  it('clears current when nothing unheard is left anywhere', () => {
    const solo = createSession(makeResponse([makeArtist(1, [makeTrack('a1')])]));
    const session = run(solo, { type: 'play-track', artistId: 1, soundcloudId: 'a1' }, { type: 'track-ended', soundcloudId: 'a1' });
    expect(session.current).toBeNull();
    expect(session.playNonce).toBe(1);
    expect(isCaughtUp(session)).toBe(true);
  });

  it('advances from the focused track when nothing has played yet', () => {
    const session = run(baseSession(), { type: 'advance' });
    expect(current(session)).toBe('a3');
  });
});

describe('verdicts', () => {
  const playing = (): StoriesSession => run(baseSession(), { type: 'play-track', artistId: 1, soundcloudId: 'a1' });

  it('Like marks listened and keeps playing the same track', () => {
    const session = run(playing(), { type: 'verdict', soundcloudId: 'a1', decision: 'keep' });
    expect(current(session)).toBe('a1');
    expect(session.playNonce).toBe(1);
    expect(focusTrack(session)).toMatchObject({ decision: 'keep', listened: true });
  });

  it.each(['not_quite', 'nope'] as const)('%s marks listened and advances, keeping the track in the list', (decision) => {
    const session = run(playing(), { type: 'verdict', soundcloudId: 'a1', decision });
    expect(current(session)).toBe('a3');
    expect(session.artists[0].tracks[0]).toMatchObject({ soundcloud_id: 'a1', decision, listened: true });
  });

  it('Skip before anything played advances within the artist, not past it', () => {
    const session = run(baseSession(), { type: 'verdict', soundcloudId: 'a1', decision: 'nope' });
    expect(session.activeArtistId).toBe(1);
    expect(current(session)).toBe('a3');
  });

  it('a track ending while browsing another artist continues with the shown artist', () => {
    const session = run(
      baseSession(),
      { type: 'play-track', artistId: 1, soundcloudId: 'a1' },
      { type: 'mark-listened', soundcloudId: 'b1' },
      { type: 'select-artist', artistId: 2 },
      { type: 'track-ended', soundcloudId: 'a1' }
    );
    expect(session.activeArtistId).toBe(3);
    expect(current(session)).toBe('shared');
  });

  it('set-decision rolls a failed verdict back without touching listened', () => {
    const session = run(
      playing(),
      { type: 'verdict', soundcloudId: 'a1', decision: 'keep' },
      { type: 'set-decision', soundcloudId: 'a1', decision: null }
    );
    expect(session.artists[0].tracks[0]).toMatchObject({ decision: null, listened: true });
  });
});

describe('listened is global per track', () => {
  it('marks the same track under every artist', () => {
    const session = run(baseSession(), { type: 'mark-listened', soundcloudId: 'shared' });
    expect(session.artists[2].tracks[0].listened).toBe(true);
  });
});

describe('visible artists', () => {
  it('keeps a finished artist while active and drops it once the user leaves', () => {
    const finished = run(
      baseSession(),
      { type: 'play-track', artistId: 1, soundcloudId: 'a1' },
      { type: 'mark-listened', soundcloudId: 'a1' },
      { type: 'mark-listened', soundcloudId: 'a3' }
    );
    expect(visibleIds(finished)).toEqual([1, 2, 3]);
    expect(visibleIds(run(finished, { type: 'select-artist', artistId: 2 }))).toEqual([2, 3]);
  });

  it('drops an artist whose tracks were all heard elsewhere', () => {
    const session = run(baseSession(), { type: 'mark-listened', soundcloudId: 'shared' });
    expect(visibleIds(session)).toEqual([1, 2]);
  });
});

describe('select-artist', () => {
  it('plays the first unheard track of the clicked artist', () => {
    const session = run(baseSession(), { type: 'select-artist', artistId: 3 });
    expect(session.activeArtistId).toBe(3);
    expect(current(session)).toBe('shared');
    expect(session.playNonce).toBe(1);
  });

  it('only shows an artist whose tracks are all heard', () => {
    const heard = run(baseSession(), { type: 'mark-listened', soundcloudId: 'b1' }, { type: 'select-artist', artistId: 2 });
    expect(heard.activeArtistId).toBe(2);
    expect(heard.current).toBeNull();
    expect(heard.playNonce).toBe(0);
    expect(focusTrack(heard)?.soundcloud_id).toBe('b1');
  });

  it('does not restart the artist that is already playing', () => {
    const session = run(baseSession(), { type: 'play-track', artistId: 1, soundcloudId: 'a3' }, { type: 'select-artist', artistId: 1 });
    expect(current(session)).toBe('a3');
    expect(session.playNonce).toBe(1);
  });
});

describe('previous', () => {
  it('is unavailable before two tracks have played', () => {
    expect(canGoPrevious(baseSession())).toBe(false);
    expect(canGoPrevious(run(baseSession(), { type: 'play-track', artistId: 1, soundcloudId: 'a1' }))).toBe(false);
  });

  it('steps back through history and re-shows a dropped artist while active', () => {
    const moved = run(
      baseSession(),
      { type: 'play-track', artistId: 1, soundcloudId: 'a1' },
      { type: 'verdict', soundcloudId: 'a1', decision: 'nope' },
      { type: 'verdict', soundcloudId: 'a3', decision: 'nope' }
    );
    expect(current(moved)).toBe('b1');
    expect(visibleIds(moved)).toEqual([2, 3]);

    const back = run(moved, { type: 'previous' });
    expect(back.activeArtistId).toBe(1);
    expect(current(back)).toBe('a3');
    expect(back.playNonce).toBe(moved.playNonce + 1);
    expect(visibleIds(back)).toEqual([1, 2, 3]);

    const twice = run(back, { type: 'previous' });
    expect(current(twice)).toBe('a1');
    expect(canGoPrevious(twice)).toBe(false);
  });

  it('returns to the last track after everything finished', () => {
    const solo = createSession(makeResponse([makeArtist(1, [makeTrack('a1')])]));
    const done = run(solo, { type: 'play-track', artistId: 1, soundcloudId: 'a1' }, { type: 'track-ended', soundcloudId: 'a1' });
    expect(current(run(done, { type: 'previous' }))).toBe('a1');
  });
});

describe('track-ended', () => {
  it('ignores ends for a track that is no longer current', () => {
    const session = run(baseSession(), { type: 'play-track', artistId: 1, soundcloudId: 'a3' });
    expect(run(session, { type: 'track-ended', soundcloudId: 'a1' })).toBe(session);
  });

  it('marks the ended track listened before advancing', () => {
    const session = run(baseSession(), { type: 'play-track', artistId: 1, soundcloudId: 'a1' }, { type: 'track-ended', soundcloudId: 'a1' });
    expect(session.artists[0].tracks[0]).toMatchObject({ listened: true, decision: null });
    expect(current(session)).toBe('a3');
  });
});

describe('player helpers', () => {
  it('detects a story ending only on a transition from its id to null', () => {
    expect(isStoryTrackEnd(7, null, 7)).toBe(true);
    expect(isStoryTrackEnd(7, 8, 7)).toBe(false);
    expect(isStoryTrackEnd(8, null, 7)).toBe(false);
    expect(isStoryTrackEnd(null, null, null)).toBe(false);
  });

  it('tracks the materialized id of the current story', () => {
    const session = run(
      baseSession(),
      { type: 'play-track', artistId: 1, soundcloudId: 'a1' },
      { type: 'materialized', soundcloudId: 'a1', localTrackId: 55 }
    );
    expect(currentLocalTrackId(session)).toBe(55);
    expect(playingStoryId(session, 55)).toBe('a1');
    expect(playingStoryId(session, 99)).toBeNull();
    expect(currentLocalTrackId(null)).toBeNull();
  });

  it('highlights the current story while it is still materializing', () => {
    const session = run(baseSession(), { type: 'play-track', artistId: 1, soundcloudId: 'a1' });
    expect(playingStoryId(session, 99)).toBe('a1');
  });

  it('reports a listen once, after 5 seconds of an unheard track', () => {
    expect(shouldReportListen(makeTrack('x'), 4_999)).toBe(false);
    expect(shouldReportListen(makeTrack('x'), 5_000)).toBe(true);
    expect(shouldReportListen(makeTrack('x', { listened: true }), 60_000)).toBe(false);
    expect(shouldReportListen(null, 60_000)).toBe(false);
  });
});

describe('nextUnheardInArtist', () => {
  it('starts from the top when the anchor is unknown', () => {
    const artist = makeArtist(1, [makeTrack('a1', { listened: true }), makeTrack('a2')]);
    expect(nextUnheardInArtist(artist, null)?.soundcloud_id).toBe('a2');
    expect(nextUnheardInArtist(artist, 'a2')).toBeNull();
  });
});
