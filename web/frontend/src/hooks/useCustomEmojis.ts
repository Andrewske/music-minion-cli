import { useQuery } from '@tanstack/react-query';

export interface CustomPickerEmoji {
  id: string;
  name: string;
  keywords: string[];
  skins: { src: string }[];
}

/**
 * Custom emojis in emoji-mart format. Shared by the picker and by
 * EmojiDisplay, which uses it to resolve a bare custom-emoji UUID to its image.
 */
export function useCustomEmojis(): CustomPickerEmoji[] {
  const { data } = useQuery({
    queryKey: ['emojis', 'custom-for-picker'],
    queryFn: async (): Promise<CustomPickerEmoji[]> => {
      const res = await fetch('/api/emojis/custom-picker');
      if (!res.ok) return [];
      return res.json();
    },
    staleTime: 5 * 60 * 1000,
  });
  return data ?? [];
}

export function findCustomEmojiSrc(
  emojis: CustomPickerEmoji[],
  emojiId: string,
): string | undefined {
  return emojis.find((e) => e.id === emojiId)?.skins[0]?.src;
}
