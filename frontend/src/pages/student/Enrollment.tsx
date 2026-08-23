import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Camera, Check, Trash2, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  startEnrollment,
  captureEnrollmentSlot,
  deleteEnrollmentSlot,
  validateEnrollment,
  confirmEnrollment,
  videoFeedUrl,
  type EnrollmentSlotResult,
} from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { cn } from '@/lib/utils'

const SLOTS = [0, 1, 2, 3, 4]

export default function StudentEnrollment() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const [started, setStarted] = useState(false)
  const [captured, setCaptured] = useState<Record<number, boolean>>({})
  const [results, setResults] = useState<EnrollmentSlotResult[] | null>(null)
  const [canProceed, setCanProceed] = useState(false)
  const [busy, setBusy] = useState(false)

  if (!user) return null

  async function handleStart() {
    setBusy(true)
    try {
      await startEnrollment(user!.id, user!.full_name)
      setStarted(true)
    } finally {
      setBusy(false)
    }
  }

  async function handleCapture(idx: number) {
    await captureEnrollmentSlot(user!.id, user!.full_name, idx)
    setCaptured((c) => ({ ...c, [idx]: true }))
    setResults(null)
  }

  async function handleDelete(idx: number) {
    await deleteEnrollmentSlot(user!.id, idx)
    setCaptured((c) => ({ ...c, [idx]: false }))
    setResults(null)
  }

  async function handleValidate() {
    setBusy(true)
    try {
      const r = await validateEnrollment(user!.id)
      setResults(r.results)
      setCanProceed(r.can_proceed)
    } finally {
      setBusy(false)
    }
  }

  async function handleConfirm() {
    setBusy(true)
    try {
      await confirmEnrollment(user!.id, user!.full_name)
      setUser({ ...user!, face_enrolled: 1 })
      navigate('/student')
    } finally {
      setBusy(false)
    }
  }

  const stateFor = (idx: number) => results?.find((r) => r.slot === idx)

  return (
    <div>
      <h1 className="mb-1">Face enrollment</h1>
      <p className="mb-6 text-sm text-ink-3">Capture 5 photos of your face — at least 3 must pass validation.</p>

      {!started ? (
        <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-[var(--radius-lg)] bg-graphite">
          <Camera className="size-8 text-graphite-ink-2" />
          <Button onClick={handleStart} loading={busy}>
            Start camera
          </Button>
        </div>
      ) : (
        <div className="rounded-[var(--radius-lg)] bg-graphite p-5">
          <div className="mb-4 overflow-hidden rounded-[var(--radius-md)] border border-graphite-rule bg-black">
            <img src={videoFeedUrl} alt="Enrollment camera feed" className="aspect-video w-full object-cover" />
          </div>

          <div className="grid grid-cols-5 gap-3">
            {SLOTS.map((idx) => {
              const result = stateFor(idx)
              return (
                <div key={idx} className="text-center">
                  <div
                    className={cn(
                      'mb-1.5 flex aspect-square items-center justify-center rounded-[var(--radius-sm)] border-2 border-dashed border-graphite-rule',
                      captured[idx] && 'border-solid border-accent bg-accent-tint',
                      result?.state === 'valid' && 'border-solid border-success bg-success-tint',
                      result?.state === 'warn' && 'border-solid border-warning bg-warning-tint',
                      result?.state === 'invalid' && 'border-solid border-danger bg-danger-tint',
                    )}
                  >
                    {captured[idx] ? <Check className="size-5 text-graphite-ink" /> : <span className="font-mono-label text-graphite-ink-2">{idx + 1}</span>}
                  </div>
                  <div className="flex justify-center gap-1">
                    <button
                      onClick={() => handleCapture(idx)}
                      className="font-mono-label text-graphite-ink-2 hover:text-accent"
                    >
                      shoot
                    </button>
                    {captured[idx] && (
                      <button onClick={() => handleDelete(idx)} className="text-graphite-ink-2 hover:text-danger">
                        <Trash2 className="size-3" />
                      </button>
                    )}
                  </div>
                  {result && <p className="mt-1 text-[0.6rem] text-graphite-ink-2">{result.message}</p>}
                </div>
              )
            })}
          </div>

          <div className="mt-5 flex items-center gap-3">
            <Button variant="outline" className="border-graphite-rule text-graphite-ink hover:border-accent" onClick={handleValidate} loading={busy}>
              <ShieldCheck className="size-4" /> Validate
            </Button>
            {results && (
              <Badge variant={canProceed ? 'success' : 'danger'} dot>
                {canProceed ? 'Ready to confirm' : 'Needs at least 3 valid photos'}
              </Badge>
            )}
            <Button onClick={handleConfirm} disabled={!canProceed} loading={busy} className="ml-auto">
              Confirm enrollment
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
