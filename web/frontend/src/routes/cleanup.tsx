import { createFileRoute } from '@tanstack/react-router';
import { TagReviewPage } from '../components/cleanup/TagReviewPage';

export const Route = createFileRoute('/cleanup')({
  component: TagReviewPage,
});
