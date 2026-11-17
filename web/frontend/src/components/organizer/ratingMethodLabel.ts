import type { BucketRatingPreview } from '../../api/buckets';

/** One-line explanation of how the preview's ratings were derived. */
export function methodLabel(preview: BucketRatingPreview): string {
  if (preview.method === 'redistribute') return "Re-deals this bucket's current ratings in your order.";
  const afters = preview.rows.map((r) => r.after);
  return `Unrated bucket: spread ${Math.round(Math.max(...afters))} to ${Math.round(Math.min(...afters))}.`;
}
