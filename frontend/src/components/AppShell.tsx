import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { ScanFace, Search, LogOut, LayoutDashboard, BookOpen, Users, Scale, Settings, Video, History } from 'lucide-react'
import { useAuth } from '@/lib/auth'
import { NAV_BY_ROLE } from '@/lib/nav'
import { CommandPalette } from './CommandPalette'
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
  const [paletteOpen, setPaletteOpen] = useState(false)

  if (!user) return null
  const items = NAV_BY_ROLE[user.role]

  return (
    <div className="flex h-screen">
      <aside className="flex w-56 shrink-0 flex-col border-r border-rule bg-paper-2/40">
        <div className="flex h-14 items-center gap-2 border-b border-rule px-4">
          <ScanFace className="size-5 text-accent" aria-hidden />
          <span className="font-display text-base font-semibold text-ink">
            Attend<span className="text-accent">IQ</span>
          </span>
        </div>
        <nav className="flex-1 space-y-0.5 p-2">
          {items.map((item) => {
            const Icon = ICONS[item.icon]
            return (
              <NavLink
                key={item.id}
                to={item.to}
                end
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2.5 rounded-[var(--radius-sm)] px-3 py-2 text-sm text-ink-2 transition-colors',
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
        <div className="border-t border-rule p-3">
          <div className="mb-2 flex items-center gap-2">
            <div className="flex size-8 items-center justify-center rounded-full bg-paper-3 font-mono-label text-ink-2">
              {user.full_name?.[0] ?? user.username[0]}
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-ink">{user.full_name || user.username}</p>
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

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-end border-b border-rule px-5">
          <button
            onClick={() => setPaletteOpen(true)}
            className="flex items-center gap-2 rounded-[var(--radius-sm)] border border-rule-2 px-3 py-1.5 text-sm text-ink-3 hover:border-accent hover:text-accent"
          >
            <Search className="size-3.5" />
            Jump to…
            <kbd className="font-mono-label rounded border border-rule px-1 py-0.5">⌘K</kbd>
          </button>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>

      <CommandPalette
        items={items.map((i) => ({ id: i.id, label: i.label, to: i.to }))}
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
      />
    </div>
  )
}
