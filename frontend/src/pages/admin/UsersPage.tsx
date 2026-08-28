import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Pencil, KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Dialog } from '@/components/ui/dialog'
import { Table, Thead, Tbody, Tr, Td } from '@/components/ui/table'
import { getUsers, createUser, updateUser, resetPassword, deleteUser, type User, type Role } from '@/lib/api'
import { showToast } from '@/components/ui/toast'
import { cn } from '@/lib/utils'
import { useAuth } from '@/lib/auth'

const TABS: (Role | 'all')[] = ['all', 'admin', 'lecturer', 'student']

export default function AdminUsers() {
  const qc = useQueryClient()
  const { user, setUser } = useAuth()
  const [tab, setTab] = useState<Role | 'all'>('all')
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState({ username: '', password: '', role: 'student' as Role, full_name: '', title: '', student_id: '', email: '' })

  const [editUser, setEditUser] = useState<User | null>(null)
  const [editForm, setEditForm] = useState({ full_name: '', title: '', username: '', student_id: '', email: '' })
  const [newPassword, setNewPassword] = useState('')
  const [deleteConfirmUser, setDeleteConfirmUser] = useState<User | null>(null)

  const { data: users } = useQuery({ queryKey: ['users'], queryFn: () => getUsers() })
  const filtered = tab === 'all' ? users : users?.filter((u) => u.role === tab)

  const createMut = useMutation({
    mutationFn: () =>
      createUser({
        username: form.username,
        password: form.password,
        role: form.role,
        full_name: form.full_name,
        title: form.title || undefined,
        student_id: form.student_id || undefined,
        email: form.email || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      setCreateOpen(false)
      setForm({ username: '', password: '', role: 'student', full_name: '', title: '', student_id: '', email: '' })
      showToast('success', 'User created')
    },
    onError: (err: Error) => showToast('error', err.message || 'Failed to create user'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      showToast('success', 'User deleted')
    },
    onError: (err: Error) => showToast('error', err.message || 'Failed to delete user'),
  })

  const editMut = useMutation({
    mutationFn: async () => {
      if (!editUser) return
      const data: Partial<User> = {}
      if (editForm.full_name !== editUser.full_name) data.full_name = editForm.full_name
      if (editForm.title !== (editUser.title ?? '')) data.title = editForm.title || undefined
      if (editForm.username !== editUser.username) data.username = editForm.username
      if (editForm.student_id !== (editUser.student_id ?? '')) data.student_id = editForm.student_id || undefined
      if (editForm.email !== (editUser.email ?? '')) data.email = editForm.email || undefined
      return updateUser(editUser.id, data)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['users'] })
      if (editUser && user && editUser.id === user.id) {
        setUser({
          ...user,
          full_name: editForm.full_name,
          username: editForm.username,
          title: editForm.title || null,
          student_id: editForm.student_id || null,
          email: editForm.email || null,
        })
      }
      setEditUser(null)
      showToast('success', 'User updated')
    },
    onError: (err: Error) => showToast('error', err.message || 'Failed to update user'),
  })

  const resetPwMut = useMutation({
    mutationFn: async () => {
      if (!editUser || !newPassword) return
      return resetPassword(editUser.id, newPassword)
    },
    onSuccess: () => {
      setNewPassword('')
      showToast('success', 'Password reset')
    },
    onError: (err: Error) => showToast('error', err.message || 'Failed to reset password'),
  })

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="mb-1">Users</h1>
          <p className="text-sm text-ink-3">Manage admin, lecturer, and student accounts.</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="size-4" /> New user
        </Button>
      </div>

      <div className="mb-4 flex gap-1 overflow-x-auto border-b border-rule">
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
          <th>Matric No. / Email</th>
          <th>Role</th>
          <th>Face enrolled</th>
          <th />
        </Thead>
        <Tbody>
          {filtered?.map((u) => (
            <Tr key={u.id}>
              <Td className="font-medium text-ink">
                {u.title ? `${u.title} ` : ''}{u.full_name}
              </Td>
              <Td className="font-mono-label text-xs">
                {u.role === 'student' ? (u.student_id || '—') : (u.email || u.username)}
              </Td>
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
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      setEditUser(u)
                      setEditForm({
                        full_name: u.full_name,
                        title: u.title ?? '',
                        username: u.username,
                        student_id: u.student_id ?? '',
                        email: u.email ?? '',
                      })
                      setNewPassword('')
                    }}
                    className="text-ink-3 hover:text-accent"
                    aria-label="Edit user"
                  >
                    <Pencil className="size-4" />
                  </button>
                  {u.role !== 'admin' && (
                    <button
                      onClick={() => setDeleteConfirmUser(u)}
                      className="text-ink-3 hover:text-danger"
                      aria-label="Delete user"
                    >
                      <Trash2 className="size-4" />
                    </button>
                  )}
                </div>
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
          {form.role === 'lecturer' && (
            <select
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className="h-10 w-full rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
            >
              <option value="">No title</option>
              <option value="Dr.">Dr.</option>
              <option value="Prof.">Prof.</option>
              <option value="Assoc. Prof.">Assoc. Prof.</option>
              <option value="Asst. Prof.">Asst. Prof.</option>
              <option value="Mr.">Mr.</option>
              <option value="Mrs.">Mrs.</option>
              <option value="Ms.">Ms.</option>
            </select>
          )}
          {form.role === 'student' && (
            <>
              <Input placeholder="Matric Number *" value={form.student_id} onChange={(e) => setForm({ ...form, student_id: e.target.value })} required />
              <Input type="email" placeholder="Email *" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
            </>
          )}
          {form.role === 'lecturer' && (
            <Input type="email" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          )}
          <Button type="submit" className="w-full" loading={createMut.isPending}>
            Create user
          </Button>
        </form>
      </Dialog>

      <Dialog open={!!editUser} onClose={() => setEditUser(null)} title={`Edit ${editUser?.full_name ?? ''}`}>
        <div className="space-y-4">
          <div className="space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-3">User Info</p>
            <Input
              placeholder="Full name"
              value={editForm.full_name}
              onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
            />
            <Input
              placeholder="Username"
              value={editForm.username}
              onChange={(e) => setEditForm({ ...editForm, username: e.target.value })}
            />
            {editUser?.role === 'lecturer' && (
              <select
                value={editForm.title}
                onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                className="h-10 w-full rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
              >
                <option value="">No title</option>
                <option value="Dr.">Dr.</option>
                <option value="Prof.">Prof.</option>
                <option value="Assoc. Prof.">Assoc. Prof.</option>
                <option value="Asst. Prof.">Asst. Prof.</option>
                <option value="Mr.">Mr.</option>
                <option value="Mrs.">Mrs.</option>
                <option value="Ms.">Ms.</option>
              </select>
            )}
            {(editUser?.role === 'student' || editUser?.role === 'lecturer') && (
              <Input
                type="email"
                placeholder="Email"
                value={editForm.email}
                onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
              />
            )}
            {editUser?.role === 'student' && (
              <Input
                placeholder="Matric Number"
                value={editForm.student_id}
                onChange={(e) => setEditForm({ ...editForm, student_id: e.target.value })}
              />
            )}
            <Button onClick={() => editMut.mutate()} loading={editMut.isPending} className="w-full">
              Save changes
            </Button>
          </div>

          <div className="border-t border-rule pt-4 space-y-3">
            <p className="text-xs font-medium uppercase tracking-wide text-ink-3 flex items-center gap-1.5">
              <KeyRound className="size-3.5" /> Reset Password
            </p>
            <Input
              type="password"
              placeholder="New password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            <Button
              variant="danger"
              onClick={() => resetPwMut.mutate()}
              loading={resetPwMut.isPending}
              disabled={!newPassword}
              className="w-full"
            >
              Reset password
            </Button>
          </div>
        </div>
      </Dialog>

      <Dialog open={!!deleteConfirmUser} onClose={() => setDeleteConfirmUser(null)} title="Delete user">
        <div className="space-y-4 pt-2">
          <p className="text-sm text-ink-2">
            Are you sure you want to delete <strong>{deleteConfirmUser?.full_name}</strong>? This action cannot be undone.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setDeleteConfirmUser(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                if (deleteConfirmUser) {
                  deleteMut.mutate(deleteConfirmUser.id)
                  setDeleteConfirmUser(null)
                }
              }}
              loading={deleteMut.isPending}
            >
              Delete
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  )
}
