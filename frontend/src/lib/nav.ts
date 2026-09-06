import type { Role } from './api'

export interface NavItem {
  id: string
  label: string
  to: string
  icon: string
}

export const NAV_BY_ROLE: Record<Role, NavItem[]> = {
  admin: [
    { id: 'dashboard', label: 'Dashboard', to: '/admin', icon: 'LayoutDashboard' },
    { id: 'classes', label: 'Classes', to: '/admin/classes', icon: 'BookOpen' },
    { id: 'users', label: 'Users', to: '/admin/users', icon: 'Users' },
    { id: 'bias', label: 'Bias evaluation', to: '/admin/bias', icon: 'Scale' },
    { id: 'settings', label: 'Settings', to: '/admin/settings', icon: 'Settings' },
  ],
  lecturer: [
    { id: 'dashboard', label: 'Dashboard', to: '/lecturer', icon: 'LayoutDashboard' },
    { id: 'classes', label: 'Classes', to: '/lecturer/classes', icon: 'BookOpen' },
    { id: 'students', label: 'Students', to: '/lecturer/students', icon: 'Users' },
    { id: 'live', label: 'Live session', to: '/lecturer/live', icon: 'Video' },
    { id: 'history', label: 'History', to: '/lecturer/history', icon: 'History' },
  ],
  student: [
    { id: 'dashboard', label: 'Dashboard', to: '/student', icon: 'LayoutDashboard' },
    { id: 'courses', label: 'Courses', to: '/student/courses', icon: 'BookOpen' },
    { id: 'enrollment', label: 'Enrollment', to: '/student/enrollment', icon: 'ScanFace' },
    { id: 'settings', label: 'Settings', to: '/student/settings', icon: 'Settings' },
  ],
}
