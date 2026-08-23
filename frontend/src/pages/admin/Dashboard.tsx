import { useQuery } from '@tanstack/react-query'
import { Users, BookOpen, GraduationCap, Scale } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { getUsers, getClasses } from '@/lib/api'

export default function AdminDashboard() {
  const { data: users } = useQuery({ queryKey: ['users'], queryFn: () => getUsers() })
  const { data: classes } = useQuery({ queryKey: ['classes'], queryFn: () => getClasses() })

  const lecturers = users?.filter((u) => u.role === 'lecturer').length ?? 0
  const students = users?.filter((u) => u.role === 'student').length ?? 0

  const stats = [
    { label: 'Students', value: students, icon: GraduationCap },
    { label: 'Lecturers', value: lecturers, icon: Users },
    { label: 'Classes', value: classes?.length ?? 0, icon: BookOpen },
  ]

  return (
    <div>
      <h1 className="mb-1">Admin dashboard</h1>
      <p className="mb-6 text-sm text-ink-3">System overview.</p>

      <div className="grid grid-cols-3 gap-4">
        {stats.map((s) => (
          <Card key={s.label}>
            <CardContent className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-[var(--radius-sm)] bg-accent-tint text-accent">
                <s.icon className="size-5" />
              </div>
              <div>
                <p className="font-mono-label text-ink-3">{s.label}</p>
                <p className="font-display text-2xl font-semibold text-ink">{s.value}</p>
              </div>
            </CardContent>
          </Card>
        ))}
        <Card className="col-span-3">
          <CardContent className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-[var(--radius-sm)] bg-warning-tint text-warning-ink">
              <Scale className="size-5" />
            </div>
            <div>
              <p className="font-mono-label text-ink-3">Bias evaluation</p>
              <p className="text-sm text-ink-2">
                Run and review recognition-accuracy disparity across skin type and gender in{' '}
                <a href="/admin/bias" className="text-accent underline">
                  Bias evaluation
                </a>
                .
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
