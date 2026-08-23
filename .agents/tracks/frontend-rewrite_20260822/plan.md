# Plan — Frontend rewrite + design overhaul

## Phase 0 — Scaffolding ✅
- [x] `frontend/` — Vite + React + TypeScript project (via bun)
- [x] Tailwind v4 (`@theme` CSS-first config) wired to Cobalt tokens
- [x] `tokens.css` — Cobalt palette (OKLCH), type scale, spacing, radii, easings
- [x] Fonts: Space Grotesk (display) + Inter (body) + JetBrains Mono (data/labels)
- [x] React Router routes for the 3 role areas + login
- [x] `src/lib/api.ts` — typed fetch client matching `core/backend.py` routes
- [x] Vitest + RTL config; Playwright config

## Phase 1 — App shell + auth ✅
- [x] Login screen (Cobalt voice — bordered card, mono meta line for
      university/author credit, cobalt-accent primary button)
- [x] App shell: bordered top nav + working ⌘K command palette + role-based
      sidebar
- [x] Auth flow wired to `POST /api/auth/login`, role-based route guarding

## Phase 2 — Lecturer screens ✅
- [x] Dashboard
- [x] Live attendance session — the dark graphite "instrument panel" band:
      camera feed card, mono status chips (confidence %, marked count),
      start/stop controls
- [x] History — date-range filter, table, CSV/Excel export

## Phase 3 — Admin screens ✅
- [x] Dashboard, Classes (CRUD + enrollment), Users (CRUD), Settings
- [x] Bias evaluation — Recharts bars (single-hue accent, no multi-hue
      palette needed — dataviz validator not required), Fitzpatrick x gender
      disparity table

## Phase 4 — Student screens ✅
- [x] Dashboard (attendance records)
- [x] Enrollment wizard (photo capture slots, validation feedback states)

## Phase 5 — Backend wiring + full-stack verification ✅
- [x] python venv on py3.14: dlib/face_recognition compile from source and
      work — needed `setuptools<81` pinned (pkg_resources removed upstream)
      and `python-multipart` (form uploads) — both added to `requirements.txt`
- [x] `core/backend.py` static mount auto-prefers `frontend/dist`, falls back
      to legacy `web/`
- [x] Fixed: `/api/auth/login` was leaking `password_hash` in the response
- [x] Real end-to-end verification: real login (admin/admin) against the
      actual SQLite DB, real seeded users rendered in the Users table
- [ ] Full pywebview smoke test via `main_web.py` (deps ready, not yet run)

## Phase 6 — Tests ✅
- [x] Vitest unit tests (Button component, 8-state coverage)
- [x] Playwright e2e (mocked): login success/failure, ⌘K command palette
- [ ] Playwright e2e (real backend) smoke pass — manual pass done ad hoc,
      not yet a checked-in automated spec

## Phase 7 — Dev ergonomics (added, not in original scope) ✅
- [x] `setup.sh`/`dev.sh`/`build.sh` + PowerShell equivalents at repo root
- [x] `core/backend.py` static mount made dist-aware for `build.sh`
- [x] Root `README.md` and `frontend/README.md` updated to current stack

## Verification criteria
- All 3 roles reachable and functional against the real FastAPI backend
- No visual regressions vs. feature parity checklist (every `web/app.js`
  function has a React equivalent)
- Hallmark slop-test gates pass on the new design (no gradient CTAs, no
  glassmorphism, hairlines not card-shadows, etc.)
- `npm run build` + `npm run test` + `npx playwright test` all green
