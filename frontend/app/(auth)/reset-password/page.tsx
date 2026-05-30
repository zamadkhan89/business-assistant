"use client"

import { useState, Suspense } from "react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import { Sparkles, Loader2, CheckCircle2, XCircle, ArrowRight, Eye, EyeOff } from "lucide-react"
import { Button, buttonVariants } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

function PwdInput({
  id, value, onChange, placeholder, autoComplete, show, onToggle,
}: {
  id: string; value: string; onChange: (v: string) => void
  placeholder: string; autoComplete: string; show: boolean; onToggle: () => void
}) {
  return (
    <div className="flex items-center rounded-lg border border-input bg-transparent focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50 transition-colors dark:bg-input/30">
      <input
        id={id} type={show ? "text" : "password"} value={value}
        onChange={e => onChange(e.target.value)} placeholder={placeholder}
        autoComplete={autoComplete}
        className="flex-1 h-10 px-2.5 bg-transparent outline-none text-sm text-foreground placeholder:text-muted-foreground"
      />
      <button type="button" onClick={onToggle}
        className="flex items-center justify-center h-10 w-10 shrink-0 text-muted-foreground hover:text-foreground transition-colors rounded-r-lg">
        {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  )
}

function ResetForm() {
  const params = useSearchParams()
  const token = params.get("token") ?? ""

  const [pwd, setPwd] = useState("")
  const [confirm, setConfirm] = useState("")
  const [showP, setShowP] = useState(false)
  const [showC, setShowC] = useState(false)
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState("")

  const matchOk = pwd === confirm && confirm.length > 0

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")
    if (!token) { setError("Invalid or missing reset token."); return }
    if (pwd.length < 8) { setError("Password must be at least 8 characters."); return }
    if (!matchOk) { setError("Passwords do not match."); return }
    setLoading(true)
    try {
      const r = await fetch(`${BACKEND}/api/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: pwd }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
      setDone(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="text-center space-y-3">
        <XCircle className="size-10 text-destructive mx-auto" />
        <p className="font-semibold">Invalid reset link</p>
        <p className="text-sm text-muted-foreground">This link is missing a reset token.</p>
        <Link href="/forgot-password" className={cn(buttonVariants(), "gap-2")}>
          Request a new link
        </Link>
      </div>
    )
  }

  if (done) {
    return (
      <div className="text-center space-y-4">
        <div className="size-14 rounded-2xl bg-green-100 dark:bg-green-950/40 flex items-center justify-center mx-auto">
          <CheckCircle2 className="size-7 text-green-600 dark:text-green-400" />
        </div>
        <div>
          <p className="font-semibold">Password reset!</p>
          <p className="text-sm text-muted-foreground mt-1">You can now sign in with your new password.</p>
        </div>
        <Link href="/login" className={cn(buttonVariants(), "gap-2")}>
          Sign in <ArrowRight className="size-4" />
        </Link>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <div className="space-y-1.5">
        <Label htmlFor="pwd">New password</Label>
        <PwdInput id="pwd" value={pwd} onChange={setPwd}
          placeholder="Min. 8 characters" autoComplete="new-password"
          show={showP} onToggle={() => setShowP(v => !v)} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="confirm">Confirm new password</Label>
        <PwdInput id="confirm" value={confirm} onChange={setConfirm}
          placeholder="Repeat your password" autoComplete="new-password"
          show={showC} onToggle={() => setShowC(v => !v)} />
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
          ? <><Loader2 className="size-4 animate-spin" /> Resetting…</>
          : <>Reset password <ArrowRight className="size-4" /></>}
      </Button>
    </form>
  )
}

export default function ResetPasswordPage() {
  return (
    <div className="w-full max-w-md">
      <div className="flex flex-col items-center gap-2 mb-8">
        <Link href="/" className="size-11 rounded-2xl bg-primary flex items-center justify-center shadow-lg hover:opacity-90 transition-opacity">
          <Sparkles className="size-5 text-primary-foreground" />
        </Link>
        <h1 className="text-2xl font-bold tracking-tight">Set a new password</h1>
        <p className="text-sm text-muted-foreground">Choose a strong password for your account.</p>
      </div>

      <div className="rounded-2xl border border-border bg-card shadow-sm p-7 space-y-5">
        <Suspense fallback={null}>
          <ResetForm />
        </Suspense>
      </div>
    </div>
  )
}
