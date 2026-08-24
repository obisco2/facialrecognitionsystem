import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Play, Square, UserPlus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { getClasses, getUsers, startSession, stopSession, getLiveSession, logManualAttendance, videoFeedUrl } from '@/lib/api'
import type { User } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export default function LiveSession() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [classId, setClassId] = useState<number | null>(null)
  const [running, setRunning] = useState(false)
  const [starting, setStarting] = useState(false)
  const [showManual, setShowManual] = useState(false)
  const [manualMsg, setManualMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)
  const [manualMarked, setManualMarked] = useState<Set<number>>(new Set())

  const { data: classes } = useQuery({
    queryKey: ['classes', user?.id],
    queryFn: () => getClasses(user?.id),
    enabled: !!user,
  })

  const { data: students } = useQuery({
    queryKey: ['users', 'student'],
    queryFn: () => getUsers('student'),
    enabled: showManual,
  })

  const { data: live } = useQuery({
    queryKey: ['live-session'],
    queryFn: getLiveSession,
    enabled: running,
    refetchInterval: running ? 1500 : false,
  })

  const manualMut = useMutation({
    mutationFn: (studentId: number) =>
      logManualAttendance(studentId, classId!, user!.id),
    onSuccess: (_data, studentId) => {
      queryClient.invalidateQueries({ queryKey: ['live-session'] })
      setManualMarked((prev) => new Set(prev).add(studentId))
      const s = students?.find((u: User) => u.id === studentId)
      setManualMsg({ type: 'ok', text: `${s?.full_name ?? 'Student'} marked.` })
      setTimeout(() => setManualMsg(null), 2500)
    },
    onError: (_err, studentId) => {
      const s = students?.find((u: User) => u.id === studentId)
      setManualMsg({ type: 'err', text: `${s?.full_name ?? 'Student'} already marked today.` })
      setManualMarked((prev) => new Set(prev).add(studentId))
      setTimeout(() => setManualMsg(null), 2500)
    },
  })

  function isMarked(s: User) {
    if (manualMarked.has(s.id)) return true
    return live?.marked.some((m) => m.name === s.full_name) ?? false
  }

  async function handleStart() {
    if (!classId || !user) return
    setStarting(true)
    try {
      await startSession(classId, user.id)
      setRunning(true)
    } finally {
      setStarting(false)
    }
  }

  async function handleStop() {
    await stopSession()
    setRunning(false)
    setShowManual(false)
    setManualMarked(new Set())
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="mb-4 flex shrink-0 items-center justify-between">
        <div>
          <h1 className="mb-1">Live session</h1>
          <p className="text-sm text-ink-3">Start recognition against a class roster.</p>
        </div>
        <div className="flex items-center gap-2">
          {!running ? (
            <>
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
              <Button onClick={handleStart} disabled={!classId} loading={starting}>
                <Play className="size-4" /> Start session
              </Button>
            </>
          ) : (
            <Button variant="danger" onClick={handleStop}>
              <Square className="size-4" /> Stop session
            </Button>
          )}
          {running && (
            <Badge variant={live?.running ? 'success' : 'neutral'} dot>
              {live?.running ? 'LIVE' : 'CONNECTING'}
            </Badge>
          )}
        </div>
      </div>

      {/* Main panel */}
      <div className="flex min-h-0 flex-1 flex-col gap-4 rounded-[var(--radius-lg)] bg-graphite p-4">
        {/* Camera feed */}
        <div className="min-h-0 flex-1 overflow-hidden rounded-[var(--radius-md)] border border-graphite-rule bg-black">
          {running ? (
            <img src={videoFeedUrl} alt="Live camera feed" className="h-full w-full object-contain" />
          ) : (
            <div className="flex h-full items-center justify-center">
              <p className="font-mono-label text-graphite-ink-2">Select a class and start a session</p>
            </div>
          )}
        </div>

        {/* Stats row */}
        {running && (
          <div className="grid grid-cols-3 gap-3 shrink-0">
            <Stat label="Marked" value={String((live?.marked.length ?? 0) + manualMarked.size)} />
            <Stat label="Unknown" value={String(live?.unknown ?? 0)} />
            <Stat label="Session date" value={live?.date ?? '—'} />
          </div>
        )}

        {/* Marked list */}
        {running && (live?.marked.length ?? 0) > 0 && (
          <ul className="max-h-40 space-y-1.5 overflow-y-auto shrink-0">
            {live!.marked.slice().reverse().map((m, i) => (
              <li
                key={i}
                className="flex items-center justify-between rounded-[var(--radius-sm)] border border-graphite-rule bg-graphite-2 px-3 py-2"
              >
                <span className="text-sm text-graphite-ink">{m.name}</span>
                <span className="font-mono-label text-graphite-ink-2">
                  {m.time} · conf {m.conf}
                </span>
              </li>
            ))}
          </ul>
        )}

        {/* Manual attendance */}
        {running && (
          <div className="shrink-0 space-y-3">
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                className="border-graphite-rule text-graphite-ink hover:border-accent"
                onClick={() => setShowManual(!showManual)}
              >
                <UserPlus className="size-3.5" /> {showManual ? 'Close' : 'Log manually'}
              </Button>
              {manualMsg && (
                <span className={`text-sm ${manualMsg.type === 'ok' ? 'text-success-ink' : 'text-danger'}`}>
                  {manualMsg.text}
                </span>
              )}
            </div>

            {showManual && (
              <div className="max-h-48 space-y-1.5 overflow-y-auto rounded-[var(--radius-sm)] border border-graphite-rule bg-graphite-2 p-2">
                {students?.map((s: User) => {
                  const marked = isMarked(s)
                  return (
                    <button
                      key={s.id}
                      onClick={() => !marked && manualMut.mutate(s.id)}
                      disabled={marked || manualMut.isPending}
                      className={`flex w-full items-center justify-between rounded px-3 py-2 text-left text-sm ${
                        marked
                          ? 'cursor-default text-graphite-ink-2'
                          : 'text-graphite-ink hover:bg-graphite-rule/50'
                      }`}
                    >
                      <span>{s.full_name}</span>
                      {marked ? (
                        <Badge variant="success" dot>marked</Badge>
                      ) : (
                        <span className="font-mono-label text-graphite-ink-2">tap to mark</span>
                      )}
                    </button>
                  )
                })}
                {students?.length === 0 && (
                  <p className="py-2 text-center text-sm text-graphite-ink-2">No students found.</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--radius-sm)] border border-graphite-rule bg-graphite-2 px-3 py-2.5">
      <p className="font-mono-label text-graphite-ink-2">{label}</p>
      <p className="mt-0.5 font-display text-lg font-semibold text-graphite-ink">{value}</p>
    </div>
  )
}
