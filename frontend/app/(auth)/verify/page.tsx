"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { signOut, useSession } from "next-auth/react"
import Link from "next/link"
import { Sparkles, Loader2, ArrowRight, RotateCcw, Mail, LogOut } from "lucide-react"
import { Button } from "@/components/ui/button"

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"
const RESEND_SECONDS = 60

export default function VerifyPage() {
  const { data: session, update } = useSession()
  const [digits, setDigits]       = useState(["", "", "", "", "", ""])
  const [error, setError]         = useState("")
  const [loading, setLoading]     = useState(false)
  const [cooldown, setCooldown]   = useState(RESEND_SECONDS)
  const [resending, setResending] = useState(false)
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])

  // Countdown timer
  useEffect(() => {
    if (cooldown <= 0) return
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => clearTimeout(t)
  }, [cooldown])

  const focusAt = useCallback((i: number) => inputRefs.current[i]?.focus(), [])

  function handleChange(i: number, val: string) {
    if (!/^\d*$/.test(val)) return
    const next = [...digits]
    next[i] = val.slice(-1)
    setDigits(next)
    setError("")
    if (val && i < 5) focusAt(i + 1)
  }

  function handleKeyDown(i: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Backspace" && !digits[i] && i > 0) focusAt(i - 1)
    if (e.key === "ArrowLeft" && i > 0) focusAt(i - 1)
    if (e.key === "ArrowRight" && i < 5) focusAt(i + 1)
  }

  function handlePaste(e: React.ClipboardEvent) {
    e.preventDefault()
    const text = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6)
    if (!text) return
    const next = [...digits]
    for (let i = 0; i < 6; i++) next[i] = text[i] ?? ""
    setDigits(next)
    focusAt(Math.min(text.length, 5))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const code = digits.join("")
    if (code.length < 6) return setError("Please enter all 6 digits")
    setLoading(true)
    setError("")
    try {
      const r = await fetch(`${BACKEND}/api/auth/verify-email`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.accessToken}`,
        },
        body: JSON.stringify({ code }),
      })
      const data = await r.json().catch(() => ({}))
      if (!r.ok) {
        setError(data.detail ?? "Invalid code. Please try again.")
        setLoading(false)
        return
      }
      // Refresh session so middleware stops redirecting
      await update({ isVerified: true })
      window.location.replace("/home")
    } catch {
      setError("Something went wrong. Please try again.")
      setLoading(false)
    }
  }

  async function handleResend() {
    setResending(true)
    setError("")
    try {
      await fetch(`${BACKEND}/api/auth/send-verification`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session?.accessToken}` },
      })
    } finally {
      setResending(false)
      setCooldown(RESEND_SECONDS)
      setDigits(["", "", "", "", "", ""])
      focusAt(0)
    }
  }

  const email = session?.user?.email ?? ""
  const allFilled = digits.every((d) => d !== "")

  return (
    <div className="w-full max-w-md">

      {/* Brand */}
      <div className="flex flex-col items-center gap-2 mb-8">
        <div className="size-11 rounded-2xl bg-primary flex items-center justify-center shadow-lg">
          <Sparkles className="size-5 text-primary-foreground" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight">Check your inbox</h1>
        <p className="text-sm text-muted-foreground text-center max-w-xs">
          We sent a 6-digit code to{" "}
          {email && <span className="font-medium text-foreground">{email}</span>}
        </p>
      </div>

      <div className="rounded-2xl border border-border bg-card shadow-sm p-7 space-y-6">

        {/* Mail icon */}
        <div className="flex justify-center">
          <div className="size-16 rounded-2xl bg-primary/10 flex items-center justify-center">
            <Mail className="size-8 text-primary" />
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">

          {/* OTP inputs */}
          <div>
            <p className="text-xs text-muted-foreground text-center mb-3">Enter the 6-digit verification code</p>
            <div className="flex gap-2 justify-center" onPaste={handlePaste}>
              {digits.map((d, i) => (
                <input
                  key={i}
                  ref={(el) => { inputRefs.current[i] = el }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={d}
                  onChange={(e) => handleChange(i, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(i, e)}
                  onFocus={(e) => e.target.select()}
                  className={`w-11 h-13 text-center text-xl font-bold rounded-xl border-2 bg-transparent outline-none transition-all
                    ${d ? "border-primary text-primary" : "border-border"}
                    focus:border-primary focus:ring-2 focus:ring-primary/20
                    ${error ? "border-destructive" : ""}`}
                />
              ))}
            </div>
          </div>

          {error && (
            <p className="text-sm text-destructive text-center">{error}</p>
          )}

          <Button
            type="submit"
            className="w-full h-10 gap-2"
            disabled={loading || !allFilled}
          >
            {loading
              ? <><Loader2 className="size-4 animate-spin" /> Verifying…</>
              : <>Verify email <ArrowRight className="size-4" /></>}
          </Button>
        </form>

        {/* Resend */}
        <div className="text-center space-y-1">
          <p className="text-xs text-muted-foreground">Didn&apos;t receive the code?</p>
          {cooldown > 0 ? (
            <p className="text-xs text-muted-foreground">
              Resend in <span className="font-semibold tabular-nums text-foreground">{cooldown}s</span>
            </p>
          ) : (
            <button
              type="button"
              onClick={handleResend}
              disabled={resending}
              className="text-xs text-primary hover:text-primary/80 underline underline-offset-2 transition-colors flex items-center gap-1 mx-auto"
            >
              {resending
                ? <><Loader2 className="size-3 animate-spin" /> Sending…</>
                : <><RotateCcw className="size-3" /> Resend code</>}
            </button>
          )}
        </div>

        {/* Sign out */}
        <div className="border-t border-border pt-4 text-center">
          <button
            type="button"
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1.5 mx-auto transition-colors"
          >
            <LogOut className="size-3" /> Sign out and use a different account
          </button>
        </div>
      </div>

      <p className="text-center text-xs text-muted-foreground mt-6">
        The code expires in 15 minutes.{" "}
        <Link href="/login" className="text-primary underline underline-offset-2 hover:text-primary/80">
          Back to login
        </Link>
      </p>
    </div>
  )
}
