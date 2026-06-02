"use client"

import { useState } from "react"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism"

interface Props {
  language?: string
  children: string
}

export function CodeBlock({ language = "sql", children }: Props) {
  const [copied, setCopied] = useState(false)

  function copy() {
    navigator.clipboard.writeText(children.trim()).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }).catch(() => {/* silent — clipboard may be unavailable */})
  }

  return (
    <div className="relative group">
      <SyntaxHighlighter
        language={language}
        style={oneDark}
        customStyle={{ borderRadius: "0.5rem", fontSize: "0.75rem", margin: 0 }}
        wrapLongLines
      >
        {children.trim()}
      </SyntaxHighlighter>
      <button
        onClick={copy}
        className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity px-2 py-0.5 rounded text-[10px] bg-white/10 text-white hover:bg-white/20 font-mono"
      >
        {copied ? "Copied!" : "Copy"}
      </button>
    </div>
  )
}
