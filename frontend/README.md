# AttendIQ Frontend

React + TypeScript UI for the Face Recognition Attendance System — replaces the
legacy vanilla-JS `web/` app. Talks to `core/backend.py` (FastAPI) over `/api/*`.

---

## Table of Contents

1. [Stack](#stack)
2. [Design System](#design-system)
3. [Getting Started](#getting-started)
4. [Available Scripts](#available-scripts)
5. [Project Structure](#project-structure)
6. [API Client](#api-client)
7. [Testing](#testing)
8. [Building for the Desktop App](#building-for-the-desktop-app)

---

## Stack

- **React 19 + TypeScript + Vite** — bundler/dev server
- **Tailwind CSS v4** (CSS-first `@theme`) — styling, tokens sourced from `src/styles/tokens.css`
- **React Router** — role-scoped routing (`/admin/*`, `/lecturer/*`, `/student/*`)
- **TanStack Query** — server-state/data fetching against the FastAPI backend
- **Recharts** — bias-evaluation charts
- **class-variance-authority + tailwind-merge** — component variant styling
- **Vitest + React Testing Library** — unit/component tests
- **Playwright** — e2e tests (mocked API + real-backend smoke pass)
- **Bun** — package manager/runtime (see root `README.md` — used project-wide)

---

## Design System

Built via the **Hallmark** skill — genre: modern-minimal, theme: **Cobalt**. Cool
near-white paper, one electric-cobalt signal accent, hairline borders (no card
shadows), a single dark "graphite" band per screen for the live-camera/
instrument-panel moments (live attendance session, enrollment capture), and a
bordered nav with a working ⌘K command palette.

Tokens live in `src/styles/tokens.css` (OKLCH palette, 4pt spacing scale, type
scale, radii, easings) and are wired into Tailwind via `@theme inline` in
`src/index.css`. See `.hallmark/log.json` at the repo root for the design
decision record, and `.agents/tracks/frontend-rewrite_20260822/spec.md` for the
full rewrite spec.

Fonts: Space Grotesk (display), Inter (body), JetBrains Mono (data/status labels).

---

## Getting Started

From the repo root, `./setup.sh` (or `.\setup.ps1` on Windows) installs this
directory's dependencies via `bun install`. To run standalone:

```bash
bun install
bun run dev
```

The dev server proxies `/api` to `http://127.0.0.1:8000` (see `vite.config.ts`)
— start the backend separately, or use `./dev.sh` / `.\dev.ps1` from the repo
root to run both together.

---

## Available Scripts

| Command | Description |
|---------|-------------|
| `bun run dev` | Start the Vite dev server (`:5173`) with HMR |
| `bun run build` | Type-check (`tsc -b`) and build to `dist/` |
| `bun run preview` | Preview the production build locally |
| `bun run typecheck` | Type-check only, no build |
| `bun run lint` | Lint with Oxlint |
| `bun run test` | Run Vitest unit/component tests once |
| `bun run test:watch` | Run Vitest in watch mode |
| `bun run e2e` | Run Playwright e2e tests (mocked API, auto-starts dev server) |

---

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── ui/              # Button, Input, Card, Badge, Dialog, Table (CVA variants)
│   │   ├── AppShell.tsx      # Bordered nav + sidebar + ⌘K trigger
│   │   ├── CommandPalette.tsx
│   │   ├── ProtectedRoute.tsx
│   │   └── Stub.tsx          # Placeholder for not-yet-built screens
│   ├── pages/
│   │   ├── Login.tsx
│   │   ├── admin/            # Dashboard, Classes, Users, Bias, Settings
│   │   ├── lecturer/         # Dashboard, LiveSession, History
│   │   └── student/          # Dashboard, Enrollment
│   ├── lib/
│   │   ├── api.ts            # Typed client — mirrors core/backend.py routes 1:1
│   │   ├── auth.tsx          # Auth context (localStorage-persisted user)
│   │   ├── nav.ts            # Role -> nav item config
│   │   └── utils.ts          # cn() class-merge helper
│   ├── styles/tokens.css     # Cobalt design tokens (source of truth)
│   ├── test/setup.ts         # Vitest + jest-dom setup
│   └── App.tsx / main.tsx
├── e2e/                       # Playwright specs
├── vite.config.ts
├── vitest.config.ts
└── playwright.config.ts
```

---

## API Client

`src/lib/api.ts` is a hand-written typed wrapper — one function per
`core/backend.py` route (auth, users, classes, enrollments, attendance history,
live session, enrollment capture, config, bias). No codegen: when a backend
route changes, update the matching function/type here. This is the single
place the frontend talks to the network — pages never call `fetch` directly.

---

## Testing

- **Unit/component** (`bun run test`) — Vitest + React Testing Library, colocated
  as `*.test.tsx` next to the component (e.g. `src/components/ui/button.test.tsx`)
- **E2e, mocked backend** (`bun run e2e`) — Playwright specs in `e2e/`, intercept
  `/api/*` with `page.route()` for fast, deterministic runs
- **E2e, real backend** — run `./dev.sh` (or `.\dev.ps1`) from the repo root,
  then point Playwright's `baseURL`/backend at the live servers for a full-stack
  smoke pass before release (see the track's `plan.md` for the checklist)

---

## Building for the Desktop App

```bash
bun run build
```

`core/backend.py` automatically mounts `frontend/dist` once it exists (falling
back to the legacy `web/` folder otherwise), so `python main_web.py` at the
repo root picks up the built frontend with no further wiring. The root
`build.sh` / `build.ps1` scripts wrap this same command.
