// Typed client for core/backend.py — mirrors its routes 1:1.

const BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL}/api`
  : '/api'

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function getAccessToken(): string | null {
  return localStorage.getItem('attendiq.access_token')
}
function getRefreshToken(): string | null {
  return localStorage.getItem('attendiq.refresh_token')
}
export function clearTokens() {
  localStorage.removeItem('attendiq.access_token')
  localStorage.removeItem('attendiq.refresh_token')
}
export function setTokens(access: string, refresh: string) {
  localStorage.setItem('attendiq.access_token', access)
  localStorage.setItem('attendiq.refresh_token', refresh)
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(opts.headers as Record<string, string> | undefined),
  }
  // Attach JWT unless caller already set Authorization
  const token = getAccessToken()
  if (token && !headers['Authorization'] && !headers['authorization']) {
    headers['Authorization'] = `Bearer ${token}`
  }
  // Only set JSON content-type if not FormData
  const isForm = opts.body instanceof FormData
  if (!isForm && !headers['Content-Type']) headers['Content-Type'] = 'application/json'

  let res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers,
  })
  // Auto-refresh on 401 once
  if (res.status === 401 && !path.includes('/auth/refresh') && !path.includes('/auth/login')) {
    const refresh = getRefreshToken()
    if (refresh) {
      try {
        const r = await fetch(`${BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refresh }),
        })
        if (r.ok) {
          const data = await r.json()
          setTokens(data.access_token, data.refresh_token)
          // retry original request with new token
          headers['Authorization'] = `Bearer ${data.access_token}`
          res = await fetch(`${BASE}${path}`, { ...opts, headers })
        } else {
          clearTokens()
        }
      } catch {
        clearTokens()
      }
    }
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      /* no json body */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

const get = <T>(path: string) => request<T>(path)
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined })
const put = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined })
const del = <T>(path: string) => request<T>(path, { method: 'DELETE' })

// --- Types ---

export type Role = 'admin' | 'lecturer' | 'student'

export interface User {
  id: number
  username: string
  role: Role
  full_name: string
  title?: string | null  // Dr., Professor, etc.
  student_id?: string | null
  email?: string | null
  department?: string | null
  faculty?: string | null
  level?: string | null
  face_enrolled?: number
  created_at?: string | null
}

export interface ClassSummary {
  class_id: number
  class_name: string
  class_code: string
  lecturer_name?: string | null
  schedule?: string | null
  sessions_present: number
  total_sessions: number
  percent: number
}

export interface SchoolClass {
  id: number
  name: string
  code: string
  lecturer_id: number
  schedule?: string | null
  room?: string | null
  department?: string | null
}

export interface AttendanceRecord {
  id: number
  student_id: number
  class_id: number
  full_name: string
  session_date: string
  timestamp: string
  method: 'face' | 'manual'
  confidence?: number | null
  marked_by?: number | null
}

export interface LiveSessionState {
  running: boolean
  mode: 'attendance' | 'enrollment' | 'test' | null
  marked: { time: string; name: string; conf: string }[]
  unknown: number
  date: string | null
  camera_active?: boolean
}

export interface EnrollmentSlotResult {
  slot: number
  state: 'empty' | 'invalid' | 'warn' | 'valid'
  message: string
}

export interface BiasMetrics {
  status?: string
  msg?: string
  [key: string]: unknown
}

export interface SystemConfig {
  camera_index: number
  frame_scale: number
  tolerance: number
  recognition_engine: string
  stream_url: string
}

// --- Auth ---
export type AuthResponse = User & { access_token: string; refresh_token: string; token_type: string }
export const login = (identifier: string, password: string) =>
  post<AuthResponse>('/auth/login', { identifier, password })
export const refreshTokens = (refresh_token: string) =>
  post<AuthResponse>('/auth/refresh', { refresh_token })
export const logout = (refresh_token: string) =>
  post<{ status: string }>('/auth/logout', { refresh_token })

// --- Users ---
export const getUsers = (role?: Role) => get<User[]>(`/users${role ? `?role=${role}` : ''}`)
export const createUser = (data: Omit<User, 'id' | 'face_enrolled'> & { password: string }) =>
  post<{ id: number; username: string; role: Role }>('/users', data)
export const updateUser = (id: number, data: Partial<User>) => put<{ status: string }>(`/users/${id}`, data)
export const resetPassword = (id: number, newPassword: string) =>
  post<{ status: string }>(`/users/${id}/reset-password`, { new_password: newPassword })
export const deleteUser = (id: number) => del<{ status: string }>(`/users/${id}`)

// --- Classes ---
export const getClasses = (lecturerId?: number) =>
  get<SchoolClass[]>(`/classes${lecturerId ? `?lecturer_id=${lecturerId}` : ''}`)
export const createClass = (
  lecturerId: number,
  data: { name: string; code: string; schedule?: string; room?: string; department?: string },
) => post<{ id: number }>(`/classes?lecturer_id=${lecturerId}`, data)
export const updateClass = (id: number, data: Partial<SchoolClass>) => put<{ status: string }>(`/classes/${id}`, data)
export const deleteClass = (id: number) => del<{ status: string }>(`/classes/${id}`)

export const getClassEnrollments = (classId: number) =>
  get<{ enrolled: User[]; unenrolled: User[] }>(`/classes/${classId}/enrollments`)
export const enrollStudent = (classId: number, studentId: number) =>
  post<{ status: string }>(`/classes/${classId}/enrollments?student_id=${studentId}`)
export const unenrollStudent = (classId: number, studentId: number) =>
  del<{ status: string }>(`/classes/${classId}/enrollments/${studentId}`)

// --- Attendance ---
export const getAttendanceHistory = (classId: number, date: string) =>
  get<AttendanceRecord[]>(`/attendance/history?class_id=${classId}&date=${date}`)
export const getAttendanceHistoryRange = (classId: number, dateFrom: string, dateTo: string) =>
  get<AttendanceRecord[]>(`/attendance/history-range?class_id=${classId}&date_from=${dateFrom}&date_to=${dateTo}`)
export const deleteAttendanceRecord = (id: number) => del<{ status: string }>(`/attendance/history/${id}`)
export const logManualAttendance = (studentId: number, classId: number, markedBy: number) =>
  post<{ status: string }>('/attendance/manual', { student_id: studentId, class_id: classId, marked_by: markedBy })
export const getStudentAttendance = (studentName: string) =>
  get<AttendanceRecord[]>(`/student/attendance/${encodeURIComponent(studentName)}`)
export const exportAttendanceData = (params: {
  classId: number
  date?: string
  dateFrom?: string
  dateTo?: string
  format?: 'csv' | 'xlsx'
}) => {
  const q = new URLSearchParams({ class_id: String(params.classId) })
  if (params.date) q.set('date', params.date)
  if (params.dateFrom) q.set('date_from', params.dateFrom)
  if (params.dateTo) q.set('date_to', params.dateTo)
  if (params.format) q.set('format', params.format)
  return get<{ filename: string; content: string; mime: string }>(`/attendance/export-data?${q}`)
}

// --- Live session ---
export const startSession = (classId: number, lecturerId: number, cameraSource?: string) => {
  const q = new URLSearchParams({ class_id: String(classId), lecturer_id: String(lecturerId) })
  if (cameraSource) q.set('camera_source', cameraSource)
  return post<{ status: string }>(`/session/start?${q}`)
}
export const stopSession = () => post<{ status: string }>('/session/stop')
export const getLiveSession = () => get<LiveSessionState>('/session/live')
export const videoFeedUrl = `${BASE}/session/video_feed`

// --- Browser-based recognition ---
export interface RecognizeResult {
  name: string | null
  confidence: number | null
  is_known: boolean
  box: { top: number; right: number; bottom: number; left: number }
}
export interface RecognizeFrameResponse {
  recognized: RecognizeResult[]
  total_faces: number
  known_faces: number
  unknown_faces: number
}
export const recognizeFrame = (frameBase64: string) =>
  post<RecognizeFrameResponse>('/recognize/frame', { frame: frameBase64 })

// --- Enrollment ---
export const startEnrollment = (userId: number, fullName: string, cameraSource?: string) => {
  const q = new URLSearchParams({ user_id: String(userId), full_name: fullName })
  if (cameraSource) q.set('camera_source', cameraSource)
  return post<{ status: string }>(`/enrollment/start?${q}`)
}
export const uploadEnrollment = (userId: number, files: File[], slotIdx?: number) => {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  const q = new URLSearchParams({ user_id: String(userId) })
  if (slotIdx !== undefined) q.set('slot_idx', String(slotIdx))
  return request<{ status: string; count: number }>(`/enrollment/upload?${q}`, {
    method: 'POST',
    body: form,
    headers: {},
  })
}
export const captureEnrollmentSlot = (userId: number, fullName: string, slotIdx: number) =>
  post<{ status: string; filepath: string }>(
    `/enrollment/capture?user_id=${userId}&full_name=${encodeURIComponent(fullName)}&slot_idx=${slotIdx}`,
  )
export const deleteEnrollmentSlot = (userId: number, slotIdx: number) =>
  del<{ status: string }>(`/enrollment/slot?user_id=${userId}&slot_idx=${slotIdx}`)
export const enrollmentCaptureUrl = (userId: number, slotIdx: number) =>
  `${BASE}/enrollment/capture/${userId}/${slotIdx}`
export const validateEnrollment = (userId: number) =>
  post<{ results: EnrollmentSlotResult[]; valid_count: number; can_proceed: boolean }>(
    `/enrollment/validate?user_id=${userId}`,
  )
export const startEnrollmentTest = (userId: number, fullName: string) =>
  post<{ status: string }>(`/enrollment/test/start?user_id=${userId}&full_name=${encodeURIComponent(fullName)}`)
export const confirmEnrollment = (userId: number, fullName: string) =>
  post<{ status: string }>(`/enrollment/confirm?user_id=${userId}&full_name=${encodeURIComponent(fullName)}`)

// --- Student summary ---
export const getStudentSummary = (studentId: number) =>
  get<ClassSummary[]>(`/student/summary/${studentId}`)

// --- Student retrain ---
export const retrainFaceModel = (userId: number, fullName: string) =>
  post<{ status: string }>(`/student/retrain?user_id=${userId}&full_name=${encodeURIComponent(fullName)}`)

// --- Config ---
export const getConfig = () => get<SystemConfig>('/config')
export const saveConfig = (data: SystemConfig) => post<{ status: string }>('/config', data)

// --- Admin stats ---
export interface AdminStats {
  total_users: number
  students: number
  students_enrolled: number
  students_pending: number
  lecturers: number
  classes: number
  total_attendance: number
  today_attendance: number
  total_enrollments: number
}
export const getAdminStats = () => get<AdminStats>('/admin/stats')

// --- Bias ---
export const runBiasEvaluation = () => post<{ status: string }>('/bias/evaluate')
export const getBiasResults = () => get<BiasMetrics>('/bias/results')

// --- Faculties & Departments ---
export interface Faculty {
  id: number
  name: string
}
export interface Department {
  id: number
  faculty_id: number
  name: string
  faculty_name?: string
}
export const getFaculties = () => get<Faculty[]>('/faculties')
export const createFaculty = (name: string) => post<{ id: number; status: string }>('/faculties', { name })
export const deleteFaculty = (id: number) => del<{ status: string }>(`/faculties/${id}`)

export const getDepartments = (facultyId?: number) => {
  const q = facultyId ? `?faculty_id=${facultyId}` : ''
  return get<Department[]>(`/departments${q}`)
}
export const createDepartment = (facultyId: number, name: string) =>
  post<{ id: number; status: string }>('/departments', { faculty_id: facultyId, name })
export const deleteDepartment = (id: number) => del<{ status: string }>(`/departments/${id}`)

// --- Liveness verification ---
export const verifyLiveness = (userId: number, files: File[]) => {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  return request<{ status: string; message: string }>(`/enrollment/liveness?user_id=${userId}`, {
    method: 'POST',
    body: form,
    headers: {},
  })
}

// --- Class blocks (lecturer control) ---
export const getBlocked = (classId: number) => get<{ id: number; student_id: number; full_name: string; matric: string; reason?: string }[]>(`/classes/${classId}/blocks`)
export const blockStudent = (classId: number, studentId: number, reason?: string) =>
  post<{ status: string }>(`/classes/${classId}/blocks`, { student_id: studentId, reason })
export const unblockStudent = (classId: number, studentId: number) =>
  del<{ status: string }>(`/classes/${classId}/blocks/${studentId}`)
export const getUnassigned = () => get<SchoolClass[]>(`/classes/unassigned`)
export const assignSelf = (classId: number, lecturerId: number) =>
  post<{ status: string }>(`/classes/${classId}/assign`, { lecturer_id: lecturerId })

// --- Security Q/PIN ---
export const setupSecurity = (question: string, answer: string, pin: string) =>
  post<{ status: string }>(`/auth/setup-security`, { question, answer, pin })
export const getSecurityQuestion = (identifier: string) =>
  get<{ question: string }>(`/auth/security-question?identifier=${encodeURIComponent(identifier)}`)
export const resetWithSecurity = (identifier: string, new_password: string, answer?: string, pin?: string) =>
  post<{ status: string }>(`/auth/reset-with-security`, { identifier, new_password, answer, pin })

export { ApiError }
