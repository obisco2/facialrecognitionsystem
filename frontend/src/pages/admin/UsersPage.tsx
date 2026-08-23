import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Dialog } from '@/components/ui/dialog'
import { Table, Thead, Tbody, Tr, Td } from '@/components/ui/table'
import { getUsers, createUser, deleteUser, type Role } from '@/lib/api'
import { cn } from '@/lib/utils'

const TABS: (Role | 'all')[] = ['all', 'admin', 'lecturer', 'student']

export default function AdminUsers() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<Role | 'all'>('all')
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState({ username: '', password: '', role: 'student' as Role, full_name: '', student_id: '', email: '' })

  const { data: users } = useQuery({ queryKey: ['users'], queryFn: () => getUsers() })
  const filtered = tab === 'all' ? users : users?.filter((u) => u.role === tab)

  const createMut = useMutation({
    mutationFn: () =>
      createUser({
        username: form.username,
        password: form.password,
        role: form.role,
        full_name: form.full_name,
        student_id: form.student_id || undefined,
        email: form.email || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      setCreateOpen(false)
      setForm({ username: '', password: '', role: 'student', full_name: '', student_id: '', email: '' })
    },
  })

  const deleteMut = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  })

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="mb-1">Users</h1>
          <p className="text-sm text-ink-3">Manage admin, lecturer, and student accounts.</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" /> New user
        </Button>
      </div>

      <div className="mb-4 flex gap-1 border-b border-rule">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              'border-b-2 px-3 py-2 text-sm font-medium capitalize',
              tab === t ? 'border-accent text-accent' : 'border-transparent text-ink-3 hover:text-ink',
            )}
          >
            {t}
          </button>
        ))}
      </div>

      <Table>
        <Thead>
          <th>Name</th>
          <th>Username</th>
          <th>Role</th>
          <th>Face enrolled</th>
          <th />
        </Thead>
        <Tbody>
          {filtered?.map((u) => (
            <Tr key={u.id}>
              <Td className="font-medium text-ink">{u.full_name}</Td>
              <Td className="font-mono-label">{u.username}</Td>
              <Td>
                <Badge variant="neutral">{u.role}</Badge>
              </Td>
              <Td>
                {u.role === 'student' ? (
                  <Badge variant={u.face_enrolled ? 'success' : 'warning'} dot>
                    {u.face_enrolled ? 'enrolled' : 'pending'}
                  </Badge>
                ) : (
                  '—'
                )}
              </Td>
              <Td>
                <button
                  onClick={() => confirm(`Delete ${u.full_name}?`) && deleteMut.mutate(u.id)}
                  className="text-ink-3 hover:text-danger"
                  aria-label="Delete user"
                >
                  <Trash2 className="size-4" />
                </button>
              </Td>
            </Tr>
          ))}
          {filtered?.length === 0 && (
            <Tr>
              <Td colSpan={5} className="py-8 text-center text-ink-3">
                No users in this category.
              </Td>
            </Tr>
          )}
        </Tbody>
      </Table>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} title="New user">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            createMut.mutate()
          }}
          className="space-y-3"
        >
          <Input placeholder="Full name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
          <Input placeholder="Username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
          <Input
            type="password"
            placeholder="Password"
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
          />
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value as Role })}
            className="h-10 w-full rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
          >
            <option value="student">Student</option>
            <option value="lecturer">Lecturer</option>
            <option value="admin">Admin</option>
          </select>
          {form.role === 'student' && (
            <Input placeholder="Student ID (optional)" value={form.student_id} onChange={(e) => setForm({ ...form, student_id: e.target.value })} />
          )}
          <Input placeholder="Email (optional)" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <Button type="submit" className="w-full" loading={createMut.isPending}>
            Create user
          </Button>
        </form>
      </Dialog>
    </div>
  )
}
