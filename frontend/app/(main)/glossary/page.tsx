"use client"

import { useCallback, useEffect, useState } from "react"
import { useSession } from "next-auth/react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

interface Entry {
  id: string
  term: string
  definition: string
}

interface FormState {
  term: string
  definition: string
}

const emptyForm: FormState = { term: "", definition: "" }

export default function GlossaryPage() {
  const { data: session } = useSession()
  const router = useRouter()
  const [entries, setEntries] = useState<Entry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const authHeader = { Authorization: `Bearer ${session?.accessToken}` }

  const fetchEntries = useCallback(async () => {
    if (!session?.accessToken) return
    setLoading(true)
    try {
      const r = await fetch(`${BACKEND}/api/glossary`, { headers: authHeader })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setEntries(await r.json())
    } catch (err) {
      setError(`Failed to load glossary: ${err instanceof Error ? err.message : err}`)
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  useEffect(() => { fetchEntries() }, [fetchEntries])

  function startEdit(entry: Entry) {
    setEditingId(entry.id)
    setForm({ term: entry.term, definition: entry.definition })
    setError(null)
  }

  function cancelEdit() {
    setEditingId(null)
    setForm(emptyForm)
    setError(null)
  }

  async function handleSave(e: { preventDefault(): void }) {
    e.preventDefault()
    const term = form.term.trim()
    const definition = form.definition.trim()
    if (!term || !definition) {
      setError("Both term and definition are required.")
      return
    }
    setSaving(true)
    setError(null)
    try {
      const url = editingId
        ? `${BACKEND}/api/glossary/${editingId}`
        : `${BACKEND}/api/glossary`
      const method = editingId ? "PUT" : "POST"
      const r = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json", ...authHeader },
        body: JSON.stringify({ term, definition }),
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        throw new Error(d?.detail ?? `HTTP ${r.status}`)
      }
      setForm(emptyForm)
      setEditingId(null)
      await fetchEntries()
    } catch (err) {
      setError(`Save failed: ${err instanceof Error ? err.message : err}`)
    } finally {
      setSaving(false)
    }
  }

  async function handleDelete(id: string, term: string) {
    if (!confirm(`Delete "${term}"?`)) return
    setError(null)
    try {
      const r = await fetch(`${BACKEND}/api/glossary/${id}`, {
        method: "DELETE",
        headers: authHeader,
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      await fetchEntries()
      if (editingId === id) cancelEdit()
    } catch (err) {
      setError(`Delete failed: ${err instanceof Error ? err.message : err}`)
    }
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Business Glossary</h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => router.back()}>← Back</Button>
        </div>
      </header>

      <p className="text-sm text-muted-foreground">
        Terms defined here are automatically injected into SQL generation prompts so the AI uses
        your business definitions when querying data.
      </p>

      {/* Add / Edit form */}
      <form onSubmit={handleSave} className="border rounded-xl p-4 space-y-3 bg-card">
        <h2 className="font-medium text-sm">{editingId ? "Edit entry" : "Add new term"}</h2>
        <div className="flex gap-2 flex-col sm:flex-row">
          <Input
            placeholder="Term (e.g. GMV)"
            value={form.term}
            onChange={(e) => setForm((p) => ({ ...p, term: e.target.value }))}
            className="sm:w-48 shrink-0"
          />
          <Input
            placeholder="Definition"
            value={form.definition}
            onChange={(e) => setForm((p) => ({ ...p, definition: e.target.value }))}
            className="flex-1"
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <div className="flex gap-2">
          <Button type="submit" size="sm" disabled={saving}>
            {saving ? "Saving…" : editingId ? "Save changes" : "Add term"}
          </Button>
          {editingId && (
            <Button type="button" size="sm" variant="ghost" onClick={cancelEdit}>
              Cancel
            </Button>
          )}
        </div>
      </form>

      {/* Table */}
      {loading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-8">
          No entries yet. Add your first business term above.
        </p>
      ) : (
        <div className="border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted text-muted-foreground">
              <tr>
                <th className="text-left px-4 py-2 font-medium w-40">Term</th>
                <th className="text-left px-4 py-2 font-medium">Definition</th>
                <th className="px-4 py-2 w-24" />
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id} className="border-t hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-2 font-medium">{entry.term}</td>
                  <td className="px-4 py-2 text-muted-foreground">{entry.definition}</td>
                  <td className="px-4 py-2">
                    <div className="flex gap-1 justify-end">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => startEdit(entry)}
                      >
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 text-xs text-red-600 hover:text-red-700"
                        onClick={() => handleDelete(entry.id, entry.term)}
                      >
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
