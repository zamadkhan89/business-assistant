"use client"

import { useState, Suspense, useEffect } from "react"
import { signIn, useSession } from "next-auth/react"
import { useSearchParams } from "next/navigation"
import Link from "next/link"
import {
  Sparkles, Eye, EyeOff, ArrowRight,
  Loader2, CheckCircle2, XCircle,
} from "lucide-react"
import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { Label } from "@/components/ui/label"

/* ── password input with working show/hide ──────────────────────────────── */
function PwdInput({
  id, value, onChange, placeholder, autoComplete, show, onToggle,
}: {
  id: string; value: string; onChange: (v: string) => void
  placeholder: string; autoComplete: string; show: boolean; onToggle: () => void
}) {
  return (
    <div className="flex items-center rounded-lg border border-input bg-transparent focus-within:border-ring focus-within:ring-[3px] focus-within:ring-ring/50 transition-colors dark:bg-input/30">
      <input
        id={id}
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        className="flex-1 h-10 px-2.5 bg-transparent outline-none text-sm text-foreground placeholder:text-muted-foreground"
      />
      <button
        type="button"
        onClick={onToggle}
        className="flex items-center justify-center h-10 w-10 shrink-0 text-muted-foreground hover:text-foreground transition-colors rounded-r-lg"
      >
        {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  )
}

/* ── form (needs useSearchParams → Suspense boundary) ───────────────────── */
function LoginForm() {
  const params       = useSearchParams()
  const justSignedUp = params.get("signup") === "1"
  const { status }   = useSession()

  useEffect(() => {
    if (status === "authenticated") window.location.replace("/home")
  }, [status])

  const [email,   setEmail]   = useState("")
  const [pwd,     setPwd]     = useState("")
  const [showPwd, setShowPwd] = useState(false)
  const [error,   setError]   = useState("")
  const [loading, setLoading] = useState(false)

  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError("")

    if (!email.trim()) return setError("Please enter your email address.")
    if (!emailOk)      return setError("Please enter a valid email address.")
    if (!pwd.trim())   return setError("Please enter your password.")

    setLoading(true)

    try {
      const result = await signIn("credentials", {
        email,
        password: pwd,
        redirect: false,
      })
      setLoading(false)
      if (!result || result.error) {
        setError("Incorrect email or password. Please try again.")
        return
      }
      window.location.replace("/home")
    } catch {
      setLoading(false)
      setError("Something went wrong. Please try again.")
    }
  }

  return (
    <>
      {justSignedUp && (
        <div className="rounded-lg bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 px-4 py-3 text-sm text-green-700 dark:text-green-400 flex items-center gap-2">
          <CheckCircle2 className="size-4 shrink-0" />
          Account created! Sign in below to get started.
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4" noValidate>

        {/* email */}
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

        {/* password */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="pwd">Password</Label>
            <Link href="/forgot-password" className="text-xs text-muted-foreground/70 hover:text-primary underline underline-offset-2 transition-colors">
              Forgot password?
            </Link>
          </div>
          <PwdInput id="pwd" value={pwd} onChange={setPwd}
            placeholder="••••••••" autoComplete="current-password"
            show={showPwd} onToggle={() => setShowPwd((v) => !v)} />
        </div>

        {/* error */}
        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 px-3 py-2.5 text-sm text-destructive flex items-start gap-2">
            <XCircle className="size-4 mt-0.5 shrink-0" /> {error}
          </div>
        )}

        <Button type="submit" className="w-full h-10 gap-2" disabled={loading}>
          {loading
            ? <><Loader2 className="size-4 animate-spin" /> Signing in…</>
            : <>Sign in <ArrowRight className="size-4" /></>}
        </Button>
      </form>
    </>
  )
}

/* ── page ────────────────────────────────────────────────────────────────── */
export default function LoginPage() {
  return (
    <div className="w-full max-w-md">

      {/* brand */}
      <div className="flex flex-col items-center gap-2 mb-8">
        <Link href="/" className="size-11 rounded-2xl bg-primary flex items-center justify-center shadow-lg hover:opacity-90 transition-opacity">
          <Sparkles className="size-5 text-primary-foreground" />
        </Link>
        <h1 className="text-2xl font-bold tracking-tight">Welcome back</h1>
        <p className="text-sm text-muted-foreground">Sign in to your Business Assistant account</p>
      </div>

      <div className="rounded-2xl border border-border bg-card shadow-sm p-7 space-y-5">
        <Suspense fallback={null}>
          <LoginForm />
        </Suspense>

        <div className="relative">
          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-border" /></div>
          <div className="relative flex justify-center">
            <span className="bg-card px-3 text-xs text-muted-foreground">New to Business Assistant?</span>
          </div>
        </div>

        <Link href="/signup" className={cn(buttonVariants({ variant: "outline" }), "w-full h-10")}>
          Create an account
        </Link>
      </div>

      <p className="text-center text-xs text-muted-foreground mt-6">
        Protected by industry-standard JWT authentication.
      </p>
    </div>
  )
}
