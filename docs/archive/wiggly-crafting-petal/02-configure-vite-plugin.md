# Configure Vite with TanStack Router Plugin

## Files to Modify/Create
- `web/frontend/vite.config.ts` (modify)

## Implementation Details

Add the TanStack Router plugin to Vite configuration. **Critical:** The plugin must be placed BEFORE the React plugin in the array.

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { TanStackRouterVite } from '@tanstack/router-plugin/vite'

export default defineConfig({
  plugins: [
    // Must be before react() so router plugin transforms files first
    TanStackRouterVite({
      target: 'react',
      autoCodeSplitting: true,
    }),
    react(),
  ],
})
```

### Configuration Options
- `target: 'react'` - Specifies React as the framework
- `autoCodeSplitting: true` - Enables automatic code splitting for routes

## Acceptance Criteria
- [ ] `TanStackRouterVite` import added
- [ ] Plugin placed before `react()` in plugins array
- [ ] Configuration includes `target` and `autoCodeSplitting` options
- [ ] Vite dev server starts without errors

## Dependencies
- Task 01 (packages must be installed first)
