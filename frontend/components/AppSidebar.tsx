"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useSession, signOut } from "next-auth/react"
import {
  Sparkles, Home, MessageSquare, Database, BookOpen,
  BarChart2, FileText, Repeat2, Cloud, Crown,
  ChevronLeft, ChevronRight, LogOut, User, FlaskConical,
} from "lucide-react"
import { ThemeToggle } from "@/components/ThemeToggle"

const NAV = [
  { href: "/home",          icon: Home,          label: "Home"          },
  { href: "/chat",          icon: MessageSquare, label: "Chat"          },
  { href: "/datasets",      icon: Database,      label: "Datasets"      },
  { href: "/analysis",      icon: FlaskConical,  label: "Analysis"      },
  { href: "/glossary",      icon: BookOpen,      label: "Glossary"      },
  { href: "/saved-queries", icon: FileText,      label: "Saved Queries" },
  { href: "/routines",      icon: Repeat2,       label: "Routines"      },
  { href: "/catalog",       icon: BarChart2,     label: "Catalog"       },
  { href: "/athena",        icon: Cloud,         label: "Athena"        },
]

const STORAGE_KEY = "sidebar_collapsed"

export function AppSidebar() {
  const pathname = usePathname()
  const { data: session } = useSession()
  const [collapsed, setCollapsed] = useState(false)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved !== null) setCollapsed(saved === "true")
  }, [])

  function toggle() {
    setCollapsed((c) => {
      const next = !c
      localStorage.setItem(STORAGE_KEY, String(next))
      return next
    })
  }

  if (!mounted) return <div className={collapsed ? "w-14" : "w-60"} />

  const isActive = (href: string) =>
    href === "/home" ? pathname === "/home" : pathname.startsWith(href)

  return (
    <aside
      className={`
        flex flex-col h-screen bg-card border-r border-border shrink-0 transition-all duration-200
        ${collapsed ? "w-14" : "w-60"}
      `}
    >
      {/* Logo */}
      <div className={`flex items-center h-14 px-3 border-b border-border shrink-0 ${collapsed ? "justify-center" : "gap-2.5"}`}>
        <div className="size-7 rounded-lg bg-primary flex items-center justify-center shrink-0">
          <Sparkles className="size-3.5 text-primary-foreground" />
        </div>
        {!collapsed && (
          <span className="font-semibold text-sm truncate">Business Assistant</span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-2 space-y-0.5 px-1.5">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = isActive(href)
          return (
            <Link
              key={href}
              href={href}
              title={collapsed ? label : undefined}
              className={`
                flex items-center gap-3 rounded-lg px-2 py-2 text-sm font-medium transition-colors
                ${collapsed ? "justify-center" : ""}
                ${active
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"}
              `}
            >
              <Icon className="size-4 shrink-0" />
              {!collapsed && <span className="truncate">{label}</span>}
            </Link>
          )
        })}

        {session?.isAdmin && (
          <Link
            href="/admin"
            title={collapsed ? "Admin Panel" : undefined}
            className={`
              flex items-center gap-3 rounded-lg px-2 py-2 text-sm font-medium transition-colors
              ${collapsed ? "justify-center" : ""}
              ${pathname.startsWith("/admin")
                ? "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400"
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"}
            `}
          >
            <Crown className="size-4 shrink-0" />
            {!collapsed && <span className="truncate">Admin Panel</span>}
          </Link>
        )}
      </nav>

      {/* Bottom */}
      <div className="border-t border-border p-1.5 space-y-0.5 shrink-0">
        <Link
          href="/profile"
          title={collapsed ? "Profile" : undefined}
          className={`
            flex items-center gap-3 rounded-lg px-2 py-2 text-sm font-medium transition-colors
            ${collapsed ? "justify-center" : ""}
            ${pathname.startsWith("/profile")
              ? "bg-primary/10 text-primary"
              : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"}
          `}
        >
          <User className="size-4 shrink-0" />
          {!collapsed && (
            <span className="truncate text-xs">
              {session?.user?.name ?? session?.user?.email ?? "Profile"}
            </span>
          )}
        </Link>

        <div className={`flex items-center ${collapsed ? "justify-center" : "justify-between"} px-2 py-1`}>
          {!collapsed && <ThemeToggle />}
          {collapsed && <ThemeToggle />}
          {!collapsed && (
            <button
              onClick={() => signOut({ callbackUrl: "/login" })}
              title="Sign out"
              className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
            >
              <LogOut className="size-3.5" />
            </button>
          )}
        </div>

        {collapsed && (
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            title="Sign out"
            className="flex items-center justify-center w-full py-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
          >
            <LogOut className="size-4" />
          </button>
        )}

        {/* Collapse toggle */}
        <button
          onClick={toggle}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={`
            flex items-center rounded-lg px-2 py-2 text-xs text-muted-foreground
            hover:bg-muted/60 hover:text-foreground transition-colors w-full
            ${collapsed ? "justify-center" : "gap-2"}
          `}
        >
          {collapsed ? <ChevronRight className="size-4" /> : <><ChevronLeft className="size-4" /><span>Collapse</span></>}
        </button>
      </div>
    </aside>
  )
}
