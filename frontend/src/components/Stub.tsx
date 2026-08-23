export function Stub({ title, note }: { title: string; note?: string }) {
  return (
    <div>
      <h1 className="mb-1">{title}</h1>
      <p className="mb-6 text-sm text-ink-3">{note ?? 'This screen is being rebuilt in the Cobalt design system.'}</p>
      <div className="flex h-64 items-center justify-center rounded-[var(--radius-md)] border border-dashed border-rule-2">
        <p className="font-mono-label text-ink-3">Coming next in this track</p>
      </div>
    </div>
  )
}
