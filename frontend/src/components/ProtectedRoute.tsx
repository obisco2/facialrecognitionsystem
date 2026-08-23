import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@/lib/auth'
import type { Role } from '@/lib/api'

export function ProtectedRoute({ role }: { role: Role }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== role) return <Navigate to={`/${user.role}`} replace />
  return <Outlet />
}
