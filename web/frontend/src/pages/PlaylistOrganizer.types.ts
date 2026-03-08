export interface PlaylistOrganizerProps {
  playlistId: number;
  playlistName: string;
  playlistType: 'manual' | 'smart';
  playlistLibrary: string;
}
