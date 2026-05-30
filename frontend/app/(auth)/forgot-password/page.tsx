"use client"

import { useState } from "react"
import Link from "next/link"
import { Sparkles, ArrowLeft, Loader2, CheckCircle2, XCircle, Mail } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"
import { buttonVariants } from "@/components/ui/button"

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState("")

  const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!emailOk) { setError("Please enter a valid email address."); return }
    setError("")
    setLoading(true)
    try {
      await fetch(`${BACKEND}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      })
      setSent(true)
    } catch {
      setError("Something went wrong. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full max-w-md">
      {/* Brand */}
      <div className="flex flex-col items-center gap-2 mb-8">
        <Link href="/" className="size-11 rounded-2xl bg-primary flex items-center justify-center shadow-lg hover:opacity-90 transition-opacity">
          <Sparkles className="size-5 text-primary-foreground" />
        </Link>
        <h1 className="text-2xl font-bold tracking-tight">Forgot your password?</h1>
        <p className="text-sm text-muted-foreground text-center">
          Enter your email and we&apos;ll send a reset link.
        </p>
      </div>

      <div className="rounded-2xl border border-border bg-card shadow-sm p-7 space-y-5">
        {sent ? (
          <div className="space-y-4 text-center">
            <div className="size-14 rounded-2xl bg-green-100 dark:bg-green-950/40 flex items-center justify-center mx-auto">
              <Mail className="size-7 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <p className="font-semibold">Check your inbox</p>
              <p className="text-sm text-muted-foreground mt-1">
                If <strong>{email}</strong> is registered, you&apos;ll receive a reset link shortly.
                <br />
                <span className="text-xs">(No email configured? Check the backend console for the link.)</span>
              </p>
            </div>
            <Link href="/login" className={cn(buttonVariants({ variant: "outline" }), "w-full gap-2")}>
              <ArrowLeft className="size-4" /> Back to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div className="space-y-1.5">
              <Label htmlFor="email">Email address</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                className="h-10"
              />
            </div>
            {error && (
              <div className="rounded-lg bg-destructive/10 border border-destructive/20 px-3 py-2.5 text-sm text-destructive flex items-start gap-2">
                <XCircle className="size-4 mt-0.5 shrink-0" /> {error}
              </div>
            )}
            <Button type="submit" className="w-full h-10 gap-2" disabled={loading}>
              {loading
                ? <><Loader2 className="size-4 animate-spin" /> Sending…</>
                : <><Mail className="size-4" /> Send reset link</>}
            </Button>
          </form>
        )}

        <div className="relative">
          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-border" /></div>
          <div className="relative flex justify-center">
            <span className="bg-card px-3 text-xs text-muted-foreground">Remember your password?</span>
          </div>
        </div>

        <Link href="/login" className={cn(buttonVariants({ variant: "outline" }), "w-full h-10 gap-2")}>
          <ArrowLeft className="size-4" /> Sign in instead
        </Link>
      </div>
    </div>
  )
}
