import { Music } from 'lucide-react';
import { usePlayerStore } from '../stores/playerStore';
import { usePlaylists } from '../hooks/usePlaylists';
import { useQuery } from '@tanstack/react-query';
import { getStations, type Station } from '../api/radio';
import type { Playlist } from '../types';
import type { Track } from '../api/builder';

export function HomePage(): JSX.Element {
  const { currentTrack, queue, queueIndex, isPlaying } = usePlayerStore();
  const { data: playlistsData } = usePlaylists();
  const { data: stations } = useQuery({
    queryKey: ['stations'],
    queryFn: getStations,
  });

  const playlists = playlistsData || [];

  return (
    <div className="container mx-auto p-6 space-y-8">
      {/* Now Playing - prominent section */}
      {currentTrack ? (
        <section className="bg-card rounded-lg p-6">
          <h2 className="text-sm font-medium text-muted-foreground mb-4">Now Playing</h2>
          <div className="flex gap-6">
            {/* Large album art */}
            <div className="w-48 h-48 bg-muted rounded-lg overflow-hidden flex-shrink-0">
              {currentTrack.album && (
                <div className="w-full h-full flex items-center justify-center text-muted-foreground">
                  <Music className="h-16 w-16" />
                </div>
              )}
            </div>

            {/* Track info + queue preview */}
            <div className="flex-1 min-w-0">
              <h1 className="text-2xl font-bold truncate">{currentTrack.title}</h1>
              <p className="text-lg text-muted-foreground truncate">{currentTrack.artist}</p>
              {currentTrack.album && (
                <p className="text-sm text-muted-foreground truncate">{currentTrack.album}</p>
              )}

              {/* Mini queue preview */}
              {queue.length > queueIndex + 1 && (
                <div className="mt-6">
                  <h3 className="text-sm font-medium text-muted-foreground mb-2">Up Next</h3>
                  <div className="space-y-1">
                    {queue.slice(queueIndex + 1, queueIndex + 4).map((track, i) => (
                      <div key={track.id} className="text-sm flex items-center gap-2">
                        <span className="text-muted-foreground">{i + 1}.</span>
                        <span className="truncate">{track.title}</span>
                        <span className="text-muted-foreground truncate">- {track.artist}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      ) : (
        <section className="text-center py-12">
          <Music className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h2 className="text-lg font-medium">Nothing playing</h2>
          <p className="text-muted-foreground">Select a playlist or station to start</p>
        </section>
      )}

      {/* Playlists grid */}
      <section>
        <h2 className="text-lg font-semibold mb-4">Playlists</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
          {playlists.map((playlist) => (
            <PlaylistCard key={playlist.id} playlist={playlist} />
          ))}
        </div>
      </section>

      {/* Stations quick access */}
      {stations && stations.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold mb-4">Stations</h2>
          <div className="flex flex-wrap gap-2">
            {stations.map((station) => (
              <StationChip key={station.id} station={station} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function PlaylistCard({ playlist }: { playlist: Playlist }): JSX.Element {
  const { play } = usePlayerStore();

  const handleClick = async (): Promise<void> => {
    // Fetch playlist tracks to get the first track
    const response = await fetch(`/api/playlists/${playlist.id}/tracks`);
    if (!response.ok) {
      console.error('Failed to fetch playlist tracks');
      return;
    }
    const data = await response.json();
    const tracks: Track[] = data.tracks;

    if (tracks.length > 0) {
      await play(tracks[0], {
        type: 'playlist',
        playlist_id: playlist.id,
        start_index: 0,
      });
    }
  };

  return (
    <div
      onClick={handleClick}
      className="bg-card rounded-lg p-4 cursor-pointer hover:bg-accent transition-colors"
    >
      <div className="w-full aspect-square bg-muted rounded mb-3 flex items-center justify-center">
        <Music className="h-8 w-8 text-muted-foreground" />
      </div>
      <h3 className="font-medium truncate">{playlist.name}</h3>
      <p className="text-sm text-muted-foreground">{playlist.track_count} tracks</p>
    </div>
  );
}

function StationChip({ station }: { station: Station }): JSX.Element {
  const { play } = usePlayerStore();

  const handleClick = async (): Promise<void> => {
    // Fetch playlist tracks to get the first track
    const response = await fetch(`/api/playlists/${station.playlist_id}/tracks`);
    if (!response.ok) {
      console.error('Failed to fetch station playlist tracks');
      return;
    }
    const data = await response.json();
    const tracks: Track[] = data.tracks;

    if (tracks.length > 0) {
      await play(tracks[0], {
        type: 'playlist',
        playlist_id: station.playlist_id,
        start_index: 0,
        shuffle: station.shuffle_enabled,
      });
    }
  };

  return (
    <button
      onClick={handleClick}
      className="px-4 py-2 bg-card rounded-full hover:bg-accent transition-colors"
    >
      {station.name}
    </button>
  );
}
