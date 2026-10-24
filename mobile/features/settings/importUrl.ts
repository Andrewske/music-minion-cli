/**
 * Which backend import endpoint handles a pasted or shared URL.
 */
export type ImportEndpoint = '/youtube/import' | '/soundcloud/import';

export const importEndpoint = (url: string): ImportEndpoint | null => {
  const trimmed = url.trim();
  if (trimmed.includes('youtube.com') || trimmed.includes('youtu.be')) return '/youtube/import';
  if (trimmed.includes('soundcloud.com')) return '/soundcloud/import';
  return null;
};
