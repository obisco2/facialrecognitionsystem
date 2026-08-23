import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, Thead, Tbody, Tr, Td } from '@/components/ui/table'
import { getBiasResults, runBiasEvaluation } from '@/lib/api'

const ACCENT = 'oklch(58% 0.20 256)'

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
  intersectional?: Record<string, GroupMetric>
  tolerance?: number
}

function toChartData(group?: Record<string, GroupMetric>) {
  return Object.entries(group ?? {}).map(([name, m]) => ({ name, accuracy: Math.round(m.accuracy * 100) }))
}

export default function AdminBias() {
  const qc = useQueryClient()
  const [running, setRunning] = useState(false)
  const { data } = useQuery({ queryKey: ['bias'], queryFn: getBiasResults })
  const metrics = data as Metrics | undefined

  const runMut = useMutation({
    mutationFn: runBiasEvaluation,
    onSuccess: () => {
      setRunning(true)
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ['bias'] })
        setRunning(false)
      }, 4000)
    },
  })

  if (!metrics || metrics.status === 'no_metrics') {
    return (
      <div>
        <h1 className="mb-1">Bias evaluation</h1>
        <p className="mb-6 text-sm text-ink-3">Gender Shades methodology — accuracy disparity across Fitzpatrick skin type and gender.</p>
        <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-[var(--radius-md)] border border-dashed border-rule-2">
          <p className="font-mono-label text-ink-3">{metrics?.msg ?? 'No evaluation run yet.'}</p>
          <Button onClick={() => runMut.mutate()} loading={runMut.isPending || running}>
            <RefreshCw className="size-4" /> Run evaluation
          </Button>
        </div>
      </div>
    )
  }

  const skinData = toChartData(metrics.by_skin_type)
  const genderData = toChartData(metrics.by_gender)
  const overall = metrics.overall

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="mb-1">Bias evaluation</h1>
          <p className="text-sm text-ink-3">Gender Shades methodology — tolerance {metrics.tolerance ?? '—'}.</p>
        </div>
        <Button variant="outline" onClick={() => runMut.mutate()} loading={runMut.isPending || running}>
          <RefreshCw className="size-4" /> Re-run
        </Button>
      </div>

      {overall && (
        <div className="mb-6 grid grid-cols-4 gap-4">
          <Stat label="Total images" value={String(overall.total_images)} />
          <Stat label="Detection rate" value={`${Math.round(overall.detection_rate * 100)}%`} />
          <Stat label="Recognition accuracy" value={`${Math.round(overall.recognition_accuracy * 100)}%`} />
          <Stat label="False negative rate" value={`${Math.round(overall.false_negative_rate * 100)}%`} />
        </div>
      )}

      <div className="mb-6 grid grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Accuracy by skin type</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={skinData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-rule)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: 'var(--color-ink-3)', fontSize: 12 }} axisLine={{ stroke: 'var(--color-rule)' }} tickLine={false} />
                <YAxis tick={{ fill: 'var(--color-ink-3)', fontSize: 12 }} axisLine={false} tickLine={false} unit="%" />
                <Tooltip contentStyle={{ background: 'var(--color-paper)', border: '1px solid var(--color-rule-2)', borderRadius: 6 }} />
                <Bar dataKey="accuracy" fill={ACCENT} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Accuracy by gender</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={genderData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-rule)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: 'var(--color-ink-3)', fontSize: 12 }} axisLine={{ stroke: 'var(--color-rule)' }} tickLine={false} />
                <YAxis tick={{ fill: 'var(--color-ink-3)', fontSize: 12 }} axisLine={false} tickLine={false} unit="%" />
                <Tooltip contentStyle={{ background: 'var(--color-paper)', border: '1px solid var(--color-rule-2)', borderRadius: 6 }} />
                <Bar dataKey="accuracy" fill={ACCENT} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Intersectional (skin type × gender)</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <Thead>
              <th>Group</th>
              <th>Count</th>
              <th>Detection rate</th>
              <th>Accuracy</th>
            </Thead>
            <Tbody>
              {Object.entries(metrics.intersectional ?? {}).map(([key, m]) => (
                <Tr key={key}>
                  <Td className="font-medium text-ink">{key}</Td>
                  <Td>{m.count}</Td>
                  <Td>{Math.round(m.detection_rate * 100)}%</Td>
                  <Td>{Math.round(m.accuracy * 100)}%</Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--radius-md)] border border-rule px-4 py-3">
      <p className="font-mono-label text-ink-3">{label}</p>
      <p className="mt-0.5 font-display text-xl font-semibold text-ink">{value}</p>
    </div>
  )
}
