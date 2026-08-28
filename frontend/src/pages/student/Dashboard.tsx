import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CheckCircle2, ScanFace, AlertTriangle, BookOpen } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, Thead, Tbody, Tr, Td } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { getStudentAttendance, getStudentSummary } from '@/lib/api'
import type { AttendanceRecord } from '@/lib/api'
import { useAuth } from '@/lib/auth'

function greeting() {
  const h = new Date().getHours()
  if (h < 12) return 'Good morning'
  if (h < 17) return 'Good afternoon'
  return 'Good evening'
}

function todayFormatted() {
  return new Date().toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

function classStatus(percent: number) {
  if (percent >= 75) return { label: 'OK', variant: 'success' as const }
  if (percent >= 60) return { label: 'LOW', variant: 'warning' as const }
  return { label: 'CRITICAL', variant: 'danger' as const }
}

export default function StudentDashboard() {
  const { user } = useAuth()

  const { data: records } = useQuery({
    queryKey: ['student-attendance', user?.full_name],
    queryFn: () => getStudentAttendance(user!.full_name),
    enabled: !!user,
  })

  const { data: summary } = useQuery({
    queryKey: ['student-summary', user?.id],
    queryFn: () => getStudentSummary(user!.id),
    enabled: !!user,
  })

  const distinctClasses = useMemo(() => {
    if (!records) return 0
    const names = new Set((records as AttendanceRecord[]).map((r) => (r as unknown as { class_name: string }).class_name))
    return names.size
  }, [records])

  const attendanceRate = useMemo(() => {
    if (!summary || summary.length === 0) return null
    const totalPresent = summary.reduce((s, c) => s + c.sessions_present, 0)
    const totalSessions = summary.reduce((s, c) => s + c.total_sessions, 0)
    if (totalSessions === 0) return 0
    return Math.round((totalPresent / totalSessions) * 100)
  }, [summary])

  return (
    <div>
      {/* Greeting */}
      <div className="mb-6 flex items-center gap-3 sm:gap-4">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-accent-tint font-display text-base font-semibold text-accent sm:size-12 sm:text-lg">
          {user?.full_name?.[0] ?? '?'}
        </div>
        <div>
          <h1 className="text-lg sm:text-xl">
            {greeting()}, {user?.full_name?.split(' ')[0]}
          </h1>
          <p className="text-xs text-ink-3 sm:text-sm">
            {user?.student_id ? `Matric: ${user.student_id}  ·  ` : ''}
            {todayFormatted()}
          </p>
        </div>
      </div>

      {/* Enrollment warning */}
      {!user?.face_enrolled && (
        <Link to="/student/enrollment">
          <Card className="mb-6 border-warning-ink/30 bg-warning-tint">
            <CardContent className="flex items-center gap-3">
              <ScanFace className="size-5 text-warning-ink" />
              <p className="text-sm text-warning-ink">
                Your face isn't enrolled yet — recognition can't mark you present. <strong>Enroll now.</strong>
              </p>
            </CardContent>
          </Card>
        </Link>
      )}

      {/* Low attendance warning */}
      {attendanceRate !== null && attendanceRate < 75 && (
        <Card className="mb-6 border-danger/30 bg-danger-tint">
          <CardContent className="flex items-center gap-3">
            <AlertTriangle className="size-5 text-danger" />
            <p className="text-sm text-danger">
              Your overall attendance is {attendanceRate}%. Keep attending to stay above 75%.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Stat cards */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Card>
          <CardContent className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-[var(--radius-sm)] bg-success-tint text-success-ink">
              <CheckCircle2 className="size-5" />
            </div>
            <div>
              <p className="font-mono-label text-ink-3">Sessions attended</p>
              <p className="font-display text-xl font-semibold text-ink sm:text-2xl">{records?.length ?? '—'}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-[var(--radius-sm)] bg-accent-tint text-accent">
              <BookOpen className="size-5" />
            </div>
            <div>
              <p className="font-mono-label text-ink-3">Classes tracked</p>
              <p className="font-display text-xl font-semibold text-ink sm:text-2xl">{distinctClasses || '—'}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-3">
            <div
              className={`flex size-10 items-center justify-center rounded-[var(--radius-sm)] ${
                attendanceRate === null
                  ? 'bg-paper-2 text-ink-3'
                  : attendanceRate >= 75
                    ? 'bg-success-tint text-success-ink'
                    : 'bg-warning-tint text-warning-ink'
              }`}
            >
              <span className="font-display text-sm font-semibold">{attendanceRate !== null ? `${attendanceRate}%` : '—'}</span>
            </div>
            <div>
              <p className="font-mono-label text-ink-3">Attendance rate</p>
              <p className="font-display text-xl font-semibold text-ink sm:text-2xl">{attendanceRate !== null ? `${attendanceRate}%` : '—'}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-[var(--radius-sm)] bg-accent-tint text-accent">
              <ScanFace className="size-5" />
            </div>
            <div>
              <p className="font-mono-label text-ink-3">Face enrollment</p>
              <Badge variant={user?.face_enrolled ? 'success' : 'warning'} dot>
                {user?.face_enrolled ? 'enrolled' : 'pending'}
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Per-class breakdown */}
      {summary && summary.length > 0 && (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>My classes</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {summary.map((cls) => {
              const status = classStatus(cls.percent)
              return (
                <div key={cls.class_id} className="flex items-center gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <span className="font-mono-label text-accent">{cls.class_code}</span>
                      <span className="truncate text-sm text-ink">{cls.class_name}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-paper-3">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${cls.percent}%`,
                            backgroundColor: status.variant === 'success'
                              ? 'var(--color-success)'
                              : status.variant === 'warning'
                                ? 'var(--color-warning)'
                                : 'var(--color-danger)',
                          }}
                        />
                      </div>
                      <span className="font-mono-label text-ink-3 whitespace-nowrap">
                        {cls.sessions_present}/{cls.total_sessions} sessions
                      </span>
                    </div>
                  </div>
                  <Badge variant={status.variant}>{status.label}</Badge>
                </div>
              )
            })}
          </CardContent>
        </Card>
      )}

      {/* Attendance history */}
      <Card>
        <CardHeader>
          <CardTitle>Attendance history</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <Thead>
              <th>Class</th>
              <th>Date</th>
              <th>Time</th>
              <th>Method</th>
            </Thead>
            <Tbody>
              {records?.map((r) => (
                <Tr key={r.id}>
                  <Td className="font-medium text-ink">{(r as unknown as { class_name: string }).class_name}</Td>
                  <Td>{r.session_date}</Td>
                  <Td>{r.timestamp}</Td>
                  <Td className="font-mono-label">{r.method}</Td>
                </Tr>
              ))}
              {records?.length === 0 && (
                <Tr>
                  <Td colSpan={4} className="py-8 text-center text-ink-3">
                    No attendance recorded yet.
                  </Td>
                </Tr>
              )}
            </Tbody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
