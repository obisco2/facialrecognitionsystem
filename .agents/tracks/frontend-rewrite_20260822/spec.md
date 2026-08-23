# Spec — Frontend rewrite + design overhaul

## Problem

The current frontend (`web/` — vanilla JS/CSS, 5000+ lines, `app.js` 1754 lines of
DOM-string templating) is functional but:
- Hard to maintain (no component model, manual DOM diffing via innerHTML)
- Design tied to `design.md`'s dark/warm-red "AttendIQ" system, which the user
  wants replaced entirely — not iterated on
- No automated test coverage of UI behavior

The user wants: (1) a full framework rewrite, not an in-place redesign, and
(2) an entirely new visual design, ignoring `design.md`.

## Scope

- Replace `web/` with a React + TypeScript + Vite app.
- New design system ("Cobalt", picked via the Hallmark skill — see
  `.hallmark/log.json` for the design decision record) replaces `design.md`.
- Preserve existing information architecture: 3 roles (admin / lecturer /
  student), same screens, same FastAPI backend (`core/backend.py`) — no backend
  route changes required for parity.
- New capability added incidentally by the design system: a working ⌘K command
  palette (Cobalt's signature nav move) for cross-role search/navigation.
- Backend continues to serve the built frontend as static files (`StaticFiles`
  mount in `core/backend.py`), same as today's `web/` — main_web.py / pywebview
  shell unchanged.

## Out of scope

- Backend/API changes (routes in `core/backend.py` stay as-is for this track)
- Recognition engine changes (`core/face_encoder.py`, `core/recognizer.py`)
- Bias evaluation methodology changes (`bias/`)

## Design system reference

See Hallmark pick recorded in `.hallmark/log.json` (2026-08-22 entry) and the
new `tokens.css` this track produces:
- Genre: modern-minimal · Theme: Cobalt
- Cool near-white paper, electric cobalt accent, Space Grotesk + Inter +
  JetBrains Mono, hairline borders (no card shadows), one dark graphite band
  per screen (used for the live-camera/session view), bordered nav + ⌘K palette.

## Testing strategy

1. Vitest + React Testing Library — component/unit tests for shared UI
   primitives and page logic.
2. Playwright — e2e against the Vite dev server using mocked API responses
   (fast iteration), plus one full-stack pass against the real FastAPI backend
   (`main.py`/`core/backend.py`) once the Python env (dlib/opencv on py3.14) is
   confirmed working.
3. Hallmark's `scripts/validate_palette.js` (from the `dataviz` skill) run
   against any chart colors (bias evaluation charts, attendance charts) before
   shipping.
4. Manual smoke test via `main_web.py` (pywebview) for full desktop-app sanity.
