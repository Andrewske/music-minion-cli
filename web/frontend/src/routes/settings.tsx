import { createFileRoute } from '@tanstack/react-router';
import { SettingsPage } from '../components/Settings/SettingsPage';

type SettingsSearch = {
  tab?: 'youtube' | 'emoji';
};

export const Route = createFileRoute('/settings')({
  component: SettingsPage,
  validateSearch: (search: Record<string, unknown>): SettingsSearch => {
    return {
      tab: search.tab === 'emoji' ? 'emoji' : 'youtube',
    };
  },
});
