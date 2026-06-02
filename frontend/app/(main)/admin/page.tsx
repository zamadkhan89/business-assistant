"use client"

import { useCallback, useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import {
  Users, ShieldCheck, Database, MessageSquare,
  CheckCircle2, XCircle, Crown, Loader2,
  Table2, Clock, Search, Trash2, ShieldOff, Shield,
  ShieldX, AlertTriangle, HardDrive, X, ScrollText,
  Zap, GitBranch,
} from "lucide-react"

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

type Filter = "all" | "verified" | "unverified" | "datasets" | "threads" | "blocked"

interface AuditEntry {
  id: string
  admin_email: string
  action: string
  target_email: string | null
  detail: string | null
  created_at: string | null
}

interface AdminUser {
  id: string
  email: string
  name: string | null
  is_verified: boolean
  is_admin: boolean
  is_blocked: boolean
  created_at: string | null
  thread_count: number
  dataset_count: number
  storage_used_mb: number
  storage_quota_mb: number | null
  streaming_enabled: boolean
  sql_approval_required: boolean
}

interface Dataset { table_name: string; row_count: number; source_type: string }
interface ThreadItem { id: string; title: string; updated_at: string | null }

function timeAgo(iso: string | null): string {
  if (!iso) return "—"
  const diff = Date.now() - new Date(iso).getTime()
  const days = Math.floor(diff / 86_400_000)
  const hours = Math.floor(diff / 3_600_000)
  const mins = Math.floor(diff / 60_000)
  if (mins < 2) return "just now"
  if (mins < 60) return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  return `${days}d ago`
}

function initials(user: AdminUser): string {
  if (user.name) return user.name.split(" ").map((w) => w[0]).join("").toUpperCase().slice(0, 2)
  return user.email[0].toUpperCase()
}

function fmtMb(mb: number): string {
  if (mb < 1) return `${Math.round(mb * 1024)} KB`
  if (mb < 1024) return `${mb.toFixed(1)} MB`
  return `${(mb / 1024).toFixed(2)} GB`
}

function StorageBar({ used, quota }: { used: number; quota: number | null }) {
  if (quota === null) {
    return (
      <div className="space-y-1">
        <div className="flex justify-between text-[10px] text-muted-foreground">
          <span>{fmtMb(used)} used</span>
          <span>No limit</span>
        </div>
        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
          <div className="h-full w-0 bg-primary/40 rounded-full" />
        </div>
      </div>
    )
  }
  const pct = Math.min(100, (used / quota) * 100)
  const color = pct >= 90 ? "bg-destructive" : pct >= 70 ? "bg-amber-500" : "bg-primary"
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{fmtMb(used)} used</span>
        <span>{fmtMb(quota)} limit</span>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function StatCard({
  icon: Icon, label, value, color, active, onClick,
}: {
  icon: React.ElementType; label: string; value: string | number
  color: string; active: boolean; onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`card-elevated p-5 flex items-center gap-4 w-full text-left transition-all hover:shadow-md ${
        active ? "ring-2 ring-primary ring-offset-2 ring-offset-background" : ""
      }`}
    >
      <div className={`size-11 rounded-xl bg-linear-to-br ${color} flex items-center justify-center shrink-0 shadow-sm`}>
        <Icon className="size-5 text-white" />
      </div>
      <div>
        <p className="text-2xl font-bold tabular-nums">{value}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{label}</p>
      </div>
    </button>
  )
}

function ConfirmDialog({ message, onConfirm, onCancel }: {
  message: string; onConfirm: () => void; onCancel: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-card rounded-2xl shadow-2xl max-w-sm w-full p-6 space-y-4">
        <div className="flex items-start gap-3">
          <div className="size-9 rounded-xl bg-destructive/10 flex items-center justify-center shrink-0">
            <AlertTriangle className="size-4 text-destructive" />
          </div>
          <div>
            <p className="font-semibold text-sm">Are you sure?</p>
            <p className="text-sm text-muted-foreground mt-0.5">{message}</p>
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <button onClick={onCancel} className="btn-ghost px-4 py-1.5 text-sm">Cancel</button>
          <button onClick={onConfirm} className="px-4 py-1.5 text-sm rounded-lg bg-destructive text-white hover:bg-destructive/90 transition-colors">
            Confirm
          </button>
        </div>
      </div>
    </div>
  )
}

export default function AdminPage() {
  const { data: session } = useSession()
  const [users, setUsers]           = useState<AdminUser[]>([])
  const [loading, setLoading]       = useState(true)
  const [search, setSearch]         = useState("")
  const [filter, setFilter]         = useState<Filter>("all")
  const [selected, setSelected]     = useState<AdminUser | null>(null)
  const [datasets, setDatasets]     = useState<Dataset[]>([])
  const [threads, setThreads]       = useState<ThreadItem[]>([])
  const [detailTab, setDetailTab]   = useState<"datasets" | "threads" | "storage">("datasets")
  const [detailLoad, setDetailLoad] = useState(false)
  const [actionLoad, setActionLoad] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [confirm, setConfirm]       = useState<{ message: string; action: () => void } | null>(null)
  const [quotaInput, setQuotaInput] = useState("")
  const [savingQuota, setSavingQuota] = useState(false)
  const [auditLog, setAuditLog]     = useState<AuditEntry[]>([])
  const [auditLoading, setAuditLoading] = useState(false)

  const authHeader = { Authorization: `Bearer ${session?.accessToken}` }

  const fetchUsers = useCallback(async () => {
    if (!session?.accessToken) return
    setLoading(true)
    try {
      const r = await fetch(`${BACKEND}/api/admin/users`, { headers: authHeader })
      if (r.ok) setUsers(await r.json())
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  useEffect(() => { fetchUsers() }, [fetchUsers])

  const fetchAuditLog = useCallback(async () => {
    if (!session?.accessToken) return
    setAuditLoading(true)
    try {
      const r = await fetch(`${BACKEND}/api/admin/audit-log`, { headers: authHeader })
      if (r.ok) setAuditLog(await r.json())
    } finally {
      setAuditLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  useEffect(() => { fetchAuditLog() }, [fetchAuditLog])

  async function selectUser(user: AdminUser) {
    setSelected(user)
    setDetailTab("datasets")
    setQuotaInput(user.storage_quota_mb != null ? String(user.storage_quota_mb) : "")
    setDetailLoad(true)
    try {
      const [dsRes, thRes] = await Promise.all([
        fetch(`${BACKEND}/api/admin/users/${user.id}/datasets`, { headers: authHeader }),
        fetch(`${BACKEND}/api/admin/users/${user.id}/threads`,  { headers: authHeader }),
      ])
      setDatasets(dsRes.ok ? await dsRes.json() : [])
      setThreads(thRes.ok  ? await thRes.json() : [])
    } finally {
      setDetailLoad(false)
    }
  }

  async function doAction(key: string, url: string, method: string, body?: unknown, onSuccess?: () => void) {
    setActionLoad(key)
    setActionError(null)
    try {
      const r = await fetch(url, {
        method,
        headers: { ...authHeader, "Content-Type": "application/json" },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      })
      if (r.ok) {
        const listRes = await fetch(`${BACKEND}/api/admin/users`, { headers: authHeader })
        if (listRes.ok) {
          const list: AdminUser[] = await listRes.json()
          setUsers(list)
          fetchAuditLog()
          const fresh = list.find((u) => u.id === selected?.id)
          if (fresh) { setSelected(fresh); setQuotaInput(fresh.storage_quota_mb != null ? String(fresh.storage_quota_mb) : "") }
          else setSelected(null)
        }
        onSuccess?.()
      } else {
        const err = await r.json().catch(() => ({}))
        setActionError(err.detail ?? "Action failed — please try again.")
      }
    } catch {
      setActionError("Could not reach the server. Is the backend running?")
    } finally {
      setActionLoad(null)
    }
  }

  function askConfirm(message: string, loadKey: string, action: () => void) {
    setConfirm({
      message,
      action: () => {
        setActionLoad(loadKey)
        setActionError(null)
        setConfirm(null)
        action()
      },
    })
  }

  async function deleteDataset(tableName: string) {
    if (!selected) return
    await doAction(
      `ds-${tableName}`,
      `${BACKEND}/api/admin/users/${selected.id}/datasets/${encodeURIComponent(tableName)}`,
      "DELETE",
      undefined,
      () => setDatasets((ds) => ds.filter((d) => d.table_name !== tableName))
    )
  }

  async function saveQuota() {
    if (!selected) return
    setSavingQuota(true)
    const quota_mb = quotaInput.trim() === "" ? null : parseInt(quotaInput, 10)
    try {
      await doAction("quota", `${BACKEND}/api/admin/users/${selected.id}/quota`, "PATCH", { quota_mb })
    } finally {
      setSavingQuota(false)
    }
  }

  const stats = {
    total:    users.length,
    verified: users.filter((u) => u.is_verified).length,
    datasets: users.reduce((s, u) => s + u.dataset_count, 0),
    threads:  users.reduce((s, u) => s + u.thread_count, 0),
  }

  const STAT_CARDS = [
    { key: "all"      as Filter, icon: Users,         label: "Total users",       value: stats.total,    color: "from-violet-500 to-purple-600" },
    { key: "verified" as Filter, icon: ShieldCheck,   label: "Verified",          value: stats.verified, color: "from-emerald-500 to-teal-500"  },
    { key: "datasets" as Filter, icon: Database,      label: "Datasets uploaded", value: stats.datasets, color: "from-blue-500 to-cyan-500"     },
    { key: "threads"  as Filter, icon: MessageSquare, label: "Conversations",     value: stats.threads,  color: "from-amber-500 to-orange-500"  },
  ]

  function applyFilter(u: AdminUser): boolean {
    if (search && !u.email.toLowerCase().includes(search.toLowerCase()) &&
        !(u.name ?? "").toLowerCase().includes(search.toLowerCase())) return false
    if (filter === "verified")   return u.is_verified && !u.is_blocked
    if (filter === "unverified") return !u.is_verified
    if (filter === "datasets")   return u.dataset_count > 0
    if (filter === "threads")    return u.thread_count > 0
    if (filter === "blocked")    return u.is_blocked
    return true
  }

  const filtered = users.filter(applyFilter)

  function toggleFilter(f: Filter) {
    setFilter((prev) => prev === f ? "all" : f)
  }

  return (
    <div className="min-h-screen bg-background">
      {confirm && (
        <ConfirmDialog message={confirm.message} onConfirm={confirm.action} onCancel={() => setConfirm(null)} />
      )}

      <div className="page-header flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="size-9 rounded-xl bg-linear-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-sm">
            <Crown className="size-4 text-white" />
          </div>
          <div>
            <h1 className="page-title">Admin Panel</h1>
            <p className="page-subtitle">User accounts, datasets, and conversations</p>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto p-6 space-y-6">

        {/* Stats — clickable to filter */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {STAT_CARDS.map(({ key, icon, label, value, color }) => (
            <StatCard
              key={key}
              icon={icon} label={label} value={value} color={color}
              active={filter === key}
              onClick={() => toggleFilter(key)}
            />
          ))}
        </div>

        {/* Active filter chip */}
        {filter !== "all" && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Filtering by:</span>
            <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full bg-primary/10 text-primary">
              {filter}
              <button onClick={() => setFilter("all")} className="hover:text-primary/70 transition-colors">
                <X className="size-3" />
              </button>
            </span>
            <span className="text-xs text-muted-foreground">{filtered.length} user{filtered.length !== 1 ? "s" : ""}</span>
          </div>
        )}

        <div className="grid lg:grid-cols-3 gap-6">

          {/* User list */}
          <div className="lg:col-span-2 space-y-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by name or email…"
                className="input-modern pl-9 w-full"
              />
            </div>

            {loading ? (
              <div className="card-elevated p-8 flex items-center justify-center gap-2 text-muted-foreground">
                <Loader2 className="size-4 animate-spin" /> Loading users…
              </div>
            ) : filtered.length === 0 ? (
              <div className="card-elevated p-8 text-center text-sm text-muted-foreground">No users found.</div>
            ) : (
              <div className="space-y-2">
                {filtered.map((u) => (
                  <button
                    key={u.id}
                    onClick={() => selectUser(u)}
                    className={`w-full text-left rounded-xl border-2 p-4 transition-all hover:border-primary/40 hover:bg-muted/20 ${
                      selected?.id === u.id ? "border-primary bg-primary/5" : "border-border bg-card"
                    } ${u.is_blocked ? "opacity-60" : ""}`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`size-9 rounded-full flex items-center justify-center text-sm font-bold text-white shrink-0 ${
                        u.is_admin    ? "bg-linear-to-br from-violet-500 to-purple-600" :
                        u.is_blocked  ? "bg-linear-to-br from-red-400 to-red-500" :
                        "bg-linear-to-br from-slate-400 to-slate-500"
                      }`}>
                        {initials(u)}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="font-medium text-sm truncate">{u.name ?? u.email}</p>
                          {u.is_admin   && <Crown    className="size-3 text-violet-500 shrink-0" />}
                          {u.is_blocked && <ShieldX  className="size-3 text-destructive shrink-0" />}
                          {u.is_verified
                            ? <CheckCircle2 className="size-3 text-emerald-500 shrink-0" />
                            : <XCircle      className="size-3 text-amber-500 shrink-0" />}
                        </div>
                        <p className="text-xs text-muted-foreground truncate">{u.email}</p>
                      </div>
                      <div className="flex items-center gap-3 shrink-0 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1"><Database className="size-3" />{u.dataset_count}</span>
                        <span className="flex items-center gap-1"><MessageSquare className="size-3" />{u.thread_count}</span>
                        <span className="flex items-center gap-1"><HardDrive className="size-3" />{fmtMb(u.storage_used_mb)}</span>
                      </div>
                    </div>
                    {/* Storage bar on user card if quota is set */}
                    {u.storage_quota_mb != null && (
                      <div className="mt-2 pl-12">
                        <StorageBar used={u.storage_used_mb} quota={u.storage_quota_mb} />
                      </div>
                    )}
                    <p className="text-[10px] text-muted-foreground mt-1.5 pl-12">
                      Joined {u.created_at ? new Date(u.created_at).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—"}
                      {" · "}{u.is_blocked ? "Blocked" : u.is_verified ? "Verified" : "Not verified"}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Detail panel */}
          <div className="lg:col-span-1">
            {!selected ? (
              <div className="card-elevated p-8 flex flex-col items-center justify-center gap-3 text-muted-foreground h-64 sticky top-6">
                <Users className="size-8 opacity-30" />
                <p className="text-sm text-center">Select a user to view and manage their account</p>
              </div>
            ) : (
              <div className="card-elevated p-4 space-y-4 sticky top-6 max-h-[calc(100vh-8rem)] overflow-y-auto">
                {/* User header */}
                <div className="flex items-center gap-3">
                  <div className={`size-10 rounded-full flex items-center justify-center text-sm font-bold text-white shrink-0 ${
                    selected.is_admin   ? "bg-linear-to-br from-violet-500 to-purple-600" :
                    selected.is_blocked ? "bg-linear-to-br from-red-400 to-red-500" :
                    "bg-linear-to-br from-slate-400 to-slate-500"
                  }`}>
                    {initials(selected)}
                  </div>
                  <div className="min-w-0">
                    <p className="font-semibold text-sm truncate">{selected.name ?? selected.email}</p>
                    <p className="text-xs text-muted-foreground truncate">{selected.email}</p>
                  </div>
                </div>

                {/* Status badges */}
                <div className="flex flex-wrap gap-1.5">
                  {selected.is_admin && (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400 flex items-center gap-1">
                      <Crown className="size-2.5" /> Admin
                    </span>
                  )}
                  {selected.is_blocked && (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 flex items-center gap-1">
                      <ShieldX className="size-2.5" /> Blocked
                    </span>
                  )}
                  {selected.is_verified ? (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 flex items-center gap-1">
                      <CheckCircle2 className="size-2.5" /> Verified
                    </span>
                  ) : (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 flex items-center gap-1">
                      <XCircle className="size-2.5" /> Unverified
                    </span>
                  )}
                </div>

                {/* Actions */}
                <div className="space-y-1.5">
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Actions</p>
                  {actionError && (
                    <p className="text-[11px] text-destructive bg-destructive/10 rounded-lg px-3 py-2">{actionError}</p>
                  )}
                  <div className="grid grid-cols-2 gap-1.5">
                    <button
                      onClick={() => askConfirm(
                        selected.is_blocked ? `Unblock ${selected.email}?` : `Block ${selected.email}? They will be immediately signed out.`,
                        "block",
                        () => doAction("block", `${BACKEND}/api/admin/users/${selected.id}/${selected.is_blocked ? "unblock" : "block"}`, "POST")
                      )}
                      disabled={actionLoad !== null}
                      className={`flex items-center justify-center gap-1.5 text-xs font-medium py-1.5 px-3 rounded-lg transition-colors ${
                        selected.is_blocked
                          ? "bg-emerald-100 text-emerald-700 hover:bg-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-400"
                          : "bg-amber-100 text-amber-700 hover:bg-amber-200 dark:bg-amber-900/30 dark:text-amber-400"
                      }`}
                    >
                      {actionLoad === "block" ? <Loader2 className="size-3 animate-spin" /> :
                        selected.is_blocked ? <Shield className="size-3" /> : <ShieldOff className="size-3" />}
                      {selected.is_blocked ? "Unblock" : "Block"}
                    </button>

                    <button
                      onClick={() => askConfirm(
                        `${selected.is_admin ? "Remove admin from" : "Make admin"} ${selected.email}?`,
                        "admin",
                        () => doAction("admin", `${BACKEND}/api/admin/users/${selected.id}/toggle-admin`, "POST")
                      )}
                      disabled={actionLoad !== null}
                      className={`flex items-center justify-center gap-1.5 text-xs font-medium py-1.5 px-3 rounded-lg transition-colors ${
                        selected.is_admin
                          ? "bg-violet-100 text-violet-700 hover:bg-violet-200 dark:bg-violet-900/30 dark:text-violet-400"
                          : "bg-muted text-muted-foreground hover:bg-muted/80"
                      }`}
                    >
                      {actionLoad === "admin" ? <Loader2 className="size-3 animate-spin" /> : <Crown className="size-3" />}
                      {selected.is_admin ? "Revoke admin" : "Make admin"}
                    </button>

                    <button
                      onClick={() => askConfirm(
                        `Permanently delete ${selected.email} and ALL their data? This cannot be undone.`,
                        "delete",
                        () => doAction("delete", `${BACKEND}/api/admin/users/${selected.id}`, "DELETE", undefined, () => setSelected(null))
                      )}
                      disabled={actionLoad !== null}
                      className="col-span-2 flex items-center justify-center gap-1.5 text-xs font-medium py-1.5 px-3 rounded-lg bg-destructive/10 text-destructive hover:bg-destructive/20 transition-colors"
                    >
                      {actionLoad === "delete" ? <Loader2 className="size-3 animate-spin" /> : <Trash2 className="size-3" />}
                      Delete user &amp; all data
                    </button>
                  </div>
                </div>

                {/* Feature toggles */}
                <div className="space-y-1.5">
                  <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Feature Settings</p>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between rounded-lg bg-muted/30 px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Zap className="size-3.5 text-amber-500 shrink-0" />
                        <div>
                          <p className="text-xs font-medium">Streaming</p>
                          <p className="text-[10px] text-muted-foreground">Live step progress via SSE</p>
                        </div>
                      </div>
                      <button
                        onClick={() => doAction(
                          `streaming-${selected.id}`,
                          `${BACKEND}/api/admin/users/${selected.id}/settings`,
                          "PATCH",
                          { streaming_enabled: !selected.streaming_enabled }
                        )}
                        disabled={actionLoad !== null}
                        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                          selected.streaming_enabled ? "bg-amber-500" : "bg-muted-foreground/30"
                        }`}
                      >
                        {actionLoad === `streaming-${selected.id}`
                          ? <Loader2 className="size-3 animate-spin mx-auto text-white" />
                          : <span className={`inline-block size-3.5 rounded-full bg-white shadow transition-transform ${
                              selected.streaming_enabled ? "translate-x-4" : "translate-x-0.5"
                            }`} />}
                      </button>
                    </div>
                    <div className="flex items-center justify-between rounded-lg bg-muted/30 px-3 py-2">
                      <div className="flex items-center gap-2">
                        <GitBranch className="size-3.5 text-blue-500 shrink-0" />
                        <div>
                          <p className="text-xs font-medium">SQL Approval</p>
                          <p className="text-[10px] text-muted-foreground">Require review before executing SQL</p>
                        </div>
                      </div>
                      <button
                        onClick={() => doAction(
                          `approval-${selected.id}`,
                          `${BACKEND}/api/admin/users/${selected.id}/settings`,
                          "PATCH",
                          { sql_approval_required: !selected.sql_approval_required }
                        )}
                        disabled={actionLoad !== null}
                        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                          selected.sql_approval_required ? "bg-blue-500" : "bg-muted-foreground/30"
                        }`}
                      >
                        {actionLoad === `approval-${selected.id}`
                          ? <Loader2 className="size-3 animate-spin mx-auto text-white" />
                          : <span className={`inline-block size-3.5 rounded-full bg-white shadow transition-transform ${
                              selected.sql_approval_required ? "translate-x-4" : "translate-x-0.5"
                            }`} />}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Tabs */}
                <div className="flex gap-1 bg-muted/50 rounded-lg p-1">
                  {(["datasets", "threads", "storage"] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setDetailTab(tab)}
                      className={`flex-1 text-xs py-1.5 rounded-md font-medium transition-all capitalize ${
                        detailTab === tab ? "bg-card shadow-sm text-foreground" : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {tab === "datasets" ? `Data (${selected.dataset_count})` :
                       tab === "threads"  ? `Chats (${selected.thread_count})` : "Storage"}
                    </button>
                  ))}
                </div>

                {/* Tab content */}
                {detailLoad ? (
                  <div className="flex items-center justify-center py-6 gap-2 text-muted-foreground text-xs">
                    <Loader2 className="size-3.5 animate-spin" /> Loading…
                  </div>
                ) : detailTab === "datasets" ? (
                  <div className="space-y-1.5 max-h-60 overflow-y-auto">
                    {datasets.length === 0 ? (
                      <p className="text-xs text-muted-foreground text-center py-4">No datasets uploaded</p>
                    ) : datasets.map((ds) => (
                      <div key={ds.table_name} className="flex items-center gap-2 rounded-lg bg-muted/30 px-3 py-2">
                        <Table2 className="size-3.5 text-muted-foreground shrink-0" />
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-mono font-semibold truncate">{ds.table_name}</p>
                          <p className="text-[10px] text-muted-foreground">{ds.row_count.toLocaleString()} rows · {ds.source_type}</p>
                        </div>
                        <button
                          onClick={() => askConfirm(`Delete '${ds.table_name}'? This cannot be undone.`, `ds-${ds.table_name}`, () => deleteDataset(ds.table_name))}
                          disabled={actionLoad === `ds-${ds.table_name}`}
                          className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors shrink-0"
                        >
                          {actionLoad === `ds-${ds.table_name}` ? <Loader2 className="size-3 animate-spin" /> : <Trash2 className="size-3" />}
                        </button>
                      </div>
                    ))}
                  </div>
                ) : detailTab === "threads" ? (
                  <div className="space-y-1.5 max-h-60 overflow-y-auto">
                    {threads.length === 0 ? (
                      <p className="text-xs text-muted-foreground text-center py-4">No conversations</p>
                    ) : threads.map((t) => (
                      <div key={t.id} className="flex items-start gap-2 rounded-lg bg-muted/30 px-3 py-2">
                        <MessageSquare className="size-3.5 text-muted-foreground shrink-0 mt-0.5" />
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium truncate">{t.title || "Untitled"}</p>
                          <p className="text-[10px] text-muted-foreground flex items-center gap-1 mt-0.5">
                            <Clock className="size-2.5" />{timeAgo(t.updated_at)}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  /* Storage tab */
                  <div className="space-y-4">
                    <StorageBar used={selected.storage_used_mb} quota={selected.storage_quota_mb} />

                    <div className="space-y-2">
                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">Storage Limit (MB)</p>
                      <div className="flex gap-2">
                        <input
                          type="number"
                          min="1"
                          value={quotaInput}
                          onChange={(e) => setQuotaInput(e.target.value)}
                          placeholder="No limit"
                          className="input-modern flex-1 text-sm h-8"
                        />
                        <button
                          onClick={saveQuota}
                          disabled={savingQuota}
                          className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                        >
                          {savingQuota ? <Loader2 className="size-3 animate-spin" /> : "Save"}
                        </button>
                      </div>
                      {quotaInput && (
                        <p className="text-[10px] text-muted-foreground">
                          Limit: {parseInt(quotaInput, 10) >= 1024
                            ? `${(parseInt(quotaInput, 10) / 1024).toFixed(1)} GB`
                            : `${quotaInput} MB`}
                        </p>
                      )}
                      <button
                        onClick={() => { setQuotaInput(""); doAction("quota", `${BACKEND}/api/admin/users/${selected.id}/quota`, "PATCH", { quota_mb: null }) }}
                        className="text-[10px] text-muted-foreground hover:text-foreground underline underline-offset-2 transition-colors"
                      >
                        Remove limit
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Audit log */}
        <div className="card-elevated p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ScrollText className="size-4 text-muted-foreground" />
              <p className="font-semibold text-sm">Admin Audit Log</p>
            </div>
            <button onClick={fetchAuditLog} disabled={auditLoading} className="text-xs text-muted-foreground hover:text-foreground transition-colors">
              {auditLoading ? <Loader2 className="size-3 animate-spin" /> : "Refresh"}
            </button>
          </div>
          {auditLoading && auditLog.length === 0 ? (
            <div className="flex items-center justify-center py-6 gap-2 text-muted-foreground text-xs">
              <Loader2 className="size-3.5 animate-spin" /> Loading…
            </div>
          ) : auditLog.length === 0 ? (
            <p className="text-xs text-muted-foreground text-center py-4">No admin actions recorded yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-muted-foreground border-b border-border">
                    <th className="pb-2 pr-4 font-medium">When</th>
                    <th className="pb-2 pr-4 font-medium">Admin</th>
                    <th className="pb-2 pr-4 font-medium">Action</th>
                    <th className="pb-2 pr-4 font-medium">Target</th>
                    <th className="pb-2 font-medium">Detail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {auditLog.map((e) => (
                    <tr key={e.id} className="hover:bg-muted/20 transition-colors">
                      <td className="py-2 pr-4 text-muted-foreground whitespace-nowrap">{timeAgo(e.created_at)}</td>
                      <td className="py-2 pr-4 font-mono truncate max-w-[140px]">{e.admin_email}</td>
                      <td className="py-2 pr-4">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                          e.action === "delete_user"   ? "bg-destructive/10 text-destructive" :
                          e.action === "block"         ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400" :
                          e.action === "grant_admin"   ? "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400" :
                          e.action === "revoke_admin"  ? "bg-muted text-muted-foreground" :
                          "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                        }`}>
                          {e.action.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground truncate max-w-[160px]">{e.target_email ?? "—"}</td>
                      <td className="py-2 text-muted-foreground truncate max-w-[160px]">{e.detail ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
