# Face Recognition Attendance System with Bias Evaluation

A facial recognition attendance system that measures its own bias across skin tones and gender. Built as a final year project using OpenCV, dlib, FastAPI, React, and SQLite.

---

## What It Does

Students enroll by capturing or uploading 5 face photos. Lecturers start live sessions where a webcam identifies students in real time and logs attendance automatically. The admin dashboard shows system stats, manages users and classes, and runs bias evaluations using the Gender Shades methodology.

The system ships with two recognition engines: dlib's 128-D ResNet encoder (primary) and OpenCV LBPH (fallback). If dlib fails to install, the system degrades to LBPH without crashing.

---

## Quick Start

### Prerequisites

- Python 3.10+
- C++ compiler + CMake (for dlib; optional if using LBPH only)
- [Bun](https://bun.sh) (for the React frontend)
- A webcam

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
python main_web.py    # Opens in a native window
```

### Legacy Tkinter GUI

```bash
python main.py
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   React Frontend                         │
│         Role-scoped routes: admin / lecturer / student   │
├─────────────────────────────────────────────────────────┤
│                  FastAPI Backend                          │
│           REST API + MJPEG camera streaming               │
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
- Run bias evaluation and view accuracy charts

### Lecturer
- Dashboard with class overview
- Manage own classes and enrollment
- Start/stop live attendance sessions with real-time recognition
- Log manual attendance for students not recognized by camera

### Student
- Dashboard with attendance history and per-class breakdown
- Face enrollment (capture via camera or upload files, validate, confirm)
- Settings (account info, retrain face model)

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
│   ├── database.py         # SQLite layer
│   ├── backend.py          # FastAPI app + camera streaming
│   ├── face_detector.py    # Haar/DNN face detection
│   ├── face_encoder.py     # dlib 128-D / LBPH encoding
│   ├── recognizer.py       # Recognition engine
│   ├── data_collector.py   # Training data capture
│   └── attendance.py       # CSV attendance export
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

### Why MJPEG Streaming?

The backend reads frames from the webcam, runs face detection and encoding, draws bounding boxes, and serves the annotated frame as an MJPEG stream. The React frontend displays it in an `<img>` tag. No WebRTC, no WebSocket, no external streaming service.

---

## Known Limitations

- Frontal faces only. The Haar cascade detector struggles with profiles and heavy occlusion.
- No liveness detection. A photo or video of an enrolled person could fool the system.
- Lighting sensitivity. Performance drops in poor lighting or strong backlight.
- No GPU acceleration by default. The DNN detector option exists but is not the default.

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
