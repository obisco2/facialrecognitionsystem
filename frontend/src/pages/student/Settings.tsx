import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { retrainFaceModel } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export default function StudentSettings() {
  const { user } = useAuth()
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<'ok' | 'error' | null>(null)
  const [errorMsg, setErrorMsg] = useState('')

  if (!user) return null

  async function handleRetrain() {
    setBusy(true)
    setResult(null)
    setErrorMsg('')
    try {
      await retrainFaceModel(user!.id, user!.full_name)
      setResult('ok')
    } catch (err) {
      setResult('error')
      setErrorMsg(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <h1 className="mb-1">Settings</h1>
      <p className="mb-6 text-sm text-ink-3">Manage your account and recognition settings.</p>

      <div className="space-y-6">
        {/* Account info */}
        <Card className="max-w-lg">
          <CardHeader>
            <CardTitle>Account</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Row label="Name" value={user.full_name} />
            {user.student_id && <Row label="Matric Number" value={user.student_id} />}
            {user.email && <Row label="Email" value={user.email} />}
            {user.faculty && <Row label="Faculty" value={user.faculty} />}
            {user.department && <Row label="Department" value={user.department} />}
            {user.level && <Row label="Level" value={user.level} />}
            <Row
              label="Face enrollment"
              value={
                <Badge variant={user.face_enrolled ? 'success' : 'warning'} dot>
                  {user.face_enrolled ? 'enrolled' : 'pending'}
                </Badge>
              }
            />
          </CardContent>
        </Card>

        {/* Retrain model */}
        <Card className="max-w-lg">
          <CardHeader>
            <CardTitle>Recognition</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-4 text-sm text-ink-2">
              Re-encode your face from stored photos. Use this if recognition accuracy has dropped or after
              a significant appearance change.
            </p>
            <div className="flex items-center gap-3">
              <Button onClick={handleRetrain} loading={busy} disabled={!user.face_enrolled}>
                Retrain face model
              </Button>
              {result === 'ok' && <span className="text-sm text-success-ink">Done.</span>}
              {result === 'error' && <span className="text-sm text-danger">{errorMsg}</span>}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-ink-3">{label}</span>
      <span className="font-medium text-ink">{value}</span>
    </div>
  )
}
