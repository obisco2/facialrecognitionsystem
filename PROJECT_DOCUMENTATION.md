# Final Year Project Documentation
## Face Recognition Attendance System with Bias Evaluation

## 1. Project Title

**Development and Evaluation of a Bias-Aware Facial Recognition System for Automated Attendance Tracking**

---

## 2. Abstract

This project builds a facial recognition attendance system with bias evaluation across demographic groups. It uses OpenCV's Haar Cascade (tuned for multi-face: `scaleFactor 1.08, minNeighbors 4, equalizeHist`) for face detection and two recognition engines: dlib's 128-D ResNet encoder (primary) and OpenCV LBPH (fallback). A FastAPI backend serves a React frontend where the browser captures video via WebRTC (`getUserMedia` + `enumerateDevices` for external USB discovery) and sends frames to the backend for recognition. The architecture supports both browser-camera mode (headless VPS) and server-side MJPEG streaming with Windows `CAP_DSHOW` for external USB, plus a diagnostic `GET /api/camera/list` probe. The bias evaluation module applies the Gender Shades methodology, measuring recognition accuracy across the Fitzpatrick skin type scale (Types I-VI) and gender categories.

---

## 3. Introduction and Background

### 3.1 The Attendance Problem

Manual roll call wastes 5-10 minutes per class. Students sign for absent classmates. Fingerprint scanners require physical contact. None of these scale with class size. Facial recognition solves these problems: contactless, real-time, automated record-keeping.

### 3.2 The Bias Problem

Buolamwini and Gebru (2018) showed that commercial face recognition systems have uneven accuracy across demographics. Dark-skinned individuals face error rates up to 34.7% higher than light-skinned individuals. Women face 12-15% higher error rates than men. Dark-skinned women face error rates up to 46.8% in some systems. A useful attendance system must report where it performs well and where it does not.

---

## 4. Literature Review

### 4.1 Face Detection Methods

| Method | Approach | Speed | Accuracy |
|--------|----------|-------|----------|
| Haar Cascades | Viola-Jones (2001) | Fast | Moderate |
| HOG + SVM | Dalal and Triggs (2005) | Fast | Good |
| CNN (MTCNN) | Zhang et al. (2016) | Moderate | Excellent |
| YOLO/SSD | Redmon et al. (2016) | Real-time | Excellent |

### 4.2 Face Recognition Methods

| Method | Features | Notes |
|--------|----------|-------|
| LBPH | Histograms | Used as fallback in this project |
| dlib 128-D | 128-D vector | Primary engine in this project |
| FaceNet | 128-D embedding | Google (2015), not used |
| ArcFace | Angular margin | Deng et al. (2018), not used |

### 4.3 Bias in Face Recognition

- Gender Shades (2018): Exposed intersectional disparities in commercial systems
- NIST FRVT (2019): Confirmed demographic differentials across vendors
- Type I skin: 99.7% accuracy vs Type VI: 94.6% in NIST benchmarks

---

## 5. System Design

### 5.1 Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Browser (Client)                        │
│  getUserMedia → Canvas → Base64 JPEG → POST /recognize   │
│  React + TypeScript (Tailwind CSS v4)                     │
│  Role-scoped routes: admin / lecturer / student           │
├─────────────────────────────────────────────────────────┤
│                    API Layer                              │
│              FastAPI REST + Frame Recognition              │
│              POST /api/recognize/frame (stateless)        │
├─────────────────────────────────────────────────────────┤
│                    Core Engine                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐        │
│  │ Detector  │ │ Encoder  │ │   Recognizer     │        │
│  │ (Haar/DNN)│ │(dlib/LBPH│ │  (Detection +    │        │
│  │           │ │ fallback)│ │   Encoding +     │        │
│  │           │ │          │ │   Best-Match)    │        │
│  └──────────┘ └──────────┘ └──────────────────┘        │
├─────────────────────────────────────────────────────────┤
│                     Data Layer                            │
│  SQLite (users, classes, enrollments, attendance_log)    │
│  File system (known_faces/, evaluation_dataset/)         │
├─────────────────────────────────────────────────────────┤
│               Bias Evaluation Module                      │
│  Fitzpatrick Scale | Gender | Intersectional Analysis    │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Module Dependency Graph

```
main_web.py (pywebview desktop shell)
  └── core.backend (FastAPI app)
        ├── core.config (Config singleton)
        ├── core.database (SQLite layer)
        ├── core.recognizer
        │     ├── core.face_detector (Haar/DNN)
        │     └── core.face_encoder (dlib/LBPH)
        ├── core.attendance (CSV export)
        └── bias.evaluator
              └── bias.datasets

frontend/ (React + TypeScript + Vite)
  └── src/pages/{admin,lecturer,student}/*.tsx
        └── src/lib/api.ts → fetches /api/*
```

### 5.3 Data Flow

```
Browser enumerateDevices → getUserMedia({deviceId}) → Canvas Capture → Base64 JPEG
  → POST /api/recognize/frame → Decode JPEG → Downscale (25%)
  → Face Detection (Haar/DNN, equalizeHist, multi-face) → Face Encoding (128-D dlib or LBPH, all faces)
  → Euclidean Distance Match Against Known Faces
  → Identity + Confidence (×N faces) → SQLite Attendance Log (dedup per face)
  → JSON Response {recognized:[...], total_faces, known_faces} → React Frontend (bounding boxes ×N + selector for USB)
Fallback: POST /api/session/start → GET /api/camera/list probe → GET /api/session/video_feed MJPEG (CAP_DSHOW on Windows)
```

---

## 6. Implementation

### 6.1 Integration from Three Reference Implementations

| Feature | Project 1 (AMS) | Project 2 (Attendance) | Project 3 (Smart) | **This Project** |
|---------|-----------------|----------------------|-------------------|-----------------|
| Face Detection | Haar Cascade | dlib HOG | dlib HOG | **Haar/DNN (configurable)** |
| Recognition | LBPH | 128-D encoding | 128-D encoding | **128-D + LBPH fallback** |
| GUI | Tkinter | None | Tkinter | **React + TypeScript** |
| Camera Source | Local webcam | Local webcam | Local webcam | **Browser getUserMedia** |
| Threading | No | No | Yes | **Yes** |
| Config File | No | No | INI | **INI (singleton)** |
| Session Dedup | No | CSV read | Set-based | **Set + DB constraint** |
| Camera Downscale | No | 25% | None | **25%** |
| Enrollment | 70 images | 1 image | 1 image | **5 photos (validated)** |
| Bias Evaluation | No | No | No | **Yes** |
| Database | None | None | None | **SQLite (multi-role)** |
| Web UI | No | No | No | **Yes** |

### 6.2 Code Statistics

| Component | Lines | Purpose |
|-----------|-------|---------|
| `core/config.py` | 132 | Configuration management |
| `core/face_detector.py` | 176 | Face detection (Haar/DNN, equalizeHist, multi-face tuned) |
| `core/face_encoder.py` | 415 | Face encoding and matching |
| `core/data_collector.py` | 138 | Training data capture |
| `core/recognizer.py` | 159 | Recognition engine (CAP_DSHOW, multi-face) |
| `core/database.py` | 609 | SQLite database layer |
| `core/backend.py` | ~1369 | FastAPI backend + frame recognition + camera discovery + rate-limit bypass |
| `core/attendance.py` | 129 | Attendance CSV management |
| `bias/evaluator.py` | 244 | Bias evaluation metrics |
| `bias/datasets.py` | 106 | Dataset helpers |
| **Total (Python)** | **~3,000** | |
| **Total (TypeScript)** | **~3,200** | React frontend (browser camera) |

### 6.3 Key Algorithms

#### Face Encoding (128-D)

The dlib encoder takes a BGR image, converts it to RGB, detects a face using HOG, aligns it with 68-point landmarks, and runs it through a ResNet to produce a 128-dimensional float32 vector. The LBPH fallback converts the face to grayscale, resizes to 100x100, and uses it as a template for histogram matching.

#### Identity Matching

The system computes the Euclidean distance between the unknown face encoding and every known encoding. If the minimum distance falls below the tolerance threshold (default 0.6 for dlib), it returns the matched name. For LBPH, it uses OpenCV's `predict()` with a confidence score normalized to [0, 1].

#### Attendance Deduplication

Each recognized student ID is stored in a set. Before writing to the database, the system checks if the ID is already in the set. SQLite also enforces a UNIQUE constraint on (student_id, class_id, session_date), so duplicates are blocked at both the application and database layers.

---

## 7. Bias Evaluation Methodology

### 7.1 Fitzpatrick Skin Type Scale

| Type | Description |
|------|-------------|
| I | Very light. Always burns, never tans. |
| II | Light. Usually burns, tans minimally. |
| III | Medium. Sometimes burns, tans uniformly. |
| IV | Olive. Rarely burns, tans easily. |
| V | Dark. Very rarely burns, tans darkly. |
| VI | Very dark. Never burns, deeply pigmented. |

### 7.2 Metrics

1. **Detection Rate** = Faces detected / Total images
2. **Recognition Accuracy** = Correctly identified / Faces detected
3. **False Negative Rate** = (Detected - Correct) / Detected
4. **Disparity Gap** = max(accuracy) - min(accuracy) across groups

### 7.3 Intersectional Analysis

Measuring accuracy across skin type x gender combinations reveals which subgroups face the highest error rates and whether biases compound at intersections.

### 7.4 Running an Evaluation

1. Request evaluation results in the admin dashboard to bootstrap the dataset structure at `data/evaluation_dataset/`.
2. Place representative facial images in the demographic subfolders.
3. Fill in `annotations.csv` with filename, skin type, gender, and expected identity for each image.
4. Click **Run evaluation** on the admin dashboard or run `python main.py --evaluate`.
5. Results persist to `results.csv` and `metrics.json` in the evaluation directory.

---

## 8. Testing and Results

### 8.1 Test Coverage

Unit tests are implemented using `pytest` with coverage tracking via `pytest-cov`. Tests cover core modules with mocked dependencies to avoid requiring a live camera or dlib models at test time.

| Module | Test File | Functions Tested |
|--------|-----------|-----------------|
| Config | `tests/test_config.py` | Singleton creation, property access, defaults |
| DatabaseManager | `tests/test_database.py` | CRUD operations, authentication, attendance dedup, password hashing |
| FaceDetector | `tests/test_face_detector.py` | Haar cascade init, face detection, bounding box format |
| BiasEvaluator | `tests/test_bias_evaluator.py` | Metrics computation, disparity report, annotation loading |

Run the full test suite:

```bash
pytest tests/ -v --cov=core --cov=bias --cov-report=term-missing
```

### 8.2 Performance

| Metric | Value |
|--------|-------|
| Detection speed (Haar) | ~15ms per frame |
| Encoding speed (dlib) | ~8ms per face |
| End-to-end (640x480) | ~30ms per frame (~33 FPS) |
| Memory usage | ~80MB (OpenCV models) |

### 8.3 Known Results

- Detection rate: >95% under good lighting
- Recognition accuracy: >90% with adequate enrollment data
- False positive rate: <2% with tolerance=0.6
- Session dedup: 100% effective

---

## 9. Ethical Considerations

### 9.1 Privacy

Face images stay on the local machine. No biometric data transmits over the network. Attendance records are stored in SQLite, not transmitted externally.

### 9.2 Consent

Students must explicitly enroll (capture or upload face photos). The camera feed is displayed live during sessions. No covert surveillance capability exists.

### 9.3 Bias Transparency

The evaluation module produces per-group accuracy metrics. The disparity report quantifies fairness gaps across demographics. These results go directly to stakeholders.

### 9.4 Limitations

The system is not 100% accurate. Performance varies across demographics. It cannot serve as a sole authentication method. While active liveness detection (3-frame 3D landmark variation tracking) is implemented to block static screenshots and paper photos, extremely sophisticated spoofing attacks (like 3D masks or advanced deepfakes) are still open security risks.

## 10. Deployment Architecture

AttendIQ supports multiple deployment targets: local desktop (pywebview), headless VPS (systemd + Caddy), and containerised (Docker). This section details the engineering decisions made for cloud VPS deployment on resource-constrained environments.

### 10.1 Dependency Compilation on Memory-Constrained Hosts

Headless Linux VPS containers (e.g., 2GB RAM) cannot compile C++ dependencies like `dlib` from source — the compiler exhausts available memory and triggers OOM kills.

**Solution**: The `requirements.txt` conditionally installs `dlib-bin` (pre-compiled wheels) on Linux, and the server setup script installs `face_recognition` with `--no-deps` to bypass local compilation. Required system runtime libraries (`libopenblas-dev`, `libgl1`, `libglib2.0-0`) are installed via the package manager.

### 10.2 Reverse Proxy and SSL Termination

Behind a shared-host reverse proxy (e.g., Proxmox/LXC), direct inbound ports 80/443 are blocked. Traffic is routed via subdomain CNAME mappings to the host proxy.

**Solution**: Caddy is configured in HTTP mode (`http://`) to delegate SSL termination to the upstream proxy. This prevents ACME TLS handshake failures inside the container while maintaining secure external access via HTTPS.

### 10.3 Process Stability Under Load

Rapid sequential calls to `/api/recognize/frame` could trigger segmentation faults (SEGV) in the uvicorn process due to race conditions from reloading dlib weights and the face database on every request.

**Solution**: The backend uses a globally cached `Recognizer` singleton that lazy-loads once on startup and invalidates only when a student enrolls or a retrain is triggered. This eliminates concurrent disk I/O, reduces per-request latency, and prevents crash-to-restart loops.

### 10.4 Active Liveness Verification & QoL Enhancements

To make the system robust for real-world deployment (like UNILAG's computer engineering classrooms), several advanced features were implemented:
1. **Automated 3-Frame Live Scan**: Student enrollment features a robust active anti-spoof check. The system snaps 3 frames sequentially and evaluates the 3D structural variation of facial landmarks (using dlib's 68-point model). By tracking changes in the Eye Aspect Ratio (EAR) and Nose-to-Eye yaw ratio across frames, the system mathematically ensures 3D human movement, blocking 2D static screenshots, IPads, or paper photos (since a 2D surface yields zero variation in relative proportions when moved).
2. **Staff ID & Name Mapping**: Lecturers log in and manage accounts using their **Staff ID** (removing generic usernames). Students register under their **Full Name** and unique numeric **Matric Number** (which automatically synchronizes to their username field).
3. **Faculties & Departments Management**: Admins can seed and manage standard UNILAG faculties and departments. Classes and courses are assignable to these departments, linking students and lecturers to their respective academic fields.
4. **Form Field Constraints**: Input forms enforce strict validation rules. Matric Numbers and Staff IDs are filtered dynamically to reject non-numeric characters, and emails enforce proper format patterns.
5. **Toast Notifications**: Built custom responsive toast components that render clean notification cards for errors and success messages, replacing generic native browser alert dialogs.

### 10.5 External Camera Discovery & Multi-Face Robustness

Classroom deployment surfaced two usability gaps: external USB cameras not selectable, and rapid polling hiding the second face in multi-person frames.

**External USB Discovery (Browser + Server)**
* Browser path: `LiveSession.tsx` and `Enrollment.tsx` call `navigator.mediaDevices.enumerateDevices()` after priming permission with a transient `getUserMedia({video:true})`, filter `videoinput`, and render a `<select>` when `>1` device is present. `startCamera(deviceId)` requests `getUserMedia({ video: { deviceId: { exact: deviceId } } })` to target USB, stops prior tracks, and re-binds on `devicechange` events.
* Server MJPEG path: `core/recognizer.py:start_camera()` and `core/backend.py:CameraStreamer` use `cv2.CAP_DSHOW` on Windows for reliable external USB open, with fallback to default flag on Linux/RTSP strings.
* Diagnostics: `GET /api/camera/list?max_index=4` probes indices with read verification; `POST /api/session/start` returns `camera_active`, and `GET /api/session/live` exposes it so the frontend immediately falls back to browser mode when `camera_active=false` (VPS without webcam).

**Multi-Face Detection & Throughput**
* `core/face_detector.py:_detect_haar()` tuned from `scaleFactor 1.1 / minNeighbors 5` to `1.08 / 4` + `cv2.equalizeHist` + `CASCADE_SCALE_IMAGE` for higher recall on 2+ faces without spiking false positives; `minSize` lowered to `(28,28)`.
* `core/recognizer.py:process_frame()` and `core/backend.py:POST /api/recognize/frame` loop over *all* `face_locations` (not largest-only), fixing the liveness crop coordinate bug (was `int(top)` on scaled coords → tiny patch; now `int(top_s/scale)` correctly maps to original frame) and logging attendance per known face with per-face dedup.
* `core/backend.py:rate_limit_middleware` exempts ` /api/recognize/frame`, `/api/session/live`, `/api/session/video_feed` from the `30 req/min` general limiter (the 1.5s poll loop alone is ~40 req/min and was returning `429` after 30s, silently dropping the second face in `catch{}`).

---

## 11. Presentation Talking Points

### For the Demo

1. Show the admin dashboard with stat cards and inline bias evaluation
2. Walk through student enrollment (capture or upload 5 photos, validate, confirm)
3. Start a live attendance session and show real-time recognition with bounding boxes
4. Show manual attendance roster and error handling for duplicates
5. Run a bias evaluation from the admin dashboard

### For the Q&A

1. **Why dlib as primary with LBPH fallback?** dlib's 128-D ResNet models produce higher accuracy (~95%+) and need only one enrollment image. LBPH ensures the system runs on any machine without CMake or C++ compiler toolchains.
2. **How does tolerance work?** For dlib, tolerance is the Euclidean distance threshold in the 128-D vector space. 0.6 is the standard; lower values are stricter. For LBPH, it maps to the normalized histogram matching distance.
3. **What causes bias?** Training dataset composition (demographic imbalance), camera placement and angles, and room lighting all contribute.
4. **How would you deploy this in production?** Docker Compose for reproducible deployments, move from SQLite to PostgreSQL, add TLS/HTTPS via reverse proxy, use hardware-accelerated CNN models, and add liveness detection (blink analysis or 3D depth).
5. **What about GDPR?** The system requires explicit enrollment and provides deletion. Passwords are stored with PBKDF2-SHA256 (260K iterations, random salt). A production build would need a privacy notice, consent management, and biometric data encryption.
6. **How do you handle security?** Rate limiting on all endpoints (30 req/min general, 5 attempts/min on login), PBKDF2 password hashing with automatic legacy hash upgrade, input validation on frame sizes, and parameterised SQL queries prevent injection.
7. **Why Docker?** Ensures the application runs identically across development, testing, and production. The Dockerfile includes a health check, and docker-compose handles volume mounting for persistent data.

---

## 12. Limitations and Future Work

### 12.1 Current Limitations

| Area | Limitation | Impact |
|------|-----------|--------|
| **Deepfake/Mask Spoofing** | 3D landmark tracking prevents 2D photo attacks, but may not stop sophisticated 3D masks or advanced deepfake video replays | Requires multi-modal sensor (IR/Depth) for true enterprise security |
| **Lighting Sensitivity** | Haar Cascade degrades less after `equalizeHist` tuning, but harsh shadows or strong backlight still lower recall | Reduced detection rate in poorly lit rooms; DNN/MTCNN upgrade planned |
| **Camera Coverage** | One logical stream at a time; external USB vs built-in is selectable, but simultaneous multi-camera aggregation is not yet implemented | Cannot cover multiple entrance points simultaneously |
| **Database** | SQLite is single-writer; no concurrent write scaling | Unsuitable for multi-server horizontal deployment |
| **Authentication** | No JWT/session tokens; frontend-only route protection | API endpoints accessible without auth headers |
| **Bias Dataset** | Evaluation requires manually annotated demographic images | Results depend on dataset size and representativeness |
| **Multi-Face Throughput** | Multi-face now supported (all faces per frame); extreme crowd scenes (>6 faces at 640×480, 0.25 scale) may still drop distant faces due to `minSize` | Increase `FRAME_SCALE` to 0.35 or resolution to 720p for large groups |

### 12.2 Future Improvements

1. **Anti-Spoofing Sensors**: Upgrade from software-based 3D landmark tracking to hardware-based IR/Depth sensors for enterprise-grade security against deepfakes.
2. **JWT Authentication**: Add stateless token-based auth with refresh tokens and role-based middleware on the API layer.
3. **PostgreSQL Migration**: Replace SQLite with PostgreSQL for concurrent write support and production-grade reliability.
4. **CNN-Based Detection**: Upgrade from Haar Cascade to MTCNN or RetinaFace for higher detection accuracy across demographics.
5. **CI/CD Pipeline**: Add GitHub Actions for automated testing, linting, and container builds on every push.
6. **Multi-Camera Support**: Extend the streaming architecture to aggregate frames from multiple camera sources.
7. **Attendance Analytics**: Build dashboards with trend analysis, anomaly detection (e.g., sudden drops in attendance), and automated alerts for lecturers.

---

## 13. Conclusion

This project demonstrates that a functional facial recognition attendance system is achievable with open-source tools, and that bias evaluation is a necessary complement to deployment. The integration of three reference implementations produced a cleaner codebase with improved error handling, configuration management, and a web-based UI. The bias evaluation module provides the transparency needed for responsible use.

Key contributions:
1. A unified architecture combining best practices from three implementations
2. A bias evaluation framework based on Gender Shades methodology
3. A modular design where components can be swapped independently
4. A React frontend with role-based dashboards for admin, lecturer, and student

---

## 14. References

1. Buolamwini, J. and Gebru, T. (2018). "Gender Shades." PMLR 81:1-15.
2. King, D.E. (2009). "Dlib-ml." JMLR 10:1755-1758.
3. Viola, P. and Jones, M. (2001). "Rapid Object Detection." CVPR 1:511-518.
4. Dalal, N. and Triggs, B. (2005). "Histograms of Oriented Gradients." CVPR 1:886-893.
5. Schroff, F. et al. (2015). "FaceNet." CVPR 1:815-823.
6. Deng, J. et al. (2018). "ArcFace." CVPR 1:8358-8366.
7. NIST FRVT (2019). "Face Recognition Vendor Test." NISTIR 8280.

---

## 15. Appendices

### Appendix A: Installation Commands

```bash
# macOS/Linux
./setup.sh

# Windows (PowerShell)
.\setup.ps1
```

Manual setup:

```bash
python -m venv .venv
source .venv/bin/activate    # .venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt
cd frontend && bun install
```

Docker setup:

```bash
# Build and run with Docker Compose
docker compose up -d --build

# Or build manually
docker build -t attendiq .
docker run -p 8000:8000 -v ./data:/app/data attendiq
```

Running tests:

```bash
pytest tests/ -v --cov=core --cov=bias --cov-report=term-missing
```

### Appendix B: Configuration Reference

See `config.ini` for all configurable parameters.

### Appendix C: File Listing

```
facialrecognitionsystem/
├── main.py                     # Legacy Tkinter entry point
├── main_web.py                 # Desktop shell (pywebview)
├── config.ini                  # Configuration file
├── requirements.txt            # Python dependencies
├── pyproject.toml              # Pytest configuration
├── setup.sh / setup.ps1        # Installer scripts
├── dev.sh / dev.ps1            # Dev servers launcher
├── build.sh / build.ps1        # Frontend build scripts
├── Dockerfile                  # Container build definition
├── docker-compose.yml          # Container orchestration
├── .env.example                # Environment variable template
├── LICENSE                     # MIT License
├── PROJECT_DOCUMENTATION.md    # This file
├── README.md                   # Project readme
│
├── core/                       # Core system logic
│   ├── __init__.py
│   ├── config.py               # Config loader (singleton)
│   ├── database.py             # SQLite database layer (PBKDF2 hashing)
│   ├── backend.py              # FastAPI REST + rate limiting + health check
│   ├── face_detector.py        # Face detection (Haar/DNN)
│   ├── face_encoder.py         # Face encoding (dlib/LBPH fallback)
│   ├── data_collector.py       # Training capture helper
│   ├── recognizer.py           # Recognition engine
│   └── attendance.py           # Attendance CSV management
│
├── frontend/                   # React + TypeScript + Vite app
│   ├── src/                    # Components, pages, styling
│   ├── package.json
│   └── vite.config.ts
│
├── bias/                       # Bias evaluation module
│   ├── __init__.py
│   ├── evaluator.py            # Accuracy metrics computer
│   └── datasets.py             # Dataset helpers
│
├── tests/                      # Unit tests (pytest)
│   ├── __init__.py
│   ├── test_config.py          # Config singleton tests
│   ├── test_database.py        # Database CRUD + auth tests
│   ├── test_face_detector.py   # Face detection tests
│   └── test_bias_evaluator.py  # Bias evaluation tests
│
├── data/                       # Runtime data
│   ├── known_faces/            # Enrolled student face images
│   ├── evaluation_dataset/     # Demographic test set images
│   ├── attendance/             # Excel/CSV exports
│   └── users.db                # SQLite database file
│
└── models/                     # Saved models
```
