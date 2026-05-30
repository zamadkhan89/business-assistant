"use client"

import { useCallback, useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import {
  Calendar, Play, Plus, Trash2, Edit2, X,
  ChevronDown, ChevronRight, Loader2,
  CheckCircle2, AlertCircle, Table2, Code, BarChart2,
} from "lucide-react"
import { ChartMessage } from "@/components/chat/ChartMessage"

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

interface Routine {
  id: string
  name: string
  questions: string[]
  created_at: string
}

interface RoutineResult {
  question: string
  content: string
  chart_json: string
  query_results: Record<string, unknown>[]
  executed_sql: string
  error: string
}

// ── Single result card ─────────────────────────────────────────────────────

function ResultItem({ item }: { item: RoutineResult }) {
  const [showSql, setShowSql] = useState(false)
  const [showTable, setShowTable] = useState(false)
  const cols = item.query_results.length > 0 ? Object.keys(item.query_results[0]) : []

  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <div className="flex items-start gap-2.5 px-4 py-3 bg-muted/30">
        {item.error ? (
          <AlertCircle className="size-4 text-destructive shrink-0 mt-0.5" />
        ) : (
          <CheckCircle2 className="size-4 text-emerald-500 shrink-0 mt-0.5" />
        )}
        <p className="text-sm font-medium">{item.question}</p>
      </div>
      <div className="px-4 py-3 space-y-3">
        {item.error ? (
          <p className="text-sm text-destructive">{item.error}</p>
        ) : (
          <>
            <p className="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
              {item.content}
            </p>

            {item.chart_json && (
              <div>
                <button
                  onClick={() => setShowTable(v => !v)}
                  className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors mb-2"
                >
                  <BarChart2 className="size-3.5" /> Chart
                </button>
                <ChartMessage chartJson={item.chart_json} />
              </div>
            )}

            {item.query_results.length > 0 && (
              <div>
                <button
                  onClick={() => setShowTable((v) => !v)}
                  className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors"
                >
                  <Table2 className="size-3.5" />
                  {showTable ? "Hide" : "Show"} table ({item.query_results.length} rows)
                  {showTable ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
                </button>
                {showTable && (
                  <div className="mt-2 rounded-lg border border-border overflow-x-auto max-h-52">
                    <table className="w-full text-xs">
                      <thead className="bg-muted/50 sticky top-0">
                        <tr>
                          {cols.map((c) => (
                            <th key={c} className="px-3 py-1.5 text-left font-medium text-muted-foreground max-w-35 truncate">
                              {c}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {item.query_results.slice(0, 50).map((row, i) => (
                          <tr key={i} className="border-t border-border/50 hover:bg-muted/30">
                            {cols.map((c) => (
                              <td key={c} className="px-3 py-1.5 text-muted-foreground max-w-35 truncate">
                                {String(row[c] ?? "")}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {item.executed_sql && (
              <div>
                <button
                  onClick={() => setShowSql((v) => !v)}
                  className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors"
                >
                  <Code className="size-3.5" />
                  {showSql ? "Hide" : "View"} SQL
                  {showSql ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
                </button>
                {showSql && (
                  <pre className="mt-2 bg-muted/60 rounded-lg px-3 py-2.5 text-xs font-mono overflow-x-auto text-foreground/80 leading-relaxed">
                    {item.executed_sql}
                  </pre>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ── Create / Edit modal ────────────────────────────────────────────────────

function RoutineModal({
  initial,
  onSave,
  onClose,
}: {
  initial?: Routine
  onSave: (name: string, questions: string[]) => Promise<void>
  onClose: () => void
}) {
  const [name, setName] = useState(initial?.name ?? "")
  const [questions, setQuestions] = useState<string[]>(
    initial?.questions.length ? initial.questions : [""],
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function addQuestion() {
    setQuestions((prev) => [...prev, ""])
  }

  function updateQuestion(idx: number, val: string) {
    setQuestions((prev) => prev.map((q, i) => (i === idx ? val : q)))
  }

  function removeQuestion(idx: number) {
    if (questions.length <= 1) return
    setQuestions((prev) => prev.filter((_, i) => i !== idx))
  }

  async function handleSave() {
    const trimName = name.trim()
    const trimQs = questions.map((q) => q.trim()).filter(Boolean)
    if (!trimName) { setError("Name is required"); return }
    if (trimQs.length === 0) { setError("Add at least one question"); return }
    setSaving(true)
    setError(null)
    try {
      await onSave(trimName, trimQs)
    } catch (err) {
      setError(`Save failed: ${err instanceof Error ? err.message : err}`)
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
      <div className="bg-card border border-border rounded-2xl shadow-2xl w-full max-w-lg animate-scale-in">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="font-bold text-base">{initial ? "Edit Routine" : "New Routine"}</h2>
          <button onClick={onClose} className="btn-ghost p-1.5">
            <X className="size-4" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4 max-h-[60vh] overflow-y-auto">
          <div>
            <label className="section-label block mb-1.5">Routine name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Daily Sales Summary"
              className="input-modern"
              autoFocus
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="section-label">Questions ({questions.length})</label>
              <button
                onClick={addQuestion}
                className="text-[11px] text-primary hover:text-primary/80 flex items-center gap-1 transition-colors"
              >
                <Plus className="size-3" /> Add question
              </button>
            </div>
            <div className="space-y-2">
              {questions.map((q, idx) => (
                <div key={idx} className="flex gap-2 items-start">
                  <span className="text-xs text-muted-foreground/60 font-mono w-5 shrink-0 pt-2.5 text-right">
                    {idx + 1}.
                  </span>
                  <textarea
                    value={q}
                    onChange={(e) => updateQuestion(idx, e.target.value)}
                    placeholder={`Question ${idx + 1}`}
                    rows={2}
                    className="input-modern resize-none flex-1"
                  />
                  {questions.length > 1 && (
                    <button
                      onClick={() => removeQuestion(idx)}
                      className="btn-ghost p-1.5 mt-0.5 text-muted-foreground hover:text-destructive"
                    >
                      <X className="size-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-border">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={handleSave} disabled={saving} className="btn-primary">
            {saving ? (
              <><Loader2 className="size-3.5 animate-spin" /> Saving…</>
            ) : (
              "Save routine"
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function RoutinesPage() {
  const { data: session } = useSession()
  const [routines, setRoutines] = useState<Routine[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [modal, setModal] = useState<{ open: boolean; routine?: Routine }>({ open: false })
  const [runningId, setRunningId] = useState<string | null>(null)
  const [results, setResults] = useState<Record<string, RoutineResult[]>>({})
  const [expandedId, setExpandedId] = useState<string | null>(null)

  const authHeader = { Authorization: `Bearer ${session?.accessToken}` }

  const fetchRoutines = useCallback(async () => {
    if (!session?.accessToken) return
    setLoading(true)
    try {
      const r = await fetch(`${BACKEND}/api/routines`, { headers: authHeader })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setRoutines(await r.json())
    } catch (err) {
      setError(`Failed to load routines: ${err instanceof Error ? err.message : err}`)
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  useEffect(() => { fetchRoutines() }, [fetchRoutines])

  async function handleSave(name: string, questions: string[]) {
    const url = modal.routine
      ? `${BACKEND}/api/routines/${modal.routine.id}`
      : `${BACKEND}/api/routines`
    const method = modal.routine ? "PUT" : "POST"
    const r = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json", ...authHeader },
      body: JSON.stringify({ name, questions }),
    })
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      throw new Error(d?.detail ?? `HTTP ${r.status}`)
    }
    setModal({ open: false })
    await fetchRoutines()
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Delete routine "${name}"?`)) return
    try {
      await fetch(`${BACKEND}/api/routines/${id}`, { method: "DELETE", headers: authHeader })
      setRoutines((prev) => prev.filter((r) => r.id !== id))
      if (expandedId === id) setExpandedId(null)
    } catch (err) {
      setError(`Delete failed: ${err instanceof Error ? err.message : err}`)
    }
  }

  async function handleRun(id: string) {
    setRunningId(id)
    setExpandedId(id)
    setError(null)
    try {
      const r = await fetch(`${BACKEND}/api/routines/${id}/run`, {
        method: "POST",
        headers: authHeader,
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        throw new Error(d?.detail ?? `HTTP ${r.status}`)
      }
      const data: RoutineResult[] = await r.json()
      setResults((prev) => ({ ...prev, [id]: data }))
    } catch (err) {
      setError(`Run failed: ${err instanceof Error ? err.message : err}`)
    } finally {
      setRunningId(null)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      {modal.open && (
        <RoutineModal
          initial={modal.routine}
          onSave={handleSave}
          onClose={() => setModal({ open: false })}
        />
      )}

      <div className="page-header flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="size-9 rounded-xl gradient-primary flex items-center justify-center shadow-sm">
            <Calendar className="size-4 text-white" />
          </div>
          <div>
            <h1 className="page-title">Daily Routines</h1>
            <p className="page-subtitle">Run multiple questions with one click</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setModal({ open: true })} className="btn-primary">
            <Plus className="size-4" /> New Routine
          </button>
        </div>
      </div>

      <div className="max-w-4xl mx-auto p-6 space-y-4">
        {error && (
          <div className="rounded-xl px-4 py-3 bg-destructive/10 border border-destructive/20 text-sm text-destructive flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0" /> {error}
          </div>
        )}

        {loading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="card-elevated h-24 animate-pulse" />
            ))}
          </div>
        ) : routines.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">
              <Calendar className="size-6" />
            </div>
            <div>
              <p className="font-semibold text-foreground">No routines yet</p>
              <p className="text-sm text-muted-foreground mt-1">
                Create a routine to run multiple questions at once each day
              </p>
            </div>
            <button onClick={() => setModal({ open: true })} className="btn-primary">
              <Plus className="size-4" /> Create your first routine
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {routines.map((routine) => {
              const isRunning = runningId === routine.id
              const isExpanded = expandedId === routine.id
              const routineResults = results[routine.id]

              return (
                <div key={routine.id} className="card-elevated animate-fade-in">
                  <div className="flex items-center gap-3 px-4 py-3">
                    <button
                      onClick={() => setExpandedId(isExpanded ? null : routine.id)}
                      className="flex-1 flex items-center gap-3 text-left min-w-0"
                    >
                      <div className="size-9 rounded-xl gradient-primary flex items-center justify-center shrink-0 shadow-sm">
                        <Calendar className="size-4 text-white" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="font-bold text-sm">{routine.name}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {routine.questions.length} question{routine.questions.length !== 1 ? "s" : ""}
                          <span className="mx-1.5 opacity-30">·</span>
                          Created {new Date(routine.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      {isExpanded
                        ? <ChevronDown className="size-4 text-muted-foreground shrink-0" />
                        : <ChevronRight className="size-4 text-muted-foreground shrink-0" />}
                    </button>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        onClick={() => handleRun(routine.id)}
                        disabled={!!runningId}
                        className="btn-primary py-1.5 px-3 text-xs"
                        title="Run all questions"
                      >
                        {isRunning ? (
                          <><Loader2 className="size-3.5 animate-spin" /> Running…</>
                        ) : (
                          <><Play className="size-3.5" /> Run</>
                        )}
                      </button>
                      <button
                        onClick={() => setModal({ open: true, routine })}
                        className="btn-secondary py-1.5 px-2 text-xs"
                        title="Edit"
                      >
                        <Edit2 className="size-3.5" />
                      </button>
                      <button
                        onClick={() => handleDelete(routine.id, routine.name)}
                        className="btn-danger py-1.5 px-2 text-xs"
                        title="Delete"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="border-t border-border px-4 py-4 space-y-3 animate-fade-in">
                      {!routineResults && !isRunning && (
                        <>
                          <p className="section-label mb-2">Questions</p>
                          {routine.questions.map((q, i) => (
                            <div key={i} className="flex items-start gap-2.5">
                              <span className="size-5 rounded-full bg-primary/10 text-primary text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                                {i + 1}
                              </span>
                              <p className="text-sm text-foreground">{q}</p>
                            </div>
                          ))}
                        </>
                      )}

                      {isRunning && (
                        <div className="flex items-center gap-2.5 py-3 text-sm text-muted-foreground">
                          <Loader2 className="size-4 animate-spin text-primary" />
                          Running {routine.questions.length} question{routine.questions.length !== 1 ? "s" : ""}…
                          <span className="text-xs text-muted-foreground/60">(this may take a minute)</span>
                        </div>
                      )}

                      {routineResults && (
                        <>
                          <div className="flex items-center justify-between">
                            <p className="section-label">
                              Results — {new Date().toLocaleTimeString()}
                            </p>
                            <button
                              onClick={() => handleRun(routine.id)}
                              disabled={!!runningId}
                              className="text-xs text-primary hover:text-primary/80 flex items-center gap-1 transition-colors disabled:opacity-50"
                            >
                              <Play className="size-3" /> Run again
                            </button>
                          </div>
                          {routineResults.map((item, idx) => (
                            <ResultItem key={idx} item={item} />
                          ))}
                        </>
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
