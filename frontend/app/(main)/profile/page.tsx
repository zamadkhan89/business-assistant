"use client"

import { useEffect, useState } from "react"
import { signOut, useSession } from "next-auth/react"
import { CheckCircle2, Loader2, LogOut, Sparkles, User, XCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

interface Profile { id: string; email: string; name: string | null }

export default function ProfilePage() {
  const { data: session, update: updateSession } = useSession()
  const authHeader = { Authorization: `Bearer ${session?.accessToken}` }

  const [profile, setProfile] = useState<Profile | null>(null)
  const [name, setName] = useState("")
  const [saving, setSaving] = useState(false)
  const [profileMsg, setProfileMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const [curPwd, setCurPwd] = useState("")
  const [newPwd, setNewPwd] = useState("")
  const [confirmPwd, setConfirmPwd] = useState("")
  const [changingPwd, setChangingPwd] = useState(false)
  const [pwdMsg, setPwdMsg] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    if (!session?.accessToken) return
    fetch(`${BACKEND}/api/auth/profile`, { headers: authHeader })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d) { setProfile(d); setName(d.name ?? "") }
      })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setProfileMsg(null)
    try {
      const r = await fetch(`${BACKEND}/api/auth/profile`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({ name, email: profile?.email }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
      setProfile(d)
      await updateSession()
      setProfileMsg({ ok: true, text: "Profile updated successfully." })
    } catch (err) {
      setProfileMsg({ ok: false, text: err instanceof Error ? err.message : "Update failed" })
    } finally {
      setSaving(false)
    }
  }

  async function handlePwdChange(e: React.FormEvent) {
    e.preventDefault()
    setPwdMsg(null)
    if (newPwd.length < 8)       { setPwdMsg({ ok: false, text: "New password must be at least 8 characters." }); return }
    if (!/[A-Z]/.test(newPwd))   { setPwdMsg({ ok: false, text: "New password must contain an uppercase letter." }); return }
    if (!/[0-9]/.test(newPwd))   { setPwdMsg({ ok: false, text: "New password must contain a number." }); return }
    if (!/[^A-Za-z0-9]/.test(newPwd)) { setPwdMsg({ ok: false, text: "New password must contain a symbol." }); return }
    if (newPwd !== confirmPwd)   { setPwdMsg({ ok: false, text: "Passwords do not match." }); return }
    setChangingPwd(true)
    try {
      const r = await fetch(`${BACKEND}/api/auth/password`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({ current_password: curPwd, new_password: newPwd }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail ?? `HTTP ${r.status}`)
      setCurPwd(""); setNewPwd(""); setConfirmPwd("")
      setPwdMsg({ ok: true, text: "Password changed successfully." })
    } catch (err) {
      setPwdMsg({ ok: false, text: err instanceof Error ? err.message : "Failed to change password" })
    } finally {
      setChangingPwd(false)
    }
  }

  const initials = (name || profile?.email || "").slice(0, 2).toUpperCase()

  function PwdRule({ ok, text }: { ok: boolean; text: string }) {
    return (
      <span className={`flex items-center gap-1 text-[11px] ${ok ? "text-green-600" : "text-muted-foreground"}`}>
        {ok ? <CheckCircle2 className="size-3" /> : <XCircle className="size-3 opacity-40" />}
        {text}
      </span>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Nav */}
      <nav className="sticky top-0 z-40 border-b border-border/60 bg-background/80 backdrop-blur-md">
        <div className="max-w-3xl mx-auto flex items-center px-6 py-3">
          <div className="flex items-center gap-2.5">
            <div className="size-7 rounded-lg bg-primary flex items-center justify-center">
              <Sparkles className="size-4 text-primary-foreground" />
            </div>
            <span className="font-bold tracking-tight">Business Assistant</span>
          </div>
        </div>
      </nav>

      <main className="max-w-3xl mx-auto px-6 py-10 space-y-8">
        {/* Avatar + heading */}
        <div className="flex items-center gap-5">
          <div className="size-16 rounded-2xl bg-primary flex items-center justify-center text-primary-foreground text-xl font-bold shadow-md">
            {profile ? initials : <User className="size-7" />}
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{name || "Your Profile"}</h1>
            <p className="text-sm text-muted-foreground">{profile?.email}</p>
          </div>
        </div>

        {/* Profile form — name only, email is read-only */}
        <section className="rounded-2xl border border-border bg-card p-6 space-y-5">
          <h2 className="font-semibold text-base">Personal information</h2>
          <form onSubmit={handleProfileSave} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="name">Full name</Label>
              <Input id="name" value={name} onChange={e => setName(e.target.value)}
                placeholder="Alex Johnson" className="h-10" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="email">Email address</Label>
              <Input
                id="email"
                type="email"
                value={profile?.email ?? ""}
                readOnly
                disabled
                className="h-10 opacity-60 cursor-not-allowed select-none"
              />
              <p className="text-[11px] text-muted-foreground">Email cannot be changed after sign-up.</p>
            </div>
            {profileMsg && (
              <div className={`rounded-lg px-3 py-2.5 text-sm flex items-center gap-2 ${
                profileMsg.ok
                  ? "bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400"
                  : "bg-destructive/10 border border-destructive/20 text-destructive"
              }`}>
                {profileMsg.ok ? <CheckCircle2 className="size-4 shrink-0" /> : <XCircle className="size-4 shrink-0" />}
                {profileMsg.text}
              </div>
            )}
            <Button type="submit" disabled={saving} className="gap-2">
              {saving ? <><Loader2 className="size-4 animate-spin" /> Saving…</> : "Save changes"}
            </Button>
          </form>
        </section>

        {/* Password form */}
        <section className="rounded-2xl border border-border bg-card p-6 space-y-5">
          <h2 className="font-semibold text-base">Change password</h2>
          <form onSubmit={handlePwdChange} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="curPwd">Current password</Label>
              <Input id="curPwd" type="password" value={curPwd} onChange={e => setCurPwd(e.target.value)}
                placeholder="••••••••" autoComplete="current-password" className="h-10" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="newPwd">New password</Label>
              <Input id="newPwd" type="password" value={newPwd} onChange={e => setNewPwd(e.target.value)}
                placeholder="Min. 8 characters" autoComplete="new-password" className="h-10" />
              {newPwd && (
                <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
                  <PwdRule ok={newPwd.length >= 8}           text="8+ chars" />
                  <PwdRule ok={/[A-Z]/.test(newPwd)}         text="Uppercase" />
                  <PwdRule ok={/[0-9]/.test(newPwd)}         text="Number" />
                  <PwdRule ok={/[^A-Za-z0-9]/.test(newPwd)} text="Symbol" />
                </div>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirmPwd">Confirm new password</Label>
              <Input id="confirmPwd" type="password" value={confirmPwd} onChange={e => setConfirmPwd(e.target.value)}
                placeholder="Repeat new password" autoComplete="new-password" className="h-10" />
              {confirmPwd && (
                <p className={`text-[11px] flex items-center gap-1 ${newPwd === confirmPwd ? "text-green-600" : "text-destructive"}`}>
                  {newPwd === confirmPwd
                    ? <><CheckCircle2 className="size-3" /> Passwords match</>
                    : <><XCircle className="size-3" /> Passwords do not match</>}
                </p>
              )}
            </div>
            {pwdMsg && (
              <div className={`rounded-lg px-3 py-2.5 text-sm flex items-center gap-2 ${
                pwdMsg.ok
                  ? "bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400"
                  : "bg-destructive/10 border border-destructive/20 text-destructive"
              }`}>
                {pwdMsg.ok ? <CheckCircle2 className="size-4 shrink-0" /> : <XCircle className="size-4 shrink-0" />}
                {pwdMsg.text}
              </div>
            )}
            <Button type="submit" disabled={changingPwd || !curPwd || !newPwd || !confirmPwd} variant="outline" className="gap-2">
              {changingPwd ? <><Loader2 className="size-4 animate-spin" /> Changing…</> : "Change password"}
            </Button>
          </form>
        </section>

        {/* Danger zone */}
        <section className="rounded-2xl border border-destructive/20 bg-card p-6 space-y-3">
          <h2 className="font-semibold text-base text-destructive">Sign out</h2>
          <p className="text-sm text-muted-foreground">You will be redirected to the login page.</p>
          <Button variant="destructive" className="gap-2" onClick={() => { if (confirm("Sign out?")) signOut({ callbackUrl: "/login" }) }}>
            <LogOut className="size-4" /> Sign out
          </Button>
        </section>
      </main>
    </div>
  )
}
