import { auth } from "@/lib/auth"
import { redirect } from "next/navigation"
import Link from "next/link"
import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"
import {
  Sparkles, BarChart2, Database, Shield,
  ArrowRight, Zap, MessageSquare, CheckCircle,
} from "lucide-react"

const FEATURES = [
  {
    icon: MessageSquare,
    title: "Natural Language Queries",
    desc: "Ask in plain English. Our AI handles typos, abbreviations, and context — no SQL knowledge needed.",
  },
  {
    icon: BarChart2,
    title: "Instant Visualisations",
    desc: "Results rendered as bar charts, line graphs, scatter plots, or interactive tables automatically.",
  },
  {
    icon: Shield,
    title: "Human-in-the-loop",
    desc: "Review, edit, and approve every SQL query before it runs. Full transparency, zero surprises.",
  },
  {
    icon: Database,
    title: "Upload Your Own Data",
    desc: "Drop any CSV file and start asking questions immediately. Your data stays private and isolated.",
  },
]

const STEPS = [
  {
    num: "01",
    title: "Ask a question",
    desc: 'Type something like "Show top 5 customers by revenue" — typos and abbreviations handled.',
  },
  {
    num: "02",
    title: "Review the SQL",
    desc: "See the generated query explained in plain English. Edit it if you want, or approve as-is.",
  },
  {
    num: "03",
    title: "Get your insight",
    desc: "A chart or table appears with an AI-written summary. Download the data as CSV anytime.",
  },
]

export default async function HomePage() {
  const session = await auth()
  if (session) redirect("/home")

  return (
    <div className="min-h-screen bg-background text-foreground">

      {/* ── Nav ─────────────────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-md">
        <div className="mx-auto max-w-6xl flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2.5">
            <div className="size-8 rounded-xl bg-primary flex items-center justify-center shadow-sm">
              <Sparkles className="size-4 text-primary-foreground" />
            </div>
            <span className="font-bold text-lg tracking-tight">Business Assistant</span>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/login"
              className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "text-muted-foreground hover:text-foreground")}
            >
              Sign in
            </Link>
            <Link
              href="/signup"
              className={cn(buttonVariants({ size: "sm" }), "gap-1.5")}
            >
              Get started <ArrowRight className="size-3.5" />
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="relative isolate overflow-hidden py-28 sm:py-36">
        <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
          <div className="absolute left-1/2 top-0 -translate-x-1/2 h-125 w-225 rounded-full bg-primary/8 blur-3xl" />
          <div className="absolute bottom-0 right-0 h-75 w-125 rounded-full bg-primary/5 blur-3xl" />
        </div>

        <div className="mx-auto max-w-4xl px-6 text-center">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/25 bg-primary/8 px-4 py-1.5 text-xs font-semibold text-primary mb-8 tracking-wide uppercase">
            <Zap className="size-3" /> Multi-agent AI analytics
          </span>

          <h1 className="text-5xl sm:text-6xl font-extrabold tracking-tight leading-[1.1] mb-6">
            Business intelligence,<br />
            <span className="text-primary">spoken naturally.</span>
          </h1>

          <p className="text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed mb-10">
            Ask questions about your data in plain English. Business Assistant generates SQL, builds charts,
            and delivers AI-written summaries — with your approval at every step.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link
              href="/signup"
              className={cn(buttonVariants({ size: "lg" }), "gap-2 px-8 text-base h-12 shadow-md")}
            >
              Start for free <ArrowRight className="size-4" />
            </Link>
            <Link
              href="/login"
              className={cn(buttonVariants({ variant: "outline", size: "lg" }), "px-8 text-base h-12")}
            >
              Sign in
            </Link>
          </div>

          <p className="mt-5 text-xs text-muted-foreground/70">No credit card required · Takes 30 seconds</p>
        </div>
      </section>

      {/* ── Features ─────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <div className="text-center mb-14">
          <h2 className="text-3xl font-bold tracking-tight mb-3">
            Everything you need to understand your data
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            From raw CSV files to boardroom-ready charts — without writing a single line of SQL.
          </p>
        </div>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div
              key={title}
              className="group rounded-2xl border border-border bg-card p-6 hover:border-primary/40 hover:shadow-sm transition-all duration-200"
            >
              <div className="size-11 rounded-xl bg-primary/10 flex items-center justify-center mb-4 group-hover:bg-primary/15 transition-colors">
                <Icon className="size-5 text-primary" />
              </div>
              <h3 className="font-semibold text-sm mb-2">{title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────────────────────── */}
      <section className="border-y border-border/50 bg-muted/20">
        <div className="mx-auto max-w-5xl px-6 py-24">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold tracking-tight mb-3">How it works</h2>
            <p className="text-muted-foreground text-lg">Three steps from question to insight</p>
          </div>
          <div className="grid md:grid-cols-3 gap-10">
            {STEPS.map(({ num, title, desc }) => (
              <div key={num} className="text-center">
                <div className="text-6xl font-black text-primary/15 font-mono mb-3 select-none">{num}</div>
                <h3 className="font-semibold text-base mb-2">{title}</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Trust strip ──────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-4xl px-6 py-16 text-center">
        <div className="flex flex-wrap justify-center gap-x-8 gap-y-3 text-sm text-muted-foreground">
          {[
            "Multi-agent LangGraph pipeline",
            "Human-in-the-loop SQL approval",
            "CSV upload support",
            "Business glossary",
            "Dark & light mode",
          ].map((item) => (
            <span key={item} className="flex items-center gap-1.5">
              <CheckCircle className="size-4 text-primary/70" /> {item}
            </span>
          ))}
        </div>
      </section>

      {/* ── CTA ──────────────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-3xl px-6 py-24 text-center">
        <h2 className="text-3xl font-bold tracking-tight mb-4">Ready to talk to your data?</h2>
        <p className="text-muted-foreground text-lg mb-10 max-w-xl mx-auto">
          Create a free account in seconds and start getting answers from your business data today.
        </p>
        <Link
          href="/signup"
          className={cn(buttonVariants({ size: "lg" }), "gap-2 px-10 text-base h-12 shadow-md")}
        >
          Create free account <ArrowRight className="size-4" />
        </Link>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────────── */}
      <footer className="border-t border-border/50 bg-muted/10">
        <div className="mx-auto max-w-6xl px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-muted-foreground">
          <div className="flex items-center gap-2.5">
            <div className="size-5 rounded-md bg-primary flex items-center justify-center">
              <Sparkles className="size-3 text-primary-foreground" />
            </div>
            <span className="font-semibold text-foreground">Business Assistant</span>
            <span className="ml-1">© 2026. All rights reserved.</span>
          </div>
          <div className="flex gap-6">
            <Link href="/login" className="hover:text-foreground transition-colors">Sign in</Link>
            <Link href="/signup" className="hover:text-foreground transition-colors">Sign up</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
