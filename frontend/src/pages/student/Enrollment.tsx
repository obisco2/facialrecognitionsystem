import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Camera, Check, Trash2, ShieldCheck, CheckCircle2, Upload } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import {
  startEnrollment,
  captureEnrollmentSlot,
  deleteEnrollmentSlot,
  validateEnrollment,
  confirmEnrollment,
  uploadEnrollment,
  enrollmentCaptureUrl,
  videoFeedUrl,
  type EnrollmentSlotResult,
} from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { cn } from '@/lib/utils'

const SLOTS = [0, 1, 2, 3, 4]

export default function StudentEnrollment() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)
  const [started, setStarted] = useState(false)
  const [captured, setCaptured] = useState<Record<number, boolean>>({})
  const [previews, setPreviews] = useState<Record<number, string>>({})
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
    // Fetch the captured image directly from the saved file
    try {
      const res = await fetch(enrollmentCaptureUrl(user!.id, idx))
      if (res.ok) {
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        setPreviews((p) => ({ ...p, [idx]: url }))
      }
    } catch {
      // Preview not critical — slot still marked as captured
    }
  }

  async function handleDelete(idx: number) {
    await deleteEnrollmentSlot(user!.id, idx)
    setCaptured((c) => ({ ...c, [idx]: false }))
    setPreviews((p) => {
      const next = { ...p }
      if (next[idx]) URL.revokeObjectURL(next[idx])
      delete next[idx]
      return next
    })
    setResults(null)
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files || files.length === 0) return
    setBusy(true)
    try {
      await startEnrollment(user!.id, user!.full_name)
      const fileArray = Array.from(files).slice(0, 5)
      await uploadEnrollment(user!.id, fileArray)

      // Build previews from the uploaded files
      const filled: Record<number, boolean> = {}
      const newPreviews: Record<number, string> = {}
      fileArray.forEach((f, i) => {
        filled[i] = true
        newPreviews[i] = URL.createObjectURL(f)
      })
      setCaptured(filled)
      setPreviews(newPreviews)
      setStarted(true)
      setResults(null)
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function handleSnapReplace(idx: number) {
    // Start camera if not started, then capture into a specific slot
    if (!started) {
      setBusy(true)
      try {
        await startEnrollment(user!.id, user!.full_name)
        setStarted(true)
      } finally {
        setBusy(false)
      }
    }
    // Small delay to let the camera stream initialize
    await new Promise((r) => setTimeout(r, 300))
    await handleCapture(idx)
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

  async function handleReEnroll() {
    setBusy(true)
    try {
      await startEnrollment(user!.id, user!.full_name)
      setCaptured({})
      setPreviews({})
      setResults(null)
      setCanProceed(false)
      setStarted(true)
    } finally {
      setBusy(false)
    }
  }

  const stateFor = (idx: number) => results?.find((r) => r.slot === idx)

  // --- Already enrolled: show completion state ---
  if (user.face_enrolled && !started) {
    return (
      <div className="flex h-full flex-col">
        <h1 className="mb-1">Face enrollment</h1>
        <p className="mb-6 text-sm text-ink-3">Your facial recognition profile.</p>

        <Card className="max-w-lg border-success-ink/30 bg-success-tint">
          <CardContent className="flex flex-col items-center gap-4 py-8">
            <div className="flex size-14 items-center justify-center rounded-full bg-success text-success-ink">
              <CheckCircle2 className="size-7" />
            </div>
            <div className="text-center">
              <h2 className="text-lg font-semibold text-ink">Enrollment complete</h2>
              <p className="mt-1 text-sm text-ink-2">
                Your face data is registered in the system and will be used for attendance marking.
              </p>
            </div>
            <Button variant="outline" onClick={handleReEnroll}>
              Re-enroll face
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  // --- Enroll / re-enroll flow ---
  return (
    <div className="flex h-full flex-col">
      <h1 className="mb-1 shrink-0">Face enrollment</h1>
      <p className="mb-4 shrink-0 text-sm text-ink-3">Capture or upload 5 photos of your face — at least 3 must pass validation.</p>

      {!started ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-[var(--radius-lg)] bg-graphite">
          <Camera className="size-8 text-graphite-ink-2" />
          <div className="flex items-center gap-3">
            <Button onClick={handleStart} loading={busy}>
              <Camera className="size-4" /> Start camera
            </Button>
            <span className="text-sm text-graphite-ink-2">or</span>
            <Button variant="outline" className="border-graphite-rule text-graphite-ink hover:border-accent" onClick={() => fileRef.current?.click()} loading={busy}>
              <Upload className="size-4" /> Upload photos
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={handleUpload}
            />
          </div>
        </div>
      ) : (
        <div className="flex flex-1 flex-col gap-4 overflow-hidden rounded-[var(--radius-lg)] bg-graphite p-4">
          {/* Camera feed */}
          <div className="min-h-0 flex-1 overflow-hidden rounded-[var(--radius-md)] border border-graphite-rule bg-black">
            <img
              src={videoFeedUrl}
              alt="Enrollment camera feed"
              className="h-full w-full object-contain"
            />
          </div>

          {/* Slots with previews */}
          <div className="grid grid-cols-5 gap-2 shrink-0">
            {SLOTS.map((idx) => {
              const result = stateFor(idx)
              const hasPhoto = captured[idx]
              const previewUrl = previews[idx]
              return (
                <div key={idx} className="text-center">
                  <div
                    className={cn(
                      'group relative mb-1 flex aspect-square items-center justify-center overflow-hidden rounded-[var(--radius-sm)] border-2 border-dashed border-graphite-rule',
                      hasPhoto && 'border-solid border-accent bg-accent-tint',
                      result?.state === 'valid' && 'border-solid border-success bg-success-tint',
                      result?.state === 'warn' && 'border-solid border-warning bg-warning-tint',
                      result?.state === 'invalid' && 'border-solid border-danger bg-danger-tint',
                    )}
                  >
                    {previewUrl ? (
                      <img src={previewUrl} alt={`Slot ${idx + 1}`} className="h-full w-full object-cover" />
                    ) : hasPhoto ? (
                      <Check className="size-5 text-graphite-ink" />
                    ) : (
                      <span className="font-mono-label text-graphite-ink-2">{idx + 1}</span>
                    )}

                    {/* Overlay actions on hover when photo exists */}
                    {hasPhoto && (
                      <div className="absolute inset-0 flex items-center justify-center gap-1 bg-black/50 opacity-0 transition-opacity group-hover:opacity-100">
                        <button
                          onClick={() => handleSnapReplace(idx)}
                          title="Replace with camera"
                          className="flex size-7 items-center justify-center rounded bg-paper/20 text-paper hover:bg-paper/40"
                        >
                          <Camera className="size-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(idx)}
                          title="Delete"
                          className="flex size-7 items-center justify-center rounded bg-danger/40 text-paper hover:bg-danger/60"
                        >
                          <Trash2 className="size-3.5" />
                        </button>
                      </div>
                    )}
                  </div>

                  <div className="flex justify-center gap-1">
                    {!hasPhoto && (
                      <>
                        <button
                          onClick={() => handleCapture(idx)}
                          className="font-mono-label text-graphite-ink-2 hover:text-accent"
                        >
                          shoot
                        </button>
                        <span className="text-graphite-ink-2">·</span>
                        <button
                          onClick={() => {
                            // Trigger file input for single-slot upload
                            const input = document.createElement('input')
                            input.type = 'file'
                            input.accept = 'image/*'
                            input.onchange = async (e) => {
                              const file = (e.target as HTMLInputElement).files?.[0]
                              if (!file) return
                              if (!started) {
                                await startEnrollment(user!.id, user!.full_name)
                                setStarted(true)
                              }
                              setBusy(true)
                              try {
                                await uploadEnrollment(user!.id, [file])
                                setCaptured((c) => ({ ...c, [idx]: true }))
                                setPreviews((p) => ({ ...p, [idx]: URL.createObjectURL(file) }))
                                setResults(null)
                              } finally {
                                setBusy(false)
                              }
                            }
                            input.click()
                          }}
                          className="font-mono-label text-graphite-ink-2 hover:text-accent"
                        >
                          upload
                        </button>
                      </>
                    )}
                  </div>
                  {result && <p className="mt-0.5 text-[0.6rem] text-graphite-ink-2">{result.message}</p>}
                </div>
              )
            })}
          </div>

          {/* Actions */}
          <div className="flex shrink-0 items-center gap-3">
            <Button variant="outline" className="border-graphite-rule text-graphite-ink hover:border-accent" onClick={handleValidate} loading={busy}>
              <ShieldCheck className="size-4" /> Validate
            </Button>
            <Button variant="ghost" className="text-graphite-ink-2 hover:text-accent" onClick={() => fileRef.current?.click()}>
              <Upload className="size-3.5" /> Upload more
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={handleUpload}
            />
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
