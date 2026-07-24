import { useState } from 'react';
import type { ReactElement } from 'react';
import { Link } from '@tanstack/react-router';
import { HardDrive, Link2, Music } from 'lucide-react';
import type { ArtistConnection, ConnectionRelation, ConnectionTrack } from '../../api/artists';
import { useArtistConnections } from '../../hooks/useArtists';

const COLLAPSED_TRACK_COUNT = 4;

/** Relation tag from the page artist's perspective. */
const RELATION_TAGS: Record<ConnectionRelation, { label: string; cls: string }> = {
  collab: { label: 'collab', cls: 'text-purple-400 bg-purple-400/10' },
  features: { label: 'feat', cls: 'text-sky-400 bg-sky-400/10' },
  featured_on: { label: 'feat', cls: 'text-sky-400 bg-sky-400/10' },
  remixed: { label: 'remix of', cls: 'text-amber-400 bg-amber-400/10' },
  remixed_by: { label: 'remixed by', cls: 'text-amber-400 bg-amber-400/10' },
};

function ConnectionTrackRow({ track }: { track: ConnectionTrack }): ReactElement {
  const tag = RELATION_TAGS[track.relation];
  return (
    <li className="flex items-center gap-2 px-3 py-1.5 text-xs">
      <Music className="w-3 h-3 shrink-0 text-white/20" />
      <span className="min-w-0 flex-1 truncate text-white/70">
        {track.title ?? 'Untitled'}
        {track.artist && <span className="text-white/35"> — {track.artist}</span>}
      </span>
      <span
        className={`shrink-0 px-1.5 py-0.5 rounded font-sf-mono text-[10px] uppercase tracking-wide ${tag.cls}`}
      >
        {tag.label}
      </span>
      {track.is_local && (
        <span title="Local file on disk" className="shrink-0 flex">
          <HardDrive className="w-3 h-3 text-emerald-400" />
        </span>
      )}
    </li>
  );
}

function ConnectionName({ connection }: { connection: ArtistConnection }): ReactElement {
  const cls = 'block text-sm text-white truncate hover:text-obsidian-accent transition-colors';
  if (connection.artist_id != null) {
    return (
      <Link
        to="/artists/$artistId"
        params={{ artistId: String(connection.artist_id) }}
        className={cls}
      >
        {connection.display_name}
      </Link>
    );
  }
  return (
    <Link to="/artists/local/$name" params={{ name: connection.display_name }} className={cls}>
      {connection.display_name}
    </Link>
  );
}

function ConnectionCard({ connection }: { connection: ArtistConnection }): ReactElement {
  const [expanded, setExpanded] = useState(false);
  const tracks = expanded
    ? connection.tracks
    : connection.tracks.slice(0, COLLAPSED_TRACK_COUNT);
  const hiddenCount = connection.tracks.length - tracks.length;

  return (
    <div className="rounded border border-obsidian-border bg-obsidian-surface">
      <div className="flex items-center gap-3 px-3 py-2.5 border-b border-obsidian-border/60">
        {connection.avatar_url ? (
          <img
            src={connection.avatar_url}
            alt=""
            className="w-8 h-8 rounded-full object-cover shrink-0"
          />
        ) : (
          <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center shrink-0">
            <Music className="w-3.5 h-3.5 text-white/30" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <ConnectionName connection={connection} />
          {connection.is_following === false && (
            <span className="font-sf-mono text-[10px] text-white/30">not following</span>
          )}
        </div>
        <span className="flex items-center gap-1 font-sf-mono text-xs text-obsidian-accent shrink-0">
          <Link2 className="w-3 h-3" />
          {connection.shared_count} shared
        </span>
      </div>
      <ul className="py-1 divide-y divide-white/[0.03]">
        {tracks.map((t) => (
          <ConnectionTrackRow key={`${t.track_id}:${t.relation}`} track={t} />
        ))}
      </ul>
      {hiddenCount > 0 && (
        <button
          onClick={() => setExpanded(true)}
          className="w-full px-3 py-1.5 font-sf-mono text-[11px] text-white/40 hover:text-white text-left transition-colors"
        >
          + {hiddenCount} more
        </button>
      )}
    </div>
  );
}

interface ArtistConnectionsProps {
  artistId: number;
}

/** Artists sharing song credits — collabs, feats, remixes — most-shared first. */
export function ArtistConnections({ artistId }: ArtistConnectionsProps): ReactElement {
  const { data: connections, isPending, error } = useArtistConnections(artistId);

  if (isPending) {
    return (
      <p className="font-sf-mono text-sm text-white/40 py-8 text-center">Loading connections…</p>
    );
  }

  if (error) {
    return (
      <p className="font-sf-mono text-sm text-red-400 py-8 text-center">
        {error instanceof Error ? error.message : 'Failed to load connections'}
      </p>
    );
  }

  if (!connections || connections.length === 0) {
    return (
      <p className="font-sf-mono text-sm text-white/40 py-8 text-center">
        No collabs, feats, or remixes with other artists in your library.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {connections.map((c) => (
        <ConnectionCard key={`${c.artist_id ?? 'local'}:${c.display_name}`} connection={c} />
      ))}
    </div>
  );
}
