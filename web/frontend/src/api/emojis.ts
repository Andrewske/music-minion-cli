// Re-export from shared package
export {
  getTopEmojis, getAllEmojis, getRecentEmojis, searchEmojis,
  addEmojiToTrack, removeEmojiFromTrack, updateEmojiMetadata, deleteCustomEmoji,
} from '@music-minion/shared';
export type { EmojiInfo, TrackEmoji } from '@music-minion/shared';
