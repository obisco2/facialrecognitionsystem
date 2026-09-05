import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, ScanFace } from 'lucide-react'
import { Table, Thead, Tbody, Tr, Td } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { getLecturerRoster, getClasses } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export default function LecturerStudents() {
  const { user } = useAuth()
  const [search, setSearch] = useState('')
  const [courseId, setCourseId] = useState<number | ''>('')

  const { data: roster, isLoading } = useQuery({
    queryKey: ['lecturer-roster'],
    queryFn: getLecturerRoster,
    enabled: !!user,
  })
  const { data: classes } = useQuery({
    queryKey: ['classes', user?.id],
    queryFn: () => getClasses(user!.id),
    enabled: !!user,
  })

  const filtered = useMemo(() => {
    if (!roster) return []
    const q = search.trim().toLowerCase()
    return roster.filter((s) => {
      if (courseId !== '' && !s.classes.some((c) => c.id === courseId)) return false
      if (!q) return true
      return (
        s.full_name.toLowerCase().includes(q) ||
        (s.student_id ?? '').toLowerCase().includes(q) ||
        (s.email ?? '').toLowerCase().includes(q)
      )
    })
  }, [roster, search, courseId])

  if (!user) return null

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="mb-1">Students</h1>
          <p className="text-sm text-ink-3">
            Everyone registered for your courses — search, filter by course, remove from Classes.
          </p>
        </div>
      </div>

      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-3" />
          <Input
            placeholder="Search name, matric no. or email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <select
          value={courseId}
          onChange={(e) => setCourseId(e.target.value === '' ? '' : Number(e.target.value))}
          className="h-10 rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink sm:w-64"
          aria-label="Filter by course"
        >
          <option value="">All my courses</option>
          {classes?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.code} — {c.name}
            </option>
          ))}
        </select>
      </div>

      <Table>
        <Thead>
          <th>Name</th>
          <th>Matric No.</th>
          <th>Courses</th>
          <th>Face</th>
        </Thead>
        <Tbody>
          {filtered.map((s) => (
            <Tr key={s.id}>
              <Td className="font-medium text-ink">
                {s.full_name}
                {s.department && <span className="block text-xs font-normal text-ink-3">{s.department}</span>}
              </Td>
              <Td className="font-mono-label">{s.student_id ?? '—'}</Td>
              <Td>
                <div className="flex max-w-[320px] flex-wrap gap-1">
                  {s.classes.map((c) => (
                    <Badge key={c.id} variant="neutral" title={c.name}>
                      {c.code}
                    </Badge>
                  ))}
                </div>
              </Td>
              <Td>
                {s.face_enrolled ? (
                  <span className="flex items-center gap-1 text-xs text-success-ink">
                    <ScanFace className="size-3.5" /> enrolled
                  </span>
                ) : (
                  <Badge variant="warning">pending</Badge>
                )}
              </Td>
            </Tr>
          ))}
          {!isLoading && filtered.length === 0 && (
            <Tr>
              <Td colSpan={4} className="py-8 text-center text-ink-3">
                {roster?.length === 0
                  ? 'No students registered for your courses yet.'
                  : 'No students match this search.'}
              </Td>
            </Tr>
          )}
          {isLoading && (
            <Tr>
              <Td colSpan={4} className="py-8 text-center text-ink-3">
                Loading roster…
              </Td>
            </Tr>
          )}
        </Tbody>
      </Table>
      <p className="mt-3 text-xs text-ink-3">
        To remove a student from a course, open Classes → manage enrollment for that course.
      </p>
    </div>
  )
}
