"use client"

import dynamic from "next/dynamic"
import { Bot } from "lucide-react"
import { ChartMessage } from "./ChartMessage"

const CodeBlock = dynamic(
  () => import("./CodeBlock").then((m) => ({ default: m.CodeBlock })),
  { ssr: false, loading: () => <div className="bg-muted/60 rounded-lg p-3 text-xs font-mono animate-pulse">Loading…</div> }
)

interface Props {
  role: "user" | "assistant"
  content: string
  chartJson?: string
  userInitial?: string
}

function parseInline(text: string, key: string): React.ReactNode {
  const result: React.ReactNode[] = []
  const regex = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`)/g
  let last = 0
  let m
  while ((m = regex.exec(text)) !== null) {
    if (m.index > last) result.push(text.slice(last, m.index))
    const s = m[0]
    if (s.startsWith("**"))
      result.push(<strong key={`${key}-${m.index}`} className="font-semibold">{s.slice(2, -2)}</strong>)
    else if (s.startsWith("*"))
      result.push(<em key={`${key}-${m.index}`}>{s.slice(1, -1)}</em>)
    else
      result.push(
        <code key={`${key}-${m.index}`} className="px-1 py-0.5 rounded bg-black/10 dark:bg-white/10 font-mono text-[0.8em]">
          {s.slice(1, -1)}
        </code>
      )
    last = m.index + s.length
  }
  if (last < text.length) result.push(text.slice(last))
  return <>{result}</>
}

function renderTextBlock(text: string, baseKey: number): React.ReactNode {
  const lines = text.split("\n")
  const nodes: React.ReactNode[] = []
  const listItems: React.ReactNode[] = []
  let listType: "ul" | "ol" | null = null

  function flushList() {
    if (!listItems.length) return
    const key = `list-${baseKey}-${nodes.length}`
    if (listType === "ul")
      nodes.push(<ul key={key} className="list-disc list-inside space-y-0.5 my-1 ml-1">{[...listItems]}</ul>)
    else
      nodes.push(<ol key={key} className="list-decimal list-inside space-y-0.5 my-1 ml-1">{[...listItems]}</ol>)
    listItems.length = 0
    listType = null
  }

  lines.forEach((line, i) => {
    const trimmed = line.trim()
    if (!trimmed) { flushList(); return }

    const ulMatch = trimmed.match(/^[-*•]\s+(.+)/)
    if (ulMatch) {
      if (listType !== "ul") { flushList(); listType = "ul" }
      listItems.push(<li key={i}>{parseInline(ulMatch[1], `${baseKey}-${i}`)}</li>)
      return
    }

    const olMatch = trimmed.match(/^\d+\.\s+(.+)/)
    if (olMatch) {
      if (listType !== "ol") { flushList(); listType = "ol" }
      listItems.push(<li key={i}>{parseInline(olMatch[1], `${baseKey}-${i}`)}</li>)
      return
    }

    flushList()

    const hMatch = trimmed.match(/^#{1,3}\s+(.+)/)
    if (hMatch) {
      nodes.push(<p key={i} className="font-semibold mt-2">{parseInline(hMatch[1], `${baseKey}-${i}`)}</p>)
      return
    }

    nodes.push(<p key={i} className="leading-relaxed">{parseInline(trimmed, `${baseKey}-${i}`)}</p>)
  })

  flushList()
  return <div key={baseKey} className="space-y-1">{nodes}</div>
}

function renderContent(content: string): React.ReactNode[] {
  const parts: React.ReactNode[] = []
  const CODE_FENCE = /```(\w*)\n?([\s\S]*?)```/g
  let lastIdx = 0
  let match: RegExpExecArray | null

  CODE_FENCE.lastIndex = 0
  while ((match = CODE_FENCE.exec(content)) !== null) {
    if (match.index > lastIdx)
      parts.push(renderTextBlock(content.slice(lastIdx, match.index), lastIdx))
    parts.push(<CodeBlock key={match.index} language={match[1] || "text"}>{match[2]}</CodeBlock>)
    lastIdx = match.index + match[0].length
  }

  if (lastIdx < content.length)
    parts.push(renderTextBlock(content.slice(lastIdx), lastIdx))

  return parts
}

export function MessageBubble({ role, content, chartJson, userInitial }: Props) {
  const isUser = role === "user"

  if (isUser) {
    return (
      <div className="flex items-end justify-end gap-2">
        <div className="rounded-2xl rounded-br-sm px-4 py-2.5 max-w-[78%] text-sm bg-primary text-primary-foreground leading-relaxed">
          {content}
        </div>
        <div className="size-7 rounded-full bg-primary/20 text-primary flex items-center justify-center text-xs font-semibold shrink-0 mb-0.5">
          {userInitial ?? "U"}
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-2">
      <div className="size-7 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-0.5">
        <Bot className="size-3.5" />
      </div>
      <div className="rounded-2xl rounded-tl-sm px-4 py-2.5 max-w-[82%] text-sm bg-muted text-foreground space-y-2 leading-relaxed">
        {content && <div className="space-y-1">{renderContent(content)}</div>}
        {chartJson && <ChartMessage chartJson={chartJson} />}
      </div>
    </div>
  )
}
