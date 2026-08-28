import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  GraduationCap,
  Users,
  BookOpen,
  ScanFace,
  ClipboardCheck,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { getAdminStats, getBiasResults, runBiasEvaluation } from '@/lib/api'
import { showToast } from '@/components/ui/toast'
import { Link } from 'react-router-dom'

const ACCENT = 'oklch(58% 0.20 256)'
const SUCCESS = 'oklch(66% 0.15 152)'
const WARNING = 'oklch(78% 0.15 80)'

interface GroupMetric {
  count: number
  detection_rate: number
  accuracy: number
}

interface Metrics {
  status?: string
  msg?: string
  overall?: {
    total_images: number
    detection_rate: number
    recognition_accuracy: number
    false_negatives: number
    false_negative_rate: number
  }
  by_skin_type?: Record<string, GroupMetric>
  by_gender?: Record<string, GroupMetric>
  tolerance?: number
}

function toChartData(group?: Record<string, GroupMetric>) {
  return Object.entries(group ?? {}).map(([name, m]) => ({
    name,
    accuracy: Math.round(m.accuracy * 100),
  }))
}

export default function AdminDashboard() {
  const qc = useQueryClient()
  const [biasRunning, setBiasRunning] = useState(false)

  const { data: stats } = useQuery({ queryKey: ['admin-stats'], queryFn: getAdminStats })
  const { data: biasData } = useQuery({ queryKey: ['bias'], queryFn: getBiasResults })
  const bias = biasData as Metrics | undefined

  const biasMut = useMutation({
    mutationFn: runBiasEvaluation,
    onSuccess: () => {
      setBiasRunning(true)
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ['bias'] })
        setBiasRunning(false)
      }, 5000)
    },
    onError: (err: Error) => {
      showToast('error', err.message || 'Failed to run bias evaluation')
    },
  })

  const enrollmentRate = stats ? Math.round((stats.students_enrolled / Math.max(stats.students, 1)) * 100) : 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="font-display text-xl font-semibold text-ink sm:text-2xl">Admin dashboard</h1>
          <p className="mt-1 text-sm text-ink-3">System overview and quick actions.</p>
        </div>
        <div className="page-header-actions">
          <Link to="/admin/users">
            <Button variant="outline" size="sm">
              <Users className="size-4" /> Manage users
            </Button>
          </Link>
          <Link to="/admin/classes">
            <Button variant="outline" size="sm">
              <BookOpen className="size-4" /> Manage classes
            </Button>
          </Link>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          icon={GraduationCap}
          label="Students"
          value={stats?.students ?? '—'}
          accent="accent"
          detail={`${stats?.students_enrolled ?? 0} enrolled · ${stats?.students_pending ?? 0} pending`}
        />
        <StatCard
          icon={Users}
          label="Lecturers"
          value={stats?.lecturers ?? '—'}
          accent="accent"
          detail={`${stats?.classes ?? 0} classes assigned`}
        />
        <StatCard
          icon={ScanFace}
          label="Enrollment rate"
          value={`${enrollmentRate}%`}
          accent={enrollmentRate >= 80 ? 'success' : enrollmentRate >= 50 ? 'warning' : 'danger'}
          detail={`${stats?.students_enrolled ?? 0} of ${stats?.students ?? 0} students`}
        />
        <StatCard
          icon={ClipboardCheck}
          label="Attendance today"
          value={stats?.today_attendance ?? '—'}
          accent="success"
          detail={`${stats?.total_attendance ?? 0} total records`}
        />
      </div>

      {/* Enrollment progress + quick info */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Enrollment bar */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Student enrollment progress</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-3 flex items-baseline justify-between">
              <span className="font-display text-2xl font-semibold text-ink sm:text-3xl">{enrollmentRate}%</span>
              <span className="text-sm text-ink-3">
                {stats?.students_enrolled ?? 0} / {stats?.students ?? 0} students
              </span>
            </div>
            <div className="h-3 w-full overflow-hidden rounded-full bg-paper-3">
              <div
                className="h-full rounded-full transition-all duration-700 ease-out"
                style={{
                  width: `${enrollmentRate}%`,
                  background: enrollmentRate >= 80
                    ? `linear-gradient(90deg, ${SUCCESS}, oklch(60% 0.18 152))`
                    : enrollmentRate >= 50
                      ? `linear-gradient(90deg, ${WARNING}, oklch(72% 0.16 80))`
                      : `linear-gradient(90deg, oklch(58% 0.22 25), oklch(52% 0.22 25))`,
                }}
              />
            </div>
            <p className="mt-2 text-sm text-ink-3">
              {enrollmentRate >= 80
                ? 'Great — most students are ready for face recognition.'
                : enrollmentRate >= 50
                  ? 'Halfway there. Encourage pending students to enroll.'
                  : 'Low enrollment. Students need to complete face registration.'}
            </p>
          </CardContent>
        </Card>

        {/* Quick info */}
        <Card>
          <CardHeader>
            <CardTitle>Quick info</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <InfoRow label="Total users" value={String(stats?.total_users ?? '—')} />
            <InfoRow label="Active classes" value={String(stats?.classes ?? '—')} />
            <InfoRow label="Enrollments" value={String(stats?.total_enrollments ?? '—')} />
            <InfoRow label="Face records" value={String(stats?.students_enrolled ?? '—')} />
            <div className="pt-2">
              <Link to="/admin/settings" className="text-sm text-accent hover:underline">
                System settings →
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Bias evaluation */}
      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <CardTitle>Bias evaluation</CardTitle>
            <p className="mt-0.5 text-sm text-ink-3">
              Gender Shades methodology — accuracy disparity across skin type and gender.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => biasMut.mutate()}
            loading={biasMut.isPending || biasRunning}
          >
            <RefreshCw className="size-4" /> {bias?.overall ? 'Re-run' : 'Run evaluation'}
          </Button>
        </CardHeader>
        <CardContent>
          {!bias || bias.status === 'no_metrics' ? (
            <div className="flex flex-col items-center justify-center gap-3 py-10">
              <div className="flex size-12 items-center justify-center rounded-full bg-warning-tint">
                <AlertTriangle className="size-6 text-warning-ink" />
              </div>
              <p className="text-sm text-ink-3">{bias?.msg ?? 'No evaluation run yet.'}</p>
              <Button onClick={() => biasMut.mutate()} loading={biasMut.isPending || biasRunning}>
                <RefreshCw className="size-4" /> Run evaluation
              </Button>
            </div>
          ) : (
            <div className="space-y-5">
              {/* Overall metrics */}
              {bias.overall && (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  <MiniStat
                    label="Images"
                    value={String(bias.overall.total_images)}
                  />
                  <MiniStat
                    label="Detection"
                    value={`${Math.round(bias.overall.detection_rate * 100)}%`}
                    good={bias.overall.detection_rate >= 0.9}
                  />
                  <MiniStat
                    label="Accuracy"
                    value={`${Math.round(bias.overall.recognition_accuracy * 100)}%`}
                    good={bias.overall.recognition_accuracy >= 0.85}
                  />
                  <MiniStat
                    label="False neg rate"
                    value={`${Math.round(bias.overall.false_negative_rate * 100)}%`}
                    good={bias.overall.false_negative_rate <= 0.1}
                  />
                </div>
              )}

              {/* Charts */}
              {(Object.keys(bias.by_skin_type ?? {}).length > 0 ||
                Object.keys(bias.by_gender ?? {}).length > 0) && (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {Object.keys(bias.by_skin_type ?? {}).length > 0 && (
                    <div>
                      <p className="mb-2 font-mono-label text-ink-3">By skin type</p>
                      <ResponsiveContainer width="100%" height={180}>
                        <BarChart data={toChartData(bias.by_skin_type)}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-rule)" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: 'var(--color-ink-3)', fontSize: 11 }} axisLine={{ stroke: 'var(--color-rule)' }} tickLine={false} />
                          <YAxis domain={[0, 100]} tick={{ fill: 'var(--color-ink-3)', fontSize: 11 }} axisLine={false} tickLine={false} unit="%" />
                          <Tooltip
                            contentStyle={{
                              background: 'var(--color-paper)',
                              border: '1px solid var(--color-rule-2)',
                              borderRadius: 6,
                              fontSize: 12,
                            }}
                          />
                          <Bar dataKey="accuracy" fill={ACCENT} radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                  {Object.keys(bias.by_gender ?? {}).length > 0 && (
                    <div>
                      <p className="mb-2 font-mono-label text-ink-3">By gender</p>
                      <ResponsiveContainer width="100%" height={180}>
                        <BarChart data={toChartData(bias.by_gender)}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-rule)" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: 'var(--color-ink-3)', fontSize: 11 }} axisLine={{ stroke: 'var(--color-rule)' }} tickLine={false} />
                          <YAxis domain={[0, 100]} tick={{ fill: 'var(--color-ink-3)', fontSize: 11 }} axisLine={false} tickLine={false} unit="%" />
                          <Tooltip
                            contentStyle={{
                              background: 'var(--color-paper)',
                              border: '1px solid var(--color-rule-2)',
                              borderRadius: 6,
                              fontSize: 12,
                            }}
                          />
                          <Bar dataKey="accuracy" fill={ACCENT} radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              )}

              {/* View full report link */}
              <Link
                to="/admin/bias"
                className="inline-flex items-center gap-1.5 text-sm text-accent hover:underline"
              >
                View full report <ArrowRight className="size-3.5" />
              </Link>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

/* ── Sub-components ────────────────────────────────────────────── */

function StatCard({
  icon: Icon,
  label,
  value,
  accent,
  detail,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string | number
  accent: 'accent' | 'success' | 'warning' | 'danger'
  detail: string
}) {
  const tintMap = {
    accent: 'bg-accent-tint text-accent',
    success: 'bg-success-tint text-success-ink',
    warning: 'bg-warning-tint text-warning-ink',
    danger: 'bg-danger-tint text-danger',
  }
  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardContent className="flex items-start gap-3">
        <div className={`flex size-10 shrink-0 items-center justify-center rounded-[var(--radius-sm)] ${tintMap[accent]}`}>
          <Icon className="size-5" />
        </div>
        <div className="min-w-0">
          <p className="font-mono-label text-ink-3">{label}</p>
          <p className="font-display text-xl font-semibold text-ink sm:text-2xl">{value}</p>
          <p className="mt-0.5 truncate text-xs text-ink-3">{detail}</p>
        </div>
      </CardContent>
    </Card>
  )
}

function MiniStat({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="rounded-[var(--radius-sm)] border border-rule px-3 py-2">
      <p className="font-mono-label text-ink-3">{label}</p>
      <div className="mt-0.5 flex items-center gap-1.5">
        <p className="font-display text-lg font-semibold text-ink">{value}</p>
        {good !== undefined && (
          good ? (
            <CheckCircle2 className="size-3.5 text-success-ink" />
          ) : (
            <AlertTriangle className="size-3.5 text-warning-ink" />
          )
        )}
      </div>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-ink-3">{label}</span>
      <span className="font-medium text-ink">{value}</span>
    </div>
  )
}
