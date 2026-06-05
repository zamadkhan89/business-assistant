"use client"

import { useEffect, useRef, useState, useCallback, useMemo } from "react"
import { useSession } from "next-auth/react"
import { v4 as uuidv4 } from "uuid"
import Link from "next/link"
import {
  Sparkles, Plus, Trash2, BookOpen,
  Database, Upload, Download, PanelLeft, Workflow, X,
  Cpu, Search, Code, BarChart2, Cloud, Table2,
  Bookmark, ChevronUp, ChevronDown, ChevronsUpDown,
  CheckSquare, Square, Filter, MessageSquare, Check, Pencil,
} from "lucide-react"
import dynamic from "next/dynamic"
import { Button } from "@/components/ui/button"
import { MessageBubble } from "@/components/chat/MessageBubble"
import { ChartMessage } from "@/components/chat/ChartMessage"

const CodeBlock = dynamic(
  () => import("@/components/chat/CodeBlock").then((m) => ({ default: m.CodeBlock })),
  { ssr: false, loading: () => <div className="bg-muted/60 rounded-lg p-3 text-xs font-mono animate-pulse">Loading…</div> }
)

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

interface Message {
  role: "user" | "assistant"
  content: string
  status?: "done" | "needs_approval"
  draftSql?: string
  sqlExplanation?: string
  chartJson?: string
  executedSql?: string
  resultRows?: Record<string, unknown>[]
  agentSteps?: string[]
  resumeQuery?: string
  interpretationNote?: string
  cleanedQuestion?: string
}

interface Dataset { table_name: string; row_count: number; source_type?: string }
interface ThreadSummary { id: string; title: string; updated_at: string }
interface BackendMessage {
  id: string
  role: string
  content: string
  meta?: {
    chart_json?: string
    query_results?: Record<string, unknown>[]
    executed_sql?: string
    steps_taken?: string[]
    interpretation_note?: string
    cleaned_question?: string
  }
}

const AGENT_META: Record<string, { label: string; icon: React.ElementType; description: string }> = {
  supervisor:      { label: "Intent",   icon: Cpu,      description: "Classifies your question" },
  schema_agent:    { label: "Schema",   icon: Search,   description: "Finds relevant tables" },
  sql_agent:       { label: "SQL",      icon: Code,     description: "Generates the query" },
  analysis_agent:  { label: "Analysis", icon: BarChart2, description: "Runs query & builds chart" },
}
const PIPELINE_ORDER = ["supervisor", "schema_agent", "sql_agent", "analysis_agent"]

// ── Result Panel ───────────────────────────────────────────────────────────

type ResultTab = "table" | "chart" | "pivot" | "custom"

function SortIcon({ col, sortCol, sortDir }: { col: string; sortCol: string | null; sortDir: "asc" | "desc" }) {
  if (sortCol !== col) return <ChevronsUpDown className="size-3 text-muted-foreground/40 ml-1 shrink-0" />
  return sortDir === "asc"
    ? <ChevronUp className="size-3 text-primary ml-1 shrink-0" />
    : <ChevronDown className="size-3 text-primary ml-1 shrink-0" />
}

function ResultPanel({ rows, chartJson, sql, onExport }: {
  rows: Record<string, unknown>[]
  chartJson?: string
  sql?: string
  onExport?: () => void
}) {
  const PAGE_SIZE = 50
  const [tab, setTab] = useState<ResultTab>("table")
  const [sqlOpen, setSqlOpen] = useState(false)
  const [sortCol, setSortCol] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc")
  const [page, setPage] = useState(0)

  const cols = rows.length > 0 ? Object.keys(rows[0]) : []
  const numCols = cols.filter((c) => typeof rows[0]?.[c] === "number")
  const catCols = cols.filter((c) => typeof rows[0]?.[c] !== "number")

  const [pivotBy, setPivotBy] = useState(() => catCols[0] ?? cols[0] ?? "")
  const [pivotMetric, setPivotMetric] = useState(() => numCols[0] ?? "")
  // Custom chart: X defaults to categorical, Y defaults to numeric
  const [chartType, setChartType] = useState<"bar" | "line" | "scatter" | "pie">("bar")
  const [xCol, setXCol] = useState(() => catCols[0] ?? cols[0] ?? "")
  const [yCol, setYCol] = useState(() => numCols[0] ?? (cols[1] ?? cols[0] ?? ""))

  function toggleSort(col: string) {
    if (sortCol === col) setSortDir((d) => d === "asc" ? "desc" : "asc")
    else { setSortCol(col); setSortDir("asc") }
  }

  const sortedRows = useMemo(() => {
    setPage(0)  // reset page when sort changes
    if (!sortCol) return rows
    return [...rows].sort((a, b) => {
      const av = a[sortCol]; const bv = b[sortCol]
      if (av == null && bv == null) return 0
      if (av == null) return 1
      if (bv == null) return -1
      if (typeof av === "number" && typeof bv === "number")
        return sortDir === "asc" ? av - bv : bv - av
      return sortDir === "asc"
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av))
    })
  }, [rows, sortCol, sortDir])

  const pivotData = useMemo(() => {
    if (!pivotBy || !pivotMetric) return []
    const agg: Record<string, number> = {}
    for (const row of rows) {
      const key = String(row[pivotBy] ?? "(blank)")
      agg[key] = (agg[key] ?? 0) + Number(row[pivotMetric] ?? 0)
    }
    return Object.entries(agg)
      .map(([k, v]) => ({ [pivotBy]: k, [pivotMetric]: v }))
      .sort((a, b) => (b[pivotMetric] as number) - (a[pivotMetric] as number))
  }, [rows, pivotBy, pivotMetric])

  const customChartJson = useMemo(() => {
    if (!xCol || !yCol || !rows.length) return ""
    const xVals = rows.map((r) => r[xCol])
    const yVals = rows.map((r) => r[yCol])
    const trace = chartType === "pie"
      ? { type: "pie", labels: xVals, values: yVals, hole: 0.3 }
      : { type: chartType, x: xVals, y: yVals, marker: { color: "oklch(0.55 0.22 264)" } }
    return JSON.stringify({
      data: [trace],
      layout: { margin: { l: 40, r: 20, t: 20, b: 60 }, paper_bgcolor: "transparent", plot_bgcolor: "transparent", font: { size: 11 } },
    })
  }, [rows, xCol, yCol, chartType])

  if (!rows.length) return null

  const tabs: { id: ResultTab; label: string; icon: React.ElementType; hidden?: boolean }[] = [
    { id: "table",  label: "Table",  icon: Table2 },
    { id: "chart",  label: "Chart",  icon: BarChart2, hidden: !chartJson },
    { id: "pivot",  label: "Pivot",  icon: Workflow },
    { id: "custom", label: "Custom", icon: Cpu },
  ]

  return (
    <div className="mt-3 card-elevated overflow-hidden animate-fade-in">
      {/* SQL toggle bar */}
      {sql && (
        <div className="border-b border-border">
          <button
            onClick={() => setSqlOpen((v) => !v)}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-xs text-muted-foreground hover:bg-muted/50 transition-colors text-left group"
          >
            <Code className="size-3 shrink-0 text-primary/60" />
            <span className="font-mono truncate group-hover:text-foreground transition-colors">
              {sql.replace(/\s+/g, " ").slice(0, 90)}{sql.length > 90 ? "…" : ""}
            </span>
            <span className="ml-auto shrink-0 text-muted-foreground/50">{sqlOpen ? "▲" : "▼"}</span>
          </button>
          {sqlOpen && (
            <div className="px-4 pb-3 pt-1 animate-fade-in">
              <CodeBlock language="sql">{sql}</CodeBlock>
            </div>
          )}
        </div>
      )}

      {/* Tab bar */}
      <div className="flex items-center border-b border-border bg-muted/20 overflow-x-auto">
        {tabs.filter((t) => !t.hidden).map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 shrink-0 transition-all
              ${tab === t.id
                ? "border-primary text-primary bg-background/60"
                : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40"}`}
          >
            <t.icon className="size-3" />
            {t.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2 px-4 text-[10px] text-muted-foreground shrink-0">
          <span className="badge-neutral px-2 py-0.5 rounded-full text-[10px]">
            {rows.length} rows · {cols.length} cols
          </span>
          {onExport && (
            <button onClick={onExport} className="btn-ghost py-1 px-2 text-[10px] gap-1" title="Download CSV">
              <Download className="size-3" /> CSV
            </button>
          )}
        </div>
      </div>

      {/* Table tab */}
      {tab === "table" && (() => {
        const pageCount = Math.ceil(sortedRows.length / PAGE_SIZE)
        const pagedRows = sortedRows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE)
        return (
          <>
            <div className="overflow-x-auto max-h-80">
              <table className="w-full text-xs border-collapse">
                <thead className="sticky top-0 bg-muted/80 backdrop-blur-sm z-10">
                  <tr>
                    {cols.map((c) => (
                      <th
                        key={c}
                        onClick={() => toggleSort(c)}
                        className="px-3 py-2.5 text-left font-semibold text-foreground border-b border-border whitespace-nowrap cursor-pointer select-none hover:bg-muted transition-colors group"
                      >
                        <span className="flex items-center gap-0.5">
                          {c}
                          <SortIcon col={c} sortCol={sortCol} sortDir={sortDir} />
                        </span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {pagedRows.map((row, ri) => (
                    <tr key={ri} className="row-interactive border-b border-border/30 last:border-0">
                      {cols.map((c) => (
                        <td key={c} className="px-3 py-1.5 text-foreground whitespace-nowrap">
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
            {pageCount > 1 && (
              <div className="flex items-center justify-between px-4 py-2 border-t border-border text-[11px] text-muted-foreground">
                <span>Rows {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, sortedRows.length)} of {sortedRows.length}</span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setPage((p) => Math.max(0, p - 1))}
                    disabled={page === 0}
                    className="px-2 py-0.5 rounded hover:bg-muted disabled:opacity-30 transition-colors"
                  >
                    ‹ Prev
                  </button>
                  <span className="px-2">{page + 1} / {pageCount}</span>
                  <button
                    onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
                    disabled={page >= pageCount - 1}
                    className="px-2 py-0.5 rounded hover:bg-muted disabled:opacity-30 transition-colors"
                  >
                    Next ›
                  </button>
                </div>
              </div>
            )}
          </>
        )
      })()}

      {/* Chart tab */}
      {tab === "chart" && chartJson && (
        <div className="p-3 animate-fade-in">
          <ChartMessage chartJson={chartJson} />
        </div>
      )}

      {/* Pivot tab */}
      {tab === "pivot" && (
        <div className="p-4 space-y-4 animate-fade-in">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="space-y-1.5">
              <label className="section-label">Group by</label>
              <select value={pivotBy} onChange={(e) => setPivotBy(e.target.value)} className="select-modern">
                {cols.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="section-label">Sum of</label>
              <select value={pivotMetric} onChange={(e) => setPivotMetric(e.target.value)} className="select-modern">
                {(numCols.length ? numCols : cols).map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
          {pivotData.length > 0 ? (
            <div className="overflow-x-auto max-h-72 rounded-lg border border-border">
              <table className="w-full text-xs border-collapse">
                <thead className="sticky top-0 bg-muted/80">
                  <tr>
                    <th className="px-3 py-2.5 text-left font-semibold border-b border-border">{pivotBy}</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-b border-border">{pivotMetric}</th>
                  </tr>
                </thead>
                <tbody>
                  {pivotData.map((row, i) => (
                    <tr key={i} className="row-interactive border-b border-border/30 last:border-0">
                      <td className="px-3 py-1.5">{String(row[pivotBy])}</td>
                      <td className="px-3 py-1.5 text-right font-mono tabular-nums">
                        {typeof row[pivotMetric] === "number"
                          ? (row[pivotMetric] as number).toLocaleString(undefined, { maximumFractionDigits: 2 })
                          : String(row[pivotMetric])}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Select a numeric metric to aggregate.</p>
          )}
        </div>
      )}

      {/* Custom chart tab — all columns available */}
      {tab === "custom" && (
        <div className="p-4 space-y-4 animate-fade-in">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="space-y-1.5">
              <label className="section-label">Chart type</label>
              <select value={chartType} onChange={(e) => setChartType(e.target.value as typeof chartType)} className="select-modern">
                {["bar", "line", "scatter", "pie"].map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="section-label">{chartType === "pie" ? "Labels" : "X axis"}</label>
              <select value={xCol} onChange={(e) => setXCol(e.target.value)} className="select-modern">
                {/* All columns, but categoricals first */}
                {[...catCols, ...numCols].map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="space-y-1.5">
              <label className="section-label">{chartType === "pie" ? "Values" : "Y axis"}</label>
              <select value={yCol} onChange={(e) => setYCol(e.target.value)} className="select-modern">
                {/* All columns, but numerics first */}
                {[...numCols, ...catCols].map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>
          {customChartJson && <div className="animate-fade-in"><ChartMessage chartJson={customChartJson} /></div>}
        </div>
      )}
    </div>
  )
}

// ── Agent trace ────────────────────────────────────────────────────────────

function AgentTrace({ steps, onShowGraph }: { steps: string[]; onShowGraph: () => void }) {
  const ran = new Set(steps)
  const visible = PIPELINE_ORDER.filter((id) => ran.has(id))
  if (!visible.length) return null
  return (
    <div className="flex items-center gap-1.5 mt-2 ml-9 flex-wrap">
      <span className="section-label mr-0.5">via</span>
      {visible.map((id, i) => {
        const meta = AGENT_META[id]; const Icon = meta.icon
        return (
          <span key={id} className="flex items-center gap-1">
            {i > 0 && <span className="text-muted-foreground/30 text-[10px]">→</span>}
            <span title={meta.description} className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-[10px] font-medium">
              <Icon className="size-2.5" />{meta.label}
            </span>
          </span>
        )
      })}
      <button onClick={onShowGraph} className="ml-1 text-[10px] text-muted-foreground/50 hover:text-primary transition-colors">
        <Workflow className="size-3 inline" />
      </button>
    </div>
  )
}

const PIPELINE_NODES = [
  { key: "supervisor",     icon: Cpu,      label: "Supervisor",     desc: "Classifies intent and routes the question",      color: "bg-violet-500/15 border-violet-400/40 text-violet-600 dark:text-violet-400" },
  { key: "schema_agent",  icon: Search,   label: "Schema Agent",   desc: "Finds relevant tables and columns via semantic search", color: "bg-blue-500/15 border-blue-400/40 text-blue-600 dark:text-blue-400" },
  { key: "sql_agent",     icon: Code,     label: "SQL Agent",      desc: "Generates, validates, and optionally pauses for approval", color: "bg-amber-500/15 border-amber-400/40 text-amber-600 dark:text-amber-400" },
  { key: "analysis_agent",icon: BarChart2, label: "Analysis Agent", desc: "Executes the query, builds a chart, summarises results", color: "bg-emerald-500/15 border-emerald-400/40 text-emerald-600 dark:text-emerald-400" },
]

function GraphModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-card rounded-2xl shadow-2xl max-w-lg w-full p-6 space-y-5 animate-scale-in" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2"><Workflow className="size-4 text-primary" /><h2 className="font-semibold">Agent Pipeline</h2></div>
          <button onClick={onClose} className="btn-ghost p-1.5 rounded-lg"><X className="size-4" /></button>
        </div>
        <div className="flex flex-col items-center gap-0">
          {PIPELINE_NODES.map((node, i) => (
            <div key={node.key} className="flex flex-col items-center w-full">
              <div className={`flex items-center gap-3 w-full rounded-xl border px-4 py-3 ${node.color}`}>
                <node.icon className="size-4 shrink-0" />
                <div className="min-w-0">
                  <p className="font-semibold text-sm">{node.label}</p>
                  <p className="text-[11px] opacity-75 leading-snug">{node.desc}</p>
                </div>
              </div>
              {i < PIPELINE_NODES.length - 1 && (
                <div className="flex flex-col items-center py-1">
                  <div className="w-px h-3 bg-border" />
                  <div className="text-[9px] text-muted-foreground font-mono px-2 py-0.5 rounded bg-muted border border-border -my-px z-10">
                    {i === 0 ? "data_query" : i === 2 ? "approved" : "→"}
                  </div>
                  <div className="w-px h-3 bg-border" />
                </div>
              )}
            </div>
          ))}
        </div>
        <p className="text-[10px] text-muted-foreground text-center leading-relaxed">
          Off-topic questions return directly from Supervisor · Schema agent selects only relevant tables · SQL agent skips HITL when approval is disabled for your account
        </p>
      </div>
    </div>
  )
}

// ── SQL approval panel ─────────────────────────────────────────────────────

function ApprovalPanel({
  draftSql, sqlExplanation, loading, onApprove, onReject, onEdit,
}: {
  draftSql: string; sqlExplanation: string; loading: boolean
  onApprove: () => void; onReject: () => void; onEdit: (sql: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [editedSql, setEditedSql] = useState(draftSql)

  return (
    <div className="ml-9 mt-2 rounded-xl border border-primary/20 bg-primary/5 p-4 space-y-3 max-w-2xl">
      {sqlExplanation && (
        <p className="text-sm text-muted-foreground">{sqlExplanation}</p>
      )}
      <div className="space-y-1.5">
        <span className="section-label">SQL to execute</span>
        {editing ? (
          <textarea
            value={editedSql}
            onChange={(e) => setEditedSql(e.target.value)}
            className="w-full font-mono text-xs bg-muted rounded-lg p-3 border border-border outline-none focus:ring-1 focus:ring-primary/40 resize-y min-h-28"
            spellCheck={false}
          />
        ) : (
          <pre className="text-xs font-mono bg-muted rounded-lg p-3 overflow-auto max-h-48 leading-relaxed whitespace-pre-wrap">{draftSql}</pre>
        )}
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        {editing ? (
          <>
            <button
              onClick={() => { onEdit(editedSql); setEditing(false) }}
              disabled={loading || !editedSql.trim()}
              className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5 disabled:opacity-50"
            >
              {loading
                ? <span className="size-3 border-2 border-white/30 border-t-white rounded-full animate-spin inline-block" />
                : <Check className="size-3" />}
              Submit edit
            </button>
            <button
              onClick={() => { setEditing(false); setEditedSql(draftSql) }}
              disabled={loading}
              className="btn-secondary text-xs py-1.5 px-3"
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            <button
              onClick={onApprove}
              disabled={loading}
              className="btn-primary text-xs py-1.5 px-3 flex items-center gap-1.5 disabled:opacity-50"
            >
              {loading
                ? <span className="size-3 border-2 border-white/30 border-t-white rounded-full animate-spin inline-block" />
                : <Check className="size-3" />}
              Approve &amp; run
            </button>
            <button
              onClick={() => { setEditing(true) }}
              disabled={loading}
              className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1.5"
            >
              <Pencil className="size-3" /> Edit SQL
            </button>
            <button
              onClick={onReject}
              disabled={loading}
              className="text-xs text-destructive hover:text-destructive/80 transition-colors flex items-center gap-1.5 px-2 py-1.5"
            >
              <X className="size-3" /> Reject
            </button>
          </>
        )}
      </div>
    </div>
  )
}

// ── Save question modal ────────────────────────────────────────────────────

function SaveModal({ question, sql, datasets, onSave, onClose }: {
  question: string; sql: string; datasets: string[]; onSave: (name: string) => void; onClose: () => void
}) {
  const [name, setName] = useState(question.slice(0, 60))
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-card rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-4 animate-scale-in" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2">
          <div className="size-8 rounded-lg bg-primary/10 flex items-center justify-center">
            <Bookmark className="size-4 text-primary" />
          </div>
          <h2 className="font-semibold">Save Question</h2>
        </div>
        <div className="space-y-1.5">
          <label className="section-label">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="input-modern"
            placeholder="e.g. Monthly revenue by product"
            autoFocus
          />
        </div>
        {datasets.length > 0 && (
          <div className="space-y-1.5">
            <label className="section-label">Datasets</label>
            <div className="flex flex-wrap gap-1.5">
              {datasets.map((d) => (
                <span key={d} className="badge-info text-[11px] px-2 py-0.5 rounded-full font-medium">{d}</span>
              ))}
            </div>
          </div>
        )}
        {sql && (
          <div className="space-y-1.5">
            <label className="section-label">SQL (preview)</label>
            <div className="font-mono text-[11px] bg-muted rounded-lg p-2.5 text-muted-foreground truncate">{sql.slice(0, 120)}</div>
          </div>
        )}
        <div className="flex gap-2 justify-end pt-1">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={() => onSave(name.trim() || question.slice(0, 60))} className="btn-primary" disabled={!name.trim()}>
            <Bookmark className="size-3.5" /> Save
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Dataset selector ───────────────────────────────────────────────────────

function DatasetSelector({ datasets, selected, onChange }: {
  datasets: Dataset[]
  selected: string[]
  onChange: (v: string[]) => void
}) {
  const [open, setOpen] = useState(false)
  if (!datasets.length) return null
  const allSelected = selected.length === 0

  function toggle(name: string) {
    if (selected.includes(name)) {
      const next = selected.filter((x) => x !== name)
      onChange(next)
    } else {
      onChange([...selected, name])
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all
          ${allSelected
            ? "border-border text-muted-foreground hover:border-primary/30 hover:text-foreground bg-background"
            : "border-primary/40 text-primary bg-primary/5 hover:bg-primary/10"}`}
      >
        <Filter className="size-3" />
        {allSelected ? "All datasets" : `${selected.length} dataset${selected.length > 1 ? "s" : ""}`}
      </button>
      {open && (
        <div className="absolute top-full mt-1.5 right-0 z-20 bg-popover border border-border rounded-xl shadow-xl p-1.5 min-w-50 animate-scale-in">
          <button
            onClick={() => { onChange([]); setOpen(false) }}
            className={`w-full flex items-center gap-2 px-3 py-2 text-xs rounded-lg transition-colors
              ${allSelected ? "bg-primary/10 text-primary font-medium" : "hover:bg-muted text-foreground"}`}
          >
            {allSelected ? <CheckSquare className="size-3.5" /> : <Square className="size-3.5 text-muted-foreground" />}
            All datasets
          </button>
          <div className="my-1 border-t border-border/50" />
          {datasets.map((d) => {
            const active = selected.includes(d.table_name)
            return (
              <button
                key={d.table_name}
                onClick={() => toggle(d.table_name)}
                className={`w-full flex items-center gap-2 px-3 py-2 text-xs rounded-lg transition-colors
                  ${active ? "bg-primary/10 text-primary font-medium" : "hover:bg-muted text-foreground"}`}
              >
                {active ? <CheckSquare className="size-3.5" /> : <Square className="size-3.5 text-muted-foreground" />}
                <span className="truncate">{d.table_name}</span>
                {d.source_type === "athena" && (
                  <span className="shrink-0 text-[9px] font-semibold px-1.5 py-0.5 rounded bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300">Athena</span>
                )}
                {d.source_type === "athena_direct" && (
                  <span className="shrink-0 text-[9px] font-semibold px-1.5 py-0.5 rounded bg-purple-100 dark:bg-purple-950/40 text-purple-700 dark:text-purple-300">Direct</span>
                )}
                {d.source_type !== "athena" && d.source_type !== "athena_direct" && (
                  <span className="ml-auto text-muted-foreground/60">{d.row_count.toLocaleString()}</span>
                )}
              </button>
            )
          })}
          <div className="mt-1 pt-1 border-t border-border/50">
            <button onClick={() => setOpen(false)} className="w-full text-center text-xs text-muted-foreground hover:text-foreground py-1 transition-colors">Done</button>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Typing indicator ───────────────────────────────────────────────────────

const EXAMPLE_PROMPTS_BASE = [
  "Show top 5 rows from my data",
  "What columns does my table have?",
  "Show me a summary of the data",
  "Which records have the highest values?",
]

function TypingDots() {
  return (
    <div className="flex items-start gap-2">
      <div className="size-7 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0">
        <Sparkles className="size-3.5" />
      </div>
      <div className="rounded-2xl rounded-tl-sm px-4 py-3 bg-muted flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <span key={i} className="size-1.5 rounded-full bg-muted-foreground block"
            style={{ animation: `typing-dot 1.2s ease-in-out ${i * 0.2}s infinite` }} />
        ))}
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function ChatPage() {
  const { data: session } = useSession()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [approvalLoading, setApprovalLoading] = useState(false)
  const [streamStep, setStreamStep] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [threadId, setThreadId] = useState(() => uuidv4())
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [selectedDatasets, setSelectedDatasets] = useState<string[]>([])
  const [glossaryCount, setGlossaryCount] = useState(0)
  const [uploading, setUploading] = useState(false)
  const [threads, setThreads] = useState<ThreadSummary[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [showGraph, setShowGraph] = useState(false)
  const [saveModal, setSaveModal] = useState<{ question: string; sql: string; msgIndex: number; datasets: string[]; results: Record<string, unknown>[] } | null>(null)
  // Maps message render-index → saved query ID for bookmark toggle (separate from messages array to avoid stale-closure bugs)
  const [msgSavedIds, setMsgSavedIds] = useState<Record<number, string>>({})
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const pendingQueryRef = useRef<string | null>(null)
  const [selectionInfo, setSelectionInfo] = useState<{ text: string; x: number; y: number } | null>(null)
  const [threadSearch, setThreadSearch] = useState("")
  const [streamingEnabled, setStreamingEnabled] = useState(false)

  const userInitial = session?.user?.email?.[0]?.toUpperCase() ?? "U"
  const authHeader = { Authorization: `Bearer ${session?.accessToken}` }

  // ── Select-and-ask ─────────────────────────────────────────────────────────
  function handleTextSelect() {
    const sel = window.getSelection()
    if (!sel || sel.isCollapsed) return
    const text = sel.toString().trim()
    if (!text) return
    const rect = sel.getRangeAt(0).getBoundingClientRect()
    setSelectionInfo({ text, x: rect.left + rect.width / 2, y: rect.top })
  }

  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if ((e.target as Element)?.closest("[data-selection-popup]")) return
      setSelectionInfo(null)
    }
    document.addEventListener("mousedown", onMouseDown)
    return () => document.removeEventListener("mousedown", onMouseDown)
  }, [])

  function applySelection() {
    if (!selectionInfo) return
    setInput(`"${selectionInfo.text}"\n\n`)
    setSelectionInfo(null)
    window.getSelection()?.removeAllRanges()
    textareaRef.current?.focus()
  }
  // ──────────────────────────────────────────────────────────────────────────

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = Math.min(el.scrollHeight, 180) + "px"
  }, [input])

  const fetchDatasets = useCallback(async () => {
    try {
      const [dr, gr] = await Promise.all([
        fetch(`${BACKEND}/api/datasets`, { headers: authHeader }),
        fetch(`${BACKEND}/api/glossary`,  { headers: authHeader }),
      ])
      if (dr.ok) setDatasets(await dr.json())
      if (gr.ok) { const gl = await gr.json(); setGlossaryCount(Array.isArray(gl) ? gl.length : 0) }
    } catch { /* silent */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  // Fetch live user settings so admin toggles take effect without re-login
  useEffect(() => {
    if (!session?.accessToken) return
    fetch(`${BACKEND}/api/auth/me`, { headers: { Authorization: `Bearer ${session.accessToken}` } })
      .then((r) => r.ok ? r.json() : null)
      .then((u) => { if (u) setStreamingEnabled(u.streaming_enabled ?? false) })
      .catch(() => {})
  }, [session?.accessToken])

  const fetchThreads = useCallback(async () => {
    if (!session?.accessToken) return
    try {
      const r = await fetch(`${BACKEND}/api/threads`, { headers: authHeader })
      if (r.ok) setThreads(await r.json())
    } catch { /* silent */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  useEffect(() => { fetchDatasets() }, [fetchDatasets])
  useEffect(() => { fetchThreads() }, [fetchThreads])

  // Read pending query from sessionStorage (set by saved-queries page before navigating here)
  useEffect(() => {
    if (typeof window === "undefined") return
    const q = sessionStorage.getItem("pendingChatQuery")
    if (q) {
      sessionStorage.removeItem("pendingChatQuery")
      pendingQueryRef.current = q
      setInput(q)  // pre-fill so user can Send manually if auto-submit fails
    }
  }, [])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }) }, [messages, loading])

  async function loadThread(id: string) {
    // Cancel any in-flight request for the previous thread so its response
    // doesn't land on top of the thread we're navigating to.
    abortRef.current?.abort()
    abortRef.current = null
    setLoading(false)
    setError(null)
    setLoadingHistory(true)
    try {
      const r = await fetch(`${BACKEND}/api/threads/${id}/messages`, { headers: authHeader })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const backendMsgs: BackendMessage[] = await r.json()
      setMsgSavedIds({})
      setMessages(backendMsgs.map((m) => ({
        role: m.role as "user" | "assistant",
        content: m.content,
        chartJson: m.meta?.chart_json || undefined,
        resultRows: m.meta?.query_results?.length ? m.meta.query_results : undefined,
        executedSql: m.meta?.executed_sql || undefined,
        agentSteps: m.meta?.steps_taken ?? [],
        interpretationNote: m.meta?.interpretation_note || undefined,
        cleanedQuestion: m.meta?.cleaned_question || undefined,
      })))
      setThreadId(id)
      setThreadSearch("")
      setSidebarOpen(false)
      // Refresh the sidebar so any thread created since the last response appears.
      fetchThreads()
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") return
      setError(`Could not load thread: ${err instanceof Error ? err.message : err}`)
    } finally { setLoadingHistory(false) }
  }

  function newChat() {
    abortRef.current?.abort()
    abortRef.current = null
    setLoading(false)
    setMessages([]); setThreadId(uuidv4()); setError(null); setSidebarOpen(false); setMsgSavedIds({})
    fetchThreads()
  }

  async function deleteThread(id: string, e: React.MouseEvent) {
    e.stopPropagation()
    if (!confirm("Delete this conversation?")) return
    try {
      await fetch(`${BACKEND}/api/threads/${id}`, { method: "DELETE", headers: authHeader })
      if (id === threadId) newChat()
      setThreads((prev) => prev.filter((t) => t.id !== id))
    } catch { setError("Could not delete conversation") }
  }

  function stopQuery() {
    abortRef.current?.abort(); abortRef.current = null; setLoading(false)
    setMessages((prev) => {
      const lastUser = [...prev].reverse().find((m) => m.role === "user")?.content
      return [...prev, { role: "assistant", content: "Query stopped.", resumeQuery: lastUser }]
    })
  }

  async function submitMessage(text: string) {
    if (!text || loading) return
    setMessages((prev) => [...prev, { role: "user", content: text }])
    setInput(""); setLoading(true); setError(null); setStreamStep(null)

    abortRef.current = new AbortController()
    const useStreaming = streamingEnabled

    if (useStreaming) {
      // SSE streaming path — shows live step progress
      try {
        const res = await fetch(`${BACKEND}/api/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeader },
          body: JSON.stringify({ thread_id: threadId, message: text, selected_datasets: selectedDatasets }),
          signal: abortRef.current.signal,
        })
        if (!res.ok) {
          const detail = await res.json().catch(() => ({}))
          throw new Error(detail?.detail ?? `HTTP ${res.status}`)
        }

        const reader = res.body!.getReader()
        const decoder = new TextDecoder()
        let buf = ""
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buf += decoder.decode(value, { stream: true })
          const lines = buf.split("\n")
          buf = lines.pop() ?? ""
          for (const line of lines) {
            if (!line.startsWith("data: ")) continue
            let evt: Record<string, unknown>
            try { evt = JSON.parse(line.slice(6)) } catch { continue }
            if (evt.type === "step") {
              setStreamStep(evt.step as string)
            } else if (evt.type === "needs_approval") {
              setStreamStep(null)
              handleChatResponse({
                content: "Please review the SQL query below before I execute it.",
                status: "needs_approval",
                draft_sql: evt.draft_sql as string,
                sql_explanation: evt.sql_explanation as string,
                steps_taken: evt.steps_taken as string[],
              })
            } else if (evt.type === "done") {
              setStreamStep(null)
              handleChatResponse({
                content: evt.content as string,
                status: "done",
                chart_json: evt.chart_json as string,
                query_results: evt.query_results as Record<string, unknown>[],
                executed_sql: evt.executed_sql as string,
                steps_taken: evt.steps_taken as string[],
                interpretation_note: evt.interpretation_note as string,
                cleaned_question: evt.cleaned_question as string,
              })
            } else if (evt.type === "error") {
              setError(evt.message as string)
            }
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return
        setError(`Could not reach the assistant: ${err instanceof Error ? err.message : err}`)
      } finally {
        setLoading(false); setStreamStep(null); abortRef.current = null
        fetchThreads()
      }
    } else {
      // Regular POST path — waits for full response
      try {
        const res = await fetch(`${BACKEND}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeader },
          body: JSON.stringify({ thread_id: threadId, message: text, selected_datasets: selectedDatasets }),
          signal: abortRef.current.signal,
        })
        if (!res.ok) {
          const detail = await res.json().catch(() => ({}))
          throw new Error(detail?.detail ?? `HTTP ${res.status}`)
        }
        const data = await res.json()
        handleChatResponse({
          content: data.content,
          status: data.status,
          draft_sql: data.draft_sql,
          sql_explanation: data.sql_explanation,
          chart_json: data.chart_json,
          query_results: data.query_results,
          executed_sql: data.executed_sql,
          steps_taken: data.steps_taken,
          interpretation_note: data.interpretation_note,
          cleaned_question: data.cleaned_question,
        })
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") return
        setError(`Could not reach the assistant: ${err instanceof Error ? err.message : err}`)
      } finally {
        setLoading(false); abortRef.current = null
        fetchThreads()
      }
    }
  }

  // Auto-submit pending query once session is ready
  useEffect(() => {
    if (!session?.accessToken || !pendingQueryRef.current) return
    const q = pendingQueryRef.current
    pendingQueryRef.current = null
    setInput("")  // clear pre-fill now that we're auto-submitting
    submitMessage(q)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  async function resumeStopped(query: string) {
    setMessages((prev) => prev.filter((m) => !m.resumeQuery))
    await submitMessage(query)
  }

  async function handleApproval(action: "approve" | "reject" | "edit", editedSql?: string) {
    setApprovalLoading(true)
    setError(null)
    try {
      const res = await fetch(`${BACKEND}/api/chat/resume`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({ thread_id: threadId, action, edited_sql: editedSql ?? "" }),
      })
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}))
        throw new Error(detail?.detail ?? `HTTP ${res.status}`)
      }
      const data = await res.json()
      setMessages((prev) => {
        // Mark the pending approval message as done so the panel disappears
        const next = prev.map((m) =>
          m.status === "needs_approval" ? { ...m, status: "done" as const } : m
        )
        if (action === "reject") return next
        return [...next, {
          role: "assistant" as const,
          content: data.content,
          chartJson: data.chart_json || undefined,
          resultRows: data.query_results?.length ? data.query_results : undefined,
          executedSql: data.executed_sql || undefined,
          agentSteps: data.steps_taken ?? [],
          interpretationNote: data.interpretation_note || undefined,
          cleanedQuestion: data.cleaned_question || undefined,
        }]
      })
      fetchThreads()
    } catch (err) {
      setError(`Approval failed: ${err instanceof Error ? err.message : err}`)
    } finally {
      setApprovalLoading(false)
    }
  }

  async function callBackend(path: string, body: object): Promise<Response> {
    abortRef.current = new AbortController()
    const res = await fetch(`${BACKEND}/api/chat${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeader },
      body: JSON.stringify(body),
      signal: abortRef.current.signal,
    })
    abortRef.current = null
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}))
      throw new Error(detail?.detail ?? `HTTP ${res.status}`)
    }
    return res
  }

  function handleChatResponse(data: {
    content: string; status?: string
    draft_sql?: string; sql_explanation?: string
    chart_json?: string; query_results?: Record<string, unknown>[]
    executed_sql?: string; steps_taken?: string[]
    interpretation_note?: string; cleaned_question?: string
  }) {
    setError(null)
    setMessages((prev) => [...prev, {
      role: "assistant",
      content: data.content,
      status: data.status === "needs_approval" ? "needs_approval" : "done",
      draftSql: data.draft_sql || undefined,
      sqlExplanation: data.sql_explanation || undefined,
      chartJson: data.chart_json || undefined,
      resultRows: data.query_results?.length ? data.query_results : undefined,
      executedSql: data.executed_sql || undefined,
      agentSteps: data.steps_taken ?? [],
      interpretationNote: data.interpretation_note || undefined,
      cleanedQuestion: data.cleaned_question || undefined,
    }])
    fetchThreads()
  }

  async function handleSubmit(e: { preventDefault(): void }) {
    e.preventDefault()
    await submitMessage(input.trim())
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return
    setUploading(true); setError(null)
    try {
      const form = new FormData(); form.append("file", file)
      const r = await fetch(`${BACKEND}/api/datasets/upload`, { method: "POST", headers: authHeader, body: form })
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d?.detail ?? `HTTP ${r.status}`) }
      const meta = await r.json(); await fetchDatasets()
      const renameNote = meta.was_renamed
        ? ` (renamed to \`${meta.table_name}\` — a table with that name already existed)`
        : ""
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: `Uploaded **${file.name}** → table \`${meta.table_name}\` (${meta.row_count.toLocaleString()} rows)${renameNote}. Added to Data Catalog — AI enrichment running in background. You can now ask questions about it.`,
      }])
    } catch (err) { setError(`Upload failed: ${err instanceof Error ? err.message : err}`)
    } finally { setUploading(false); if (fileInputRef.current) fileInputRef.current.value = "" }
  }

  async function handleExport(sql: string) {
    try {
      const r = await fetch(`${BACKEND}/api/datasets/export`, {
        method: "POST", headers: { "Content-Type": "application/json", ...authHeader }, body: JSON.stringify({ sql }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const blob = await r.blob(); const url = URL.createObjectURL(blob)
      const a = document.createElement("a"); a.href = url; a.download = "export.csv"; a.click()
      URL.revokeObjectURL(url)
    } catch (err) { setError(`Export failed: ${err instanceof Error ? err.message : err}`) }
  }

  async function handleSave(name: string) {
    if (!saveModal) return
    // Capture values before async gap to avoid stale closure
    const { question, sql, datasets: ds, results: rs, msgIndex } = saveModal
    setSaveModal(null)
    try {
      const r = await fetch(`${BACKEND}/api/saved-queries`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({ name, question, sql, datasets: ds, results: rs }),
      })
      if (r.ok) {
        const data = await r.json()
        setMsgSavedIds((prev) => ({ ...prev, [msgIndex]: data.id }))
      }
    } catch { /* silent */ }
  }

  async function handleUnsave(msgIndex: number, savedQueryId: string) {
    try {
      await fetch(`${BACKEND}/api/saved-queries/${savedQueryId}`, {
        method: "DELETE",
        headers: authHeader,
      })
      setMsgSavedIds((prev) => {
        const next = { ...prev }
        delete next[msgIndex]
        return next
      })
    } catch { /* silent */ }
  }

  function usePrompt(text: string) { setInput(text); textareaRef.current?.focus() }

  const hasAthenaDirectSelected = selectedDatasets.length > 0 &&
    selectedDatasets.some(name => datasets.find(d => d.table_name === name)?.source_type === "athena_direct")

  // Find last user message for save prompt
  function getLastUserQuestion(): string {
    return [...messages].reverse().find((m) => m.role === "user")?.content ?? ""
  }

  return (
    <div className="flex h-full overflow-hidden bg-background">
      {showGraph && <GraphModal onClose={() => setShowGraph(false)} />}
      {saveModal && <SaveModal question={saveModal.question} sql={saveModal.sql} datasets={saveModal.datasets} onSave={handleSave} onClose={() => setSaveModal(null)} />}

      {/* ── Select-and-ask popup ── */}
      {selectionInfo && (
        <div
          data-selection-popup
          style={{ position: "fixed", left: selectionInfo.x, top: selectionInfo.y - 8, transform: "translate(-50%, -100%)", zIndex: 50 }}
          className="animate-scale-in"
        >
          <button
            onMouseDown={(e) => e.preventDefault()}
            onClick={applySelection}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-semibold shadow-lg hover:bg-primary/90 active:scale-95 transition-all select-none whitespace-nowrap"
          >
            <MessageSquare className="size-3.5 shrink-0" />
            Ask about this
          </button>
          {/* small arrow pointing down */}
          <div className="mx-auto w-0 h-0 border-l-4 border-r-4 border-t-4 border-l-transparent border-r-transparent border-t-primary" />
        </div>
      )}

      {/* ── Sidebar ── */}
      <aside className={`
        fixed inset-y-0 left-0 z-30 flex flex-col w-64 border-r border-sidebar-border
        bg-sidebar transition-transform duration-200
        ${sidebarOpen ? "translate-x-0" : "-translate-x-full"} md:relative md:translate-x-0
      `}>
        <div className="flex items-center justify-between px-3 py-3 border-b border-sidebar-border gradient-header">
          <div className="flex items-center gap-2">
            <div className="size-7 rounded-lg gradient-primary flex items-center justify-center shadow-sm">
              <Sparkles className="size-3.5 text-white" />
            </div>
            <span className="font-bold text-sm tracking-tight">Business Assistant</span>
          </div>
          <Button size="sm" variant="ghost" className="h-7 w-7 p-0 hover:bg-sidebar-accent" onClick={newChat} title="New conversation">
            <Plus className="size-4" />
          </Button>
        </div>

        <div className="px-2 py-2 border-b border-sidebar-border">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3 text-muted-foreground pointer-events-none" />
            <input
              value={threadSearch}
              onChange={(e) => setThreadSearch(e.target.value)}
              placeholder="Search conversations…"
              className="w-full h-7 pl-7 pr-2 text-xs rounded-md bg-sidebar-accent/50 border border-sidebar-border placeholder:text-muted-foreground/60 outline-none focus:ring-1 focus:ring-primary/30 focus:border-primary/40 transition-all"
            />
            {threadSearch && (
              <button onClick={() => setThreadSearch("")} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors">
                <X className="size-3" />
              </button>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          <p className="px-3 py-1.5 section-label">Conversations</p>
          {loadingHistory && <p className="text-xs text-muted-foreground px-3 py-2">Loading…</p>}
          {threads.length === 0 && !loadingHistory && (
            <p className="text-xs text-muted-foreground px-3 py-4 text-center">No conversations yet</p>
          )}
          {threads.filter((t) => !threadSearch || (t.title || "Untitled").toLowerCase().includes(threadSearch.toLowerCase())).length === 0 && threadSearch && (
            <p className="text-xs text-muted-foreground px-3 py-4 text-center">No results for "{threadSearch}"</p>
          )}
          {threads.filter((t) => !threadSearch || (t.title || "Untitled").toLowerCase().includes(threadSearch.toLowerCase())).map((t) => (
            <div key={t.id} className={`group relative flex items-center rounded-lg mx-1.5 my-0.5 transition-all
              ${t.id === threadId ? "bg-primary/10 text-primary" : "hover:bg-sidebar-accent/60"}`}>
              <button onClick={() => loadThread(t.id)} className={`flex-1 text-left px-2.5 py-2 text-sm truncate pr-7 ${t.id === threadId ? "font-semibold" : ""}`}>
                {t.title || "Untitled"}
              </button>
              <button onClick={(e) => deleteThread(t.id, e)}
                className="absolute right-1.5 opacity-0 group-hover:opacity-100 p-1 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-all">
                <Trash2 className="size-3" />
              </button>
            </div>
          ))}
        </div>

      </aside>

      {sidebarOpen && <div className="fixed inset-0 z-20 bg-black/40 md:hidden backdrop-blur-sm" onClick={() => setSidebarOpen(false)} />}

      {/* ── Main area ── */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        <header className="flex items-center justify-between px-4 py-2.5 border-b border-border glass shrink-0">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" className="md:hidden h-8 w-8 p-0" onClick={() => setSidebarOpen((v) => !v)}>
              <PanelLeft className="size-4" />
            </Button>
            <span className="font-bold text-sm hidden md:block">Business Assistant</span>
          </div>
          <div className="flex items-center gap-2">
            <DatasetSelector datasets={datasets} selected={selectedDatasets} onChange={setSelectedDatasets} />
            <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleUpload} />
            <Button variant="outline" size="sm" disabled={uploading} onClick={() => fileInputRef.current?.click()}
              className="gap-1.5 text-xs hover:border-primary/40 hover:text-primary transition-all">
              <Upload className="size-3.5" />{uploading ? "Uploading…" : "Upload CSV"}
            </Button>
          </div>
        </header>

        {/* Status banners */}
        {hasAthenaDirectSelected && (
          <div className="px-4 py-2 bg-amber-50 dark:bg-amber-950/20 border-b border-amber-200 dark:border-amber-800/50 text-xs text-amber-700 dark:text-amber-400 flex items-center gap-2 shrink-0">
            <Cloud className="size-3.5 shrink-0" />
            Querying directly via Athena — joins with CSV or other DuckDB tables are not available in this mode.
          </div>
        )}
        {glossaryCount > 0 && (
          <div className="px-4 py-1.5 border-b border-border/40 bg-emerald-50/50 dark:bg-emerald-950/10 text-[11px] text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5 shrink-0">
            <BookOpen className="size-3 shrink-0" />
            <span><strong>{glossaryCount} glossary term{glossaryCount !== 1 ? "s" : ""}</strong> active — business definitions are applied to every query automatically.</span>
            <Link href="/glossary" className="ml-auto underline underline-offset-2 hover:text-emerald-600 transition-colors shrink-0">Manage</Link>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 max-w-5xl w-full mx-auto" onMouseUp={handleTextSelect}>
          {messages.length === 0 && !loading && (
            <div className="empty-state min-h-[60vh]">
              <div className="empty-state-icon"><Sparkles className="size-6" /></div>
              {datasets.length === 0 ? (
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <h2 className="text-xl font-bold tracking-tight">No data yet</h2>
                    <p className="text-sm text-muted-foreground max-w-xs">Upload a CSV or connect Athena to start asking questions about your data.</p>
                  </div>
                  <div className="flex flex-wrap justify-center gap-2">
                    <Link href="/datasets" className="btn-primary"><Upload className="size-4" /> Upload CSV</Link>
                    <Link href="/athena" className="btn-secondary">Connect Athena</Link>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <h2 className="text-xl font-bold tracking-tight">What would you like to know?</h2>
                    <p className="text-sm text-muted-foreground max-w-xs">
                      <strong>{datasets.length}</strong> dataset{datasets.length !== 1 ? "s" : ""} ready.
                      {selectedDatasets.length > 0 && <span className="text-primary ml-1">{selectedDatasets.length} selected.</span>}
                    </p>
                  </div>
                  <div className="flex flex-wrap justify-center gap-2">
                    {EXAMPLE_PROMPTS_BASE.map((p) => (
                      <button key={p} onClick={() => usePrompt(p)}
                        className="px-3.5 py-2 text-sm rounded-xl border border-border bg-card hover:bg-primary/5 hover:border-primary/40 hover:text-primary transition-all text-muted-foreground shadow-sm">
                        {p}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {messages.map((msg, i) => {
            // Find the user question that prompted this assistant message
            const siblingQuestion = (() => {
              for (let j = i - 1; j >= 0; j--) {
                if (messages[j].role === "user") return messages[j].content
              }
              return ""
            })()

            return (
              <div key={i} className="animate-fade-in">
                <div className={msg.role === "user" ? "" : "max-w-3xl"}>
                  <MessageBubble role={msg.role} content={msg.content} userInitial={userInitial} />
                </div>
                {msg.interpretationNote && (
                  <div className="ml-9 mt-1.5 flex items-center gap-1.5 text-[11px] text-primary/60 italic">
                    <span className="inline-flex size-4 rounded-full bg-primary/10 text-primary items-center justify-center shrink-0 not-italic text-[9px] font-bold">i</span>
                    <span dangerouslySetInnerHTML={{ __html: msg.interpretationNote.replace(/\*(.*?)\*/g, "<strong>$1</strong>") }} />
                  </div>
                )}
                {msg.role === "assistant" && msg.status === "needs_approval" && msg.draftSql && (
                  <ApprovalPanel
                    draftSql={msg.draftSql}
                    sqlExplanation={msg.sqlExplanation ?? ""}
                    loading={approvalLoading}
                    onApprove={() => handleApproval("approve")}
                    onReject={() => handleApproval("reject")}
                    onEdit={(sql) => handleApproval("edit", sql)}
                  />
                )}
                {msg.role === "assistant" && msg.resultRows && msg.resultRows.length > 0 && (
                  <ResultPanel
                    rows={msg.resultRows}
                    chartJson={msg.chartJson}
                    sql={msg.executedSql}
                    onExport={msg.executedSql ? () => handleExport(msg.executedSql!) : undefined}
                  />
                )}
                {msg.role === "assistant" && msg.agentSteps && msg.agentSteps.length > 0 && (
                  <AgentTrace steps={msg.agentSteps} onShowGraph={() => setShowGraph(true)} />
                )}
                {msg.role === "assistant" && siblingQuestion && (
                  <div className="flex items-center gap-2 ml-9 mt-1.5">
                    {msgSavedIds[i] ? (
                      <button
                        onClick={() => handleUnsave(i, msgSavedIds[i])}
                        className="flex items-center gap-1.5 text-[11px] text-primary hover:text-destructive transition-colors group"
                        title="Click to unsave"
                      >
                        <Bookmark className="size-3 fill-primary group-hover:fill-destructive/30 transition-all" />
                        Saved
                      </button>
                    ) : (
                      <button
                        onClick={() => setSaveModal({ question: msg.cleanedQuestion || siblingQuestion, sql: msg.executedSql ?? "", msgIndex: i, datasets: selectedDatasets, results: msg.resultRows ?? [] })}
                        className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-primary transition-colors group"
                      >
                        <Bookmark className="size-3 group-hover:fill-primary/20 transition-all" />
                        Save question
                      </button>
                    )}
                  </div>
                )}
                {msg.resumeQuery && !loading && (
                  <div className="flex mt-1.5 ml-9">
                    <button onClick={() => resumeStopped(msg.resumeQuery!)}
                      className="flex items-center gap-1.5 text-xs text-primary border border-primary/30 hover:border-primary hover:bg-primary/5 rounded-lg px-2.5 py-1.5 transition-all">
                      <span className="rotate-180 inline-block">↺</span> Resume query
                    </button>
                  </div>
                )}
              </div>
            )
          })}

          {error && (
            <div className="rounded-xl px-4 py-3 bg-destructive/10 border border-destructive/20 text-sm text-destructive flex items-center gap-2 animate-fade-in">
              <span className="size-2 rounded-full bg-destructive shrink-0" />{error}
            </div>
          )}

          {loading && (
            <div className="flex items-center gap-3 animate-fade-in">
              <TypingDots />
              {streamStep && AGENT_META[streamStep] && (() => {
                const Icon = AGENT_META[streamStep].icon
                return (
                  <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground/70 animate-fade-in">
                    <Icon className="size-3 text-primary/50" />
                    {AGENT_META[streamStep].label}…
                  </span>
                )
              })()}
              <button onClick={stopQuery}
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-destructive border border-border hover:border-destructive/40 hover:bg-destructive/5 rounded-lg px-2.5 py-1.5 transition-all shrink-0">
                <span className="size-2 rounded-sm bg-current" /> Stop
              </button>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-4 pb-4 pt-2 max-w-3xl w-full mx-auto shrink-0">
          <form onSubmit={handleSubmit}
            className="flex items-end gap-2 rounded-2xl border border-border bg-card px-4 py-3 shadow-sm focus-within:ring-2 focus-within:ring-primary/30 focus-within:border-primary/40 transition-all">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); handleSubmit(e); return }
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(e) }
              }}
              placeholder="Ask about your data… (Enter to send, Shift+Enter for new line)"
              disabled={loading}
              rows={1}
              className="flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-muted-foreground disabled:opacity-50 max-h-45 leading-relaxed"
            />
            <Button type="submit" size="sm" disabled={loading || !input.trim()}
              className="shrink-0 px-4 gradient-primary text-white border-0 hover:opacity-90 shadow-sm">
              Send
            </Button>
          </form>
          <p className="text-center text-xs text-muted-foreground mt-1.5">Enter to send · Shift+Enter for new line</p>
          <p className="text-center text-xs text-muted-foreground mt-1">Business Assistant is AI and can make mistakes. Please double-check responses.</p>
        </div>
      </div>
    </div>
  )
}
