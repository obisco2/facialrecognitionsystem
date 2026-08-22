# Phase 0 — Foundation

## Goal
Establish the data layer, upgrade the recognition engine, and update all configuration before any UI is built. Everything in Phase 1–4 depends on this being solid.

## Files to Create / Modify

### NEW: `core/database.py`
SQLite database manager. Handles schema creation, migrations, and all CRUD operations.

**Schema:**
```sql
CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,           -- SHA-256 hex digest
    role        TEXT NOT NULL,             -- 'admin' | 'lecturer' | 'student'
    full_name   TEXT NOT NULL,
    student_id  TEXT,                      -- NULL for admin/lecturer
    email       TEXT,
    face_enrolled INTEGER DEFAULT 0,       -- 0 | 1
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE classes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    code        TEXT NOT NULL,
    lecturer_id INTEGER REFERENCES users(id),
    schedule    TEXT,                      -- e.g. "Mon/Wed 09:00-10:30"
    room        TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE enrollments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER REFERENCES users(id),
    class_id    INTEGER REFERENCES classes(id),
    enrolled_at TEXT DEFAULT (datetime('now')),
    UNIQUE(student_id, class_id)
);

CREATE TABLE attendance_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   INTEGER REFERENCES users(id),
    class_id     INTEGER REFERENCES classes(id),
    session_date TEXT NOT NULL,            -- YYYY-MM-DD
    timestamp    TEXT NOT NULL,            -- HH:MM:SS
    method       TEXT DEFAULT 'face',      -- 'face' | 'manual'
    confidence   REAL,                     -- LBPH/dlib distance (lower = better)
    marked_by    INTEGER REFERENCES users(id)  -- lecturer who triggered session
);
```

**Key methods:**
- `DatabaseManager(db_path)` — creates DB and tables on first run
- `seed_default_admin()` — creates admin/admin if no users exist
- `create_user(username, password, role, full_name, ...)` → user id
- `authenticate(username, password)` → user dict or None
- `get_users(role=None)` → list of user dicts
- `update_user(id, **fields)` / `delete_user(id)`
- `create_class(name, code, lecturer_id, schedule, room)` → class id
- `get_classes(lecturer_id=None)` → list
- `enroll_student(student_id, class_id)`
- `get_enrolled_students(class_id)` → list
- `log_attendance(student_id, class_id, date, time, method, confidence, marked_by)`
- `get_attendance(class_id, date)` → list
- `get_student_attendance(student_id, class_id=None)` → list
- `get_attendance_summary(class_id, date)` → {present, total, percent}

### UPDATED: `core/face_encoder.py`
Add dlib `face_recognition` as primary encoder with LBPH as fallback.

**Changes:**
- Try `import face_recognition` on init; set `self.use_dlib = True/False`
- When dlib available: use `face_recognition.face_encodings()` for 128-d embeddings
- Store encodings as numpy arrays in `known_encodings` list
- `identify()`: use `face_recognition.compare_faces()` + `face_recognition.face_distance()`
- Keep full LBPH path as fallback (existing code unchanged)
- Add `encode_image_file(filepath)` — encodes a single image file, used by enrollment

### UPDATED: `config.ini`
New keys:
```ini
[Database]
DB_PATH = data/users.db

[Camera]
STREAM_URL =           ; RTSP/HTTP URL, blank = use CAMERA_INDEX

[Recognition]
ENGINE = auto          ; 'auto' (dlib if available), 'lbph', 'dlib'
MIN_ENROLLMENT_PHOTOS = 5

[UI]
THEME = dark
APP_NAME = AttendIQ
```

### UPDATED: `requirements.txt`
```
opencv-contrib-python>=4.8.0
numpy>=1.24.0
Pillow>=10.0.0
scikit-learn>=1.3.0
matplotlib>=3.7.0
pandas>=2.0.0
face_recognition>=1.3.0    # dlib HOG-SVM 128-d embeddings
tkcalendar>=1.6.1           # date picker for attendance history
```

## Acceptance Criteria
- [ ] `python -c "from core.database import DatabaseManager; db = DatabaseManager('data/test.db'); print('OK')"` exits 0
- [ ] Default admin user created on first run (username: `admin`, password: `admin`)
- [ ] `core/face_encoder.py` imports without error whether or not `face_recognition` is installed
- [ ] `config.ini` has all new keys
