// Re-export from shared package
export {
  listGenres, renameGenre, assignGenreEmoji, deleteGenre,
  getTrackGenres, updateTrackGenres,
} from '@music-minion/shared';
export type { GenreInfo, TrackGenre } from '@music-minion/shared';
