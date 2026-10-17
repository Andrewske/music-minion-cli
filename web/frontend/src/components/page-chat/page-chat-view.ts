/* Pure view helpers for the page-chat widget. No React, so they're unit-testable. */
import { toolLine, type DeployMeta, type DeployState, type DesktopState, type ThreadStatus, type ToolMeta } from 'page-chat-core'

/** The dashboard section (and runner repo) that owns music-minion threads. */
export const PAGE_CHAT_SECTION = 'music-minion'
/** Repo whose live deploy means this page is running an old build. */
export const PAGE_CHAT_REPO = 'music-minion'
/** sessionStorage key: the sheet reopens after a reload (e.g. a deploy refresh). */
export const OPEN_STORAGE_KEY = 'page-chat:open'

/**
 * Bottom offset for the floating button. Mirrors PlayerBar's height rule:
 * h-16 everywhere, md:h-36 on /comparison (waveform row). Keeps a 1rem gap above it.
 */
export function chatButtonOffset(pathname: string): string {
  return pathname === '/comparison' ? 'bottom-20 md:bottom-40' : 'bottom-20'
}

/** Header subtitle while the thread is busy; null when idle. */
export function statusText(status: ThreadStatus, desktop: DesktopState | null): string | null {
  const waiting = desktop === 'waking' ? 'Waking the desktop…' : 'Waiting for the desktop…'
  if (status === 'queued' || status === 'ship_queued') return waiting
  if (status === 'running') return 'Working…'
  if (status === 'shipping') return 'Shipping…'
  return null
}

/** Collapsed label for a run of tool calls: one line, or "N steps · last". */
export function toolSummary(tools: readonly ToolMeta[]): string {
  const last = tools[tools.length - 1]
  if (!last) return ''
  return tools.length === 1 ? toolLine(last) : `${tools.length} steps · ${toolLine(last)}`
}

const STATE_LABEL: Record<DeployState, string> = {
  checking: 'Rebasing and running checks…',
  pushed: 'Pushed, deploying to the Pi…',
  live: 'Live',
  failed: 'Ship failed',
}

/** A failed step that carries a sha was pushed, but the Pi's deploy didn't confirm. */
export function deployLabel(step: DeployMeta): string {
  return step.state === 'failed' && step.sha ? 'Pushed, deploy not confirmed' : STATE_LABEL[step.state]
}

/** Offer a reload only for a deploy that went live after this page loaded. */
export function shouldOfferReload(wentLiveAt: number | null, pageLoadedAt: number): boolean {
  return wentLiveAt !== null && wentLiveAt > pageLoadedAt
}

const UNITS: readonly [number, string][] = [
  [86_400_000, 'd'],
  [3_600_000, 'h'],
  [60_000, 'm'],
]

/** Compact age for the history list: "just now", "5m ago", "3h ago", "2d ago". */
export function relativeTime(iso: string, now: number): string {
  const elapsed = now - Date.parse(iso)
  if (Number.isNaN(elapsed)) return ''
  const unit = UNITS.find(([ms]) => elapsed >= ms)
  return unit ? `${Math.floor(elapsed / unit[0])}${unit[1]} ago` : 'just now'
}
