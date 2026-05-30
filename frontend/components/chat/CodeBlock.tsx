"use client"

import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism"

interface Props {
  language?: string
  children: string
}

export function CodeBlock({ language = "sql", children }: Props) {
  return (
    <SyntaxHighlighter
      language={language}
      style={oneDark}
      customStyle={{ borderRadius: "0.5rem", fontSize: "0.75rem", margin: 0 }}
      wrapLongLines
    >
      {children.trim()}
    </SyntaxHighlighter>
  )
}
