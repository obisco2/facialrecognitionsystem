import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Camera, Check, Trash2, ShieldCheck, CheckCircle2, Upload, CameraOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import {
  startEnrollment,
  uploadEnrollment,
  validateEnrollment,
  confirmEnrollment,
  verifyLiveness,
  type EnrollmentSlotResult,
} from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { showToast } from '@/components/ui/toast'
import { cn } from '@/lib/utils'

const SLOTS = [0, 1, 2, 3, 4]

export default function StudentEnrollment() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [started, setStarted] = useState(false)
  const [captured, setCaptured] = useState<Record<number, boolean>>({})
  const [previews, setPreviews] = useState<Record<number, string>>({})
  const [results, setResults] = useState<EnrollmentSlotResult[] | null>(null)
  const [canProceed, setCanProceed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [cameraError, setCameraError] = useState<string | null>(null)
  const [cameraActive, setCameraActive] = useState(false)
  const [cameraDevices, setCameraDevices] = useState<MediaDeviceInfo[]>([])
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('')

  // Liveness validation states
  const [livenessOpen, setLivenessOpen] = useState(false)
  const [livenessStep, setLivenessStep] = useState<'idle' | 'ready' | 'scanning' | 'verifying' | 'success'>('idle')
  const [livenessError, setLivenessError] = useState<string | null>(null)
  const [livenessVerified, setLivenessVerified] = useState(false)
  const [scanProgress, setScanProgress] = useState(0)

  if (!user) return null

  // Enumerate camera devices
  const enumerateCameras = useCallback(async () => {
    try {
      const tmp = await navigator.mediaDevices.getUserMedia({ video: true })
      tmp.getTracks().forEach(t => t.stop())
      const devices = await navigator.mediaDevices.enumerateDevices()
      const cams = devices.filter(d => d.kind === 'videoinput')
      setCameraDevices(cams)
      if (cams.length && !selectedDeviceId) setSelectedDeviceId(cams[0].deviceId)
    } catch { /* permission denied */ }
  }, [selectedDeviceId])

  useEffect(() => {
    enumerateCameras()
    const h = () => enumerateCameras()
    navigator.mediaDevices?.addEventListener?.('devicechange', h)
    return () => navigator.mediaDevices?.removeEventListener?.('devicechange', h)
  }, [enumerateCameras])

  // Start browser camera — respects selectedDeviceId (external USB)
  const startCamera = useCallback(async (deviceId?: string) => {
    const targetId = deviceId ?? selectedDeviceId
    setCameraError(null)
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
    try {
      const constraints: MediaStreamConstraints = targetId
        ? { video: { deviceId: { exact: targetId }, width: 640, height: 480 } }
        : { video: { width: 640, height: 480, facingMode: 'user' } }
      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      streamRef.current = stream
      
      const bindStream = async () => {
        const videoEl = videoRef.current || document.querySelector('video')
        if (videoEl) {
          videoEl.srcObject = stream
          try {
            await videoEl.play()
            setCameraActive(true)
            return true
          } catch (e) {
            console.error('Play error:', e)
          }
        }
        return false
      }

      const bound = await bindStream()
      if (!bound) {
        // Retry shortly in case ref resolution lags behind DOM render paint
        setTimeout(async () => {
          const rebound = await bindStream()
          if (!rebound) {
            setCameraError('Camera display container not found. Please refresh.')
          }
        }, 200)
      }
    } catch (err) {
      setCameraError(err instanceof Error ? err.message : 'Camera access denied')
      setCameraActive(false)
    }
  }, [selectedDeviceId])

  // Stop browser camera
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    setCameraActive(false)
  }, [])

  // Capture frame from browser camera
  const captureFrame = useCallback((): string | null => {
    if (!videoRef.current || !canvasRef.current || !cameraActive) return null
    const video = videoRef.current
    const canvas = canvasRef.current
    
    const MAX_DIM = 800
    let w = video.videoWidth
    let h = video.videoHeight
    if (w > MAX_DIM || h > MAX_DIM) {
      const ratio = Math.min(MAX_DIM / w, MAX_DIM / h)
      w = Math.round(w * ratio)
      h = Math.round(h * ratio)
    }
    
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.drawImage(video, 0, 0, w, h)
    return canvas.toDataURL('image/jpeg', 0.8).split(',')[1]
  }, [cameraActive])

  // Cleanup on unmount
  useEffect(() => {
    if (started) {
      startCamera()
    } else {
      stopCamera()
    }
  }, [started, startCamera, stopCamera])

  async function handleStart() {
    setBusy(true)
    try {
      await startEnrollment(user!.id, user!.full_name)
      setStarted(true)
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Failed to start enrollment')
    } finally {
      setBusy(false)
    }
  }

  async function handleCapture(idx: number) {
    // Capture frame from browser camera and upload
    const base64 = captureFrame()
    if (!base64) {
      setCameraError('Camera not ready. Please wait a moment.')
      return
    }

    // Convert base64 to File and upload
    const byteString = atob(base64)
    const ab = new ArrayBuffer(byteString.length)
    const ia = new Uint8Array(ab)
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i)
    }
    const blob = new Blob([ab], { type: 'image/jpeg' })
    const file = new File([blob], `capture_${idx}.jpg`, { type: 'image/jpeg' })

    setBusy(true)
    try {
      await uploadEnrollment(user!.id, [file], idx)
      setCaptured((c) => ({ ...c, [idx]: true }))
      setPreviews((p) => ({ ...p, [idx]: URL.createObjectURL(blob) }))
      setResults(null)
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Failed to upload photo')
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete(idx: number) {
    setCaptured((c) => {
      const next = { ...c }
      delete next[idx]
      return next
    })
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
      for (let i = 0; i < fileArray.length; i++) {
        await uploadEnrollment(user!.id, [fileArray[i]], i)
      }

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
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Failed to upload photos')
    } finally {
      setBusy(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop())
      }
    }
  }, [])

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
    await new Promise((r) => setTimeout(r, 600))
    await handleCapture(idx)
  }

  async function handleValidate() {
    setBusy(true)
    try {
      const r = await validateEnrollment(user!.id)
      setResults(r.results)
      setCanProceed(r.can_proceed)
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Failed to validate enrollment')
    } finally {
      setBusy(false)
    }
  }

  async function handleConfirm() {
    setBusy(true)
    try {
      stopCamera()
      await confirmEnrollment(user!.id, user!.full_name)
      setUser({ ...user!, face_enrolled: 1 })
      navigate('/student')
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Failed to confirm enrollment')
    } finally {
      setBusy(false)
    }
  }

  function snapFrameToFile(name: string): File | null {
    if (!videoRef.current || !canvasRef.current || !cameraActive) return null
    const video = videoRef.current
    const canvas = canvasRef.current
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.drawImage(video, 0, 0)
    const dataUrl = canvas.toDataURL('image/jpeg', 0.8)
    const base64 = dataUrl.split(',')[1]

    const byteString = atob(base64)
    const ab = new ArrayBuffer(byteString.length)
    const ia = new Uint8Array(ab)
    for (let i = 0; i < byteString.length; i++) {
      ia[i] = byteString.charCodeAt(i)
    }
    const blob = new Blob([ab], { type: 'image/jpeg' })
    return new File([blob], `${name}.jpg`, { type: 'image/jpeg' })
  }

  async function startLivenessScan() {
    setLivenessError(null)
    setLivenessStep('scanning')
    setScanProgress(0)

    const files: File[] = []
    
    for (let i = 0; i < 3; i++) {
      await new Promise((resolve) => setTimeout(resolve, 400))
      const f = snapFrameToFile(`live_frame_${i}`)
      if (f) {
        files.push(f)
      }
      setScanProgress(i + 1)
    }

    if (files.length < 3) {
      setLivenessStep('ready')
      setLivenessError('Liveness capture failed. Please make sure your camera is active and focused.')
      return
    }

    setLivenessStep('verifying')
    try {
      await verifyLiveness(user!.id, files)
      setLivenessStep('success')
      setLivenessVerified(true)
      showToast('success', 'Liveness verified successfully!')
    } catch (err) {
      setLivenessStep('ready')
      setLivenessError(err instanceof Error ? err.message : 'Liveness scan failed. Please try again.')
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
    } catch (err) {
      showToast('error', err instanceof Error ? err.message : 'Failed to re-enroll')
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
        <div className="flex flex-1 flex-col items-center justify-center gap-4 rounded-[var(--radius-lg)] bg-graphite p-6">
          <Camera className="size-8 text-graphite-ink-2" />
          <div className="w-full max-w-md rounded-[var(--radius-md)] border border-warning-ink/30 bg-warning-tint p-4 text-left">
            <p className="mb-2 text-sm font-semibold text-warning-ink">📸 Photo rules — read before you start</p>
            <ul className="list-disc space-y-1 pl-5 text-xs leading-relaxed text-warning-ink">
              <li><strong>No accessories:</strong> remove sunglasses, caps, helmets, face masks, heavy makeup.</li>
              <li>Face the camera directly, neutral expression, eyes open.</li>
              <li>Use a plain background with even front lighting — no backlight or harsh shadows.</li>
              <li>Keep your whole face inside the frame, close enough to fill most of it.</li>
              <li>Photos that break these rules fail validation and hurt recognition later.</li>
            </ul>
          </div>
          <div className="flex flex-col items-center gap-3 sm:flex-row">
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
          {cameraDevices.length > 1 && (
            <div className="flex items-center gap-2">
              <label className="text-xs text-graphite-ink-2">Camera source:</label>
              <select
                value={selectedDeviceId}
                onChange={(e) => { setSelectedDeviceId(e.target.value); startCamera(e.target.value) }}
                className="h-8 rounded border border-graphite-rule bg-graphite-2 px-2 text-sm text-ink"
              >
                {cameraDevices.map(d => (
                  <option key={d.deviceId} value={d.deviceId}>{d.label || `Camera ${d.deviceId.slice(0,6)}`}</option>
                ))}
              </select>
            </div>
          )}
          {/* Camera feed */}
          <div className="relative min-h-0 flex-1 overflow-hidden rounded-[var(--radius-md)] border border-graphite-rule bg-black">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="h-full w-full object-contain"
            />
            <canvas ref={canvasRef} className="hidden" />

            {/* Camera error overlay */}
            {cameraError && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80">
                <CameraOff className="mb-2 size-8 text-danger" />
                <p className="text-sm text-danger">{cameraError}</p>
              </div>
            )}

            {/* Capture indicator */}
            {busy && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                <div className="size-8 animate-spin rounded-full border-2 border-white border-t-transparent" />
              </div>
            )}
          </div>

          {/* Slots with previews */}
          <div className="grid grid-cols-5 gap-1.5 shrink-0 sm:gap-2">
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
                      <div className="flex flex-col items-center gap-1.5 p-1 text-center">
                        <span className="font-mono-label text-[10px] text-graphite-ink-3">Slot {idx + 1}</span>
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              handleCapture(idx)
                            }}
                            title="Shoot snapshot"
                            className="flex size-6 items-center justify-center rounded bg-paper/10 text-graphite-ink hover:bg-paper/20 hover:text-accent"
                          >
                            <Camera className="size-3.5" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
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
                                  await uploadEnrollment(user!.id, [file], idx)
                                  setCaptured((c) => ({ ...c, [idx]: true }))
                                  setPreviews((p) => ({ ...p, [idx]: URL.createObjectURL(file) }))
                                  setResults(null)
                                } finally {
                                  setBusy(false)
                                }
                              }
                              input.click()
                            }}
                            title="Upload photo"
                            className="flex size-6 items-center justify-center rounded bg-paper/10 text-graphite-ink hover:bg-paper/20 hover:text-accent"
                          >
                            <Upload className="size-3.5" />
                          </button>
                        </div>
                      </div>
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

                  <div className="flex justify-center gap-1"></div>
                  {result && <p className="mt-0.5 text-[0.6rem] text-graphite-ink-2">{result.message}</p>}
                </div>
              )
            })}
          </div>

          {/* Actions */}
          <div className="flex flex-wrap shrink-0 items-center gap-2 sm:gap-3">
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
                {canProceed ? (livenessVerified ? 'Liveness verified — ready' : 'Validated — liveness check required') : 'Needs at least 3 valid photos'}
              </Badge>
            )}
            {canProceed && !livenessVerified ? (
              <Button
                onClick={() => {
                  setLivenessOpen(true)
                  setLivenessStep('ready')
                  setLivenessError(null)
                }}
                className="ml-auto"
              >
                Verify Liveness
              </Button>
            ) : (
              <Button onClick={handleConfirm} disabled={!canProceed || !livenessVerified} loading={busy} className="ml-auto">
                Confirm enrollment
              </Button>
            )}
          </div>
        </div>
      )}

      <Dialog open={livenessOpen} onClose={() => setLivenessOpen(false)} title="Liveness Spoof Check">
        <div className="space-y-4 pt-2 text-sm text-ink-2">
          <p>
            Please complete this quick anti-spoof check to verify you are a live user.
          </p>

          {livenessStep === 'ready' && (
            <div className="space-y-3">
              <div className="rounded bg-accent/10 p-3 text-accent border border-accent/20 text-xs">
                Look straight at the camera and prepare to move your head slightly or blink when the scan starts.
              </div>
              <Button className="w-full font-bold" onClick={startLivenessScan}>
                Start Live Face Scan
              </Button>
            </div>
          )}

          {livenessStep === 'scanning' && (
            <div className="space-y-3 text-center py-4">
              <div className="h-2 w-full bg-paper-3 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-accent transition-all duration-300" 
                  style={{ width: `${(scanProgress / 3) * 100}%` }}
                />
              </div>
              <p className="font-mono text-xs text-ink-3">Capturing live feed: {scanProgress} / 3 frames...</p>
            </div>
          )}

          {livenessStep === 'verifying' && (
            <div className="py-6 text-center text-ink-3">
              Analyzing frame variation and verifying matching face…
            </div>
          )}

          {livenessStep === 'success' && (
            <div className="space-y-3 text-center">
              <div className="flex justify-center text-success mb-2">
                <Check className="size-10" />
              </div>
              <p className="font-semibold text-success-ink">Liveness Verified!</p>
              <p className="text-xs text-ink-3">You can now proceed to confirm your enrollment.</p>
              <Button className="w-full" onClick={() => setLivenessOpen(false)}>
                Continue
              </Button>
            </div>
          )}

          {livenessError && (
            <p className="rounded bg-danger-tint p-3 text-xs text-danger border border-danger/20">
              {livenessError}
            </p>
          )}

          {livenessStep !== 'success' && livenessStep !== 'scanning' && livenessStep !== 'verifying' && (
            <div className="flex justify-end gap-2 border-t border-rule pt-3">
              <Button variant="outline" onClick={() => setLivenessOpen(false)}>
                Cancel
              </Button>
            </div>
          )}
        </div>
      </Dialog>
    </div>
  )
}
