"use client"

import { useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import {
  ChevronDown, ChevronRight, Cloud, Database,
  Loader2, Play, RefreshCw, Table2, AlertCircle, Save,
  Trash2, CheckCircle2, Eye, EyeOff, X, User, Globe,
  Plus, Download, RotateCcw, Zap,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

interface AthenaStatus {
  configured: boolean
  source: "personal" | "global" | "env" | null
  active_sources: string[]
  region: string | null
  has_personal: boolean
  has_global: boolean
  has_env: boolean
}
interface SavedConfig {
  aws_region: string
  aws_access_key_id: string
  aws_secret_access_key_hint: string
  athena_workgroup: string
  athena_output_bucket: string
}
interface GlueDb { name: string; description: string; source: string }
interface GlueTable { name: string; database: string; description: string; columns: GlueColumn[] }
interface GlueColumn { name: string; type: string; comment: string }
interface LoadedTableMeta {
  duckdb_table_name: string
  athena_database: string
  athena_table_name: string
  athena_cred_source: string
  row_count: number
  row_limit_applied: boolean
  loaded_at: string | null
}
interface DirectRefMeta {
  ref_name: string
  athena_database: string
  athena_table: string
  athena_cred_source: string
}

const SOURCE_LABELS: Record<string, { label: string; color: string }> = {
  personal: { label: "Personal",  color: "bg-blue-100 dark:bg-blue-950/40 text-blue-700 dark:text-blue-300" },
  global:   { label: "Shared",    color: "bg-amber-100 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300" },
  env:      { label: "Env vars",  color: "bg-muted text-muted-foreground" },
}

function fmtRows(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M rows`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K rows`
  return `${n} rows`
}

function fmtDate(iso: string | null) {
  if (!iso) return ""
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
}

// ── Credential form ────────────────────────────────────────────────────────

function CredentialForm({ title, icon: Icon, iconColor, authHeader, saveUrl, existing, onSaved, onCancel, onDelete }: {
  title: string
  icon: React.ElementType
  iconColor: string
  authHeader: Record<string, string>
  saveUrl: string
  existing: SavedConfig | null
  onSaved: () => void
  onCancel?: () => void
  onDelete?: () => void
}) {
  const [region,    setRegion]    = useState(existing?.aws_region ?? "us-east-1")
  const [keyId,     setKeyId]     = useState(existing?.aws_access_key_id ?? "")
  const [secret,    setSecret]    = useState("")
  const [workgroup, setWorkgroup] = useState(existing?.athena_workgroup ?? "primary")
  const [bucket,    setBucket]    = useState(existing?.athena_output_bucket ?? "")
  const [showSec,   setShowSec]   = useState(false)
  const [saving,    setSaving]    = useState(false)
  const [deleting,  setDeleting]  = useState(false)
  const [err,       setErr]       = useState("")

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    if (!keyId.trim()) { setErr("Access Key ID is required."); return }
    if (!secret.trim()) { setErr("Secret Access Key is required."); return }
    setSaving(true); setErr("")
    try {
      const r = await fetch(`${BACKEND}${saveUrl}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({ aws_region: region, aws_access_key_id: keyId, aws_secret_access_key: secret, athena_workgroup: workgroup, athena_output_bucket: bucket }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
      onSaved()
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed")
    } finally { setSaving(false) }
  }

  async function handleDelete() {
    if (!confirm(`Remove ${title.toLowerCase()}? This cannot be undone.`)) return
    setDeleting(true)
    try {
      await fetch(`${BACKEND}${saveUrl}`, { method: "DELETE", headers: authHeader })
      onDelete?.()
    } finally { setDeleting(false) }
  }

  return (
    <div className="rounded-2xl border border-border bg-card p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`size-9 rounded-xl flex items-center justify-center ${iconColor}`}>
            <Icon className="size-4" />
          </div>
          <div>
            <p className="font-semibold text-sm">{title}</p>
            {existing && <p className="text-xs text-muted-foreground font-mono mt-0.5">{existing.aws_access_key_id} · {existing.aws_secret_access_key_hint} · {existing.aws_region}</p>}
          </div>
        </div>
        {onCancel && (
          <button onClick={onCancel} className="p-1.5 rounded-lg hover:bg-muted transition-colors text-muted-foreground hover:text-foreground">
            <X className="size-4" />
          </button>
        )}
      </div>

      <form onSubmit={handleSave} className="space-y-3">
        <div className="grid sm:grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-xs">AWS Region</Label>
            <Input value={region} onChange={e => setRegion(e.target.value)} placeholder="us-east-1" className="h-9 font-mono text-sm" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Athena Workgroup</Label>
            <Input value={workgroup} onChange={e => setWorkgroup(e.target.value)} placeholder="primary" className="h-9 font-mono text-sm" />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">AWS Access Key ID</Label>
          <Input value={keyId} onChange={e => setKeyId(e.target.value)} placeholder="AKIAIOSFODNN7EXAMPLE" className="h-9 font-mono text-sm" autoComplete="off" />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">AWS Secret Access Key</Label>
          <div className="flex items-center rounded-lg border border-input bg-transparent focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50 transition-colors">
            <input
              type={showSec ? "text" : "password"}
              value={secret}
              onChange={e => setSecret(e.target.value)}
              placeholder={existing ? `Current: ${existing.aws_secret_access_key_hint} — enter new to change` : "wJalrXUtnFEMI/K7MDENG/…"}
              autoComplete="new-password"
              className="flex-1 h-9 px-3 bg-transparent outline-none text-sm font-mono placeholder:text-muted-foreground"
            />
            <button type="button" onClick={() => setShowSec(v => !v)} className="px-2.5 text-muted-foreground hover:text-foreground transition-colors">
              {showSec ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Athena Output Bucket <span className="text-muted-foreground font-normal">(required for queries)</span></Label>
          <Input value={bucket} onChange={e => setBucket(e.target.value)} placeholder="s3://my-bucket/athena-results/" className="h-9 font-mono text-sm" />
        </div>
        {err && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive flex items-center gap-2">
            <AlertCircle className="size-4 shrink-0" /> {err}
          </div>
        )}
        <div className="flex items-center gap-2 pt-1">
          <Button type="submit" disabled={saving} className="gap-1.5">
            {saving ? <><Loader2 className="size-4 animate-spin" /> Saving…</> : <><Save className="size-4" /> Save</>}
          </Button>
          {onCancel && <Button type="button" variant="outline" onClick={onCancel}>Cancel</Button>}
          {onDelete && existing && (
            <Button type="button" variant="ghost" className="ml-auto text-destructive hover:text-destructive hover:bg-destructive/10 gap-1.5" onClick={handleDelete} disabled={deleting}>
              {deleting ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />} Remove
            </Button>
          )}
        </div>
      </form>
    </div>
  )
}

// ── Connection card (read-only summary) ────────────────────────────────────

function ConnectionCard({ title, icon: Icon, iconColor, badge, badgeColor, saved, onEdit, onRemove, envNote, canEdit }: {
  title: string; icon: React.ElementType; iconColor: string
  badge: string; badgeColor: string
  saved: SavedConfig | null; onEdit: () => void; onRemove?: () => void; envNote?: boolean
  canEdit?: boolean
}) {
  const editable = canEdit ?? true
  return (
    <div className="rounded-2xl border border-border bg-card p-5">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`size-9 rounded-xl flex items-center justify-center shrink-0 ${iconColor}`}>
            <Icon className="size-4" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="font-semibold text-sm">{title}</p>
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${badgeColor}`}>{badge}</span>
              {!editable && <span className="text-[10px] text-muted-foreground">(managed by admin)</span>}
            </div>
            {saved && <p className="text-xs text-muted-foreground font-mono mt-0.5 truncate">{saved.aws_access_key_id} · {saved.aws_secret_access_key_hint} · {saved.aws_region}</p>}
            {envNote && !saved && <p className="text-xs text-muted-foreground mt-0.5">Configured via server environment variables</p>}
          </div>
        </div>
        {editable && (
          <div className="flex items-center gap-1.5 shrink-0">
            <Button size="sm" variant="outline" className="h-7 text-xs" onClick={onEdit}>{saved ? "Edit" : "Configure"}</Button>
            {onRemove && saved && (
              <Button size="sm" variant="ghost" className="h-7 text-xs text-destructive hover:text-destructive hover:bg-destructive/10" onClick={onRemove}>
                <Trash2 className="size-3" />
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Table / DB browser ─────────────────────────────────────────────────────

function ColTag({ col }: { col: GlueColumn }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-muted text-xs font-mono">
      {col.name}
      <span className="text-muted-foreground opacity-60">{col.type}</span>
      {col.comment && <span className="text-muted-foreground/50 text-[10px]" title={col.comment}>ⓘ</span>}
    </span>
  )
}

function TableRow({ tbl, database, source, authHeader, loadedMeta, onLoadChange, isDirectRef, onDirectRefChange }: {
  tbl: GlueTable
  database: string
  source: string
  authHeader: Record<string, string>
  loadedMeta: LoadedTableMeta | undefined
  onLoadChange: (key: string, meta: LoadedTableMeta | null) => void
  isDirectRef: boolean
  onDirectRefChange: (key: string, isDirectRef: boolean) => void
}) {
  const [open,           setOpen]           = useState(false)
  const [preview,        setPreview]        = useState<Record<string, string>[] | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [previewErr,     setPreviewErr]     = useState("")
  const [busy,           setBusy]           = useState(false)
  const [loadingMsg,     setLoadingMsg]     = useState("")
  const [opErr,          setOpErr]          = useState("")
  const tableKey = `${database}.${tbl.name}`
  const isLoaded = !!loadedMeta

  // Unified mode selector: handles activate, deactivate, and switch between modes
  async function selectMode(mode: "duckdb" | "athena") {
    const alreadyActive = mode === "duckdb" ? isLoaded : isDirectRef
    const otherActive   = mode === "duckdb" ? isDirectRef : isLoaded
    setOpErr("")

    // Deactivate if already active
    if (alreadyActive) {
      if (mode === "duckdb" && !confirm(`Remove "${tbl.name}" from DuckDB? You can reload it anytime.`)) return
      if (mode === "athena" && !confirm(`Remove "${tbl.name}" from Athena direct mode?`)) return
      setBusy(true)
      setLoadingMsg("Removing…")
      try {
        const path = mode === "duckdb" ? "load" : "direct"
        await fetch(`${BACKEND}/api/athena/databases/${encodeURIComponent(database)}/tables/${encodeURIComponent(tbl.name)}/${path}`, { method: "DELETE", headers: authHeader })
        if (mode === "duckdb") onLoadChange(tableKey, null)
        else onDirectRefChange(tableKey, false)
      } catch (err) {
        setOpErr(err instanceof Error ? err.message : "Remove failed")
      } finally { setBusy(false); setLoadingMsg("") }
      return
    }

    // Switch from other mode first (no confirm needed for Athena→DuckDB; confirm for DuckDB→Athena)
    if (otherActive && mode === "athena") {
      if (!confirm(`Switch to Athena Direct? This will remove the local DuckDB copy of "${tbl.name}".`)) return
    }

    setBusy(true)
    setLoadingMsg(mode === "duckdb"
      ? "Fetching from Athena and loading into DuckDB — this may take a minute for large tables…"
      : "Registering for Athena direct query…")
    try {
      if (otherActive) {
        // Remove the other mode silently before activating new one
        const path = mode === "duckdb" ? "direct" : "load"
        await fetch(`${BACKEND}/api/athena/databases/${encodeURIComponent(database)}/tables/${encodeURIComponent(tbl.name)}/${path}`, { method: "DELETE", headers: authHeader })
        if (mode === "duckdb") onDirectRefChange(tableKey, false)
        else onLoadChange(tableKey, null)
      }
      if (mode === "duckdb") {
        const url = `${BACKEND}/api/athena/databases/${encodeURIComponent(database)}/tables/${encodeURIComponent(tbl.name)}/load?source=${encodeURIComponent(source)}`
        const r = await fetch(url, { method: "POST", headers: authHeader })
        const d = await r.json()
        if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
        onLoadChange(tableKey, d)
      } else {
        const url = `${BACKEND}/api/athena/databases/${encodeURIComponent(database)}/tables/${encodeURIComponent(tbl.name)}/direct?source=${encodeURIComponent(source)}`
        const r = await fetch(url, { method: "POST", headers: authHeader })
        const d = await r.json()
        if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
        onDirectRefChange(tableKey, true)
      }
    } catch (err) {
      setOpErr(err instanceof Error ? err.message : "Operation failed")
    } finally { setBusy(false); setLoadingMsg("") }
  }

  async function refreshDuckDB() {
    setBusy(true); setOpErr("")
    setLoadingMsg("Re-fetching latest data from Athena…")
    try {
      const url = `${BACKEND}/api/athena/databases/${encodeURIComponent(database)}/tables/${encodeURIComponent(tbl.name)}/load?source=${encodeURIComponent(source)}`
      const r = await fetch(url, { method: "POST", headers: authHeader })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
      onLoadChange(tableKey, d)
    } catch (err) {
      setOpErr(err instanceof Error ? err.message : "Refresh failed")
    } finally { setBusy(false); setLoadingMsg("") }
  }

  async function loadPreview() {
    if (preview) { setOpen(true); return }
    setLoadingPreview(true); setPreviewErr("")
    try {
      const url = `${BACKEND}/api/athena/databases/${encodeURIComponent(database)}/tables/${encodeURIComponent(tbl.name)}/preview?limit=20&source=${encodeURIComponent(source)}`
      const r = await fetch(url, { headers: authHeader })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
      setPreview(d.rows); setOpen(true)
    } catch (err) {
      setPreviewErr(err instanceof Error ? err.message : "Preview failed")
    } finally { setLoadingPreview(false) }
  }

  const headers = preview && preview.length > 0 ? Object.keys(preview[0]) : []

  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-card">
        <div className="flex items-center gap-2.5 min-w-0">
          <Table2 className="size-4 text-muted-foreground shrink-0" />
          <div className="min-w-0">
            <p className="font-mono text-sm font-semibold">{tbl.name}</p>
            {isLoaded ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
                <span>{fmtRows(loadedMeta.row_count)}</span>
                {loadedMeta.loaded_at && <><span>·</span><span>{fmtDate(loadedMeta.loaded_at)}</span></>}
                {loadedMeta.row_limit_applied && (
                  <span className="text-amber-600 dark:text-amber-400 flex items-center gap-0.5">
                    <AlertCircle className="size-3" /> capped at 500K
                  </span>
                )}
              </div>
            ) : (
              tbl.description && <p className="text-xs text-muted-foreground truncate mt-0.5">{tbl.description}</p>
            )}
          </div>
        </div>

        {/* ── Always-visible mode toggle ── */}
        <div className="flex items-center gap-1.5 shrink-0 ml-3">
          {/* DuckDB toggle */}
          <button
            onClick={() => selectMode("duckdb")}
            disabled={busy}
            title={isLoaded ? "Loaded in DuckDB — click to remove" : "Load into DuckDB for fast local queries"}
            className={`flex items-center gap-1.5 h-7 px-2.5 text-xs rounded-lg border font-medium transition-all disabled:opacity-40
              ${isLoaded
                ? "bg-green-100 dark:bg-green-950/40 border-green-300 dark:border-green-700 text-green-700 dark:text-green-400"
                : "border-border text-muted-foreground hover:border-green-300 dark:hover:border-green-700 hover:text-green-700 dark:hover:text-green-400 hover:bg-green-50 dark:hover:bg-green-950/20"}`}
          >
            <Database className="size-3" />
            DuckDB
          </button>

          {/* Athena Direct toggle */}
          <button
            onClick={() => selectMode("athena")}
            disabled={busy}
            title={isDirectRef ? "Querying via Athena Direct — click to remove" : "Query directly in Athena (no data loaded locally)"}
            className={`flex items-center gap-1.5 h-7 px-2.5 text-xs rounded-lg border font-medium transition-all disabled:opacity-40
              ${isDirectRef
                ? "bg-purple-100 dark:bg-purple-950/40 border-purple-300 dark:border-purple-700 text-purple-700 dark:text-purple-400"
                : "border-border text-muted-foreground hover:border-purple-300 dark:hover:border-purple-700 hover:text-purple-700 dark:hover:text-purple-400 hover:bg-purple-50 dark:hover:bg-purple-950/20"}`}
          >
            <Zap className="size-3" />
            Athena
          </button>

          {/* Refresh (only when DuckDB is loaded) */}
          {isLoaded && (
            <button
              onClick={refreshDuckDB}
              disabled={busy}
              title="Re-fetch latest data from Athena"
              className="h-7 w-7 flex items-center justify-center rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40"
            >
              {busy ? <Loader2 className="size-3 animate-spin" /> : <RotateCcw className="size-3" />}
            </button>
          )}
          {busy && !isLoaded && (
            <span className="flex items-center justify-center h-7 w-7">
              <Loader2 className="size-3 animate-spin text-muted-foreground" />
            </span>
          )}

          {/* Preview */}
          <Button size="sm" variant="outline" className="h-7 text-xs gap-1.5" onClick={loadPreview} disabled={loadingPreview}>
            {loadingPreview ? <Loader2 className="size-3 animate-spin" /> : <Play className="size-3" />} Preview
          </Button>
          <button onClick={() => setOpen(v => !v)} className="p-1 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors">
            {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
          </button>
        </div>
      </div>

      {busy && loadingMsg && (
        <div className="border-t border-border px-4 py-2 bg-blue-50/50 dark:bg-blue-950/20 text-xs text-blue-600 dark:text-blue-400 flex items-center gap-1.5">
          <Loader2 className="size-3 animate-spin shrink-0" />
          {loadingMsg}
        </div>
      )}

      {opErr && (
        <div className="border-t border-border px-4 py-2 text-xs text-destructive flex items-center gap-1.5">
          <AlertCircle className="size-3.5 shrink-0" /> {opErr}
        </div>
      )}

      <div className="border-t border-border px-4 py-3 bg-muted/20">
        <div className="flex flex-wrap gap-1.5">{tbl.columns.map(col => <ColTag key={col.name} col={col} />)}</div>
      </div>

      {previewErr && (
        <div className="border-t border-border px-4 py-2 text-xs text-destructive flex items-center gap-1.5">
          <AlertCircle className="size-3.5 shrink-0" /> {previewErr}
        </div>
      )}
      {open && preview && preview.length > 0 && (
        <div className="border-t border-border overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="bg-muted/60">
              <tr>{headers.map(h => <th key={h} className="text-left px-3 py-2 font-mono font-medium text-muted-foreground whitespace-nowrap">{h}</th>)}</tr>
            </thead>
            <tbody>
              {preview.slice(0, 20).map((row, i) => (
                <tr key={i} className="border-t border-border/50 hover:bg-muted/30">
                  {headers.map(h => <td key={h} className="px-3 py-1.5 text-muted-foreground font-mono whitespace-nowrap max-w-[200px] truncate">{row[h] ?? ""}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function DatabaseSection({ db, authHeader, loadedTables, onLoadChange, directRefs, onDirectRefChange }: {
  db: GlueDb
  authHeader: Record<string, string>
  loadedTables: Map<string, LoadedTableMeta>
  onLoadChange: (key: string, meta: LoadedTableMeta | null) => void
  directRefs: Set<string>
  onDirectRefChange: (key: string, isDirectRef: boolean) => void
}) {
  const [open,    setOpen]   = useState(false)
  const [tables,  setTables] = useState<GlueTable[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [err,     setErr]    = useState("")

  const srcMeta = SOURCE_LABELS[db.source] ?? { label: db.source, color: "bg-muted text-muted-foreground" }

  async function load() {
    if (tables) { setOpen(v => !v); return }
    setLoading(true); setErr("")
    try {
      const r = await fetch(
        `${BACKEND}/api/athena/databases/${encodeURIComponent(db.name)}/tables?source=${encodeURIComponent(db.source)}`,
        { headers: authHeader }
      )
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
      setTables(d); setOpen(true)
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed")
    } finally { setLoading(false) }
  }

  return (
    <div className="rounded-2xl border border-border bg-card overflow-hidden">
      <button onClick={load} className="w-full flex items-center justify-between px-5 py-4 hover:bg-muted/30 transition-colors text-left">
        <div className="flex items-center gap-3">
          <Database className="size-4 text-primary shrink-0" />
          <div>
            <div className="flex items-center gap-2">
              <p className="font-semibold text-sm">{db.name}</p>
              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${srcMeta.color}`}>{srcMeta.label}</span>
            </div>
            {db.description && <p className="text-xs text-muted-foreground">{db.description}</p>}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {loading && <Loader2 className="size-4 animate-spin text-muted-foreground" />}
          {!loading && (open ? <ChevronDown className="size-4 text-muted-foreground" /> : <ChevronRight className="size-4 text-muted-foreground" />)}
        </div>
      </button>
      {err && <div className="border-t border-border px-5 py-2 text-xs text-destructive flex items-center gap-1.5"><AlertCircle className="size-3.5" /> {err}</div>}
      {open && tables && (
        <div className="border-t border-border px-5 py-4 space-y-3">
          {tables.length === 0
            ? <p className="text-sm text-muted-foreground">No tables in this database.</p>
            : tables.map(tbl => (
                <TableRow
                  key={tbl.name}
                  tbl={tbl}
                  database={db.name}
                  source={db.source}
                  authHeader={authHeader}
                  loadedMeta={loadedTables.get(`${db.name}.${tbl.name}`)}
                  onLoadChange={onLoadChange}
                  isDirectRef={directRefs.has(`${db.name}.${tbl.name}`)}
                  onDirectRefChange={onDirectRefChange}
                />
              ))}
        </div>
      )}
    </div>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────

type EditMode = "global" | "personal" | null

export default function AthenaPage() {
  const { data: session } = useSession()
  const authHeader = { Authorization: `Bearer ${session?.accessToken}` }

  const isAdmin = session?.isAdmin ?? false

  const [status,        setStatus]        = useState<AthenaStatus | null>(null)
  const [globalSaved,   setGlobalSaved]   = useState<SavedConfig | null>(null)
  const [personalSaved, setPersonalSaved] = useState<SavedConfig | null>(null)
  const [editing,       setEditing]       = useState<EditMode>(null)
  const [databases,     setDatabases]     = useState<GlueDb[] | null>(null)
  const [loadingDb,     setLoadingDb]     = useState(false)
  const [dbErr,         setDbErr]         = useState("")
  const [loadedTables,  setLoadedTables]  = useState<Map<string, LoadedTableMeta>>(new Map())
  const [directRefs,    setDirectRefs]    = useState<Set<string>>(new Set())

  function handleLoadChange(key: string, meta: LoadedTableMeta | null) {
    setLoadedTables(prev => {
      const next = new Map(prev)
      if (meta) next.set(key, meta)
      else next.delete(key)
      return next
    })
  }

  function handleDirectRefChange(key: string, isDirectRef: boolean) {
    setDirectRefs(prev => {
      const next = new Set(prev)
      if (isDirectRef) next.add(key)
      else next.delete(key)
      return next
    })
  }

  async function fetchAll() {
    if (!session?.accessToken) return
    const safe = (p: Promise<Response>, fallback: null | unknown[] = null) =>
      p.then(r => r.ok ? r.json() : fallback).catch(() => fallback)
    const [s, g, p, loaded, refs] = await Promise.all([
      safe(fetch(`${BACKEND}/api/athena/status`,        { headers: authHeader })),
      safe(fetch(`${BACKEND}/api/athena/global-config`, { headers: authHeader })),
      safe(fetch(`${BACKEND}/api/athena/config`,        { headers: authHeader })),
      safe(fetch(`${BACKEND}/api/athena/loaded-tables`, { headers: authHeader }), []),
      safe(fetch(`${BACKEND}/api/athena/direct-refs`,   { headers: authHeader }), []),
    ])
    if (s) setStatus(s)
    setGlobalSaved(g)
    setPersonalSaved(p)
    const map = new Map<string, LoadedTableMeta>()
    for (const m of (loaded ?? []) as LoadedTableMeta[]) {
      map.set(`${m.athena_database}.${m.athena_table_name}`, m)
    }
    setLoadedTables(map)
    const refsSet = new Set<string>()
    for (const r of (refs ?? []) as DirectRefMeta[]) {
      refsSet.add(`${r.athena_database}.${r.athena_table}`)
    }
    setDirectRefs(refsSet)
  }

  useEffect(() => { fetchAll() }, [session?.accessToken])  // eslint-disable-line react-hooks/exhaustive-deps

  async function loadDatabases() {
    setLoadingDb(true); setDbErr("")
    try {
      const r = await fetch(`${BACKEND}/api/athena/databases`, { headers: authHeader })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
      setDatabases(d)
    } catch (e) {
      setDbErr(e instanceof Error ? e.message : "Failed to load databases")
    } finally { setLoadingDb(false) }
  }

  useEffect(() => {
    if (status?.configured) loadDatabases()
  }, [status?.configured])  // eslint-disable-line react-hooks/exhaustive-deps

  async function handleSaved() {
    setEditing(null)
    await fetchAll()
    setDatabases(null)
    const s = await fetch(`${BACKEND}/api/athena/status`, { headers: authHeader }).then(r => r.ok ? r.json() : null)
    if (s?.configured) loadDatabases()
  }

  const activeSources = status?.active_sources ?? []

  return (
    <div className="min-h-screen bg-background">
      <nav className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-md">
        <div className="max-w-5xl mx-auto flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2">
            <Cloud className="size-4 text-amber-500" />
            <span className="font-semibold text-sm">Athena Browser</span>
          </div>
          <div className="flex items-center gap-2">
            {status?.configured && databases && (
              <Button size="sm" variant="ghost" className="h-7 text-xs gap-1.5" onClick={loadDatabases} disabled={loadingDb}>
                <RefreshCw className={`size-3.5 ${loadingDb ? "animate-spin" : ""}`} /> Refresh
              </Button>
            )}
          </div>
        </div>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AWS Athena / Glue Catalog</h1>
          <p className="text-muted-foreground text-sm mt-1">Browse your Glue Data Catalog, load tables into DuckDB, and query them alongside your CSV uploads.</p>
        </div>

        {!status ? (
          <div className="flex justify-center py-12"><Loader2 className="size-8 animate-spin text-muted-foreground" /></div>
        ) : (
          <>
            {/* ── Active connection badges ── */}
            {status.configured && (
              <div className="flex items-center gap-2 flex-wrap text-sm">
                <span className="flex items-center gap-1.5 text-green-600 dark:text-green-400 font-medium">
                  <CheckCircle2 className="size-4" /> Connected
                </span>
                <span className="text-muted-foreground">·</span>
                <span className="text-muted-foreground">Region: <strong>{status.region}</strong></span>
                <span className="text-muted-foreground">·</span>
                <span className="text-xs text-muted-foreground">Active:</span>
                {activeSources.map(src => {
                  const m = SOURCE_LABELS[src] ?? { label: src, color: "bg-muted text-muted-foreground" }
                  return (
                    <span key={src} className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${m.color}`}>{m.label}</span>
                  )
                })}
                {loadedTables.size > 0 && (
                  <>
                    <span className="text-muted-foreground">·</span>
                    <span className="text-xs text-muted-foreground">{loadedTables.size} table{loadedTables.size !== 1 ? "s" : ""} in DuckDB</span>
                  </>
                )}
                {directRefs.size > 0 && (
                  <>
                    <span className="text-muted-foreground">·</span>
                    <span className="text-xs text-purple-600 dark:text-purple-400">{directRefs.size} Athena direct</span>
                  </>
                )}
              </div>
            )}

            {/* ── Connections section ── */}
            <section className="space-y-3">
              <h2 className="text-base font-semibold">Connections</h2>
              <p className="text-xs text-muted-foreground -mt-1">
                Both connections are active simultaneously — databases from each appear together in the catalog below.
              </p>

              {/* Global / shared */}
              {editing === "global" && isAdmin ? (
                <CredentialForm
                  title="Shared connection"
                  icon={Globe}
                  iconColor="bg-amber-100 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400"
                  authHeader={authHeader}
                  saveUrl="/api/athena/global-config"
                  existing={globalSaved}
                  onSaved={handleSaved}
                  onCancel={() => setEditing(null)}
                  onDelete={async () => { setEditing(null); await fetchAll(); setDatabases(null) }}
                />
              ) : (
                <ConnectionCard
                  title="Shared connection"
                  icon={Globe}
                  iconColor={`${status.has_global ? "bg-amber-100 dark:bg-amber-950/40 text-amber-600 dark:text-amber-400" : "bg-muted text-muted-foreground"}`}
                  badge={status.has_global ? "Configured" : status.has_env ? "Via .env" : "Not set"}
                  badgeColor={status.has_global || status.has_env ? "bg-green-100 dark:bg-green-950/30 text-green-700 dark:text-green-400" : "bg-muted text-muted-foreground"}
                  saved={isAdmin ? globalSaved : null}
                  envNote={status.has_env && !status.has_global}
                  canEdit={isAdmin}
                  onEdit={() => setEditing("global")}
                  onRemove={status.has_global ? async () => {
                    if (!confirm("Remove shared Athena connection? This will disconnect all users.")) return
                    await fetch(`${BACKEND}/api/athena/global-config`, { method: "DELETE", headers: authHeader })
                    await fetchAll(); setDatabases(null)
                  } : undefined}
                />
              )}

              {/* Personal credentials (additive) */}
              {editing === "personal" ? (
                <CredentialForm
                  title="Personal credentials"
                  icon={User}
                  iconColor="bg-blue-100 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400"
                  authHeader={authHeader}
                  saveUrl="/api/athena/config"
                  existing={personalSaved}
                  onSaved={handleSaved}
                  onCancel={() => setEditing(null)}
                  onDelete={async () => { setEditing(null); await fetchAll(); setDatabases(null) }}
                />
              ) : status.has_personal ? (
                <ConnectionCard
                  title="Personal credentials"
                  icon={User}
                  iconColor="bg-blue-100 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400"
                  badge="Active"
                  badgeColor="bg-blue-100 dark:bg-blue-950/30 text-blue-700 dark:text-blue-400"
                  saved={personalSaved}
                  onEdit={() => setEditing("personal")}
                  onRemove={async () => {
                    if (!confirm("Remove your personal Athena credentials?")) return
                    await fetch(`${BACKEND}/api/athena/config`, { method: "DELETE", headers: authHeader })
                    await fetchAll(); setDatabases(null)
                  }}
                />
              ) : (
                <button
                  onClick={() => setEditing("personal")}
                  className="w-full flex items-center gap-3 rounded-2xl border border-dashed border-border bg-card p-4 hover:border-primary/40 hover:bg-muted/30 transition-all text-left group"
                >
                  <div className="size-9 rounded-xl bg-muted flex items-center justify-center shrink-0 group-hover:bg-primary/10 transition-colors">
                    <Plus className="size-4 text-muted-foreground group-hover:text-primary transition-colors" />
                  </div>
                  <div>
                    <p className="font-medium text-sm group-hover:text-primary transition-colors">Add personal credentials</p>
                    <p className="text-xs text-muted-foreground">Adds your own AWS account databases alongside the shared connection</p>
                  </div>
                </button>
              )}
            </section>

            {/* ── Catalog browser ── */}
            {status.configured && editing === null && (
              <section className="space-y-4">
                <div>
                  <h2 className="text-base font-semibold">Glue Data Catalog</h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Click a database to browse tables. Use <strong>Load into DuckDB</strong> to make a table queryable in the chat — you can then join it with CSV uploads or other loaded tables.
                  </p>
                </div>

                {dbErr && (
                  <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive flex items-center gap-2">
                    <AlertCircle className="size-4 shrink-0" /> {dbErr}
                  </div>
                )}

                {loadingDb && !databases && (
                  <div className="text-center py-12">
                    <Loader2 className="size-8 animate-spin text-muted-foreground mx-auto" />
                    <p className="text-sm text-muted-foreground mt-3">Loading Glue catalog…</p>
                  </div>
                )}

                {databases && databases.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-12">No databases found in your Glue catalog.</p>
                )}

                {databases && databases.length > 0 && (
                  <div className="space-y-3">
                    {databases.map(db => (
                      <DatabaseSection
                        key={`${db.source}:${db.name}`}
                        db={db}
                        authHeader={authHeader}
                        loadedTables={loadedTables}
                        onLoadChange={handleLoadChange}
                        directRefs={directRefs}
                        onDirectRefChange={handleDirectRefChange}
                      />
                    ))}
                  </div>
                )}
              </section>
            )}

            {/* ── Not configured prompt ── */}
            {!status.configured && editing === null && (
              <div className="rounded-2xl border border-dashed border-amber-300 dark:border-amber-700 bg-amber-50/50 dark:bg-amber-950/20 p-8 text-center space-y-3">
                <Cloud className="size-10 text-amber-400 mx-auto" />
                <p className="font-semibold text-sm">No Athena connection yet</p>
                <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                  Set up the shared connection above so everyone on your team can query Athena, or add your own personal credentials.
                </p>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}
