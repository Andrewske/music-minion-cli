import { describe, expect, it } from 'vitest'
import {
  chatButtonOffset,
  deployLabel,
  relativeTime,
  shouldOfferReload,
  statusText,
  toolSummary,
} from './page-chat-view'

describe('chatButtonOffset', () => {
  it('clears the h-16 PlayerBar on normal routes', () => {
    expect(chatButtonOffset('/')).toBe('bottom-20')
    expect(chatButtonOffset('/comparison/42')).toBe('bottom-20')
  })

  it('clears the md:h-36 PlayerBar on /comparison', () => {
    expect(chatButtonOffset('/comparison')).toBe('bottom-20 md:bottom-40')
  })
})

describe('statusText', () => {
  it('says the desktop is waking when the send woke it', () => {
    expect(statusText('queued', 'waking')).toBe('Waking the desktop…')
    expect(statusText('ship_queued', 'online')).toBe('Waiting for the desktop…')
  })

  it('maps running and shipping, and is null when idle', () => {
    expect(statusText('running', null)).toBe('Working…')
    expect(statusText('shipping', null)).toBe('Shipping…')
    expect(statusText('idle', null)).toBeNull()
    expect(statusText('error', 'online')).toBeNull()
  })
})

describe('toolSummary', () => {
  it('shows a single tool as its line', () => {
    expect(toolSummary([{ name: 'Read', target: 'App.tsx' }])).toBe('Read App.tsx')
  })

  it('counts steps and shows the latest', () => {
    const tools = [
      { name: 'Read', target: 'App.tsx' },
      { name: 'Grep', target: 'PlayerBar' },
    ]
    expect(toolSummary(tools)).toBe('2 steps · Grep PlayerBar')
  })

  it('is empty for no tools', () => {
    expect(toolSummary([])).toBe('')
  })
})

describe('deployLabel', () => {
  it('labels each state', () => {
    expect(deployLabel({ repo: 'music-minion', state: 'checking', sha: null, detail: null })).toBe('Rebasing and running checks…')
    expect(deployLabel({ repo: 'music-minion', state: 'live', sha: 'abc1234', detail: null })).toBe('Live')
    expect(deployLabel({ repo: 'music-minion', state: 'failed', sha: null, detail: 'tsc failed' })).toBe('Ship failed')
  })

  it('distinguishes a pushed-but-unconfirmed failure', () => {
    expect(deployLabel({ repo: 'music-minion', state: 'failed', sha: 'abc1234', detail: null })).toBe('Pushed, deploy not confirmed')
  })
})

describe('shouldOfferReload', () => {
  it('offers a reload only for deploys newer than the page load', () => {
    expect(shouldOfferReload(null, 1000)).toBe(false)
    expect(shouldOfferReload(900, 1000)).toBe(false)
    expect(shouldOfferReload(1100, 1000)).toBe(true)
  })
})

describe('relativeTime', () => {
  const now = Date.parse('2026-10-17T12:00:00Z')

  it('formats minutes, hours and days', () => {
    expect(relativeTime('2026-10-17T11:59:30Z', now)).toBe('just now')
    expect(relativeTime('2026-10-17T11:55:00Z', now)).toBe('5m ago')
    expect(relativeTime('2026-10-17T09:00:00Z', now)).toBe('3h ago')
    expect(relativeTime('2026-10-15T12:00:00Z', now)).toBe('2d ago')
  })

  it('returns empty for an unparseable date', () => {
    expect(relativeTime('not a date', now)).toBe('')
  })
})
