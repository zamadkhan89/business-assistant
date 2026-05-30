"use client"

import { useCallback, useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import Link from "next/link"
import {
  FlaskConical, BarChart2, AlertTriangle,
  GitBranch, TrendingUp, Play, Loader2, Database,
  ChevronDown, Info, Table2, Upload, ClipboardList, Zap,
} from "lucide-react"
import { ChartMessage } from "@/components/chat/ChartMessage"

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

interface Dataset { table_name: string; row_count: number }
interface Section {
  title: string
  type: "stats" | "table" | "chart" | "text"
  stats?: Record<string, string>
  data?: Record<string, unknown>[]
  chart_json?: string
  text?: string
  description?: string
}
interface AnalysisResult {
  template: string
  template_name: string
  table_name: string
  sections: Section[]
}
interface RunAllResult {
  table_name: string
  results: Array<{
    template: string
    template_name: string
    sections: Section[]
    error: string | null
  }>
}

const TEMPLATES = [
  {
    id: "profiling",
    name: "Full Profiling Report",
    description: "Shape, dtypes, nulls, per-column stats, quartiles, skewness, outlier flags, correlations.",
    icon: ClipboardList,
    color: "from-blue-500 to-blue-600",
    bg: "bg-blue-50 dark:bg-blue-950/30",
    border: "border-blue-200 dark:border-blue-800",
    text: "text-blue-700 dark:text-blue-400",
    badge: "Comprehensive",
  },
  {
    id: "distribution",
    name: "Distributions",
    description: "Min, max, mean, median and std dev for numeric columns. Top values for text columns.",
    icon: BarChart2,
    color: "from-violet-500 to-violet-600",
    bg: "bg-violet-50 dark:bg-violet-950/30",
    border: "border-violet-200 dark:border-violet-800",
    text: "text-violet-700 dark:text-violet-400",
    badge: null,
  },
  {
    id: "outliers",
    name: "Outlier Detection",
    description: "IQR method — finds rows where values fall outside the expected range.",
    icon: AlertTriangle,
    color: "from-amber-500 to-amber-600",
    bg: "bg-amber-50 dark:bg-amber-950/30",
    border: "border-amber-200 dark:border-amber-800",
    text: "text-amber-700 dark:text-amber-400",
    badge: null,
  },
  {
    id: "correlation",
    name: "Correlations",
    description: "Pearson correlation heatmap and ranked pairs between all numeric columns.",
    icon: GitBranch,
    color: "from-emerald-500 to-emerald-600",
    bg: "bg-emerald-50 dark:bg-emerald-950/30",
    border: "border-emerald-200 dark:border-emerald-800",
    text: "text-emerald-700 dark:text-emerald-400",
    badge: null,
  },
  {
    id: "time_trends",
    name: "Time Trends",
    description: "Monthly aggregations of numeric columns using a detected date column.",
    icon: TrendingUp,
    color: "from-rose-500 to-rose-600",
    bg: "bg-rose-50 dark:bg-rose-950/30",
    border: "border-rose-200 dark:border-rose-800",
    text: "text-rose-700 dark:text-rose-400",
    badge: null,
  },
]

function StatsSection({ stats }: { stats: Record<string, string> }) {
  return (
    <div className="flex flex-wrap gap-3">
      {Object.entries(stats).map(([k, v]) => (
        <div key={k} className="bg-muted/50 border border-border rounded-xl px-4 py-3 min-w-32">
          <p className="text-xs text-muted-foreground mb-0.5">{k}</p>
          <p className="text-xl font-bold tabular-nums">{v}</p>
        </div>
      ))}
    </div>
  )
}

function TableSection({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return <p className="text-sm text-muted-foreground">No data.</p>
  const cols = Object.keys(data[0])
  return (
    <div className="overflow-x-auto rounded-lg border border-border max-h-72">
      <table className="w-full text-xs border-collapse">
        <thead className="sticky top-0 bg-muted/80 backdrop-blur-sm">
          <tr>
            {cols.map((c) => (
              <th key={c} className="px-3 py-2 text-left font-semibold border-b border-border whitespace-nowrap">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, ri) => (
            <tr key={ri} className="border-b border-border/30 last:border-0 hover:bg-muted/30 transition-colors">
              {cols.map((c) => {
                const val = row[c]
                const isNum = typeof val === "number"
                return (
                  <td key={c} className="px-3 py-1.5 whitespace-nowrap">
                    {isNum
                      ? <span className="font-mono tabular-nums">{(val as number).toLocaleString()}</span>
                      : String(val ?? "")}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SectionRenderer({ section }: { section: Section }) {
  return (
    <div className="card-elevated p-4 space-y-3">
      <div>
        <h3 className="font-semibold text-sm">{section.title}</h3>
        {section.description && (
          <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1">
            <Info className="size-3 shrink-0" />{section.description}
          </p>
        )}
      </div>
      {section.type === "stats" && section.stats && <StatsSection stats={section.stats} />}
      {section.type === "table" && section.data && <TableSection data={section.data} />}
      {section.type === "chart" && section.chart_json && <ChartMessage chartJson={section.chart_json} />}
      {section.type === "text" && <p className="text-sm text-muted-foreground">{section.text}</p>}
    </div>
  )
}

function TemplateResultBlock({
  result,
}: {
  result: RunAllResult["results"][number]
}) {
  const [open, setOpen] = useState(true)
  const tpl = TEMPLATES.find((t) => t.id === result.template)
  return (
    <div className="border border-border rounded-2xl overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-5 py-4 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
      >
        {tpl && (
          <div className={`size-7 rounded-lg bg-linear-to-br ${tpl.color} flex items-center justify-center shrink-0`}>
            <tpl.icon className="size-3.5 text-white" />
          </div>
        )}
        <span className="font-semibold text-sm flex-1">{result.template_name}</span>
        {result.error && <span className="text-xs text-destructive">{result.error}</span>}
        {!result.error && (
          <span className="text-xs text-muted-foreground">{result.sections.length} sections</span>
        )}
        <ChevronDown className={`size-4 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="p-4 space-y-4 bg-background">
          {result.error ? (
            <p className="text-sm text-destructive">{result.error}</p>
          ) : result.sections.length === 0 ? (
            <p className="text-sm text-muted-foreground">No results.</p>
          ) : result.sections.map((s, i) => <SectionRenderer key={i} section={s} />)}
        </div>
      )}
    </div>
  )
}

export default function AnalysisPage() {
  const { data: session } = useSession()
  const [datasets, setDatasets]             = useState<Dataset[]>([])
  const [selectedTable, setSelectedTable]   = useState("")
  const [selectedTemplate, setSelectedTemplate] = useState("profiling")
  const [running, setRunning]               = useState(false)
  const [runningAll, setRunningAll]         = useState(false)
  const [result, setResult]                 = useState<AnalysisResult | null>(null)
  const [allResults, setAllResults]         = useState<RunAllResult | null>(null)
  const [error, setError]                   = useState<string | null>(null)
  const [mode, setMode]                     = useState<"single" | "all">("single")

  const authHeader = { Authorization: `Bearer ${session?.accessToken}` }

  const fetchDatasets = useCallback(async () => {
    if (!session?.accessToken) return
    try {
      const r = await fetch(`${BACKEND}/api/datasets`, { headers: authHeader })
      if (r.ok) {
        const data: Dataset[] = await r.json()
        setDatasets(data)
        if (data.length > 0 && !selectedTable) setSelectedTable(data[0].table_name)
      }
    } catch { /* ignore */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  useEffect(() => { fetchDatasets() }, [fetchDatasets])

  async function handleRun() {
    if (!selectedTable || !selectedTemplate) return
    setRunning(true)
    setResult(null)
    setAllResults(null)
    setError(null)
    try {
      const r = await fetch(`${BACKEND}/api/analysis/run`, {
        method: "POST",
        headers: { ...authHeader, "Content-Type": "application/json" },
        body: JSON.stringify({ table_name: selectedTable, template: selectedTemplate }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
      setResult(d)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRunning(false)
    }
  }

  async function handleRunAll() {
    if (!selectedTable) return
    setRunningAll(true)
    setResult(null)
    setAllResults(null)
    setError(null)
    try {
      const r = await fetch(`${BACKEND}/api/analysis/run-all`, {
        method: "POST",
        headers: { ...authHeader, "Content-Type": "application/json" },
        body: JSON.stringify({ table_name: selectedTable }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
      setAllResults(d)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setRunningAll(false)
    }
  }

  const chosenTemplate = TEMPLATES.find((t) => t.id === selectedTemplate)

  return (
    <div className="min-h-screen bg-background">
      <div className="page-header flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="size-9 rounded-xl bg-linear-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-sm">
            <FlaskConical className="size-4 text-white" />
          </div>
          <div>
            <h1 className="page-title">Analysis Templates</h1>
            <p className="page-subtitle">Full profiling, distributions, outliers, correlations, and time trends</p>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto p-6 space-y-6">

        {/* Dataset selector */}
        <div className="card-elevated p-4">
          <p className="section-label mb-2 flex items-center gap-1.5">
            <Database className="size-3.5" /> Select Dataset
          </p>
          {datasets.length === 0 ? (
            <div className="flex items-center gap-3 py-2">
              <p className="text-sm text-muted-foreground">No datasets available.</p>
              <Link href="/datasets" className="btn-primary text-xs py-1.5 px-3">
                <Upload className="size-3" /> Upload CSV
              </Link>
            </div>
          ) : (
            <div className="relative max-w-xs">
              <select
                value={selectedTable}
                onChange={(e) => { setSelectedTable(e.target.value); setResult(null); setAllResults(null) }}
                className="input-modern pr-8 appearance-none cursor-pointer"
              >
                {datasets.map((d) => (
                  <option key={d.table_name} value={d.table_name}>
                    {d.table_name} ({d.row_count.toLocaleString()} rows)
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
            </div>
          )}
        </div>

        {/* Mode toggle */}
        <div className="flex gap-2 bg-muted/50 rounded-xl p-1 max-w-xs">
          {(["single", "all"] as const).map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setResult(null); setAllResults(null) }}
              className={`flex-1 text-xs py-1.5 rounded-lg font-medium transition-all ${
                mode === m ? "bg-card shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {m === "single" ? "Single template" : "Run all (5)"}
            </button>
          ))}
        </div>

        {mode === "single" ? (
          <>
            {/* Template selector */}
            <div>
              <p className="section-label mb-3">Choose Analysis</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {TEMPLATES.map((t) => {
                  const Icon = t.icon
                  const active = selectedTemplate === t.id
                  return (
                    <button
                      key={t.id}
                      onClick={() => { setSelectedTemplate(t.id); setResult(null) }}
                      className={`text-left rounded-xl border-2 p-4 transition-all ${
                        active
                          ? `${t.bg} ${t.border} shadow-sm`
                          : "bg-card border-border hover:border-border/80 hover:bg-muted/30"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div className={`size-8 rounded-lg bg-linear-to-br ${t.color} flex items-center justify-center shrink-0`}>
                          <Icon className="size-4 text-white" />
                        </div>
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className={`font-semibold text-sm ${active ? t.text : ""}`}>{t.name}</p>
                            {t.badge && (
                              <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                                {t.badge}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{t.description}</p>
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>

            <button
              onClick={handleRun}
              disabled={running || !selectedTable}
              className="btn-primary w-full py-3 text-sm justify-center"
            >
              {running ? (
                <><Loader2 className="size-4 animate-spin" /> Running {chosenTemplate?.name}…</>
              ) : (
                <><Play className="size-4" /> Run {chosenTemplate?.name ?? "Analysis"}</>
              )}
            </button>

            {error && (
              <div className="rounded-xl px-4 py-3 bg-destructive/10 border border-destructive/20 text-sm text-destructive">
                {error}
              </div>
            )}

            {result && (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  {chosenTemplate && (
                    <div className={`size-6 rounded-md bg-linear-to-br ${chosenTemplate.color} flex items-center justify-center`}>
                      <chosenTemplate.icon className="size-3.5 text-white" />
                    </div>
                  )}
                  <h2 className="font-semibold">
                    {result.template_name} — <span className="font-mono text-primary">{result.table_name}</span>
                  </h2>
                  <span className="ml-auto text-xs text-muted-foreground flex items-center gap-1">
                    <Table2 className="size-3" /> {result.sections.length} section{result.sections.length !== 1 ? "s" : ""}
                  </span>
                </div>
                {result.sections.map((section, i) => (
                  <SectionRenderer key={i} section={section} />
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            <div className="card-elevated p-5 space-y-3">
              <div className="flex items-start gap-3">
                <div className="size-9 rounded-xl bg-linear-to-br from-violet-500 to-purple-600 flex items-center justify-center shrink-0">
                  <Zap className="size-4 text-white" />
                </div>
                <div>
                  <p className="font-semibold text-sm">Run All 5 Analyses</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Runs Full Profiling, Distributions, Outlier Detection, Correlations, and Time Trends back-to-back.
                    Results appear collapsed — expand each section to explore.
                  </p>
                </div>
              </div>
              <button
                onClick={handleRunAll}
                disabled={runningAll || !selectedTable}
                className="btn-primary w-full py-3 text-sm justify-center"
              >
                {runningAll ? (
                  <><Loader2 className="size-4 animate-spin" /> Running all analyses… this may take a moment</>
                ) : (
                  <><Zap className="size-4" /> Run All Analyses on {selectedTable || "selected dataset"}</>
                )}
              </button>
            </div>

            {error && (
              <div className="rounded-xl px-4 py-3 bg-destructive/10 border border-destructive/20 text-sm text-destructive">
                {error}
              </div>
            )}

            {allResults && (
              <div className="space-y-3">
                <p className="text-sm font-semibold">
                  Results for <span className="font-mono text-primary">{allResults.table_name}</span>
                </p>
                {allResults.results.map((r) => (
                  <TemplateResultBlock key={r.template} result={r} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
