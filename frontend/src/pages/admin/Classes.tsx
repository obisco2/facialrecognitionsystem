import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Users as UsersIcon, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog } from '@/components/ui/dialog'
import { Table, Thead, Tbody, Tr, Td } from '@/components/ui/table'
import {
  getClasses,
  createClass,
  deleteClass,
  getUsers,
  getClassEnrollments,
  enrollStudent,
  unenrollStudent,
} from '@/lib/api'

export default function AdminClasses() {
  const qc = useQueryClient()
  const [createOpen, setCreateOpen] = useState(false)
  const [manageId, setManageId] = useState<number | null>(null)
  const [form, setForm] = useState({ name: '', code: '', schedule: '', room: '', lecturerId: '' })

  const { data: classes } = useQuery({ queryKey: ['classes'], queryFn: () => getClasses() })
  const { data: lecturers } = useQuery({ queryKey: ['users', 'lecturer'], queryFn: () => getUsers('lecturer') })

  const createMut = useMutation({
    mutationFn: () =>
      createClass(Number(form.lecturerId), {
        name: form.name,
        code: form.code,
        schedule: form.schedule || undefined,
        room: form.room || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['classes'] })
      setCreateOpen(false)
      setForm({ name: '', code: '', schedule: '', room: '', lecturerId: '' })
    },
  })

  const deleteMut = useMutation({
    mutationFn: deleteClass,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['classes'] }),
  })

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="mb-1">Classes</h1>
          <p className="text-sm text-ink-3">Create classes and manage student enrollment.</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" /> New class
        </Button>
      </div>

      <Table>
        <Thead>
          <th>Name</th>
          <th>Code</th>
          <th>Lecturer</th>
          <th>Room</th>
          <th />
        </Thead>
        <Tbody>
          {classes?.map((c) => (
            <Tr key={c.id}>
              <Td className="font-medium text-ink">{c.name}</Td>
              <Td className="font-mono-label">{c.code}</Td>
              <Td>{lecturers?.find((l) => l.id === c.lecturer_id)?.full_name ?? '—'}</Td>
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
          {classes?.length === 0 && (
            <Tr>
              <Td colSpan={5} className="py-8 text-center text-ink-3">
                No classes yet.
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
          <select
            value={form.lecturerId}
            onChange={(e) => setForm({ ...form, lecturerId: e.target.value })}
            className="h-10 w-full rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
            required
          >
            <option value="">Assign lecturer…</option>
            {lecturers?.map((l) => (
              <option key={l.id} value={l.id}>
                {l.full_name}
              </option>
            ))}
          </select>
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

  const enrollMut = useMutation({
    mutationFn: (studentId: number) => enrollStudent(classId, studentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['enrollments', classId] }),
  })
  const unenrollMut = useMutation({
    mutationFn: (studentId: number) => unenrollStudent(classId, studentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['enrollments', classId] }),
  })

  return (
    <Dialog open onClose={onClose} title="Manage enrollment">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="mb-2 font-mono-label text-ink-3">Enrolled ({data?.enrolled.length ?? 0})</p>
          <ul className="max-h-64 space-y-1 overflow-y-auto">
            {data?.enrolled.map((s) => (
              <li key={s.id} className="flex items-center justify-between rounded-[var(--radius-sm)] border border-rule px-2.5 py-1.5 text-sm">
                {s.full_name}
                <button onClick={() => unenrollMut.mutate(s.id)} className="text-ink-3 hover:text-danger">
                  <X className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
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
