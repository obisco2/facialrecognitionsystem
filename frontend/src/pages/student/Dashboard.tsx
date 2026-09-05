import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { CheckCircle2, ScanFace, AlertTriangle, BookOpen, Plus, X } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, Thead, Tbody, Tr, Td } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { getStudentAttendance, getStudentSummary, browseClasses, enrollStudent, unenrollStudent, getFaculties, getDepartments } from '@/lib/api'
import type { AttendanceRecord } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { showToast } from '@/components/ui/toast'

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
  const qc = useQueryClient()

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

  // Course catalog filters
  const [facultyId, setFacultyId] = useState<number | ''>('')
  const [department, setDepartment] = useState('')

  const { data: faculties } = useQuery({
    queryKey: ['faculties'],
    queryFn: getFaculties,
    enabled: !!user,
  })
  const { data: departments } = useQuery({
    queryKey: ['departments', facultyId || 'all'],
    queryFn: () => getDepartments(facultyId === '' ? undefined : facultyId),
    enabled: !!user,
  })

  // Fetch course catalog for registration (all classes + enrolled flag)
  const { data: allClasses } = useQuery({
    queryKey: ['classes', 'browse', facultyId || 'all', department || 'all'],
    queryFn: () => browseClasses({
      facultyId: facultyId === '' ? undefined : facultyId,
      department: department || undefined,
    }),
    enabled: !!user,
  })

  const enrollMut = useMutation({
    mutationFn: (classId: number) => enrollStudent(classId, user!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['classes', 'browse'] })
      qc.invalidateQueries({ queryKey: ['student-summary', user?.id] })
      showToast('success', 'Successfully registered for class')
    },
    onError: (err: Error) => showToast('error', err.message || 'Failed to register'),
  })

  const unenrollMut = useMutation({
    mutationFn: (classId: number) => unenrollStudent(classId, user!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['classes', 'browse'] })
      qc.invalidateQueries({ queryKey: ['student-summary', user?.id] })
      showToast('success', 'Unregistered from class')
    },
    onError: (err: Error) => showToast('error', err.message || 'Failed to unregister'),
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

      {/* Course Registration */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Course Registration</CardTitle>
          <p className="text-sm text-ink-3">Select the courses you are offering this semester.</p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row">
            <select
              value={facultyId}
              onChange={(e) => {
                setFacultyId(e.target.value === '' ? '' : Number(e.target.value))
                setDepartment('')
              }}
              className="h-10 flex-1 rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
              aria-label="Filter by faculty"
            >
              <option value="">All faculties</option>
              {faculties?.map((f) => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </select>
            <select
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="h-10 flex-1 rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
              aria-label="Filter by department"
            >
              <option value="">All departments</option>
              {departments?.map((d) => (
                <option key={d.id} value={d.name}>{d.name}</option>
              ))}
            </select>
          </div>
          {!allClasses ? (
            <p className="text-sm text-ink-3">Loading classes...</p>
          ) : allClasses.length === 0 ? (
            <p className="text-sm text-ink-3">No classes match these filters.</p>
          ) : (
            allClasses.map((cls) => {
              const isEnrolled = cls.is_enrolled ?? summary?.some((s) => s.class_id === cls.id)
              return (
                <div key={cls.id} className="flex items-center justify-between gap-4 p-3 rounded-md bg-paper-2 border border-paper-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-mono-label text-accent">{cls.code}</span>
                      <span className="truncate text-sm font-medium text-ink">{cls.name}</span>
                    </div>
                    <p className="text-xs text-ink-3">
                      {[cls.department, cls.faculty_name].filter(Boolean).join('  ·  ') || '—'}
                      {cls.lecturer_name ? `  ·  ${cls.lecturer_name}` : ''}
                      {typeof cls.enrolled_count === 'number' ? `  ·  ${cls.enrolled_count} registered` : ''}
                    </p>
                  </div>
                  {isEnrolled ? (
                    <button
                      onClick={() => unenrollMut.mutate(cls.id)}
                      disabled={unenrollMut.isPending}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-danger bg-danger-tint rounded-md hover:opacity-80 transition-opacity disabled:opacity-50"
                    >
                      <X className="size-3.5" /> Remove
                    </button>
                  ) : (
                    <button
                      onClick={() => enrollMut.mutate(cls.id)}
                      disabled={enrollMut.isPending}
                      className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold text-accent bg-accent-tint rounded-md hover:opacity-80 transition-opacity disabled:opacity-50"
                    >
                      <Plus className="size-3.5" /> Add Course
                    </button>
                  )}
                </div>
              )
            })
          )}
        </CardContent>
      </Card>

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
