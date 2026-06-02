"use client"

import { useState, useEffect } from "react"
import { signIn, useSession } from "next-auth/react"
import Link from "next/link"
import {
  Sparkles, Eye, EyeOff, CheckCircle2, XCircle,
  ArrowRight, Loader2, X, Shield,
} from "lucide-react"
import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

/* ── password helpers ───────────────────────────────────────────────────── */
function strength(pwd: string) {
  if (!pwd) return { score: 0, label: "", color: "" }
  let s = 0
  if (pwd.length >= 8)           s++
  if (pwd.length >= 12)          s++
  if (/[A-Z]/.test(pwd))         s++
  if (/[0-9]/.test(pwd))         s++
  if (/[^A-Za-z0-9]/.test(pwd)) s++
  if (s <= 1) return { score: s, label: "Weak",   color: "bg-destructive" }
  if (s <= 2) return { score: s, label: "Fair",   color: "bg-amber-500"   }
  if (s <= 3) return { score: s, label: "Good",   color: "bg-yellow-400"  }
  return          { score: s, label: "Strong", color: "bg-green-500"   }
}

function StrengthBar({ pwd }: { pwd: string }) {
  const { score, label, color } = strength(pwd)
  if (!pwd) return null
  return (
    <div className="mt-1.5 space-y-1">
      <div className="flex gap-1 h-1">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className={`h-full flex-1 rounded-full transition-colors ${i <= score ? color : "bg-border"}`} />
        ))}
      </div>
      <p className={`text-[11px] font-medium ${
        score <= 1 ? "text-destructive" :
        score <= 2 ? "text-amber-500" :
        score <= 3 ? "text-yellow-500" : "text-green-600"}`}>
        {label} password
      </p>
    </div>
  )
}

function Rule({ ok, text }: { ok: boolean; text: string }) {
  return (
    <span className={`flex items-center gap-1 text-[11px] ${ok ? "text-green-600" : "text-muted-foreground"}`}>
      {ok ? <CheckCircle2 className="size-3" /> : <XCircle className="size-3 opacity-40" />}
      {text}
    </span>
  )
}

/* ── password input ─────────────────────────────────────────────────────── */
function PwdInput({ id, value, onChange, placeholder, autoComplete, show, onToggle }: {
  id: string; value: string; onChange: (v: string) => void
  placeholder: string; autoComplete: string; show: boolean; onToggle: () => void
}) {
  return (
    <div className="flex items-center rounded-lg border border-input bg-transparent focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50 transition-colors dark:bg-input/30">
      <input
        id={id} type={show ? "text" : "password"} value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder} autoComplete={autoComplete}
        className="flex-1 h-10 px-2.5 bg-transparent outline-none text-sm text-foreground placeholder:text-muted-foreground"
      />
      <button type="button" onClick={onToggle}
        className="flex items-center justify-center h-10 w-10 shrink-0 text-muted-foreground hover:text-foreground transition-colors rounded-r-lg">
        {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  )
}

/* ── Terms of Service modal ─────────────────────────────────────────────── */
function TosModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-card rounded-2xl shadow-2xl max-w-lg w-full p-6 space-y-4 animate-scale-in max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <div className="size-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <Shield className="size-4 text-primary" />
            </div>
            <h2 className="font-semibold text-base">Terms of Service</h2>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted transition-colors">
            <X className="size-4" />
          </button>
        </div>
        <div className="overflow-y-auto text-sm text-muted-foreground space-y-4 pr-1">
          <p className="text-xs text-muted-foreground/60">Last updated: May 2026</p>

          <section className="space-y-1.5">
            <h3 className="font-semibold text-foreground text-sm">1. Acceptance</h3>
            <p>By creating an account you agree to these Terms. If you do not agree, do not use Business Assistant.</p>
          </section>

          <section className="space-y-1.5">
            <h3 className="font-semibold text-foreground text-sm">2. Your data</h3>
            <p>You retain ownership of all data you upload. Business Assistant processes your data solely to answer your queries. We do not sell or share your data with third parties.</p>
          </section>

          <section className="space-y-1.5">
            <h3 className="font-semibold text-foreground text-sm">3. Acceptable use</h3>
            <p>You may not use Business Assistant to upload unlawful content, attempt to breach security, or reverse-engineer the service. We reserve the right to suspend accounts that violate these terms.</p>
          </section>

          <section className="space-y-1.5">
            <h3 className="font-semibold text-foreground text-sm">4. AI-generated content</h3>
            <p>Query results and summaries are generated by AI and may contain errors. Always verify important business decisions against your source data. Business Assistant is not liable for decisions made based on AI output.</p>
          </section>

          <section className="space-y-1.5">
            <h3 className="font-semibold text-foreground text-sm">5. Account security</h3>
            <p>You are responsible for keeping your credentials secure. Notify us immediately if you suspect unauthorised access to your account.</p>
          </section>

          <section className="space-y-1.5">
            <h3 className="font-semibold text-foreground text-sm">6. Limitation of liability</h3>
            <p>Business Assistant is provided "as is" without warranty of any kind. To the fullest extent permitted by law, we are not liable for indirect, incidental, or consequential damages.</p>
          </section>

          <section className="space-y-1.5">
            <h3 className="font-semibold text-foreground text-sm">7. Changes to terms</h3>
            <p>We may update these Terms at any time. Continued use after changes constitutes acceptance of the revised Terms.</p>
          </section>
        </div>
        <div className="shrink-0 pt-2 border-t border-border">
          <Button onClick={onClose} className="w-full gap-2">
            <CheckCircle2 className="size-4" /> Got it
          </Button>
        </div>
      </div>
    </div>
  )
}

/* ── page ────────────────────────────────────────────────────────────────── */
export default function SignupPage() {
  const { status } = useSession()
  useEffect(() => {
    if (status === "authenticated") window.location.replace("/home")
  }, [status])

  const [name,    setName]    = useState("")
  const [email,   setEmail]   = useState("")
  const [pwd,     setPwd]     = useState("")
  const [confirm, setConfirm] = useState("")
  const [showP,   setShowP]   = useState(false)
  const [showC,   setShowC]   = useState(false)
  const [error,   setError]   = useState("")
  const [loading, setLoading] = useState(false)
  const [showTos, setShowTos] = useState(false)

  const emailOk   = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
  const has8      = pwd.length >= 8
  const hasUpper  = /[A-Z]/.test(pwd)
  const hasNumber = /[0-9]/.test(pwd)
  const hasSymbol = /[^A-Za-z0-9]/.test(pwd)
  const pwdOk     = has8 && hasUpper && hasNumber && hasSymbol
  const matchOk   = pwd === confirm && confirm.length > 0

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")

    if (!name.trim())  return setError("Please enter your name.")
    if (!emailOk)      return setError("Please enter a valid email address.")
    if (!has8)         return setError("Password must be at least 8 characters.")
    if (!hasUpper)     return setError("Password must contain an uppercase letter.")
    if (!hasNumber)    return setError("Password must contain a number.")
    if (!hasSymbol)    return setError("Password must contain a symbol (e.g. !@#$).")
    if (!matchOk)      return setError("Passwords do not match.")

    setLoading(true)

    try {
      const res = await fetch(`${BACKEND}/api/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password: pwd, name }),
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail ?? "Signup failed. Please try again.")
        setLoading(false)
        return
      }
    } catch {
      setError("Cannot reach the server. Check your connection.")
      setLoading(false)
      return
    }

    try {
      const result = await signIn("credentials", { email, password: pwd, redirect: false })
      setLoading(false)
      if (result?.error) { window.location.href = "/login?signup=1"; return }
      // Redirect to verify page — user must confirm their email before chatting
      window.location.replace("/verify")
    } catch {
      setLoading(false)
      window.location.replace("/login?signup=1")
    }
  }

  return (
    <div className="w-full max-w-md">
      {showTos && <TosModal onClose={() => setShowTos(false)} />}

      {/* brand */}
      <div className="flex flex-col items-center gap-2 mb-8">
        <Link href="/" className="size-11 rounded-2xl bg-primary flex items-center justify-center shadow-lg hover:opacity-90 transition-opacity">
          <Sparkles className="size-5 text-primary-foreground" />
        </Link>
        <h1 className="text-2xl font-bold tracking-tight">Create your account</h1>
        <p className="text-sm text-muted-foreground">Start analysing your data with AI</p>
      </div>

      <div className="rounded-2xl border border-border bg-card shadow-sm p-7 space-y-5">
        <form onSubmit={handleSubmit} className="space-y-4" noValidate>

          <div className="space-y-1.5">
            <Label htmlFor="name">Full name</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)}
              placeholder="Alex Johnson" autoComplete="name" className="h-10" />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="email">Email address</Label>
            <div className="relative">
              <Input id="email" type="email" value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com" autoComplete="email"
                className={`h-10 pr-9 ${email && !emailOk ? "border-destructive" : ""}`} />
              {email && (
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2">
                  {emailOk
                    ? <CheckCircle2 className="size-4 text-green-500" />
                    : <XCircle className="size-4 text-destructive/70" />}
                </span>
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="pwd">Password</Label>
            <PwdInput id="pwd" value={pwd} onChange={setPwd}
              placeholder="Min. 8 characters" autoComplete="new-password"
              show={showP} onToggle={() => setShowP((v) => !v)} />
            <StrengthBar pwd={pwd} />
            {pwd && (
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
                <Rule ok={has8}      text="8+ chars" />
                <Rule ok={hasUpper}  text="Uppercase" />
                <Rule ok={hasNumber} text="Number" />
                <Rule ok={hasSymbol} text="Symbol" />
              </div>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="confirm">Confirm password</Label>
            <PwdInput id="confirm" value={confirm} onChange={setConfirm}
              placeholder="Repeat your password" autoComplete="new-password"
              show={showC} onToggle={() => setShowC((v) => !v)} />
            {confirm && (
              <p className={`text-[11px] flex items-center gap-1 ${matchOk ? "text-green-600" : "text-destructive"}`}>
                {matchOk
                  ? <><CheckCircle2 className="size-3" /> Passwords match</>
                  : <><XCircle className="size-3" /> Passwords do not match</>}
              </p>
            )}
          </div>

          {error && (
            <div className="rounded-lg bg-destructive/10 border border-destructive/20 px-3 py-2.5 text-sm text-destructive flex items-start gap-2">
              <XCircle className="size-4 mt-0.5 shrink-0" /> {error}
            </div>
          )}

          <Button type="submit" className="w-full h-10 gap-2" disabled={loading}>
            {loading
              ? <><Loader2 className="size-4 animate-spin" /> Creating account…</>
              : <>Create account <ArrowRight className="size-4" /></>}
          </Button>
        </form>

        <div className="relative">
          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-border" /></div>
          <div className="relative flex justify-center">
            <span className="bg-card px-3 text-xs text-muted-foreground">Already have an account?</span>
          </div>
        </div>

        <Link href="/login" className={cn(buttonVariants({ variant: "outline" }), "w-full h-10")}>
          Sign in instead
        </Link>
      </div>

      <p className="text-center text-xs text-muted-foreground mt-6">
        By signing up you agree to our{" "}
        <button
          type="button"
          onClick={() => setShowTos(true)}
          className="text-primary underline underline-offset-2 hover:text-primary/80 transition-colors"
        >
          Terms of Service
        </button>.
      </p>
    </div>
  )
}
