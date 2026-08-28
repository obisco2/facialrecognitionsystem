import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Table, Thead, Tbody, Tr, Td } from '@/components/ui/table'
import { getClasses, getAttendanceHistoryRange, deleteAttendanceRecord, exportAttendanceData } from '@/lib/api'
import { showToast } from '@/components/ui/toast'
import { useAuth } from '@/lib/auth'

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}
function weekAgoStr() {
  const d = new Date()
  d.setDate(d.getDate() - 7)
  return d.toISOString().slice(0, 10)
}

export default function LecturerHistory() {
  const { user } = useAuth()
  const [classId, setClassId] = useState<number | null>(null)
  const [dateFrom, setDateFrom] = useState(weekAgoStr())
  const [dateTo, setDateTo] = useState(todayStr())
  const [exporting, setExporting] = useState(false)

  const { data: classes } = useQuery({
    queryKey: ['classes', user?.id],
    queryFn: () => getClasses(user?.id),
    enabled: !!user,
  })

  const { data: records, refetch } = useQuery({
    queryKey: ['history', classId, dateFrom, dateTo],
    queryFn: () => getAttendanceHistoryRange(classId!, dateFrom, dateTo),
    enabled: !!classId,
  })

  async function handleDelete(id: number) {
    try {
      await deleteAttendanceRecord(id)
      refetch()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Failed to delete record')
    }
  }

  async function handleExport(format: 'csv' | 'xlsx') {
    if (!classId) return
    setExporting(true)
    try {
      const { filename, content, mime } = await exportAttendanceData({ classId, dateFrom, dateTo, format })
      const blob = new Blob([Uint8Array.from(atob(content), (c) => c.charCodeAt(0))], { type: mime })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Failed to export data')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <h1 className="mb-1">Attendance history</h1>
      <p className="mb-6 text-sm text-ink-3">Filter by class and date range, then export.</p>

      <div className="mb-5 flex flex-wrap items-end gap-3">
        <div>
          <label className="mb-1.5 block text-sm font-medium text-ink-2">Class</label>
          <select
            value={classId ?? ''}
            onChange={(e) => setClassId(Number(e.target.value) || null)}
            className="h-10 rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
          >
            <option value="">Select class…</option>
            {classes?.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.code})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-ink-2">From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="h-10 rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-sm font-medium text-ink-2">To</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="h-10 rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
          />
        </div>
        <div className="flex gap-2 sm:ml-auto">
          <Button variant="outline" size="sm" onClick={() => handleExport('csv')} disabled={!classId} loading={exporting}>
            <Download className="size-3.5" /> CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleExport('xlsx')} disabled={!classId} loading={exporting}>
            <Download className="size-3.5" /> Excel
          </Button>
        </div>
      </div>

      {!classId && (
        <div className="flex h-40 items-center justify-center rounded-[var(--radius-md)] border border-dashed border-rule-2">
          <p className="font-mono-label text-ink-3">Select a class to view history</p>
        </div>
      )}

      {classId && (
        <Table>
          <Thead>
            <th>Student</th>
            <th>Date</th>
            <th>Time</th>
            <th>Method</th>
            <th>Confidence</th>
            <th />
          </Thead>
          <Tbody>
            {records?.map((r) => (
              <Tr key={r.id}>
                <Td className="font-medium text-ink">{r.full_name}</Td>
                <Td>{r.session_date}</Td>
                <Td>{r.timestamp}</Td>
                <Td className="font-mono-label">{r.method}</Td>
                <Td>{r.confidence != null ? r.confidence.toFixed(2) : '—'}</Td>
                <Td>
                  <button onClick={() => handleDelete(r.id)} className="text-ink-3 hover:text-danger" aria-label="Delete record">
                    <Trash2 className="size-4" />
                  </button>
                </Td>
              </Tr>
            ))}
            {records?.length === 0 && (
              <Tr>
                <Td colSpan={6} className="py-8 text-center text-ink-3">
                  No records in this range.
                </Td>
              </Tr>
            )}
          </Tbody>
        </Table>
      )}
    </div>
  )
}
