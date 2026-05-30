"use client"

import { useEffect } from "react"
import { SessionProvider, signOut } from "next-auth/react"
import { ThemeProvider } from "@/components/ThemeProvider"

function GlobalAuthHandler() {
  useEffect(() => {
    const original = window.fetch
    window.fetch = async (...args) => {
      let res: Response
      try {
        res = await original(...args)
      } catch (err) {
        throw err  // network-level failure (backend down, CORS, etc.) — pass through unchanged
      }
      if (res.status === 401) {
        const url = typeof args[0] === "string" ? args[0] : args[0] instanceof URL ? args[0].href : (args[0] as Request).url
        // Only trigger sign-out for backend API calls, not NextAuth's own /api/auth/* routes
        if (!url.includes("/api/auth/")) {
          signOut({ callbackUrl: "/login" })
        }
      }
      return res
    }
    return () => { window.fetch = original }
  }, [])
  return null
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider refetchInterval={0} refetchOnWindowFocus={false}>
      <GlobalAuthHandler />
      <ThemeProvider>{children}</ThemeProvider>
    </SessionProvider>
  )
}
