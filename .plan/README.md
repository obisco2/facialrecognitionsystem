# Facial Recognition Attendance System — Implementation Plan

## Project Objective
Build a production-quality, multi-role attendance management system powered by real-time facial recognition. Designed as an impressive final-year project demonstrating ethical AI awareness, role-based access control, and real-world deployment considerations (IP camera streaming, bias evaluation, audit trails).

## Architecture Summary

```
facialrecognitionsystem/
├── .plan/                    ← This folder — implementation roadmap
├── core/
│   ├── database.py           ← NEW: SQLite layer (users, classes, attendance)
│   ├── face_encoder.py       ← UPDATED: dlib 128-d embeddings + LBPH fallback
│   ├── face_detector.py      ← existing
│   ├── recognizer.py         ← existing
│   ├── attendance.py         ← existing (DB-backed in new system)
│   ├── data_collector.py     ← existing
│   └── config.py             ← existing
├── gui/
│   ├── app.py                ← REFACTORED: top-level role router
│   ├── login.py              ← NEW: login screen
│   ├── components.py         ← NEW: shared styled widgets
│   ├── admin/
│   │   └── dashboard.py      ← NEW: admin panel (users, system, bias)
│   ├── lecturer/
│   │   ├── dashboard.py      ← NEW: tabbed lecturer home
│   │   ├── class_manager.py  ← NEW: create/manage classes
│   │   ├── attendance_viewer.py ← NEW: live recognition + history + RTSP
│   │   └── export_manager.py ← NEW: CSV/PDF export
│   └── student/
│       ├── dashboard.py      ← NEW: summary cards
│       ├── attendance_history.py ← NEW: per-class records
│       └── enrollment.py     ← NEW: photo upload + face validation
├── data/
│   ├── attendance/
│   ├── known_faces/
│   ├── training/
│   └── users.db              ← NEW: SQLite database
├── main.py                   ← UPDATED: boots multi-role app
├── config.ini                ← UPDATED: new keys
└── requirements.txt          ← UPDATED: face_recognition, tkcalendar
```

## Tech Stack
- **GUI**: Tkinter + ttk (dark theme, `#1a1a2e` / `#e94560` / `#16c79a` palette)
- **Database**: SQLite via Python `sqlite3` (zero new dependencies, upgradable to MySQL)
- **Face Recognition**: dlib `face_recognition` (128-d HOG-SVM embeddings) + OpenCV LBPH fallback
- **Camera**: `cv2.VideoCapture` supporting local index AND RTSP/HTTP IP camera URLs
- **Export**: CSV via `csv` module + pandas for Excel export

## Phases
| Phase | Focus | Files |
|-------|-------|-------|
| 0 | Foundation — DB + config + encoder upgrade | `core/database.py`, `core/face_encoder.py`, `config.ini`, `requirements.txt` |
| 1 | Auth shell — login + router | `gui/login.py`, `gui/app.py`, `gui/components.py`, `main.py` |
| 2 | Lecturer UI | `gui/lecturer/` (4 files) |
| 3 | Student UI | `gui/student/` (3 files) |
| 4 | Admin UI + polish | `gui/admin/dashboard.py` |

## What Makes This Impressive
1. **dlib 128-d face embeddings** — same algorithm behind commercial systems; significantly better than LBPH alone
2. **Role-based access control** backed by a real database with hashed passwords
3. **Student self-enrollment with automated quality validation** — rejects blurry/no-face images, tests recognition before committing
4. **RTSP/IP camera streaming** — real-world deployment beyond a laptop webcam
5. **Confidence score audit trail** — every attendance record stores recognition confidence
6. **Bias evaluation dashboard** — ethical AI awareness; the academic differentiator
7. **Live attendance with real-time overlay** — face boxes, name labels, confidence bars all updating at 25fps
