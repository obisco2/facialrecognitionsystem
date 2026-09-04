import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ScanFace, Mail, Lock, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { login, ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth'

export default function Login() {
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { setAuth } = useAuth()
  const navigate = useNavigate()

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
          </form>
        </div>

        <div className="mt-6 border-t border-dashed border-rule pt-4 text-center font-mono-label text-ink-3">
          <p className="text-[0.7rem] font-semibold tracking-[0.08em] text-ink-2">UNIVERSITY OF LAGOS</p>
          <p className="mt-1 text-[0.65rem]">Department of Computer Engineering</p>
        </div>
      </div>
    </div>
  )
}
