# Design — AttendIQ

Locked design system. Future Hallmark runs read this file first; pages defer
to it. Amend intentionally — the file is the rule.

## System
- Genre · utilitarian
- Macrostructure · dashboard-app (sidebar + content, existing structure preserved)
- Theme · custom (vibe: "dark, functional, warm-red accent, university attendance")
- Axes · dark paper (L < 20%) / utilitarian display (geometric-sans) / warm-red accent (hue 25)

## Tokens (canonical · `tokens.css` is the source of truth)
```css
:root {
  --color-paper:      oklch(14% 0.008 10);
  --color-paper-2:    oklch(18% 0.010 10);
  --color-paper-3:    oklch(22% 0.012 10);
  --color-ink:        oklch(94% 0.006 10);
  --color-ink-2:      oklch(80% 0.006 10);
  --color-ink-3:      oklch(58% 0.008 10);
  --color-rule:       oklch(30% 0.010 10);

  --color-accent:     oklch(62% 0.22 25);
  --color-accent-hover: oklch(56% 0.22 25);
  --color-accent-glow: oklch(62% 0.22 25 / 0.15);

  --color-success:    oklch(72% 0.16 160);
  --color-warning:    oklch(78% 0.14 70);
  --color-danger:     oklch(62% 0.22 25);
  --color-info:       oklch(78% 0.12 230);
  --color-focus:      oklch(70% 0.19 25);

  --font-display: "Plus Jakarta Sans", ui-sans-serif, system-ui, sans-serif;
  --font-body:    "Plus Jakarta Sans", ui-sans-serif, system-ui, sans-serif;
  --font-mono:    "JetBrains Mono", ui-monospace, monospace;

  /* 4-pt spacing scale: --space-3xs (2px) … --space-3xl (96px) */
  /* Type scale, 1.25 major-third: --text-xs (10.24px) … --text-3xl (48.83px) */

  --ease-out:    cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in:     cubic-bezier(0.7, 0, 0.84, 0);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-micro:   120ms;
  --dur-short:   220ms;
  --dur-long:    420ms;

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --radius-pill: 9999px;
}
```

## CTA voice
- Primary · `oklch(62% 0.22 25)` fill · `--radius-md` · `--space-sm --space-lg` padding
- Secondary (ghost) · transparent + 1px border · same radius

## Motion stance
- motion-cut (functional dashboard, no marketing animation)
- Reduced-motion fallback · ≤150 ms opacity crossfade

## Exports
`tokens.css` (in this project) is the source of truth. For Tailwind v4
`@theme`, DTCG `tokens.json`, or shadcn/ui CSS variables, ask *"extend
design.md with Tailwind exports"* — Hallmark will append them per
`export-formats.md`.
