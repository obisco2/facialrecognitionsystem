import { useState, useCallback, useEffect } from 'react'
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { ScanFace, Search, LogOut, LayoutDashboard, BookOpen, Users, Scale, Settings, Video, History, Menu, X } from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { NAV_BY_ROLE } from '@/lib/nav'
import { CommandPalette } from './CommandPalette'
import { ToastContainer } from './ui/toast'
import { cn } from '@/lib/utils'

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  LayoutDashboard,
  BookOpen,
  Users,
  Scale,
  Settings,
  Video,
  History,
  ScanFace,
}

export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  // Lock body scroll when mobile sidebar is open
  useEffect(() => {
    if (sidebarOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [sidebarOpen])

  const closeSidebar = useCallback(() => setSidebarOpen(false), [])

  if (!user) return null
  const items = NAV_BY_ROLE[user.role]

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-[oklch(24%_0.02_258/0.4)] md:hidden"
          onClick={closeSidebar}
          aria-hidden="true"
        />
      )}

      {/* Sidebar — permanent on md+, drawer on mobile */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-60 flex-col border-r border-rule bg-paper-2 transition-transform duration-200 ease-out md:static md:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-rule px-4">
          <div className="flex items-center gap-2">
            <ScanFace className="size-5 text-accent" aria-hidden />
            <span className="font-display text-base font-semibold text-ink">
              Attend<span className="text-accent">IQ</span>
            </span>
          </div>
          <button
            onClick={closeSidebar}
            className="rounded p-1 text-ink-3 hover:text-ink md:hidden"
            aria-label="Close menu"
          >
            <X className="size-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto p-2">
          {items.map((item) => {
            const Icon = ICONS[item.icon]
            return (
              <NavLink
                key={item.id}
                to={item.to}
                end
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2.5 rounded-[var(--radius-sm)] px-3 py-2.5 text-sm text-ink-2 transition-colors md:py-2',
                    isActive ? 'bg-accent-tint text-accent font-medium' : 'hover:bg-paper-3',
                  )
                }
              >
                <Icon className="size-4" />
                {item.label}
              </NavLink>
            )
          })}
        </nav>

        <div className="shrink-0 border-t border-rule p-3">
          <div className="mb-2 flex items-center gap-2">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-paper-3 font-mono-label text-ink-2">
              {user.full_name?.[0] ?? '?'}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-ink">
                {user.title ? `${user.title} ` : ''}{user.full_name}
              </p>
              <p className="font-mono-label text-ink-3">{user.role}</p>
            </div>
          </div>
          <button
            onClick={() => {
              logout()
              navigate('/login')
            }}
            className="flex w-full items-center gap-2 rounded-[var(--radius-sm)] px-3 py-1.5 text-sm text-ink-3 hover:bg-paper-3 hover:text-danger"
          >
            <LogOut className="size-4" /> Log out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-rule px-4 md:px-5">
          <button
            onClick={() => setSidebarOpen(true)}
            className="rounded p-1.5 text-ink-3 hover:bg-paper-3 hover:text-ink md:hidden"
            aria-label="Open menu"
          >
            <Menu className="size-5" />
          </button>
          <div className="flex-1" />
          <button
            onClick={() => setPaletteOpen(true)}
            className="flex items-center gap-2 rounded-[var(--radius-sm)] border border-rule-2 px-3 py-1.5 text-sm text-ink-3 hover:border-accent hover:text-accent"
          >
            <Search className="size-3.5" />
            <span className="hidden sm:inline">Jump to…</span>
            <kbd className="font-mono-label rounded border border-rule px-1 py-0.5">⌘K</kbd>
          </button>
        </header>
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <Outlet />
        </main>
      </div>

      <CommandPalette
        items={items.map((i) => ({ id: i.id, label: i.label, to: i.to }))}
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
      />
      <ToastContainer />
    </div>
  )
}
