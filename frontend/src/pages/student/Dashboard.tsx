import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, ScanFace } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Card, CardContent } from '@/components/ui/card'
import { Table, Thead, Tbody, Tr, Td } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { getStudentAttendance } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export default function StudentDashboard() {
  const { user } = useAuth()
  const { data: records } = useQuery({
    queryKey: ['student-attendance', user?.full_name],
    queryFn: () => getStudentAttendance(user!.full_name),
    enabled: !!user,
  })

  return (
    <div>
      <h1 className="mb-1">Your attendance</h1>
      <p className="mb-6 text-sm text-ink-3">Welcome back, {user?.full_name}.</p>

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

      <div className="mb-6 grid grid-cols-2 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-[var(--radius-sm)] bg-success-tint text-success-ink">
              <CheckCircle2 className="size-5" />
            </div>
            <div>
              <p className="font-mono-label text-ink-3">Sessions attended</p>
              <p className="font-display text-2xl font-semibold text-ink">{records?.length ?? '—'}</p>
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
    </div>
  )
}
