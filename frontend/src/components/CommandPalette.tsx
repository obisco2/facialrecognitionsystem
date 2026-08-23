import { useEffect, useRef, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface CommandItem {
  id: string
  label: string
  hint?: string
  to: string
}

export function CommandPalette({ items, open, onOpenChange }: {
  items: CommandItem[]
  open: boolean
  onOpenChange: (v: boolean) => void
}) {
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const filtered = useMemo(
    () => items.filter((i) => i.label.toLowerCase().includes(query.toLowerCase())),
    [items, query],
  )

  useEffect(() => {
    if (open) {
      setQuery('')
      setActive(0)
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [open])

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        onOpenChange(!open)
      }
      if (open && e.key === 'Escape') onOpenChange(false)
      if (open && e.key === 'ArrowDown') {
        e.preventDefault()
        setActive((a) => Math.min(a + 1, filtered.length - 1))
      }
      if (open && e.key === 'ArrowUp') {
        e.preventDefault()
        setActive((a) => Math.max(a - 1, 0))
      }
      if (open && e.key === 'Enter' && filtered[active]) {
        navigate(filtered[active].to)
        onOpenChange(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, filtered, active, onOpenChange, navigate])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-[oklch(24%_0.02_258/0.4)] pt-[15vh]"
      onClick={() => onOpenChange(false)}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg overflow-hidden rounded-[var(--radius-md)] border border-rule-2 bg-paper shadow-[0_8px_24px_oklch(24%_0.02_258/0.12)]"
      >
        <div className="flex items-center gap-2 border-b border-rule px-4">
          <Search className="size-4 text-ink-3" aria-hidden />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value)
              setActive(0)
            }}
            placeholder="Jump to…"
            className="h-12 w-full bg-transparent text-[0.9375rem] text-ink outline-none placeholder:text-ink-3"
          />
          <kbd className="font-mono-label rounded border border-rule px-1.5 py-0.5 text-ink-3">esc</kbd>
        </div>
        <ul className="max-h-80 overflow-y-auto py-2">
          {filtered.length === 0 && <li className="px-4 py-3 text-sm text-ink-3">No matches</li>}
          {filtered.map((item, i) => (
            <li key={item.id}>
              <button
                onClick={() => {
                  navigate(item.to)
                  onOpenChange(false)
                }}
                onMouseEnter={() => setActive(i)}
                className={cn(
                  'flex w-full items-center justify-between px-4 py-2.5 text-left text-sm text-ink-2',
                  i === active && 'bg-accent-tint text-accent',
                )}
              >
                <span>{item.label}</span>
                {item.hint && <span className="font-mono-label text-ink-3">{item.hint}</span>}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
