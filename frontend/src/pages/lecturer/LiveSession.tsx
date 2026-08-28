import { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Play, Square, UserPlus, CameraOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { getClasses, getUsers, startSession, stopSession, getLiveSession, logManualAttendance, videoFeedUrl, recognizeFrame } from '@/lib/api'
import type { User, RecognizeResult } from '@/lib/api'
import { showToast } from '@/components/ui/toast'
import { useAuth } from '@/lib/auth'

const RECOGNITION_INTERVAL = 1500 // ms between recognition frames

export default function LiveSession() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [classId, setClassId] = useState<number | null>(null)
  const [running, setRunning] = useState(false)
  const [starting, setStarting] = useState(false)
  const [showManual, setShowManual] = useState(false)
  const [manualMsg, setManualMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)
  const [manualMarked, setManualMarked] = useState<Set<number>>(new Set())

  // Browser camera fallback state (for VPS deployments)
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [cameraError, setCameraError] = useState<string | null>(null)
  const [cameraActive, setCameraActive] = useState(false)
  const [faces, setFaces] = useState<RecognizeResult[]>([])

  const [startTime, setStartTime] = useState<number | null>(null)
  const [sessionTime, setSessionTime] = useState('')
  const [elapsedTime, setElapsedTime] = useState('')

  useEffect(() => {
    if (running) {
      if (!startTime) {
        setStartTime(Date.now())
      }
    } else {
      setStartTime(null)
      setElapsedTime('')
    }
  }, [running, startTime])

  useEffect(() => {
    const interval = setInterval(() => {
      const now = new Date()
      setSessionTime(now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }))

      if (startTime) {
        const diffMs = Date.now() - startTime
        const diffSecs = Math.floor(diffMs / 1000)
        const hrs = Math.floor(diffSecs / 3600)
        const mins = Math.floor((diffSecs % 3600) / 60)
        const secs = diffSecs % 60
        const pad = (n: number) => String(n).padStart(2, '0')
        setElapsedTime(`${pad(hrs)}:${pad(mins)}:${pad(secs)}`)
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [startTime])

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
    onError: (err: Error, studentId) => {
      const s = students?.find((u: User) => u.id === studentId)
      setManualMsg({ type: 'err', text: err.message || `${s?.full_name ?? 'Student'} already marked today.` })
      setManualMarked((prev) => new Set(prev).add(studentId))
      setTimeout(() => setManualMsg(null), 2500)
    },
  })

  function isMarked(s: User) {
    if (manualMarked.has(s.id)) return true
    return live?.marked.some((m) => m.name === s.full_name) ?? false
  }

  // Start browser camera
  const startCamera = useCallback(async () => {
    setCameraError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
        setCameraActive(true)
      }
    } catch (err) {
      setCameraError(err instanceof Error ? err.message : 'Camera access denied')
      setCameraActive(false)
    }
  }, [])

  // Stop browser camera
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    setCameraActive(false)
    setFaces([])
  }, [])

  // Capture frame and send to backend for recognition
  const captureAndRecognize = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current || !cameraActive) return

    const video = videoRef.current
    const canvas = canvasRef.current
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.drawImage(video, 0, 0)
    const dataUrl = canvas.toDataURL('image/jpeg', 0.8)
    const base64 = dataUrl.split(',')[1]

    try {
      const result = await recognizeFrame(base64)
      setFaces(result.recognized)
    } catch {
      // Recognition failure is non-fatal — skip this frame
    }
  }, [cameraActive])

  // Run recognition loop (only if backend camera is inactive/missing)
  useEffect(() => {
    if (!running || !cameraActive || live?.camera_active) return
    const interval = setInterval(captureAndRecognize, RECOGNITION_INTERVAL)
    return () => clearInterval(interval)
  }, [running, cameraActive, captureAndRecognize, live?.camera_active])

  async function handleStart() {
    if (!classId || !user) return
    setStarting(true)
    try {
      await startSession(classId, user.id)
      setRunning(true)
      
      // Fetch status to check if backend camera opened successfully
      const liveData = await queryClient.fetchQuery({
        queryKey: ['live-session'],
        queryFn: getLiveSession,
      })
      
      if (liveData && !liveData.camera_active) {
        // Soft fallback to browser camera if server camera is unavailable (e.g. VPS)
        await startCamera()
      }
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Failed to start session')
    } finally {
      setStarting(false)
    }
  }

  async function handleStop() {
    try {
      await stopSession()
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Failed to stop session')
    }
    setRunning(false)
    setShowManual(false)
    setManualMarked(new Set())
    stopCamera()
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop())
      }
    }
  }, [])

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="mb-4 flex shrink-0 flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="mb-1">Live session</h1>
          <p className="text-sm text-ink-3">Start recognition against a class roster.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
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
        <div className="relative min-h-0 flex-1 overflow-hidden rounded-[var(--radius-md)] border border-graphite-rule bg-black">
          {running && (
            <div className="absolute top-4 left-4 z-10 flex flex-col gap-1 rounded bg-black/60 px-3 py-2 font-mono text-xs text-white backdrop-blur-sm">
              <div className="flex items-center gap-1.5 font-bold">
                <span className="h-2 w-2 rounded-full bg-accent animate-pulse" />
                <span>Elapsed: {elapsedTime || '00:00:00'}</span>
              </div>
              <div className="text-[10px] opacity-75">Local Time: {sessionTime}</div>
            </div>
          )}
          {running ? (
            live?.camera_active ? (
              <img src={videoFeedUrl} alt="Live camera feed" className="h-full w-full object-contain" />
            ) : (
              <>
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="h-full w-full object-contain"
                />
                <canvas ref={canvasRef} className="hidden" />

                {/* Face overlays */}
                {faces.map((face, i) => {
                  if (!face.box) return null
                  const { top, right, bottom, left } = face.box
                  return (
                    <div
                      key={i}
                      className={`absolute border-2 ${face.is_known ? 'border-green-400' : 'border-red-400'}`}
                      style={{
                        top: `${(top / 480) * 100}%`,
                        left: `${(left / 640) * 100}%`,
                        width: `${((right - left) / 640) * 100}%`,
                        height: `${((bottom - top) / 480) * 100}%`,
                      }}
                    >
                      <div
                        className={`absolute -top-6 left-0 whitespace-nowrap px-1 text-xs text-white ${
                          face.is_known ? 'bg-green-500/80' : 'bg-red-500/80'
                        }`}
                      >
                        {face.is_known
                          ? `${face.name} ${face.confidence?.toFixed(2)}`
                          : 'Unknown'}
                      </div>
                    </div>
                  )
                })}

                {/* Camera error overlay */}
                {cameraError && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80">
                    <CameraOff className="mb-2 size-8 text-danger" />
                    <p className="text-sm text-danger">{cameraError}</p>
                  </div>
                )}
              </>
            )
          ) : (
            <div className="flex h-full items-center justify-center">
              <p className="font-mono-label text-graphite-ink-2">Select a class and start a session</p>
            </div>
          )}
        </div>

        {/* Stats row */}
        {running && (
          <div className="grid grid-cols-2 gap-2 shrink-0 sm:grid-cols-3 sm:gap-3">
            <Stat label="Marked" value={String((live?.marked.length ?? 0) + manualMarked.size)} />
            <Stat label="Unknown" value={String(live?.camera_active ? (live?.unknown ?? 0) : faces.filter((f) => !f.is_known).length)} />
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
