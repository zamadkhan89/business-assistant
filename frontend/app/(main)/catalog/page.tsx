"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useSession } from "next-auth/react"
import Link from "next/link"
import {
  ArrowLeft, BookOpen, ChevronDown, ChevronRight, Loader2,
  Plus, Save, Sparkles, Star, Trash2, Wand2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

interface JoinHint { left_table: string; left_col: string; right_table: string; right_col: string; description: string }
interface ColumnMeta {
  column_name: string; display_name: string | null; description: string | null
  data_type: string | null; sample_values: string[]; is_kpi: boolean; kpi_definition: string | null
}
interface TableMeta {
  table_key: string; source_type: string; display_name: string | null
  description: string | null; business_context: string | null
  join_hints: JoinHint[]; columns: ColumnMeta[]
}

function Msg({ ok, text }: { ok: boolean; text: string }) {
  return (
    <p className={`text-sm ${ok ? "text-green-600 dark:text-green-400" : "text-destructive"}`}>
      {ok ? "✓ " : "✗ "}{text}
    </p>
  )
}

function ColumnEditor({ col, tableKey, authHeader, onSaved }: {
  col: ColumnMeta; tableKey: string
  authHeader: Record<string, string>; onSaved: (c: ColumnMeta) => void
}) {
  const [desc, setDesc]   = useState(col.description ?? "")
  const [disp, setDisp]   = useState(col.display_name ?? "")
  const [isKpi, setIsKpi] = useState(col.is_kpi)
  const [kpiDef, setKpiDef] = useState(col.kpi_definition ?? "")
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const mountedRef = useRef(false)

  // Sync local state when parent pushes enriched data (but not on first mount)
  useEffect(() => {
    if (!mountedRef.current) { mountedRef.current = true; return }
    setDesc(col.description ?? "")
    setDisp(col.display_name ?? "")
    setIsKpi(col.is_kpi)
    setKpiDef(col.kpi_definition ?? "")
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [col.description, col.display_name, col.is_kpi, col.kpi_definition])

  async function save() {
    setSaving(true); setMsg(null)
    try {
      const r = await fetch(`${BACKEND}/api/catalog/${encodeURIComponent(tableKey)}/columns/${encodeURIComponent(col.column_name)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({ display_name: disp, description: desc, is_kpi: isKpi, kpi_definition: kpiDef }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
      onSaved(d)
      setMsg({ ok: true, text: "Saved" })
    } catch (err) {
      setMsg({ ok: false, text: err instanceof Error ? err.message : "Failed" })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="border border-border rounded-xl p-4 space-y-3 bg-background">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="font-mono text-sm font-semibold">{col.column_name}</span>
          <span className="ml-2 text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{col.data_type}</span>
          {col.sample_values?.length > 0 && (
            <span className="ml-2 text-xs text-muted-foreground/60">
              e.g. {col.sample_values.slice(0, 3).join(", ")}
            </span>
          )}
        </div>
        <label className="flex items-center gap-1.5 cursor-pointer shrink-0">
          <input type="checkbox" checked={isKpi} onChange={e => setIsKpi(e.target.checked)} className="size-3.5 accent-primary" />
          <span className="text-xs flex items-center gap-1"><Star className="size-3 text-amber-500" /> KPI</span>
        </label>
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label className="text-xs">Display name</Label>
          <Input value={disp} onChange={e => setDisp(e.target.value)} placeholder={col.column_name} className="h-8 text-xs" />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Description</Label>
          <Input value={desc} onChange={e => setDesc(e.target.value)} placeholder="What this column means…" className="h-8 text-xs" />
        </div>
      </div>
      {isKpi && (
        <div className="space-y-1">
          <Label className="text-xs">KPI definition / formula</Label>
          <Input value={kpiDef} onChange={e => setKpiDef(e.target.value)} placeholder="e.g. SUM(revenue) / COUNT(orders)" className="h-8 text-xs" />
        </div>
      )}
      <div className="flex items-center gap-3">
        <Button size="sm" className="h-7 text-xs gap-1.5" onClick={save} disabled={saving}>
          {saving ? <Loader2 className="size-3 animate-spin" /> : <Save className="size-3" />} Save
        </Button>
        {msg && <Msg ok={msg.ok} text={msg.text} />}
      </div>
    </div>
  )
}

function TableEditor({ meta, authHeader, onRefresh }: {
  meta: TableMeta; authHeader: Record<string, string>; onRefresh: () => void
}) {
  const [open, setOpen] = useState(false)
  const [desc, setDesc]    = useState(meta.description ?? "")
  const [disp, setDisp]    = useState(meta.display_name ?? "")
  const [biz, setBiz]      = useState(meta.business_context ?? "")
  const [joins, setJoins]  = useState<JoinHint[]>(meta.join_hints ?? [])
  const [saving, setSaving]     = useState(false)
  const [enriching, setEnriching] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [columns, setColumns] = useState<ColumnMeta[]>(meta.columns ?? [])

  async function saveTable() {
    setSaving(true); setMsg(null)
    try {
      const r = await fetch(`${BACKEND}/api/catalog/${encodeURIComponent(meta.table_key)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({ display_name: disp, description: desc, business_context: biz, join_hints: joins }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
      setMsg({ ok: true, text: "Table metadata saved" })
    } catch (err) {
      setMsg({ ok: false, text: err instanceof Error ? err.message : "Failed" })
    } finally {
      setSaving(false)
    }
  }

  async function enrich() {
    setEnriching(true); setMsg(null)
    try {
      const r = await fetch(`${BACKEND}/api/catalog/${encodeURIComponent(meta.table_key)}/enrich`, {
        method: "POST", headers: authHeader,
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
      setDesc(d.description ?? desc)
      setDisp(d.display_name ?? disp)
      setColumns(d.columns ?? columns)
      setMsg({ ok: true, text: "AI enrichment complete — descriptions and display names populated. Review and save." })
    } catch (err) {
      setMsg({ ok: false, text: err instanceof Error ? err.message : "Enrichment failed" })
    } finally {
      setEnriching(false)
    }
  }

  function addJoin() {
    setJoins(j => [...j, { left_table: meta.table_key, left_col: "", right_table: "", right_col: "", description: "" }])
  }
  function removeJoin(i: number) { setJoins(j => j.filter((_, idx) => idx !== i)) }
  function updateJoin(i: number, field: keyof JoinHint, val: string) {
    setJoins(j => j.map((jh, idx) => idx === i ? { ...jh, [field]: val } : jh))
  }

  return (
    <div className="rounded-2xl border border-border bg-card overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-muted/40 transition-colors text-left"
      >
        <div className="flex items-center gap-3">
          <BookOpen className="size-4 text-muted-foreground shrink-0" />
          <div>
            <p className="font-semibold text-sm">{disp || meta.table_key}</p>
            <p className="text-xs text-muted-foreground font-mono mt-0.5">{meta.table_key}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {desc && <p className="text-xs text-muted-foreground hidden sm:block max-w-xs truncate">{desc}</p>}
          {open ? <ChevronDown className="size-4 text-muted-foreground shrink-0" /> : <ChevronRight className="size-4 text-muted-foreground shrink-0" />}
        </div>
      </button>

      {open && (
        <div className="border-t border-border px-5 py-5 space-y-6">
          {/* Table-level fields */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Table metadata</h3>
              <Button size="sm" variant="outline" className="h-7 text-xs gap-1.5" onClick={enrich} disabled={enriching}>
                {enriching ? <Loader2 className="size-3 animate-spin" /> : <Wand2 className="size-3" />}
                {enriching ? "Enriching…" : "AI Enrich"}
              </Button>
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs">Display name</Label>
                <Input value={disp} onChange={e => setDisp(e.target.value)} placeholder={meta.table_key} className="h-9" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Short description</Label>
                <Input value={desc} onChange={e => setDesc(e.target.value)} placeholder="What this table represents…" className="h-9" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Business context</Label>
              <textarea
                value={biz} onChange={e => setBiz(e.target.value)}
                placeholder="Describe how this table is used in business decisions, what KPIs it drives, data refresh frequency, etc."
                className="w-full h-20 rounded-lg border border-input bg-transparent px-3 py-2 text-sm resize-none focus:outline-none focus:ring-[3px] focus:ring-ring/50 focus:border-ring placeholder:text-muted-foreground"
              />
            </div>
          </div>

          {/* Join hints */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">Join hints</h3>
              <Button size="sm" variant="outline" className="h-7 text-xs gap-1.5" onClick={addJoin}>
                <Plus className="size-3" /> Add join
              </Button>
            </div>
            {joins.length === 0 ? (
              <p className="text-xs text-muted-foreground">No join hints defined. Add how this table connects to others.</p>
            ) : joins.map((jh, i) => (
              <div key={i} className="grid grid-cols-2 sm:grid-cols-5 gap-2 items-end border border-border rounded-xl p-3">
                <div className="space-y-1 col-span-1">
                  <Label className="text-[10px]">Left table</Label>
                  <Input value={jh.left_table} onChange={e => updateJoin(i, "left_table", e.target.value)} className="h-8 text-xs font-mono" />
                </div>
                <div className="space-y-1 col-span-1">
                  <Label className="text-[10px]">Left column</Label>
                  <Input value={jh.left_col} onChange={e => updateJoin(i, "left_col", e.target.value)} className="h-8 text-xs font-mono" />
                </div>
                <div className="space-y-1 col-span-1">
                  <Label className="text-[10px]">Right table</Label>
                  <Input value={jh.right_table} onChange={e => updateJoin(i, "right_table", e.target.value)} className="h-8 text-xs font-mono" />
                </div>
                <div className="space-y-1 col-span-1">
                  <Label className="text-[10px]">Right column</Label>
                  <Input value={jh.right_col} onChange={e => updateJoin(i, "right_col", e.target.value)} className="h-8 text-xs font-mono" />
                </div>
                <div className="space-y-1 col-span-2 sm:col-span-1">
                  <Label className="text-[10px]">Description</Label>
                  <div className="flex gap-1">
                    <Input value={jh.description} onChange={e => updateJoin(i, "description", e.target.value)} className="h-8 text-xs" />
                    <button onClick={() => removeJoin(i)} className="p-1.5 text-muted-foreground hover:text-destructive rounded-md hover:bg-muted transition-colors shrink-0">
                      <Trash2 className="size-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Save table */}
          <div className="flex items-center gap-3">
            <Button size="sm" className="gap-1.5" onClick={saveTable} disabled={saving}>
              {saving ? <><Loader2 className="size-3.5 animate-spin" /> Saving…</> : <><Save className="size-3.5" /> Save table metadata</>}
            </Button>
            {msg && <Msg ok={msg.ok} text={msg.text} />}
          </div>

          {/* Columns */}
          {columns.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold">Column metadata ({columns.length} columns)</h3>
              <div className="space-y-2">
                {columns.map(col => (
                  <ColumnEditor
                    key={col.column_name}
                    col={col}
                    tableKey={meta.table_key}
                    authHeader={authHeader}
                    onSaved={updated => setColumns(cs => cs.map(c => c.column_name === updated.column_name ? updated : c))}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function CatalogPage() {
  const { data: session } = useSession()
  const authHeader = { Authorization: `Bearer ${session?.accessToken}` }

  const [catalog, setCatalog] = useState<TableMeta[]>([])
  const [datasets, setDatasets] = useState<{ table_name: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)

  const fetchCatalog = useCallback(async () => {
    if (!session?.accessToken) return
    const [cat, ds] = await Promise.all([
      fetch(`${BACKEND}/api/catalog`, { headers: authHeader }).then(r => r.ok ? r.json() : []),
      fetch(`${BACKEND}/api/datasets`, { headers: authHeader }).then(r => r.ok ? r.json() : []),
    ])
    setCatalog(cat)
    setDatasets(ds)
    setLoading(false)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  useEffect(() => { fetchCatalog() }, [fetchCatalog])

  // Tables that have been uploaded but don't have catalog metadata yet
  const catalogKeys = new Set(catalog.map(c => c.table_key))
  const unregistered = datasets.filter(d => !catalogKeys.has(d.table_name))

  async function syncAll() {
    setSyncing(true)
    try {
      await Promise.all(
        unregistered.map(d =>
          fetch(`${BACKEND}/api/catalog/${encodeURIComponent(d.table_name)}/sync-schema`, {
            method: "POST", headers: authHeader,
          })
        )
      )
      await fetchCatalog()
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <nav className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-md">
        <div className="max-w-5xl mx-auto flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2">
            <BookOpen className="size-4 text-primary" />
            <span className="font-semibold text-sm">Data Catalog</span>
          </div>
          <div className="flex items-center gap-2">
            {unregistered.length > 0 && (
              <Button size="sm" variant="outline" className="gap-1.5 text-xs" onClick={syncAll} disabled={syncing}>
                {syncing ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
                Sync {unregistered.length} new table{unregistered.length !== 1 ? "s" : ""}
              </Button>
            )}
          </div>
        </div>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Data Catalog</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Add business context, column descriptions, KPI flags, and join hints to help the AI write better queries.
          </p>
        </div>

        {loading ? (
          <div className="text-center py-16">
            <Loader2 className="size-8 animate-spin text-muted-foreground mx-auto" />
          </div>
        ) : datasets.length === 0 ? (
          <div className="text-center py-16 space-y-3">
            <BookOpen className="size-10 text-muted-foreground/40 mx-auto" />
            <p className="font-semibold">No datasets yet</p>
            <p className="text-sm text-muted-foreground">Upload a CSV first to add it to the catalog.</p>
            <Link href="/datasets" className="inline-flex items-center gap-2 text-sm text-primary hover:underline underline-offset-2">
              Go to Datasets <ArrowLeft className="size-3.5 rotate-180" />
            </Link>
          </div>
        ) : (
          <>
            {unregistered.length > 0 && (
              <div className="rounded-xl border border-amber-300 dark:border-amber-700 bg-amber-50/80 dark:bg-amber-950/30 px-4 py-3 text-sm text-amber-700 dark:text-amber-400">
                <strong>{unregistered.length}</strong> uploaded table{unregistered.length !== 1 ? "s are" : " is"} not yet in the catalog.
                Click <strong>Sync</strong> above to import them.
              </div>
            )}
            <div className="space-y-3">
              {catalog.map(meta => (
                <TableEditor key={meta.table_key} meta={meta} authHeader={authHeader} onRefresh={fetchCatalog} />
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  )
}
