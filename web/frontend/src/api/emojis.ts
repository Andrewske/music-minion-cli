import { apiRequest } from './client';

export interface EmojiInfo {
  emoji_id: string;
  type: 'unicode' | 'custom';
  file_path: string | null;  // Only for custom emojis
  custom_name: string | null;
  default_name: string;
  use_count: number;
  last_used: string | null;
}

export interface TrackEmoji {
  emoji_id: string;
  added_at: string;
}

export async function getTopEmojis(limit: number = 50): Promise<EmojiInfo[]> {
  return apiRequest<EmojiInfo[]>(`/emojis/top?limit=${limit}`);
}

export async function getAllEmojis(limit: number = 100, offset: number = 0): Promise<EmojiInfo[]> {
  return apiRequest<EmojiInfo[]>(`/emojis/all?limit=${limit}&offset=${offset}`);
}

export async function getRecentEmojis(limit: number = 10): Promise<EmojiInfo[]> {
  return apiRequest<EmojiInfo[]>(`/emojis/recent?limit=${limit}`);
}

export async function searchEmojis(query: string): Promise<EmojiInfo[]> {
  return apiRequest<EmojiInfo[]>(`/emojis/search?q=${encodeURIComponent(query)}`);
}

export async function addEmojiToTrack(
  trackId: number,
  emojiId: string
): Promise<{ added: boolean }> {
  return apiRequest<{ added: boolean }>(`/emojis/tracks/${trackId}/emojis`, {
    method: 'POST',
    body: JSON.stringify({ emoji_id: emojiId }),
  });
}

export async function removeEmojiFromTrack(
  trackId: number,
  emojiId: string
): Promise<{ removed: boolean }> {
  return apiRequest<{ removed: boolean }>(
    `/emojis/tracks/${trackId}/emojis/${encodeURIComponent(emojiId)}`,
    { method: 'DELETE' }
  );
}

export async function updateEmojiMetadata(
  emojiId: string,
  customName: string | null
): Promise<{ updated: boolean }> {
  return apiRequest<{ updated: boolean }>(
    `/emojis/metadata/${encodeURIComponent(emojiId)}`,
    {
      method: 'PUT',
      body: JSON.stringify({ custom_name: customName }),
    }
  );
}

export async function deleteCustomEmoji(
  emojiId: string
): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(
    `/emojis/custom/${encodeURIComponent(emojiId)}`,
    { method: 'DELETE' }
  );
}
