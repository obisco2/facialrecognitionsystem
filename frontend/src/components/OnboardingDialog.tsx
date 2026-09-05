import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ScanFace, BookOpen, Video, History, Users, Scale, Settings, KeyRound, Glasses } from 'lucide-react'
import { Dialog } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth'
import type { Role } from '@/lib/api'

interface Step {
  icon: React.ReactNode
  title: string
  body: string
  to?: string
  cta?: string
}

const STEPS: Record<Role, { heading: string; steps: Step[] }> = {
  student: {
    heading: 'Welcome — get set up in 3 minutes',
    steps: [
      {
        icon: <ScanFace className="size-4" />,
        title: '1. Enroll your face',
        body: 'Capture 5 clear photos: no sunglasses, caps, or face masks, plain background, good front lighting, look straight at the camera. Then pass the liveness scan.',
        to: '/student/enrollment',
        cta: 'Open enrollment',
      },
      {
        icon: <BookOpen className="size-4" />,
        title: '2. Register your courses',
        body: 'On your dashboard, filter by faculty / department and add every course you are offering this semester. No registration = no attendance record.',
        to: '/student',
        cta: 'Go to dashboard',
      },
      {
        icon: <KeyRound className="size-4" />,
        title: '3. Set your recovery PIN',
        body: 'In Settings, save a security question and a 4–6 digit emergency PIN (stored hashed — even admins cannot see it) so you can reset your own password.',
        to: '/student/settings',
        cta: 'Open settings',
      },
    ],
  },
  lecturer: {
    heading: 'Welcome — run your first session',
    steps: [
      {
        icon: <BookOpen className="size-4" />,
        title: '1. Claim your courses',
        body: 'Under Classes, claim unassigned courses or create new ones. Only your own classes appear in live sessions.',
        to: '/lecturer/classes',
        cta: 'Open classes',
      },
      {
        icon: <Users className="size-4" />,
        title: '2. Manage your roster',
        body: 'Open a class to see registered students, remove anyone who should not be there, or block disruptive students — blocked faces show an amber BLOCKED box and are never marked.',
        to: '/lecturer/classes',
        cta: 'Manage roster',
      },
      {
        icon: <Video className="size-4" />,
        title: '3. Start a live session',
        body: 'Pick the class and camera (built-in or external USB), then watch names get marked in real time. Use History to correct anything manually.',
        to: '/lecturer/live',
        cta: 'Start session',
      },
      {
        icon: <History className="size-4" />,
        title: '4. Review history',
        body: 'Filter attendance by date range, export CSV/Excel, or log manual attendance for students the camera missed.',
        to: '/lecturer/history',
        cta: 'View history',
      },
    ],
  },
  admin: {
    heading: 'Welcome — administer the system',
    steps: [
      {
        icon: <Users className="size-4" />,
        title: '1. Manage users',
        body: 'Create lecturers (Staff ID) and students (Matric No.). You can reset passwords, but security answers and PINs stay hashed and invisible.',
        to: '/admin/users',
        cta: 'Open users',
      },
      {
        icon: <BookOpen className="size-4" />,
        title: '2. Organise classes',
        body: 'Create classes, assign lecturers, and manage faculties / departments used by the registration filters.',
        to: '/admin/classes',
        cta: 'Open classes',
      },
      {
        icon: <Scale className="size-4" />,
        title: '3. Run bias evaluation',
        body: 'Upload a labelled demographic set and measure detection/recognition gaps across skin tones and gender (Gender Shades method).',
        to: '/admin/bias',
        cta: 'Open evaluation',
      },
      {
        icon: <Settings className="size-4" />,
        title: '4. Tune the engine',
        body: 'Recognition tolerance, camera index, and engine (dlib/LBPH) live in Settings. Changes apply to the next session.',
        to: '/admin/settings',
        cta: 'Open settings',
      },
    ],
  },
}

export function OnboardingDialog() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (!user) return
    try {
      if (!localStorage.getItem(`attendiq.onboarded.${user.id}`)) setOpen(true)
    } catch {
      setOpen(true)
    }
  }, [user])

  if (!user) return null
  const content = STEPS[user.role]

  function dismiss() {
    try {
      localStorage.setItem(`attendiq.onboarded.${user!.id}`, '1')
    } catch { /* private mode */ }
    setOpen(false)
  }

  return (
    <Dialog open={open} onClose={dismiss} title={content.heading}>
      <div className="space-y-3">
        <p className="flex items-start gap-2 rounded-[var(--radius-sm)] bg-warning-tint p-2.5 text-xs text-warning-ink">
          <Glasses className="mt-0.5 size-4 shrink-0" />
          <span>
            <strong>Photo rule:</strong> faces must be bare — no sunglasses, caps, helmets, or masks.
            Accessories are the #1 cause of failed recognition.
          </span>
        </p>
        {content.steps.map((s) => (
          <div key={s.title} className="flex gap-3 rounded-[var(--radius-sm)] border border-rule p-3">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent-tint text-accent">
              {s.icon}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-ink">{s.title}</p>
              <p className="mt-0.5 text-xs leading-relaxed text-ink-2">{s.body}</p>
              {s.to && (
                <Link
                  to={s.to}
                  onClick={dismiss}
                  className="mt-1 inline-block text-xs font-semibold text-accent hover:underline"
                >
                  {s.cta} →
                </Link>
              )}
            </div>
          </div>
        ))}
        <Button className="w-full" onClick={dismiss}>
          Got it — start using AttendIQ
        </Button>
      </div>
    </Dialog>
  )
}
