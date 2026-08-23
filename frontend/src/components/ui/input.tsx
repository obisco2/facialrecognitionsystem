import { cn } from '@/lib/utils'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string
  icon?: React.ReactNode
}

export function Input({ className, error, icon, id, ...props }: InputProps) {
  return (
    <div className="w-full">
      <div className="relative">
        {icon && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-3 [&>svg]:size-4">{icon}</span>
        )}
        <input
          id={id}
          className={cn(
            'h-10 w-full rounded-[var(--radius-sm)] border border-rule-2 bg-paper px-3 text-[0.9375rem] text-ink placeholder:text-ink-3 transition-colors duration-[var(--dur-micro)]',
            'hover:border-ink-3 focus-visible:border-accent',
            icon && 'pl-9',
            error && 'border-danger focus-visible:outline-danger',
            className,
          )}
          aria-invalid={!!error}
          aria-describedby={error ? `${id}-error` : undefined}
          {...props}
        />
      </div>
      {error && (
        <p id={`${id}-error`} role="alert" className="mt-1.5 text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  )
}
