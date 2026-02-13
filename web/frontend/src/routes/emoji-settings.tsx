import { createFileRoute } from '@tanstack/react-router';
import { EmojiSettings } from '../components/EmojiSettings';

function EmojiSettingsPage(): JSX.Element {
  return <EmojiSettings />;
}

export const Route = createFileRoute('/emoji-settings')({
  component: EmojiSettingsPage,
});
