import { createFileRoute } from '@tanstack/react-router';
import { FeedPage } from '../components/feed/FeedPage';

export type FeedSearch = {
  top200?: boolean;
  inLibrary?: boolean;
};

export const Route = createFileRoute('/feed')({
  component: FeedPage,
  validateSearch: (search: Record<string, unknown>): FeedSearch => ({
    top200: search.top200 === true || search.top200 === 'true' || undefined,
    inLibrary: search.inLibrary === true || search.inLibrary === 'true' || undefined,
  }),
});
