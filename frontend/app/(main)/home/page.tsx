"use client"

import { useEffect, useState } from "react"
import { useSession, signOut } from "next-auth/react"
import Link from "next/link"
import {
  Sparkles, MessageSquare, Database, BookOpen, BarChart2,
  Upload, ArrowRight, LogOut, User, Cloud, Plus,
  Zap, ChevronRight, Activity, CheckCircle2, FileText,
  Search, PieChart, ShieldCheck, FlaskConical,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

interface Dataset { table_name: string; row_count: number; columns: unknown[] }
interface Thread  { id: string; title: string; updated_at: string }
interface GlossaryEntry { id: number; term: string }

function fmtNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins  = Math.floor(diff / 60_000)
  const hours = Math.floor(diff / 3_600_000)
  const days  = Math.floor(diff / 86_400_000)
  if (mins  < 2)  return "just now"
  if (mins  < 60) return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  return `${days}d ago`
}

const QUICK_ACTIONS = [
  {
    href: "/chat",
    icon: MessageSquare,
    label: "Ask a question",
    desc: "Natural language to SQL in seconds",
    gradient: "from-violet-500 to-purple-600",
    glow: "group-hover:shadow-purple-500/25",
    badge: "AI-powered",
  },
  {
    href: "/datasets",
    icon: Upload,
    label: "Upload CSV",
    desc: "Import datasets and start analysing instantly",
    gradient: "from-blue-500 to-cyan-500",
    glow: "group-hover:shadow-blue-500/25",
    badge: "CSV / Excel",
  },
  {
    href: "/catalog",
    icon: BookOpen,
    label: "Data Catalog",
    desc: "Enrich tables with descriptions and KPIs",
    gradient: "from-emerald-500 to-teal-500",
    glow: "group-hover:shadow-emerald-500/25",
    badge: "Metadata",
  },
  {
    href: "/athena",
    icon: Cloud,
    label: "Athena Connect",
    desc: "Query AWS Glue catalog tables directly",
    gradient: "from-amber-500 to-orange-500",
    glow: "group-hover:shadow-amber-500/25",
    badge: "AWS",
  },
  {
    href: "/analysis",
    icon: FlaskConical,
    label: "Analysis Templates",
    desc: "Run EDA, distributions, outliers, and time trends on any dataset",
    gradient: "from-violet-500 to-purple-600",
    glow: "group-hover:shadow-violet-500/25",
    badge: "No-code",
  },
]

export default function HomePage() {
  const { data: session } = useSession()
  const [datasets,  setDatasets]  = useState<Dataset[]>([])
  const [threads,   setThreads]   = useState<Thread[]>([])
  const [glossary,  setGlossary]  = useState<GlossaryEntry[]>([])
  const [loading,   setLoading]   = useState(true)

  const authHeader = { Authorization: `Bearer ${session?.accessToken}` }
  const displayName = (session?.user as { name?: string })?.name || session?.user?.email?.split("@")[0] || "there"
  const firstName = displayName.split(" ")[0]

  useEffect(() => {
    if (!session?.accessToken) return
    const safe = (p: Promise<Response>, fallback: unknown[] = []) =>
      p.then(r => r.ok ? r.json() : fallback).catch(() => fallback)
    Promise.all([
      safe(fetch(`${BACKEND}/api/datasets`,  { headers: authHeader })),
      safe(fetch(`${BACKEND}/api/threads`,   { headers: authHeader })),
      safe(fetch(`${BACKEND}/api/glossary`,  { headers: authHeader })),
    ]).then(([ds, th, gl]) => { setDatasets(ds); setThreads(th); setGlossary(gl) })
      .finally(() => setLoading(false))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  const oneWeekAgo   = Date.now() - 7 * 86_400_000
  const activeThisWeek = threads.filter(t => new Date(t.updated_at).getTime() > oneWeekAgo).length

  return (
    <div className="min-h-screen bg-background overflow-x-hidden">

      {/* ── Background gradient orbs ── */}
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-40 -left-40 w-150 h-150 rounded-full bg-violet-500/10 dark:bg-violet-500/6 blur-[120px]" />
        <div className="absolute -top-20 right-0 w-125 h-125 rounded-full bg-blue-500/8 dark:bg-blue-500/5 blur-[120px]" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-200 h-100 rounded-full bg-primary/4 blur-[120px]" />
      </div>

      {/* ── Nav ── */}
      <nav className="sticky top-0 z-40 border-b border-border/50 bg-background/70 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto flex items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2.5">
            <div className="size-8 rounded-xl bg-linear-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-lg shadow-purple-500/30">
              <Sparkles className="size-4 text-white" />
            </div>
            <span className="font-bold tracking-tight text-sm">DataChat</span>
          </div>
          <div className="flex items-center gap-1">
            <Link href="/profile" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "gap-1.5 text-xs")}>
              <User className="size-3.5" /> Profile
            </Link>
            <button
              onClick={() => { if (confirm("Sign out?")) signOut({ callbackUrl: "/login" }) }}
              className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "gap-1.5 text-xs text-muted-foreground")}
            >
              <LogOut className="size-3.5" /> Sign out
            </button>
          </div>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6 pb-20">

        {/* ── Hero ── */}
        <section className="pt-14 pb-12 text-center space-y-5">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border/60 bg-muted/40 text-xs text-muted-foreground mb-2">
            <Activity className="size-3 text-green-500" />
            <span>Ready to analyse</span>
            {!loading && datasets.length > 0 && (
              <span className="ml-1 font-semibold text-foreground">{datasets.length} dataset{datasets.length !== 1 ? "s" : ""} connected</span>
            )}
          </div>
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight">
            Good {getGreeting()},{" "}
            <span className="bg-linear-to-r from-violet-500 via-purple-500 to-blue-500 bg-clip-text text-transparent">
              {firstName}
            </span>
          </h1>
          <p className="text-muted-foreground text-base max-w-lg mx-auto leading-relaxed">
            {datasets.length === 0
              ? "Upload a CSV or connect Athena to start querying your business data with plain English."
              : "Your data is ready. Ask a question or explore your datasets below."}
          </p>
          <div className="flex items-center justify-center gap-3 pt-2">
            <Link href="/chat" className={cn(buttonVariants({ size: "lg" }), "gap-2 shadow-lg shadow-primary/25 rounded-xl px-6")}>
              <Zap className="size-4" /> Ask a question
            </Link>
            <Link href="/datasets" className={cn(buttonVariants({ variant: "outline", size: "lg" }), "gap-2 rounded-xl px-6")}>
              <Upload className="size-4" /> Upload data
            </Link>
          </div>
        </section>

        {/* ── Stats ── */}
        <section className="grid grid-cols-2 sm:grid-cols-4 gap-4 pb-12">
          {[
            { icon: Database,      label: "Datasets",        value: loading ? "—" : String(datasets.length),       gradient: "from-violet-500 to-purple-600",  href: "/datasets",     sub: "tables connected" },
            { icon: MessageSquare, label: "Conversations",   value: loading ? "—" : String(threads.length),        gradient: "from-blue-500 to-cyan-500",      href: "/chat",         sub: "all time" },
            { icon: Activity,      label: "Active this week",value: loading ? "—" : String(activeThisWeek),        gradient: "from-emerald-500 to-teal-500",   href: "/chat",         sub: "queries in 7 days" },
            { icon: BookOpen,      label: "Glossary terms",  value: loading ? "—" : String(glossary.length),       gradient: "from-amber-500 to-orange-500",   href: "/glossary",     sub: "business definitions" },
          ].map(({ icon: Icon, label, value, gradient, href, sub }) => (
            <Link key={label} href={href} className="group relative rounded-2xl border border-border/60 bg-card/50 backdrop-blur-sm p-5 hover:border-border transition-all duration-300 hover:shadow-lg hover:shadow-black/5 overflow-hidden">
              <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-linear-to-br from-muted/30 to-transparent rounded-2xl" />
              <div className="relative">
                <div className={`size-9 rounded-xl bg-linear-to-br ${gradient} flex items-center justify-center mb-3 shadow-lg`}>
                  <Icon className="size-4 text-white" />
                </div>
                <p className="text-2xl font-bold tracking-tight">{value}</p>
                <p className="text-xs font-medium mt-0.5">{label}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{sub}</p>
              </div>
            </Link>
          ))}
        </section>

        {/* ── Quick actions ── */}
        <section className="pb-14">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-lg font-semibold tracking-tight">Quick actions</h2>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {QUICK_ACTIONS.map(({ href, icon: Icon, label, desc, gradient, glow, badge }) => (
              <Link
                key={href}
                href={href}
                className={`group relative rounded-2xl border border-border/60 bg-card/50 backdrop-blur-sm p-5 hover:border-border transition-all duration-300 hover:shadow-xl ${glow} overflow-hidden flex flex-col gap-4`}
              >
                <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-500 bg-linear-to-br from-muted/20 to-transparent" />
                <div className="relative flex items-start justify-between">
                  <div className={`size-11 rounded-2xl bg-linear-to-br ${gradient} flex items-center justify-center shadow-lg`}>
                    <Icon className="size-5 text-white" />
                  </div>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-muted text-muted-foreground">{badge}</span>
                </div>
                <div className="relative flex-1">
                  <p className="font-semibold text-sm leading-tight">{label}</p>
                  <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{desc}</p>
                </div>
                <div className="relative flex items-center gap-1 text-xs text-muted-foreground group-hover:text-primary transition-colors">
                  <span>Open</span>
                  <ChevronRight className="size-3 group-hover:translate-x-0.5 transition-transform" />
                </div>
              </Link>
            ))}
          </div>
        </section>

        {/* ── How it works ── */}
        <section className="pb-14">
          <div className="mb-6">
            <h2 className="text-lg font-semibold tracking-tight">How it works</h2>
            <p className="text-sm text-muted-foreground mt-1">Four steps from raw data to insight — no SQL knowledge needed.</p>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              {
                step: "01", icon: Database, title: "Connect your data",
                desc: "Upload CSV files or connect AWS Athena. Your data stays private and is scoped to your account.",
                color: "text-violet-500", bg: "bg-violet-500/10",
              },
              {
                step: "02", icon: Search, title: "Ask in plain English",
                desc: "Type a question like \"Show me revenue by region last quarter\" — no SQL required.",
                color: "text-blue-500", bg: "bg-blue-500/10",
              },
              {
                step: "03", icon: ShieldCheck, title: "Review & approve SQL",
                desc: "DataChat shows you the generated SQL before running it. Edit or approve with one click.",
                color: "text-emerald-500", bg: "bg-emerald-500/10",
              },
              {
                step: "04", icon: PieChart, title: "Charts & summaries",
                desc: "Results appear as interactive charts with a plain-English explanation of the key finding.",
                color: "text-amber-500", bg: "bg-amber-500/10",
              },
            ].map(({ step, icon: Icon, title, desc, color, bg }) => (
              <div key={step} className="relative rounded-2xl border border-border/60 bg-card/50 backdrop-blur-sm p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <div className={`size-10 rounded-xl ${bg} flex items-center justify-center`}>
                    <Icon className={`size-5 ${color}`} />
                  </div>
                  <span className={`text-3xl font-black ${color} opacity-20 leading-none`}>{step}</span>
                </div>
                <div>
                  <p className="font-semibold text-sm">{title}</p>
                  <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{desc}</p>
                </div>
              </div>
            ))}
          </div>

          {/* Feature callouts */}
          <div className="mt-4 grid sm:grid-cols-3 gap-3">
            {[
              { icon: CheckCircle2, label: "Business Glossary", desc: "Define terms like \"ARR\" or \"Churn rate\" once — DataChat applies them to every query automatically.", href: "/glossary", color: "text-emerald-500" },
              { icon: FileText,     label: "Saved Queries",     desc: "Save useful queries and re-run them with one click. Share them with your team.", href: "/saved-queries", color: "text-blue-500" },
              { icon: BarChart2,    label: "Data Catalog",      desc: "Add column descriptions, KPI definitions, and join hints to make AI answers more accurate.", href: "/catalog", color: "text-violet-500" },
            ].map(({ icon: Icon, label, desc, href, color }) => (
              <Link key={href} href={href} className="group flex gap-3 rounded-xl border border-border/60 bg-card/50 p-4 hover:border-border hover:bg-card transition-all duration-200">
                <div className="shrink-0 mt-0.5">
                  <Icon className={`size-4 ${color}`} />
                </div>
                <div className="min-w-0">
                  <p className="font-semibold text-sm group-hover:text-primary transition-colors">{label}</p>
                  <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{desc}</p>
                </div>
                <ChevronRight className="size-4 text-muted-foreground/30 group-hover:text-primary shrink-0 self-center ml-auto group-hover:translate-x-0.5 transition-all" />
              </Link>
            ))}
          </div>
        </section>

        {/* ── Recent data ── */}
        <div className="grid md:grid-cols-2 gap-6 pb-12">

          {/* Recent datasets */}
          <section>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold tracking-tight">Recent datasets</h2>
              <Link href="/datasets" className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors">
                View all <ChevronRight className="size-3" />
              </Link>
            </div>
            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map(i => <div key={i} className="h-16 rounded-xl bg-muted/30 animate-pulse" />)}
              </div>
            ) : datasets.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/60 bg-muted/10 p-8 text-center space-y-3">
                <div className="size-12 rounded-2xl bg-muted/50 flex items-center justify-center mx-auto">
                  <Database className="size-5 text-muted-foreground/50" />
                </div>
                <p className="text-sm text-muted-foreground">No datasets yet</p>
                <Link href="/datasets" className={cn(buttonVariants({ size: "sm", variant: "outline" }), "gap-1.5")}>
                  <Plus className="size-3.5" /> Upload CSV
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {datasets.slice(0, 5).map((ds) => (
                  <div key={ds.table_name} className="group flex items-center justify-between rounded-xl border border-border/60 bg-card/50 px-4 py-3 hover:border-border hover:bg-card transition-all duration-200">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="size-8 rounded-lg bg-linear-to-br from-emerald-500 to-teal-500 flex items-center justify-center shrink-0 shadow-sm">
                        <Database className="size-3.5 text-white" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-mono text-sm font-semibold truncate">{ds.table_name}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {ds.row_count.toLocaleString()} rows · {ds.columns?.length ?? 0} cols
                        </p>
                      </div>
                    </div>
                    <Link href="/chat" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "gap-1 text-xs shrink-0 opacity-0 group-hover:opacity-100 transition-opacity")}>
                      Query <ArrowRight className="size-3" />
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Recent conversations */}
          <section>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold tracking-tight">Recent conversations</h2>
              <Link href="/chat" className="flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors">
                New chat <ChevronRight className="size-3" />
              </Link>
            </div>
            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map(i => <div key={i} className="h-16 rounded-xl bg-muted/30 animate-pulse" />)}
              </div>
            ) : threads.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-border/60 bg-muted/10 p-8 text-center space-y-3">
                <div className="size-12 rounded-2xl bg-muted/50 flex items-center justify-center mx-auto">
                  <MessageSquare className="size-5 text-muted-foreground/50" />
                </div>
                <p className="text-sm text-muted-foreground">No conversations yet</p>
                <Link href="/chat" className={cn(buttonVariants({ size: "sm", variant: "outline" }), "gap-1.5")}>
                  <MessageSquare className="size-3.5" /> Start chatting
                </Link>
              </div>
            ) : (
              <div className="space-y-2">
                {threads.slice(0, 5).map((t) => (
                  <Link
                    key={t.id}
                    href="/chat"
                    className="group flex items-center justify-between rounded-xl border border-border/60 bg-card/50 px-4 py-3 hover:border-border hover:bg-card transition-all duration-200"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="size-8 rounded-lg bg-linear-to-br from-violet-500 to-purple-600 flex items-center justify-center shrink-0 shadow-sm">
                        <MessageSquare className="size-3.5 text-white" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate group-hover:text-primary transition-colors">{t.title || "Untitled"}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">{timeAgo(t.updated_at)}</p>
                      </div>
                    </div>
                    <ArrowRight className="size-3.5 text-muted-foreground/30 group-hover:text-primary shrink-0 ml-2 group-hover:translate-x-0.5 transition-all" />
                  </Link>
                ))}
              </div>
            )}
          </section>
        </div>

        {/* ── Onboarding banner (no data) ── */}
        {!loading && datasets.length === 0 && (
          <section className="relative rounded-3xl overflow-hidden border border-violet-500/20 bg-linear-to-br from-violet-500/5 via-purple-500/5 to-blue-500/5 p-10 text-center">
            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute top-0 left-1/4 w-32 h-32 rounded-full bg-violet-500/10 blur-3xl" />
              <div className="absolute bottom-0 right-1/4 w-32 h-32 rounded-full bg-blue-500/10 blur-3xl" />
            </div>
            <div className="relative space-y-4">
              <div className="size-14 rounded-2xl bg-linear-to-br from-violet-500 to-purple-600 flex items-center justify-center mx-auto shadow-xl shadow-purple-500/30">
                <BarChart2 className="size-7 text-white" />
              </div>
              <div>
                <h3 className="text-xl font-bold tracking-tight">Ready to analyse your data?</h3>
                <p className="text-sm text-muted-foreground mt-2 max-w-md mx-auto leading-relaxed">
                  Upload a CSV or connect AWS Athena. Ask questions in plain English — DataChat generates SQL, builds charts, and explains the results.
                </p>
              </div>
              <div className="flex flex-wrap justify-center gap-3 pt-2">
                <Link href="/datasets" className={cn(buttonVariants({ size: "lg" }), "gap-2 rounded-xl shadow-lg shadow-primary/25 px-6")}>
                  <Upload className="size-4" /> Upload CSV
                </Link>
                <Link href="/athena" className={cn(buttonVariants({ variant: "outline", size: "lg" }), "gap-2 rounded-xl px-6")}>
                  <Cloud className="size-4" /> Connect Athena
                </Link>
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  )
}

function getGreeting(): string {
  const h = new Date().getHours()
  if (h < 12) return "morning"
  if (h < 17) return "afternoon"
  return "evening"
}
