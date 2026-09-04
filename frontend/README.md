# AttendIQ Frontend

React 19 + TypeScript + Vite, Tailwind CSS v4. Role-scoped routes for admin / lecturer / student. Talks to `core/backend.py` via `/api/*`.

```bash
bun install
bun run dev      # :5173, proxies /api → :8000
bun run build    # → frontend/dist (served by backend.py)
bun run test
```
