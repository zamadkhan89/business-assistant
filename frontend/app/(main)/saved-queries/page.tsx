"use client"

import { useCallback, useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import Link from "next/link"
import {
  Bookmark, Trash2, Play, ChevronDown, ChevronRight,
  MessageSquare, Search, Table2, Loader2,
  RefreshCw, BarChart2,
} from "lucide-react"
import { ChartMessage } from "@/components/chat/ChartMessage"

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

interface SavedQuery {
  id: string
  name: string
  question: string
  sql: string
  datasets: string[]
  results: Record<string, unknown>[]
  created_at: string
}

interface RunResult { results: Record<string, unknown>[]; chart_json: string; row_count: number }

export default function SavedQueriesPage() {
  const { data: session } = useSession()
  const [queries,    setQueries]    = useState<SavedQuery[]>([])
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [search,     setSearch]     = useState("")
  const [runningId,  setRunningId]  = useState<string | null>(null)
  const [runResults, setRunResults] = useState<Record<string, RunResult>>({})

  const authHeader = { Authorization: `Bearer ${session?.accessToken}` }

  const fetchQueries = useCallback(async () => {
    if (!session?.accessToken) return
    setLoading(true)
    try {
      const r = await fetch(`${BACKEND}/api/saved-queries`, { headers: authHeader })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setQueries(await r.json())
    } catch (err) {
      setError(`Failed to load saved queries: ${err instanceof Error ? err.message : err}`)
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  useEffect(() => { fetchQueries() }, [fetchQueries])

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Delete "${name}"?`)) return
    try {
      const r = await fetch(`${BACKEND}/api/saved-queries/${id}`, {
        method: "DELETE",
        headers: authHeader,
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setQueries((prev) => prev.filter((q) => q.id !== id))
    } catch (err) {
      setError(`Delete failed: ${err instanceof Error ? err.message : err}`)
    }
  }

  async function handleRun(q: SavedQuery) {
    setRunningId(q.id)
    setExpandedId(q.id)
    setError(null)
    try {
      const r = await fetch(`${BACKEND}/api/saved-queries/${q.id}/run`, {
        method: "POST",
        headers: authHeader,
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
      setRunResults(prev => ({ ...prev, [q.id]: d }))
    } catch (err) {
      setError(`Run failed: ${err instanceof Error ? err.message : err}`)
    } finally {
      setRunningId(null)
    }
  }

  const filtered = queries.filter(
    (q) =>
      q.name.toLowerCase().includes(search.toLowerCase()) ||
      q.question.toLowerCase().includes(search.toLowerCase()),
  )

  return (
    <div className="min-h-screen bg-background">
      <div className="page-header flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="size-9 rounded-xl gradient-primary flex items-center justify-center shadow-sm">
            <Bookmark className="size-4 text-white" />
          </div>
          <div>
            <h1 className="page-title">Saved Queries</h1>
            <p className="page-subtitle">{queries.length} saved question{queries.length !== 1 ? "s" : ""}</p>
          </div>
        </div>
      </div>

      <div className="max-w-4xl mx-auto p-6 space-y-4">
        {queries.length > 3 && (
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search saved queries…"
              className="input-modern pl-9"
            />
          </div>
        )}

        {error && (
          <div className="rounded-xl px-4 py-3 bg-destructive/10 border border-destructive/20 text-sm text-destructive">
            {error}
          </div>
        )}

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="card-elevated h-20 animate-pulse" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">
              <Bookmark className="size-6" />
            </div>
            <div>
              <p className="font-semibold text-foreground">
                {search ? "No results match your search" : "No saved queries yet"}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {search
                  ? "Try a different search term"
                  : "Save a question from the chat to see it here"}
              </p>
            </div>
            {!search && (
              <Link href="/chat" className="btn-primary">
                <MessageSquare className="size-4" /> Go to Chat
              </Link>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((q) => {
              const expanded  = expandedId === q.id
              const isRunning = runningId === q.id
              const liveResult = runResults[q.id]
              const displayResults = liveResult ? liveResult.results : (q.results ?? [])
              const displayChart   = liveResult ? liveResult.chart_json : ""
              const cols = displayResults.length > 0 ? Object.keys(displayResults[0]) : []
              return (
                <div key={q.id} className="card-elevated animate-fade-in">
                  <div className="flex items-center gap-3 px-4 py-3">
                    <button
                      onClick={() => setExpandedId(expanded ? null : q.id)}
                      className="flex-1 flex items-center gap-3 text-left min-w-0"
                    >
                      <div className="size-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                        <Bookmark className="size-3.5 text-primary" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="font-semibold text-sm truncate">{q.name}</p>
                        {q.question && q.question !== q.name && (
                          <p className="text-xs text-muted-foreground truncate mt-0.5">{q.question}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {displayResults.length > 0 && (
                          <span className="flex items-center gap-1 text-[10px] text-muted-foreground/60">
                            <Table2 className="size-3" />{displayResults.length} rows
                          </span>
                        )}
                        <span className="text-[11px] text-muted-foreground/60">
                          {new Date(q.created_at).toLocaleDateString()}
                        </span>
                        {expanded
                          ? <ChevronDown className="size-4 text-muted-foreground" />
                          : <ChevronRight className="size-4 text-muted-foreground" />}
                      </div>
                    </button>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => handleRun(q)}
                        disabled={!!runningId}
                        className="btn-primary py-1.5 px-3 text-xs"
                        title="Run query and show results here"
                      >
                        {isRunning
                          ? <><Loader2 className="size-3 animate-spin" /> Running…</>
                          : liveResult
                          ? <><RefreshCw className="size-3" /> Re-run</>
                          : <><Play className="size-3" /> Run</>}
                      </button>
                      <button
                        onClick={() => handleDelete(q.id, q.name)}
                        className="btn-danger py-1.5 px-2 text-xs"
                        title="Delete"
                      >
                        <Trash2 className="size-3" />
                      </button>
                    </div>
                  </div>

                  {isRunning && (
                    <div className="border-t border-border px-4 py-3 flex items-center gap-2.5 text-sm text-muted-foreground">
                      <Loader2 className="size-4 animate-spin text-primary" />
                      Running query…
                    </div>
                  )}

                  {expanded && !isRunning && (
                    <div className="border-t border-border mx-4 pt-3 pb-4 space-y-3 animate-fade-in">
                      {/* Live chart result */}
                      {displayChart && (
                        <div>
                          <p className="section-label mb-2 flex items-center gap-1.5">
                            <BarChart2 className="size-3.5" /> Chart
                          </p>
                          <ChartMessage chartJson={displayChart} />
                        </div>
                      )}

                      {/* Results table */}
                      {displayResults.length > 0 && cols.length > 0 && (
                        <div>
                          <p className="section-label mb-1.5">Results ({displayResults.length} rows{liveResult ? " · fresh" : " · saved"})</p>
                          <div className="overflow-x-auto max-h-64 rounded-lg border border-border">
                            <table className="w-full text-xs border-collapse">
                              <thead className="sticky top-0 bg-muted/80 backdrop-blur-sm">
                                <tr>
                                  {cols.map((c) => (
                                    <th key={c} className="px-3 py-2 text-left font-semibold border-b border-border whitespace-nowrap">{c}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {displayResults.slice(0, 100).map((row, ri) => (
                                  <tr key={ri} className="row-interactive border-b border-border/30 last:border-0">
                                    {cols.map((c) => (
                                      <td key={c} className="px-3 py-1.5 whitespace-nowrap">
                                        {typeof row[c] === "number"
                                          ? <span className="font-mono tabular-nums">{(row[c] as number).toLocaleString()}</span>
                                          : String(row[c] ?? "")}
                                      </td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}

                      {/* Datasets */}
                      {q.datasets && q.datasets.length > 0 && (
                        <div>
                          <p className="section-label mb-1.5">Datasets</p>
                          <div className="flex flex-wrap gap-1.5">
                            {q.datasets.map((d) => (
                              <span key={d} className="badge-info text-[11px] px-2 py-0.5 rounded-full font-medium">{d}</span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* SQL */}
                      {q.sql && (
                        <div>
                          <div className="flex items-center justify-between mb-1.5">
                            <p className="section-label">SQL</p>
                            <button onClick={() => navigator.clipboard.writeText(q.sql)} className="text-[10px] text-muted-foreground hover:text-primary transition-colors">Copy</button>
                          </div>
                          <pre className="bg-muted/60 rounded-lg px-3 py-2.5 text-xs font-mono overflow-x-auto text-foreground/80 leading-relaxed">{q.sql}</pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
