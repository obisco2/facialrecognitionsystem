# Face Recognition Attendance System with Bias Evaluation

A facial recognition attendance system that measures its own bias across skin tones and gender. Built as a final year project using OpenCV, dlib, FastAPI, React, and SQLite.

---

## What It Does

Students enroll by capturing or uploading 5 face photos via their browser camera (with automatic external USB camera discovery via `enumerateDevices` and a selector for built-in vs USB). Lecturers start live sessions where the browser identifies **multiple students simultaneously** in real time using WebRTC (`getUserMedia`) and logs attendance automatically. The admin dashboard shows system stats, manages users and classes, and runs bias evaluations using the Gender Shades methodology.

The system ships with two recognition engines: dlib's 128-D ResNet encoder (primary) and OpenCV LBPH (fallback). If dlib fails to install, the system degrades to LBPH without crashing. The browser-based camera architecture means the backend runs on any headless VPS without a physical webcam, while the desktop/server MJPEG path supports Windows `CAP_DSHOW` for external USB cameras and a diagnostic `GET /api/camera/list` probe.

---

## Quick Start

### Prerequisites

- Python 3.10+
- C++ compiler + CMake (for dlib; optional if using LBPH only)
- [Bun](https://bun.sh) (for the React frontend)
- A webcam (any modern browser supports WebRTC)

### Setup

```bash
# One-command setup
./setup.sh          # macOS/Linux
.\setup.ps1          # Windows PowerShell

# Or manually
python -m venv .venv
source .venv/bin/activate    # .venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
cd frontend && bun install
```

### Run

```bash
# Backend + frontend together
bun run dev

# Or with shell scripts
./dev.sh              # macOS/Linux
.\dev.ps1              # Windows PowerShell
```

Open http://127.0.0.1:5173. Sign in with the default admin account (username: `admin`, password: `admin`).

### Desktop App (pywebview)

```bash
./build.sh            # Build frontend/dist
python main.py        # Opens in a native window (or main_web.py)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Browser (Client)                        │
│  getUserMedia → Canvas → Base64 JPEG → POST /recognize   │
│  React + TypeScript (Tailwind CSS v4)                     │
├─────────────────────────────────────────────────────────┤
│                  FastAPI Backend                          │
│           REST API + Frame Recognition                    │
│           POST /api/recognize/frame (stateless)           │
├─────────────────────────────────────────────────────────┤
│                    Core Engine                            │
│  FaceDetector (Haar/DNN) ──▶ FaceEncoder (dlib/LBPH)   │
│                    ──▶ Recognizer (best-match)            │
├─────────────────────────────────────────────────────────┤
│                     SQLite                                │
│    users | classes | enrollments | attendance_log         │
├─────────────────────────────────────────────────────────┤
│               Bias Evaluation Module                      │
│       Fitzpatrick Scale | Gender | Intersectional         │
└─────────────────────────────────────────────────────────┘
```

---

## Roles

### Admin
- Dashboard with enrollment stats, attendance counts, and inline bias evaluation
- Manage users (create, edit, delete across all roles)
- Manage classes (create, delete, enroll/unenroll students)
- Manage faculties and departments (create, delete, view rosters)
- Run bias evaluation and view accuracy charts

### Lecturer
- Dashboard with class overview; dedicated **Students tab** (searchable roster with each student's courses)
- Log in via the **Lecturer tab** using **Staff ID** (role-mismatch guard blocks cross-role sign-in)
- Manage own classes, departments, and enrollment; **block/unblock** students (blocked faces show an amber **BLOCKED** box and are never marked)
- Start/stop live attendance sessions with real-time **multi-face** recognition (using full frame dlib landmark contexts) and **external USB camera selector** (browser `enumerateDevices` + `deviceId` constraint, with automatic fallback to browser when server camera is unavailable)
- **Presence tracking**: green in-room / grey walked-away dots per marked student, verification chime on each new mark, PIR motion + second-camera placeholders under `GET /api/hardware/status`
- Log manual attendance for students not recognized by camera
- Diagnostics via `GET /api/camera/list` (probe indices 0-4) and `GET /api/session/live` (`camera_active` flag)

### Student
- Dashboard with attendance history, per-class breakdown, and **course registration** (faculty/department filters, add/remove courses yourself)
- Face enrollment (capture via WebRTC camera featuring **3-frame automated live liveness scan** or upload files, validate, confirm) with **external USB camera selector** when multiple video inputs are present — bare faces only, **no sunglasses/caps/masks** (shown up front; accessories are the #1 failure cause)
- Settings (account info, retrain face model, hashed security question + emergency PIN for self password reset)
- First-login **onboarding tour** per role

---

## Bias Evaluation

Based on Joy Buolamwini's Gender Shades research (MIT Media Lab, 2018).

### How It Works

1. Bootstrap the dataset structure from the admin dashboard
2. Add face images to demographic subfolders
3. Fill in `annotations.csv` with filename, skin type (I-VI), gender, and expected identity
4. Run the evaluation from the admin dashboard or `python main.py --evaluate`

### Metrics

- **Detection Rate**: percentage of faces the detector finds
- **Recognition Accuracy**: percentage of detected faces correctly identified
- **False Negative Rate**: percentage of known faces the system fails to recognize
- **Disparity Gap**: accuracy difference between best and worst performing groups

Results display as bar charts (by skin type, by gender) and an intersectional table. They persist to `data/evaluation_dataset/metrics.json`.

---

## Configuration

Edit `config.ini` to change settings:

```ini
[Camera]
CAMERA_INDEX = 0
FRAME_SCALE = 0.25
STREAM_URL =              # blank = local webcam

[Recognition]
TOLERANCE = 0.6
ENGINE = auto             # auto | dlib | lbph
MIN_ENROLLMENT_PHOTOS = 5

[Database]
DB_PATH = data/users.db
```

| Parameter | What It Does | Default |
|-----------|-------------|---------|
| `TOLERANCE` | Match threshold (lower = stricter) | 0.6 |
| `FRAME_SCALE` | Detection downscale factor | 0.25 |
| `ENGINE` | Recognition engine selection | auto |
| `STREAM_URL` | RTSP/HTTP IP camera URL | (blank = webcam) |
| `MIN_ENROLLMENT_PHOTOS` | Minimum valid photos to confirm enrollment | 5 |

---

## Project Structure

```
facialrecognitionsystem/
├── main.py                 # Legacy Tkinter entry point
├── main_web.py             # Desktop shell (pywebview)
├── config.ini              # Configuration
├── requirements.txt        # Python dependencies
├── setup.sh / setup.ps1    # One-command bootstrap
├── dev.sh / dev.ps1        # Run backend + frontend
├── build.sh / build.ps1    # Build frontend for desktop
│
├── core/                   # Backend logic
│   ├── config.py           # Config singleton
│   ├── database.py         # SQLite layer (PBKDF2, JWT store, class blocks)
│   ├── backend.py          # FastAPI + JWT + RBAC + camera streaming
│   ├── auth.py             # JWT helpers
│   ├── face_detector.py    # Haar/DNN face detection
│   ├── face_encoder.py     # dlib 128-D / LBPH encoding
│   └── recognizer.py       # Recognition engine
│
├── frontend/               # React + TypeScript + Vite
│   └── src/
│       ├── pages/admin/    # Admin dashboard, users, classes, bias, settings
│       ├── pages/lecturer/ # Lecturer dashboard, classes, live session, history
│       ├── pages/student/  # Student dashboard, enrollment, settings
│       ├── components/     # AppShell, UI components (Card, Badge, Table, etc.)
│       └── lib/            # API client, auth, navigation
│
├── bias/                   # Bias evaluation
│   ├── evaluator.py        # Metrics computation
│   └── datasets.py         # Dataset helpers
│
├── data/                   # Runtime data
│   ├── known_faces/        # Enrolled face images (by person name)
│   ├── evaluation_dataset/ # Bias test set
│   ├── attendance/         # CSV/Excel exports
│   └── users.db            # SQLite database
│
└── models/                 # Haar cascade XML, saved models
```

---

## Technical Decisions

### dlib as Primary, LBPH as Fallback

dlib's 128-D ResNet encoder produces ~95%+ accuracy and needs one enrollment image. LBPH works everywhere with just `pip install` and no compiler. The `ENGINE=auto` setting tries dlib first, then falls back to LBPH. You get a working system either way.

### Why SQLite?

A single-file database suits a final year project. It handles users, classes, enrollments, and attendance without running a database server. The schema enforces constraints (unique attendance per student per class per day) that prevent duplicates at the database level.

### Why Browser-Based Camera?

The browser captures video via WebRTC (`getUserMedia`), extracts frames to a canvas, sends base64 JPEGs to `POST /api/recognize/frame`, and the backend returns recognized faces as JSON. This eliminates the need for a server-side camera, enabling deployment on headless VPS instances. The backend processes frames statelessly, so no MJPEG stream or WebSocket is required.

### VPS Deployment Optimization (dlib-bin, Caddy, & Caching)

Running computer vision models in resource-constrained cloud servers (e.g. 2GB RAM container on Hack Club Nest) required three key modifications:
*   **Compilation Avoidance**: We configure Python on Linux to load `dlib-bin` (a precompiled wheel) and build `face_recognition` with the `--no-deps` flag to bypass C++ compilation resource exhaustion.
*   **SSL Delegation**: Caddy is configured for internal HTTP (`http://`) to delegate SSL certificate termination to the Nest host proxy, solving ACME handshake blocks.
*   **Recognizer Caching**: The backend caches the `Recognizer` instance in memory on start and invalidates it only when user rosters are modified. This avoids concurrent disk reads/loads per frame, dramatically reducing CPU overhead and eliminating Segmentation Fault (SEGV) process crashes.

### Camera Discovery & Multi-Face Handling

*   **External USB Support**: Browser path uses `navigator.mediaDevices.enumerateDevices()` to list `videoinput` devices, presents a selector when `>1` camera is present, and requests `getUserMedia({ video: { deviceId: { exact } } })` to target external USB cameras. The server MJPEG path uses `cv2.CAP_DSHOW` on Windows for reliable external USB open and falls back without flag on Linux.
*   **Diagnostics**: `GET /api/camera/list?max_index=4` probes indices 0-4 with read verification; `POST /api/session/start` now returns `camera_active`, and `GET /api/session/live` exposes `camera_active` for immediate frontend fallback to browser mode.
*   **Multi-Face**: `FaceDetector` Haar tuned to `scaleFactor 1.08, minNeighbors 4, equalizeHist, CASCADE_SCALE_IMAGE` for higher recall on 2+ faces in classroom scenes; `Recognizer` and `POST /api/recognize/frame` loop over all detections (not just largest) and log attendance for every known face in the frame; rate limiter exempts ` /api/recognize/frame`, `/api/session/live`, `/api/session/video_feed` (previously `30 req/min` blocked the 1.5s poll loop at ~40 req/min and hid the second face).

### Security Hardening (JWT + RBAC)

Self-hosted JWT was chosen over Supabase to keep a single VPS + desktop `pywebview` deploy with SQLite intact. Supabase would be cleaner for a SaaS (managed Postgres + RLS + GoTrue), but requires migrating the `users`/`attendance_log` schema, face BLOB storage, and running face inference as a hybrid service — deferred until post-project.

*   **JWT pair**: `POST /api/auth/login` returns `access_token` (15m, `HS256`) + `refresh_token` (7d, `jti` + `sha256` hashed in `refresh_tokens` table). `POST /api/auth/refresh` rotates, `POST /api/auth/logout` revokes, `POST /api/auth/logout-all` revokes all. Secrets from `JWT_SECRET` env or `[Security] jwt_secret` (`config.ini` / `config.py:131`) — generated via `secrets.token_hex(32)` (`0d9c2a30...`, `ad8248bf...`).
*   **RBAC enforcement**: `core/auth.py: get_current_user / require_roles()` guards every endpoint. `POST /api/recognize/frame`, `POST /api/attendance/manual`, `POST /api/session/start|stop`, `GET /api/session/video_feed` require `lecturer|admin` (students get `403` — `curl` spoof blocked). `marked_by` is overwritten to `current_user.id` and class ownership checked. `POST /api/users`, `GET /api/config`, `GET /api/admin/stats`, `POST /api/bias/*` require `admin`. Enrollment endpoints enforce `student.can_only_self`.
*   **Client-side spoof blocked**: A student `curl -X POST /api/attendance/manual` without `Authorization: Bearer <lecturer JWT>` now returns `401`; with a student JWT returns `403`. Face `POST /api/recognize/frame` likewise rejects student tokens, and `is_enrolled` + `duplicate_prevention` still apply.
*   **Frontend**: `frontend/src/lib/api.ts` attaches `Authorization: Bearer` from `localStorage` (`attendiq.access_token`), auto-refreshes on `401` via `POST /api/auth/refresh`, and `frontend/src/lib/auth.tsx` stores tokens via `setAuth()` (login) and clears on `logout()` / refresh failure. `GET /api/auth/me` validates session.
*   **Headers & transport**: `security_headers_middleware` adds `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy: camera=(self)`, and `HSTS` when `x-forwarded-proto=https` (Caddy). `requirements.txt` adds `PyJWT` + `cryptography`. `refresh_tokens` table hashed (`sha256`) with `jti` uniqueness prevents replay.

---

## Known Limitations

- Frontal faces mostly. The Haar cascade handles multi-face classroom scenes well (tuned to `scaleFactor 1.08 / minNeighbors 4 / equalizeHist`) but still struggles with extreme profiles and heavy occlusion; DNN/MTCNN upgrade is planned.
- Liveness is software-only. The 3-frame 3D landmark variation check blocks 2D photos/iPads, but 3D masks or deepfake replays require IR/depth hardware for enterprise-grade guarantee.
- Lighting sensitivity reduced. `equalizeHist` improves low-light recall, but harsh shadows or strong backlight still lower detection rate.
- Browser camera permissions. Users must grant camera access in their browser; external USB selection appears only after permission is granted.
- Frame latency. Browser-to-backend round trip adds ~100-250ms per frame; recognition polling is exempt from rate limiting (every 1.5s) to sustain multi-face throughput.

---

## Future Work

- Deep learning models (FaceNet, ArcFace) for higher accuracy
- Liveness detection via blink analysis or 3D depth
- Multiple reference images per person with averaged encodings
- PostgreSQL for production deployment
- Mobile app with React Native or Flutter
- Bias mitigation through re-weighting or domain adaptation
- GDPR compliance with consent management and data retention

---

## References

1. Buolamwini, J. and Gebru, T. (2018). "Gender Shades." PMLR 81:1-15.
2. King, D.E. (2009). "Dlib-ml." JMLR 10:1755-1758.
3. Face Recognition with Python. https://github.com/ageitgey/face_recognition
4. OpenCV Documentation. https://docs.opencv.org/
5. Fitzpatrick Skin Type Scale. Fitzpatrick, T.B. (1975). "Soleil et peau." Journal de Medecine Esthetique, 2, 33-34.

---

## License

MIT License. See LICENSE file for details.

---

## Acknowledgments

This project builds on three open-source attendance systems:
- **Attendace_management_system** for the Tkinter GUI and end-to-end workflow
- **Attendance-System-Using-OpenCv** for detection and encoding patterns
- **Smart-Attendance-System-Using-OpenCV** for configuration and threading patterns

The bias evaluation framework draws from the Gender Shades project at MIT Media Lab.
