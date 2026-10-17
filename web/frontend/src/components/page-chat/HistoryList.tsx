import { useState } from 'react'
import { Rocket } from 'lucide-react'
import { isBusy, usePageChatHistory, type ThreadListItem } from 'page-chat-core'
import { cn } from '../../lib/utils'
import { relativeTime } from './page-chat-view'

interface RowProps {
  thread: ThreadListItem
  current: boolean
  now: number
  onOpen: (id: string) => void
}

function HistoryRow({ thread, current, now, onOpen }: RowProps): JSX.Element {
  return (
    <li>
      <button
        type="button"
        onClick={() => onOpen(thread.id)}
        className={cn('w-full space-y-1 px-3 py-2.5 text-left transition-colors hover:bg-obsidian-border', current && 'bg-obsidian-border')}
      >
        <p className="line-clamp-2 text-sm text-white/90">{thread.preview || '(no messages)'}</p>
        <p className="flex items-center gap-2 text-xs text-white/40">
          <span>{relativeTime(thread.updatedAt, now)}</span>
          {thread.originPath !== '/' && <span className="truncate font-sf-mono">{thread.originPath}</span>}
          {thread.shipped && (
            <span className="flex items-center gap-1 text-obsidian-accent">
              <Rocket className="h-3 w-3" /> shipped
            </span>
          )}
          {isBusy(thread.status) && <span className="animate-pulse">working</span>}
        </p>
      </button>
    </li>
  )
}

interface HistoryListProps {
  sectionId: string
  currentId: string | null
  onOpen: (id: string) => void
}

/** Past music-minion conversations; tapping one reopens it. */
export function HistoryList({ sectionId, currentId, onOpen }: HistoryListProps): JSX.Element {
  const history = usePageChatHistory(sectionId, true)
  const [now] = useState(() => Date.now())
  if (history.isLoading) return <div className="h-40 w-full animate-pulse bg-obsidian-border" />
  if (history.isError) return <p className="text-[13px] text-red-400">{history.error.message}</p>
  const threads = history.data ?? []
  if (threads.length === 0) return <p className="m-auto text-sm text-white/40">No conversations here yet.</p>
  return (
    <ul className="space-y-1">
      {threads.map((t) => (
        <HistoryRow key={t.id} thread={t} current={t.id === currentId} now={now} onOpen={onOpen} />
      ))}
    </ul>
  )
}
