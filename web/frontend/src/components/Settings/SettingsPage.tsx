import { useSearch, useNavigate } from '@tanstack/react-router';
import { YouTubeImportSection } from './YouTubeImportSection';
import { EmojiSettingsSection } from './EmojiSettingsSection';

type SettingsTab = 'youtube' | 'emoji';

export function SettingsPage() {
  const search = useSearch({ from: '/settings' });
  const navigate = useNavigate();
  const activeTab = (search.tab as SettingsTab) || 'youtube';

  const handleTabChange = (tab: SettingsTab) => {
    navigate({ to: '/settings', search: { tab } });
  };

  return (
    <div className="min-h-screen bg-black p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-white mb-2">Settings</h1>
          <p className="text-white/60">
            Manage your application settings and preferences
          </p>
        </div>

        {/* Tab Bar */}
        <div className="flex gap-2 border-b border-obsidian-border">
          <button
            onClick={() => handleTabChange('youtube')}
            className={`px-6 py-3 font-medium transition-colors relative ${
              activeTab === 'youtube'
                ? 'text-obsidian-accent'
                : 'text-white/60 hover:text-white'
            }`}
          >
            YouTube Import
            {activeTab === 'youtube' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-obsidian-accent" />
            )}
          </button>
          <button
            onClick={() => handleTabChange('emoji')}
            className={`px-6 py-3 font-medium transition-colors relative ${
              activeTab === 'emoji'
                ? 'text-obsidian-accent'
                : 'text-white/60 hover:text-white'
            }`}
          >
            Emoji Settings
            {activeTab === 'emoji' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-obsidian-accent" />
            )}
          </button>
        </div>

        {/* Content */}
        <div>
          {activeTab === 'youtube' ? <YouTubeImportSection /> : <EmojiSettingsSection />}
        </div>
      </div>
    </div>
  );
}
