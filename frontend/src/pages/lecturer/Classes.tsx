import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Users as UsersIcon, X, Ban, ShieldOff, UserPlus, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog } from '@/components/ui/dialog'
import { Table, Thead, Tbody, Tr, Td } from '@/components/ui/table'
import {
  getClasses,
  createClass,
  deleteClass,
  getClassEnrollments,
  enrollStudent,
  unenrollStudent,
  getDepartments,
  getBlocked,
  blockStudent,
  unblockStudent,
  getUnassigned,
  assignSelf,
} from '@/lib/api'
import { showToast } from '@/components/ui/toast'
import { useAuth } from '@/lib/auth'

export default function LecturerClasses() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [manageId, setManageId] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [form, setForm] = useState({
    name: '',
    code: '',
    schedule: '',
    room: '',
    department: '',
    units: '',
    level: '',
    semester: '',
  })

  const { data: classes } = useQuery({
    queryKey: ['classes', user?.id],
    queryFn: () => getClasses(user?.id),
    enabled: !!user,
  })

  const { data: departments } = useQuery({
    queryKey: ['departments'],
    queryFn: () => getDepartments(),
  })

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return classes ?? []
    return (classes ?? []).filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.code.toLowerCase().includes(q) ||
        (c.department ?? '').toLowerCase().includes(q) ||
        (c.departments ?? []).some((d) => d.toLowerCase().includes(q)),
    )
  }, [classes, search])

  const createMut = useMutation({
    mutationFn: () =>
      createClass(user!.id, {
        name: form.name,
        code: form.code,
        schedule: form.schedule || undefined,
        room: form.room || undefined,
        department: form.department || undefined,
        units: form.units === '' ? undefined : Number(form.units),
        level: form.level || undefined,
        semester: form.semester || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['classes', user?.id] })
      setCreateOpen(false)
      setForm({ name: '', code: '', schedule: '', room: '', department: '', units: '', level: '', semester: '' })
      showToast('success', 'Class created')
    },
    onError: (err: Error) => showToast('error', err.message || 'Failed to create class'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteClass,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['classes', user?.id] })
      showToast('success', 'Class deleted')
    },
    onError: (err: Error) => showToast('error', err.message || 'Failed to delete class'),
  })

  const { data: unassigned } = useQuery({ queryKey: ['unassigned'], queryFn: getUnassigned })

  const assignMut = useMutation({
    mutationFn: (classId: number) => assignSelf(classId, user!.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['classes', user?.id] })
      qc.invalidateQueries({ queryKey: ['unassigned'] })
      showToast('success', 'Assigned to class')
    },
    onError: (e: Error) => showToast('error', e.message),
  })

  if (!user) return null

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="mb-1">My classes</h1>
          <p className="text-sm text-ink-3">Manage your classes, blocks and assignment.</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" /> New class
        </Button>
      </div>

      {unassigned && unassigned.length > 0 && (
        <div className="mb-4 rounded border border-amber-200 bg-amber-50 p-3">
          <p className="mb-2 text-sm font-medium text-amber-900">Unassigned courses — claim one:</p>
          <div className="flex flex-wrap gap-2">
            {unassigned.map((c) => (
              <button
                key={c.id}
                onClick={() => assignMut.mutate(c.id)}
                className="rounded border border-amber-300 bg-white px-3 py-1 text-sm hover:bg-amber-100"
              >
                <UserPlus className="mr-1 inline size-3" /> {c.code} — {c.name}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="mb-4 max-w-sm">
        <Input icon={<Search className="size-4" />} placeholder="Search courses by name, code or department…" value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      <Table>
        <Thead>
          <th>Name</th>
          <th>Code</th>
          <th>Department</th>
          <th>Level</th>
          <th>Units</th>
          <th>Schedule</th>
          <th>Room</th>
          <th />
        </Thead>
        <Tbody>
          {filtered.map((c) => (
            <Tr key={c.id}>
              <Td className="font-medium text-ink">{c.name}</Td>
              <Td className="font-mono-label">{c.code}</Td>
              <Td className="text-xs text-ink-2 max-w-[160px] truncate">
                {(c.departments?.length ? c.departments : c.department ? [c.department] : []).join(', ') || '—'}
              </Td>
              <Td>{c.level ? `${c.level}L` : '—'}</Td>
              <Td>{c.units ?? '—'}</Td>
              <Td>{c.schedule ?? '—'}</Td>
              <Td>{c.room ?? '—'}</Td>
              <Td>
                <div className="flex justify-end gap-2">
                  <button onClick={() => setManageId(c.id)} className="text-ink-3 hover:text-accent" aria-label="Manage enrollment">
                    <UsersIcon className="size-4" />
                  </button>
                  <button
                    onClick={() => confirm(`Delete ${c.name}?`) && deleteMut.mutate(c.id)}
                    className="text-ink-3 hover:text-danger"
                    aria-label="Delete class"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
              </Td>
            </Tr>
          ))}
          {filtered.length === 0 && (
            <Tr>
              <Td colSpan={8} className="py-8 text-center text-ink-3">
                No classes match your search.
              </Td>
            </Tr>
          )}
        </Tbody>
      </Table>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} title="New class">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            createMut.mutate()
          }}
          className="space-y-3"
        >
          <Input placeholder="Class name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
          <Input placeholder="Code (e.g. CEG 501)" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
          <div className="grid grid-cols-2 gap-3">
            <Input
              type="number"
              min={0}
              placeholder="Units"
              value={form.units}
              onChange={(e) => setForm({ ...form, units: e.target.value })}
            />
            <select
              value={form.level}
              onChange={(e) => setForm({ ...form, level: e.target.value })}
              className="h-10 w-full rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
            >
              <option value="">Level…</option>
              {['100', '200', '300', '400', '500'].map((l) => (
                <option key={l} value={l}>{l}00</option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <select
              value={form.semester}
              onChange={(e) => setForm({ ...form, semester: e.target.value })}
              className="h-10 w-full rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
            >
              <option value="">Semester…</option>
              <option value="1st">First semester</option>
              <option value="2nd">Second semester</option>
            </select>
            <select
              value={form.department}
              onChange={(e) => setForm({ ...form, department: e.target.value })}
              className="h-10 w-full rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
            >
              <option value="">Department (optional)…</option>
              {departments?.map((d) => (
                <option key={d.id} value={d.name}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>
          <Input placeholder="Schedule (optional)" value={form.schedule} onChange={(e) => setForm({ ...form, schedule: e.target.value })} />
          <Input placeholder="Room (optional)" value={form.room} onChange={(e) => setForm({ ...form, room: e.target.value })} />
          <Button type="submit" className="w-full" loading={createMut.isPending}>
            Create class
          </Button>
        </form>
      </Dialog>

      {manageId != null && <EnrollmentManager classId={manageId} onClose={() => setManageId(null)} />}
    </div>
  )
}

function EnrollmentManager({ classId, onClose }: { classId: number; onClose: () => void }) {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['enrollments', classId], queryFn: () => getClassEnrollments(classId) })
  const { data: blocked } = useQuery({ queryKey: ['blocks', classId], queryFn: () => getBlocked(classId) })

  const enrollMut = useMutation({
    mutationFn: (studentId: number) => enrollStudent(classId, studentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['enrollments', classId] }),
    onError: (err: Error) => showToast('error', err.message || 'Failed to enroll student'),
  })
  const unenrollMut = useMutation({
    mutationFn: (studentId: number) => unenrollStudent(classId, studentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['enrollments', classId] }),
    onError: (err: Error) => showToast('error', err.message || 'Failed to unenroll student'),
  })
  const blockMut = useMutation({
    mutationFn: (studentId: number) => blockStudent(classId, studentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['blocks', classId] })
      qc.invalidateQueries({ queryKey: ['enrollments', classId] })
      showToast('success', 'Student blocked from class')
    },
    onError: (e: Error) => showToast('error', e.message),
  })
  const unblockMut = useMutation({
    mutationFn: (studentId: number) => unblockStudent(classId, studentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['blocks', classId] })
      showToast('success', 'Unblocked')
    },
    onError: (e: Error) => showToast('error', e.message),
  })

  const blockedIds = new Set(blocked?.map((b) => b.student_id))

  return (
    <Dialog open onClose={onClose} title="Manage enrollment & blocks">
      <div className="enroll-grid">
        <div>
          <p className="mb-2 font-mono-label text-ink-3">Enrolled ({data?.enrolled.length ?? 0})</p>
          <ul className="max-h-56 space-y-1 overflow-y-auto">
            {data?.enrolled.map((s) => (
              <li key={s.id} className="flex items-center justify-between rounded-[var(--radius-sm)] border border-rule px-2.5 py-1.5 text-sm">
                <span className={blockedIds.has(s.id) ? 'text-danger line-through' : ''}>{s.full_name}</span>
                <span className="flex gap-1">
                  {!blockedIds.has(s.id) ? (
                    <button onClick={() => blockMut.mutate(s.id)} title="Block from attending" className="text-amber-600 hover:text-amber-800">
                      <Ban className="size-3.5" />
                    </button>
                  ) : (
                    <button onClick={() => unblockMut.mutate(s.id)} title="Unblock" className="text-emerald-600 hover:text-emerald-800">
                      <ShieldOff className="size-3.5" />
                    </button>
                  )}
                  <button onClick={() => unenrollMut.mutate(s.id)} className="text-ink-3 hover:text-danger">
                    <X className="size-3.5" />
                  </button>
                </span>
              </li>
            ))}
          </ul>
          {blocked && blocked.length > 0 && (
            <div className="mt-3 rounded bg-red-50 p-2 text-xs">
              <p className="font-medium text-red-800">Blocked ({blocked.length})</p>
              <ul className="mt-1 space-y-1">
                {blocked.map((b) => (
                  <li key={b.id} className="flex justify-between">
                    <span>{b.full_name}</span>
                    <button onClick={() => unblockMut.mutate(b.student_id)} className="text-emerald-600">
                      Unblock
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        <div>
          <p className="mb-2 font-mono-label text-ink-3">Available ({data?.unenrolled.length ?? 0})</p>
          <ul className="max-h-64 space-y-1 overflow-y-auto">
            {data?.unenrolled.map((s) => (
              <li key={s.id} className="flex items-center justify-between rounded-[var(--radius-sm)] border border-rule px-2.5 py-1.5 text-sm">
                {s.full_name}
                <button onClick={() => enrollMut.mutate(s.id)} className="text-ink-3 hover:text-accent">
                  <Plus className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Dialog>
  )
}
