---
task: 03-frontend-settings-tab
status: done
depends:
  - 02-backend-soundcloud-api
files:
  - path: web/frontend/src/routes/settings.tsx
    action: modify
  - path: web/frontend/src/components/Settings/SettingsPage.tsx
    action: modify
---

# Frontend: Settings Tab Integration

## Context
Add a "SoundCloud" tab to the existing Settings page alongside YouTube and Emoji tabs. This is a small integration task that sets up the routing for the import wizard.

## Files to Modify/Create
- `web/frontend/src/routes/settings.tsx` (modify)
- `web/frontend/src/components/Settings/SettingsPage.tsx` (modify)

## Implementation Details

### Route Update (settings.tsx)

Update the `SettingsSearch` type to include `'soundcloud'`:

```typescript
type SettingsSearch = {
  tab?: 'youtube' | 'emoji' | 'soundcloud';
};

export const Route = createFileRoute('/settings')({
  component: SettingsPage,
  validateSearch: (search: Record<string, unknown>): SettingsSearch => {
    const tab = search.tab;
    if (tab === 'emoji' || tab === 'soundcloud') {
      return { tab };
    }
    return { tab: 'youtube' };
  },
});
```

### SettingsPage Component Update

Add "SoundCloud" tab button and conditional rendering:

```tsx
// Tab buttons (alongside YouTube and Emoji)
<button
  onClick={() => navigate({ search: { tab: 'soundcloud' } })}
  className={tab === 'soundcloud' ? 'active' : ''}
>
  SoundCloud
</button>

// Tab content
{tab === 'soundcloud' && <SoundCloudImportSection />}
```

Import the new component (created in next task):
```tsx
import { SoundCloudImportSection } from './SoundCloudImportSection';
```

## Verification

1. Navigate to `/settings?tab=soundcloud`
2. "SoundCloud" tab should be visible and clickable
3. Tab should show active state when selected
4. Content area should render (will be empty/placeholder until next task)
