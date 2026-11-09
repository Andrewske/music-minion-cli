import { createFileRoute } from '@tanstack/react-router';
import { StoriesPage } from '../components/stories/StoriesPage';

export const Route = createFileRoute('/stories')({
  component: StoriesPage,
});
