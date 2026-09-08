import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, X, GraduationCap, Layers, Search, BookMarked, Globe } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { browseClasses, enrollStudent, unenrollStudent, getStudentSummary } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { showToast } from '@/components/ui/toast'
import { cn } from '@/lib/utils'

const LEVELS = ['100', '200', '300', '400', '500']

type CatalogTab = 'department' | 'all'

export default function StudentCourses() {
  const { user } = useAuth()
  const qc = useQueryClient()

  const [tab, setTab] = useState<CatalogTab>('department')
  const [levelFilter, setLevelFilter] = useState('')
  const [semesterFilter, setSemesterFilter] = useState('')
  const [search, setSearch] = useState('')

  const { data: summary } = useQuery({
    queryKey: ['student-summary', user?.id],
    queryFn: () => getStudentSummary(user!.id),
    enabled: !!user,
  })

  // "My department" tab is auto-scoped to the student's department by the backend.
  // "All courses" tab requests the full catalog via scope=all.
  const { data: catalog } = useQuery({
    queryKey: ['classes', 'browse', 'student', user?.id, tab],
    queryFn: () => browseClasses(tab === 'all' ? { scope: 'all' } : {}),
    enabled: !!user,
  })

  const enrolledIds = useMemo(() => {
    const s = new Set((summary ?? []).map((c) => c.class_id))
    return s
  }, [summary])

  const enrollMut = useMutation({
    mutationFn: (classId: number) => enrollStudent(classId, user!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['classes', 'browse'] })
      qc.invalidateQueries({ queryKey: ['student-summary', user?.id] })
      showToast('success', 'Course added')
    },
    onError: (err: Error) => showToast('error', err.message || 'Failed to add course'),
  })

  const unenrollMut = useMutation({
    mutationFn: (classId: number) => unenrollStudent(classId, user!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['classes', 'browse'] })
      qc.invalidateQueries({ queryKey: ['student-summary', user?.id] })
      showToast('success', 'Course removed')
    },
    onError: (err: Error) => showToast('error', err.message || 'Failed to remove course'),
  })

  const available = useMemo(() => {
    let list = catalog ?? []
    const q = search.trim().toLowerCase()
    if (q) {
      list = list.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.code.toLowerCase().includes(q) ||
          (c.department ?? '').toLowerCase().includes(q) ||
          (c.departments ?? []).some((d) => d.toLowerCase().includes(q)),
      )
    }
    if (levelFilter) list = list.filter((c) => c.level === levelFilter)
    if (semesterFilter) list = list.filter((c) => c.semester === semesterFilter)
    return list
  }, [catalog, levelFilter, semesterFilter, search])

  const levelsPresent = useMemo(
    () => Array.from(new Set((catalog ?? []).map((c) => c.level).filter(Boolean))) as string[],
    [catalog],
  )

  const myCourses = (summary ?? []).slice().sort((a, b) => (a.class_code < b.class_code ? -1 : 1))

  const courseUnits = useMemo(() => {
    const m = new Map<number, number>()
    for (const c of catalog ?? []) if (c.id) m.set(c.id, c.units ?? 0)
    return m
  }, [catalog])

  const totalUnits = myCourses.reduce((s, c) => s + (courseUnits.get(c.class_id) ?? 0), 0)

  return (
    <div>
      <div className="mb-6">
        <h1 className="mb-1">My courses</h1>
        <p className="text-sm text-ink-3">
          Add your courses to attend sessions. Browse your department's courses or search the full catalog.
        </p>
      </div>

      {/* My courses */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>
            Enrolled ({myCourses.length})
            {totalUnits > 0 && <span className="ml-2 text-sm font-normal text-ink-3">· {totalUnits} units</span>}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {myCourses.length === 0 ? (
            <p className="text-sm text-ink-3">
              You haven't added any courses yet. Pick courses from the catalog below.
            </p>
          ) : (
            <ul className="space-y-2">
              {myCourses.map((c) => {
                const info = (catalog ?? []).find((x) => x.id === c.class_id)
                return (
                  <li
                    key={c.class_id}
                    className="flex items-center justify-between gap-3 rounded-md border border-paper-3 bg-paper-2 p-3"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono-label text-accent">{c.class_code}</span>
                        <span className="truncate text-sm font-medium text-ink">{c.class_name}</span>
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-3">
                        {info?.level && (
                          <span className="inline-flex items-center gap-1">
                            <GraduationCap className="size-3" /> {info.level}L
                          </span>
                        )}
                        {info?.semester && <span>{info.semester} semester</span>}
                        {info?.units != null && (
                          <span className="inline-flex items-center gap-1">
                            <Layers className="size-3" /> {info.units} unit{info.units === 1 ? '' : 's'}
                          </span>
                        )}
                        {c.sessions_present}/{c.total_sessions} sessions att.
                      </div>
                    </div>
                    <button
                      onClick={() => unenrollMut.mutate(c.class_id)}
                      disabled={unenrollMut.isPending}
                      className="flex shrink-0 items-center gap-1 px-3 py-1.5 text-xs font-semibold text-danger hover:opacity-80 disabled:opacity-50"
                    >
                      <X className="size-3.5" /> Remove
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Course catalog */}
      <Card>
        <CardHeader>
          <CardTitle>Course catalog</CardTitle>
          <p className="text-sm text-ink-3">
            {tab === 'department'
              ? `Showing courses for ${user?.department ?? 'your account'}. Use the "All courses" tab to search the full catalog.`
              : 'Browse and search every available course, then add the ones you need.'}
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex gap-1 border-b border-rule">
              <button
                onClick={() => setTab('department')}
                className={cn(
                  'flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium',
                  tab === 'department' ? 'border-accent text-accent' : 'border-transparent text-ink-3 hover:text-ink',
                )}
              >
                <BookMarked className="size-4" /> My department
              </button>
              <button
                onClick={() => setTab('all')}
                className={cn(
                  'flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium',
                  tab === 'all' ? 'border-accent text-accent' : 'border-transparent text-ink-3 hover:text-ink',
                )}
              >
                <Globe className="size-4" /> All courses
              </button>
            </div>
            <div className="min-w-0 flex-1">
              <Input
                icon={<Search className="size-4" />}
                placeholder="Search by course name, code or department…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <select
              value={levelFilter}
              onChange={(e) => setLevelFilter(e.target.value)}
              className="h-10 flex-1 rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
              aria-label="Filter by level"
            >
              <option value="">All levels</option>
              {LEVELS.filter((l) => levelsPresent.includes(l)).map((l) => (
                <option key={l} value={l}>
                  {l}00 Level
                </option>
              ))}
            </select>
            <select
              value={semesterFilter}
              onChange={(e) => setSemesterFilter(e.target.value)}
              className="h-10 flex-1 rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
              aria-label="Filter by semester"
            >
              <option value="">All semesters</option>
              <option value="1st">First semester</option>
              <option value="2nd">Second semester</option>
            </select>
          </div>

          {!catalog ? (
            <p className="text-sm text-ink-3">Loading courses...</p>
          ) : available.length === 0 ? (
            <p className="text-sm text-ink-3">No courses match these filters.</p>
          ) : (
            <ul className="space-y-2">
              {available.map((cls) => {
                const isEnrolled = enrolledIds.has(cls.id)
                return (
                  <li
                    key={cls.id}
                    className="flex items-center justify-between gap-3 rounded-md border border-paper-3 bg-paper-2 p-3"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-mono-label text-accent">{cls.code}</span>
                        <span className="truncate text-sm font-medium text-ink">{cls.name}</span>
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-3">
                        {cls.level && (
                          <span className="inline-flex items-center gap-1">
                            <GraduationCap className="size-3" /> {cls.level}L
                          </span>
                        )}
                        {cls.semester && <span>{cls.semester} semester</span>}
                        {cls.units != null && (
                          <span className="inline-flex items-center gap-1">
                            <Layers className="size-3" /> {cls.units} unit{cls.units === 1 ? '' : 's'}
                          </span>
                        )}
                        {cls.departments && cls.departments.length > 0 && (
                          <span className="truncate">{cls.departments.join(', ')}</span>
                        )}
                        {cls.lecturer_name ? ` · ${cls.lecturer_name}` : ''}
                      </div>
                    </div>
                    {isEnrolled ? (
                      <span className="shrink-0">
                        <Badge variant="success">added</Badge>
                      </span>
                    ) : (
                      <button
                        onClick={() => enrollMut.mutate(cls.id)}
                        disabled={enrollMut.isPending}
                        className="flex shrink-0 items-center gap-1 px-3 py-1.5 text-xs font-semibold text-accent bg-accent-tint rounded-md hover:opacity-80 transition-opacity disabled:opacity-50"
                      >
                        <Plus className="size-3.5" /> Add Course
                      </button>
                    )}
                  </li>
                )
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
