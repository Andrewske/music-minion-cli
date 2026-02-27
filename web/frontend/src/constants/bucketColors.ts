export const BUCKET_COLORS = [
  'rgb(239, 68, 68)',   // red-500
  'rgb(249, 115, 22)',  // orange-500
  'rgb(234, 179, 8)',   // yellow-500
  'rgb(34, 197, 94)',   // green-500
  'rgb(6, 182, 212)',   // cyan-500
  'rgb(59, 130, 246)',  // blue-500
  'rgb(147, 51, 234)',  // purple-500
  'rgb(236, 72, 153)',  // pink-500
  'rgb(168, 85, 247)',  // violet-500
  'rgb(20, 184, 166)',  // teal-500
] as const;

export function getBucketColor(bucketIndex: number): string {
  return BUCKET_COLORS[bucketIndex % BUCKET_COLORS.length];
}
