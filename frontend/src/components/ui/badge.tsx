import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono-label',
  {
    variants: {
      variant: {
        success: 'bg-success-tint text-success-ink',
        warning: 'bg-warning-tint text-warning-ink',
        danger: 'bg-danger-tint text-danger',
        neutral: 'bg-paper-2 text-ink-3 border border-rule',
        accent: 'bg-accent-tint text-accent',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
)

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {
  dot?: boolean
}

export function Badge({ className, variant, dot, children, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant, className }))} {...props}>
      {dot && <span className="size-1.5 rounded-full bg-current" aria-hidden />}
      {children}
    </span>
  )
}
