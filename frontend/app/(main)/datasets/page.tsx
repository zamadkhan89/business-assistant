"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useSession } from "next-auth/react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { BookOpen } from "lucide-react"
import { Button } from "@/components/ui/button"

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000"

interface Dataset {
  table_name: string
  row_count: number
  columns: { column: string; type: string }[]
}

export default function DatasetsPage() {
  const { data: session } = useSession()
  const router = useRouter()
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [deletingTable, setDeletingTable] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const authHeader = { Authorization: `Bearer ${session?.accessToken}` }

  const fetchDatasets = useCallback(async () => {
    try {
      const r = await fetch(`${BACKEND}/api/datasets`, { headers: authHeader })
      if (r.ok) setDatasets(await r.json())
    } catch {
      setError("Could not load datasets")
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.accessToken])

  useEffect(() => { fetchDatasets() }, [fetchDatasets])

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError(null)
    setSuccess(null)
    try {
      const form = new FormData()
      form.append("file", file)
      const r = await fetch(`${BACKEND}/api/datasets/upload`, {
        method: "POST",
        headers: authHeader,
        body: form,
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        throw new Error(d?.detail ?? `HTTP ${r.status}`)
      }
      const meta = await r.json()
      setSuccess(`Uploaded "${file.name}" to table "${meta.table_name}" (${meta.row_count.toLocaleString()} rows)`)
      await fetchDatasets()
    } catch (err) {
      setError(`Upload failed: ${err instanceof Error ? err.message : err}`)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

  async function handleDelete(tableName: string) {
    if (!confirm(`Delete table "${tableName}"? This cannot be undone.`)) return
    setDeletingTable(tableName)
    setError(null)
    setSuccess(null)
    try {
      const r = await fetch(`${BACKEND}/api/datasets/${tableName}`, {
        method: "DELETE",
        headers: authHeader,
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        throw new Error(d?.detail ?? `HTTP ${r.status}`)
      }
      setSuccess(`Deleted table "${tableName}"`)
      await fetchDatasets()
    } catch (err) {
      setError(`Delete failed: ${err instanceof Error ? err.message : err}`)
    } finally {
      setDeletingTable(null)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" className="text-xs h-8" onClick={() => router.back()}>← Back</Button>
          <h1 className="font-semibold text-base">Uploaded Datasets</h1>
        </div>
        <div>
          <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleUpload} />
          <Button size="sm" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
            {uploading ? "Uploading..." : "Upload CSV"}
          </Button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-6 space-y-4">
        {error && (
          <div className="rounded-lg px-4 py-3 bg-red-50 dark:bg-red-950 border border-red-300 text-sm text-red-700 dark:text-red-300">
            {error}
          </div>
        )}
        {success && (
          <div className="rounded-lg px-4 py-3 bg-green-50 dark:bg-green-950 border border-green-300 text-sm text-green-700 dark:text-green-300">
            {success}
          </div>
        )}

        {loading && (
          <p className="text-sm text-muted-foreground text-center py-12">Loading...</p>
        )}

        {!loading && datasets.length === 0 && (
          <div className="text-center py-16 space-y-4">
            <div className="size-14 rounded-2xl bg-muted flex items-center justify-center mx-auto">
              <BookOpen className="size-7 text-muted-foreground/50" />
            </div>
            <div>
              <p className="font-semibold">No datasets yet</p>
              <p className="text-sm text-muted-foreground mt-1">
                Upload a CSV file to start analysing your data with AI.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2">
              <Button size="sm" onClick={() => fileInputRef.current?.click()}>
                Upload your first CSV
              </Button>
              <Link href="/athena">
                <Button size="sm" variant="outline">Connect Athena</Button>
              </Link>
            </div>
          </div>
        )}

        {datasets.map((ds) => (
          <div key={ds.table_name} className="border rounded-xl p-4 space-y-3 bg-card">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-mono text-sm font-semibold">{ds.table_name}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {ds.row_count.toLocaleString()} rows · {ds.columns.length} columns
                </p>
              </div>
              <div className="flex gap-2">
                <Link href="/catalog">
                  <Button size="sm" variant="outline" className="gap-1.5 text-xs">
                    <BookOpen className="size-3.5" /> Catalog
                  </Button>
                </Link>
                <Button
                  size="sm"
                  variant="destructive"
                  disabled={deletingTable === ds.table_name}
                  onClick={() => handleDelete(ds.table_name)}
                >
                  {deletingTable === ds.table_name ? "Deleting..." : "Delete"}
                </Button>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {ds.columns.map((col) => (
                <span key={col.column} className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-muted text-xs font-mono">
                  {col.column}
                  <span className="text-muted-foreground opacity-60">{col.type}</span>
                </span>
              ))}
            </div>
          </div>
        ))}
      </main>
    </div>
  )
}
