import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ScanFace, Mail, Lock, ArrowRight, KeyRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog } from '@/components/ui/dialog'
import { login, ApiError, getSecurityQuestion, resetWithSecurity } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export default function Login() {
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { setAuth } = useAuth()
  const navigate = useNavigate()
  const [resetOpen, setResetOpen] = useState(false)
  const [resetId, setResetId] = useState('')
  const [q, setQ] = useState<string | null>(null)
  const [ans, setAns] = useState('')
  const [pin, setPin] = useState('')
  const [newPw, setNewPw] = useState('')
  const [resetBusy, setResetBusy] = useState(false)
  const [resetMsg, setResetMsg] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const data = await login(identifier, password)
      setAuth(data)
      navigate(`/${data.role}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }
  async function fetchQuestion() {
    if (!resetId) return
    setResetMsg(null)
    try { const r = await getSecurityQuestion(resetId); setQ(r.question) } catch (e:any) { setResetMsg(e.message); setQ(null) }
  }
  async function doReset(e: React.FormEvent) {
    e.preventDefault()
    setResetBusy(true); setResetMsg(null)
    try { await resetWithSecurity(resetId, newPw, ans || undefined, pin || undefined); setResetMsg('Password reset — now sign in'); setAns(''); setPin(''); setNewPw('') } catch(err:any){ setResetMsg(err.message)} finally{ setResetBusy(false)}
  }

  return (
    <div className="flex min-h-svh items-center justify-center bg-paper px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex items-center gap-2">
          <ScanFace className="size-6 text-accent" aria-hidden />
          <h1 className="font-display text-2xl font-semibold text-ink">
            Attend<span className="text-accent">IQ</span>
          </h1>
        </div>

        <div className="rounded-[var(--radius-md)] border border-rule bg-paper p-6">
          <p className="mb-5 text-sm text-ink-3">Sign in to your account</p>

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div>
              <label htmlFor="identifier" className="mb-1.5 block text-sm font-medium text-ink-2">
                Staff ID / Matric No. / Email
              </label>
              <Input
                id="identifier"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                icon={<Mail />}
                placeholder="Staff ID, Matric Number, or Email"
                autoComplete="username"
                required
              />
            </div>
            <div>
              <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-ink-2">
                Password
              </label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                icon={<Lock />}
                placeholder="Enter password"
                autoComplete="current-password"
                required
              />
            </div>

            {error && (
              <p role="alert" className="rounded-[var(--radius-sm)] bg-danger-tint px-3 py-2 text-sm text-danger">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full" loading={loading}>
              Sign in
              <ArrowRight className="size-4" aria-hidden />
            </Button>
            <button type="button" onClick={()=>{setResetId(identifier); setResetOpen(true)}} className="mt-3 flex items-center gap-1 text-xs text-ink-3 hover:text-accent"><KeyRound className="size-3"/> Forgot password? Reset with security question / PIN</button>
           </form>
        </div>
        <Dialog open={resetOpen} onClose={()=>setResetOpen(false)} title="Reset password (student self-service, hashed)">
          <form onSubmit={doReset} className="space-y-3 pt-2">
            <Input placeholder="Matric / Email / Username" value={resetId} onChange={e=>setResetId(e.target.value)} required />
            <Button type="button" variant="outline" onClick={fetchQuestion} className="w-full">Fetch my security question</Button>
            {q && <p className="rounded bg-amber-50 p-2 text-sm text-amber-900">Q: {q}</p>}
            <Input placeholder="Answer (if you have question)" value={ans} onChange={e=>setAns(e.target.value)} />
            <Input placeholder="Or Emergency PIN (4-6 digits)" value={pin} onChange={e=>setPin(e.target.value.replace(/\D/g,''))} maxLength={6} />
            <Input placeholder="New password" type="password" value={newPw} onChange={e=>setNewPw(e.target.value)} required />
            <Button type="submit" loading={resetBusy} className="w-full">Reset password</Button>
            {resetMsg && <p className="text-sm text-ink-2">{resetMsg}</p>}
          </form>
        </Dialog>

        <div className="mt-6 border-t border-dashed border-rule pt-4 text-center font-mono-label text-ink-3">
          <p className="text-[0.7rem] font-semibold tracking-[0.08em] text-ink-2">UNIVERSITY OF LAGOS</p>
          <p className="mt-1 text-[0.65rem]">Department of Computer Engineering</p>
        </div>
      </div>
    </div>
  )
}
