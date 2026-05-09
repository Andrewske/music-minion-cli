import { createFileRoute } from '@tanstack/react-router';
import { SettingsPage } from '../components/Settings/SettingsPage';

type SettingsSearch = {
  tab?: 'youtube' | 'emoji' | 'soundcloud' | 'genres' | 'matching';
};

export const Route = createFileRoute('/settings')({
  component: SettingsPage,
  validateSearch: (search: Record<string, unknown>): SettingsSearch => {
    const tab = search.tab;
    if (tab === 'emoji' || tab === 'soundcloud' || tab === 'genres' || tab === 'matching') {
      return { tab };
    }
    return { tab: 'youtube' };
  },
});
