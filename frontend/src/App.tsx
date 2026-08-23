import { Routes, Route, Navigate } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { useAuth } from '@/lib/auth'
import Login from '@/pages/Login'
import AdminDashboard from '@/pages/admin/Dashboard'
import AdminClasses from '@/pages/admin/Classes'
import AdminUsers from '@/pages/admin/UsersPage'
import AdminBias from '@/pages/admin/Bias'
import AdminSettings from '@/pages/admin/SettingsPage'
import LecturerDashboard from '@/pages/lecturer/Dashboard'
import LiveSession from '@/pages/lecturer/LiveSession'
import LecturerHistory from '@/pages/lecturer/History'
import StudentDashboard from '@/pages/student/Dashboard'
import StudentEnrollment from '@/pages/student/Enrollment'

function Root() {
  const { user } = useAuth()
  return <Navigate to={user ? `/${user.role}` : '/login'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Root />} />
      <Route path="/login" element={<Login />} />

      <Route element={<ProtectedRoute role="admin" />}>
        <Route element={<AppShell />}>
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/admin/classes" element={<AdminClasses />} />
          <Route path="/admin/users" element={<AdminUsers />} />
          <Route path="/admin/bias" element={<AdminBias />} />
          <Route path="/admin/settings" element={<AdminSettings />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute role="lecturer" />}>
        <Route element={<AppShell />}>
          <Route path="/lecturer" element={<LecturerDashboard />} />
          <Route path="/lecturer/live" element={<LiveSession />} />
          <Route path="/lecturer/history" element={<LecturerHistory />} />
        </Route>
      </Route>

      <Route element={<ProtectedRoute role="student" />}>
        <Route element={<AppShell />}>
          <Route path="/student" element={<StudentDashboard />} />
          <Route path="/student/enrollment" element={<StudentEnrollment />} />
        </Route>
      </Route>

      <Route path="*" element={<Root />} />
    </Routes>
  )
}
