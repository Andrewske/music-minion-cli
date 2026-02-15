import { createRootRoute, Link, Outlet, useRouterState } from '@tanstack/react-router'
import { TanStackRouterDevtools } from '@tanstack/react-router-devtools'
import { useSyncWebSocket } from '../hooks/useSyncWebSocket'
import { PlayerBar } from '../components/player/PlayerBar'

function NavButton({
  to,
  children,
}: {
  to: string
  children: React.ReactNode
}): JSX.Element {
  const routerState = useRouterState()
  const isActive = routerState.location.pathname === to

  return (
    <Link
      to={to}
      className={
        'px-4 py-2 text-sm font-medium tracking-wider transition-colors border-b-2 ' +
        (isActive
          ? 'border-obsidian-accent text-obsidian-accent'
          : 'border-transparent text-white/60 hover:text-white/90')
      }
    >
      {children}
    </Link>
  )
}

function RootComponent(): JSX.Element {
  useSyncWebSocket() // Connect to sync WebSocket for real-time updates

  return (
    <div className="min-h-screen bg-black pb-20">{/* Account for 64px player bar + margin */}

      {/* Navigation */}
      <nav className="border-b border-obsidian-border px-6 py-3">
        <div className="flex items-center gap-2">
          <NavButton to="/">Home</NavButton>
          <NavButton to="/history">History</NavButton>
          <NavButton to="/comparison">Ranking</NavButton>
          <NavButton to="/playlist-builder">Playlists</NavButton>
          <NavButton to="/youtube">YouTube</NavButton>
          <NavButton to="/emoji-settings">Emojis</NavButton>
        </div>
      </nav>

      {/* Content */}
      <Outlet />

      {/* Player bar - persists across all pages */}
      <PlayerBar />

      {/* Dev tools */}
      {import.meta.env.DEV && <TanStackRouterDevtools />}
    </div>
  )
}

export const Route = createRootRoute({
  component: RootComponent,
})
