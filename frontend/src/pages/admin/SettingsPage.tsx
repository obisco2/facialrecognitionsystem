import { useEffect, useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { getConfig, saveConfig, type SystemConfig } from '@/lib/api'
import { showToast } from '@/components/ui/toast'

export default function AdminSettings() {
  const { data } = useQuery({ queryKey: ['config'], queryFn: getConfig })
  const [form, setForm] = useState<SystemConfig | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (data) setForm(data)
  }, [data])

  const saveMut = useMutation({
    mutationFn: (cfg: SystemConfig) => saveConfig(cfg),
    onSuccess: () => {
      setSaved(true)
      showToast('success', 'Settings saved')
      setTimeout(() => setSaved(false), 2000)
    },
    onError: (err: Error) => showToast('error', err.message || 'Failed to save settings'),
  })

  if (!form) return null

  return (
    <div>
      <h1 className="mb-1">Settings</h1>
      <p className="mb-6 text-sm text-ink-3">Camera and recognition engine configuration.</p>

      <Card className="max-w-lg">
        <CardHeader>
          <CardTitle>Recognition</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field label="Camera index">
            <Input
              type="number"
              value={form.camera_index}
              onChange={(e) => setForm({ ...form, camera_index: Number(e.target.value) })}
            />
          </Field>
          <Field label="Stream URL (RTSP/HTTP, leave blank for local webcam)">
            <Input value={form.stream_url} onChange={(e) => setForm({ ...form, stream_url: e.target.value })} placeholder="rtsp://…" />
          </Field>
          <Field label="Frame scale">
            <Input
              type="number"
              step="0.05"
              value={form.frame_scale}
              onChange={(e) => setForm({ ...form, frame_scale: Number(e.target.value) })}
            />
          </Field>
          <Field label="Tolerance">
            <Input
              type="number"
              step="0.05"
              value={form.tolerance}
              onChange={(e) => setForm({ ...form, tolerance: Number(e.target.value) })}
            />
          </Field>
          <Field label="Engine">
            <select
              value={form.recognition_engine}
              onChange={(e) => setForm({ ...form, recognition_engine: e.target.value })}
              className="h-10 w-full rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-sm text-ink"
            >
              <option value="auto">Auto (dlib if installed, else LBPH)</option>
              <option value="dlib">dlib (128-D)</option>
              <option value="lbph">LBPH</option>
            </select>
          </Field>
          <div className="flex items-center gap-3">
            <Button onClick={() => saveMut.mutate(form)} loading={saveMut.isPending}>
              Save settings
            </Button>
            {saved && <span className="text-sm text-success-ink">Saved.</span>}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-ink-2">{label}</label>
      {children}
    </div>
  )
}
