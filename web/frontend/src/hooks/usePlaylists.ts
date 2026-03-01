import { useQuery } from '@tanstack/react-query';
import type { Playlist } from '../types';

export function usePlaylists(library?: string) {
  return useQuery({
    queryKey: ['playlists', library],  // Include library in cache key
    queryFn: async (): Promise<Playlist[]> => {
      const url = new URL('/api/playlists', window.location.origin);
      if (library) {
        url.searchParams.append('library', library);
      }

      const response = await fetch(url.toString());
      if (!response.ok) {
        throw new Error('Failed to fetch playlists');
      }
      const data = await response.json();
      return data.playlists;
    },
  });
}