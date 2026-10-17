import Markdown, { type Components } from 'react-markdown'

/* react-markdown ignores raw HTML by default, so agent replies can't inject markup. */
const COMPONENTS: Components = {
  p: ({ children }) => <p className="leading-relaxed">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-obsidian-accent underline underline-offset-2">
      {children}
    </a>
  ),
  ul: ({ children }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
  h1: ({ children }) => <p className="pt-1 font-semibold text-white">{children}</p>,
  h2: ({ children }) => <p className="pt-1 font-semibold text-white">{children}</p>,
  h3: ({ children }) => <p className="pt-1 font-semibold text-white">{children}</p>,
  code: ({ children }) => <code className="bg-obsidian-border px-1 font-sf-mono text-[13px] text-white/90">{children}</code>,
  pre: ({ children }) => (
    <pre className="overflow-x-auto border border-obsidian-border bg-obsidian-surface p-2 font-sf-mono text-xs [&_code]:bg-transparent [&_code]:p-0">
      {children}
    </pre>
  ),
}

/** Renders an agent reply's markdown with the obsidian palette. */
export function ChatMarkdown({ text }: { text: string }): JSX.Element {
  return (
    <div className="space-y-2">
      <Markdown components={COMPONENTS}>{text}</Markdown>
    </div>
  )
}
