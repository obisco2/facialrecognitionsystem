import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Play, Square, UserPlus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { getClasses, startSession, stopSession, getLiveSession, videoFeedUrl } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export default function LiveSession() {
  const { user } = useAuth()
  const [classId, setClassId] = useState<number | null>(null)
  const [running, setRunning] = useState(false)
  const [starting, setStarting] = useState(false)
  const pollRef = useRef<number | null>(null)

  const { data: classes } = useQuery({
    queryKey: ['classes', user?.id],
    queryFn: () => getClasses(user?.id),
    enabled: !!user,
  })

  const { data: live } = useQuery({
    queryKey: ['live-session'],
    queryFn: getLiveSession,
    enabled: running,
    refetchInterval: running ? 1500 : false,
  })

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current)
    }
  }, [])

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
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
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
        </div>
      </div>

      {/* The one dark graphite band — the instrument-panel moment */}
      <div className="rounded-[var(--radius-lg)] bg-graphite p-5">
        <div className="mb-3 flex items-center justify-between">
          <span className="font-mono-label text-graphite-ink-2">Camera feed</span>
          {running && (
            <Badge variant={live?.running ? 'success' : 'neutral'} dot>
              {live?.running ? 'LIVE' : 'CONNECTING'}
            </Badge>
          )}
        </div>

        <div className="overflow-hidden rounded-[var(--radius-md)] border border-graphite-rule bg-black">
          {running ? (
            <img src={videoFeedUrl} alt="Live camera feed" className="aspect-video w-full object-cover" />
          ) : (
            <div className="flex aspect-video items-center justify-center">
              <p className="font-mono-label text-graphite-ink-2">Select a class and start a session</p>
            </div>
          )}
        </div>

        {running && (
          <div className="mt-4 grid grid-cols-3 gap-3">
            <Stat label="Marked" value={String(live?.marked.length ?? 0)} />
            <Stat label="Unknown" value={String(live?.unknown ?? 0)} />
            <Stat label="Session date" value={live?.date ?? '—'} />
          </div>
        )}

        {running && (live?.marked.length ?? 0) > 0 && (
          <ul className="mt-4 space-y-1.5">
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

        {running && (
          <div className="mt-4">
            <Button variant="outline" size="sm" className="border-graphite-rule text-graphite-ink hover:border-accent">
              <UserPlus className="size-3.5" /> Log manually
            </Button>
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
