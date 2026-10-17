import { AlertCircle, Info, Wrench } from 'lucide-react'
import { toolLine, usePageChatClient, type ChatItem } from 'page-chat-core'
import { ChatMarkdown } from './ChatMarkdown'
import { DeployRows, ShipCard } from './ShipItems'
import { toolSummary } from './page-chat-view'

function UserBubble({ item }: { item: Extract<ChatItem, { type: 'user' }> }): JSX.Element {
  const { screenshotUrl } = usePageChatClient()
  return (
    <div className="ml-10 space-y-2 self-end bg-obsidian-border px-4 py-3 text-[15px] text-white/90">
      {item.screenshotId !== null && (
        <a href={screenshotUrl(item.screenshotId)} target="_blank" rel="noreferrer">
          <img
            src={screenshotUrl(item.screenshotId)}
            alt="Screenshot attached to this message"
            className="max-h-32 w-auto border border-white/10"
          />
        </a>
      )}
      <p className="whitespace-pre-wrap">{item.text}</p>
    </div>
  )
}

function ToolBlock({ item }: { item: Extract<ChatItem, { type: 'tools' }> }): JSX.Element {
  return (
    <details className="text-xs text-white/40">
      <summary className="flex cursor-pointer list-none items-center gap-1.5">
        <Wrench className="h-3 w-3 shrink-0" />
        <span className="truncate">{toolSummary(item.tools)}</span>
      </summary>
      <ul className="mt-1 space-y-0.5 pl-[18px] font-sf-mono">
        {item.tools.map((tool, i) => (
          <li key={i} className="truncate">{toolLine(tool)}</li>
        ))}
      </ul>
    </details>
  )
}

function Note({ text, error }: { text: string; error: boolean }): JSX.Element {
  const Icon = error ? AlertCircle : Info
  return (
    <p className={`flex gap-2 text-[13px] ${error ? 'text-red-400' : 'text-white/40'}`}>
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span className="whitespace-pre-wrap">{text}</span>
    </p>
  )
}

interface ChatItemViewProps {
  item: ChatItem
  shippableId: number | null
  onShip: () => void
}

export function ChatItemView({ item, shippableId, onShip }: ChatItemViewProps): JSX.Element {
  switch (item.type) {
    case 'user':
      return <UserBubble item={item} />
    case 'reply':
      return (
        <div className="mr-4 text-[15px] text-white/80">
          <ChatMarkdown text={item.text} />
        </div>
      )
    case 'tools':
      return <ToolBlock item={item} />
    case 'error':
      return <Note text={item.text} error />
    case 'system':
      return <Note text={item.text} error={false} />
    case 'ship':
      return <ShipCard repos={item.repos} shippable={item.id === shippableId} onShip={onShip} />
    case 'deploys':
      return <DeployRows steps={item.steps} />
  }
}
