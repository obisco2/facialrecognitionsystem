import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Video, BookOpen, ArrowRight } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { getClasses } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export default function LecturerDashboard() {
  const { user } = useAuth()
  const { data: classes, isLoading } = useQuery({
    queryKey: ['classes', user?.id],
    queryFn: () => getClasses(user?.id),
    enabled: !!user,
  })

  return (
    <div>
      <h1 className="mb-1">Dashboard</h1>
      <p className="mb-6 text-sm text-ink-3">Welcome back, {user?.full_name}.</p>

      <div className="mb-6 grid grid-cols-2 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-[var(--radius-sm)] bg-accent-tint text-accent">
              <BookOpen className="size-5" />
            </div>
            <div>
              <p className="font-mono-label text-ink-3">Your classes</p>
              <p className="font-display text-xl font-semibold text-ink sm:text-2xl">{classes?.length ?? '—'}</p>
            </div>
          </CardContent>
        </Card>
        <Link to="/lecturer/live">
          <Card className="h-full transition-colors hover:border-accent">
            <CardContent className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex size-10 items-center justify-center rounded-[var(--radius-sm)] bg-graphite text-graphite-ink">
                  <Video className="size-5" />
                </div>
                <div>
                  <p className="font-mono-label text-ink-3">Quick action</p>
                  <p className="font-display text-base font-semibold text-ink">Start live session</p>
                </div>
              </div>
              <ArrowRight className="size-4 text-ink-3" />
            </CardContent>
          </Card>
        </Link>
      </div>

      <Card>
        <CardContent>
          <h2 className="mb-3 font-display text-base font-semibold text-ink">Your classes</h2>
          {isLoading && <p className="text-sm text-ink-3">Loading…</p>}
          {classes?.length === 0 && <p className="text-sm text-ink-3">No classes assigned yet.</p>}
          <ul className="divide-y divide-rule">
            {classes?.map((c) => (
              <li key={c.id} className="flex items-center justify-between py-2.5">
                <div>
                  <p className="text-sm font-medium text-ink">{c.name}</p>
                  <p className="font-mono-label text-ink-3">{c.code}</p>
                </div>
                {c.room && <span className="text-sm text-ink-3">{c.room}</span>}
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}
