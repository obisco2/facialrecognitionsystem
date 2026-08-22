# Phase 3 — Student UI

## Goal
Give students a self-service portal: enroll their face, view their own attendance records, and get clear feedback on their standing per class.

## Files to Create

### `gui/student/dashboard.py` — `StudentDashboard`
Top-level student shell with sidebar navigation.

**Sidebar items:** Home | My Attendance | Enroll Face | [Logout]

**Home sub-panel:**
```
┌──────────────────────────────────────────────────────┐
│  Welcome back, Alice 👋                              │
│  Student ID: STU2024001                               │
├──────────────────────────────────────────────────────┤
│  [Avatar/photo]                                       │
│                                                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │  3 Classes   │ │  78% Avg     │ │  ⚠ 1 Warning  │  │
│  │  Enrolled    │ │  Attendance  │ │  < 75% cutoff │  │
│  └──────────────┘ └──────────────┘ └──────────────┘  │
│                                                       │
│  My Classes                                           │
│  ┌──────────────────────────────────────────────────┐ │
│  │ CS101  Intro Computing  [████████░░] 80%  ✓ OK  │ │
│  │ CS202  Data Structures  [█████░░░░░] 50%  ⚠ LOW │ │
│  │ CS303  Algorithms       [████████░░] 78%  ✓ OK  │ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
│  Face Enrollment Status:  ✅ Enrolled                 │
└──────────────────────────────────────────────────────┘
```

**Attendance % colour coding:**
- ≥ 75%: green (`#16c79a`)
- 60–74%: yellow (`#f5a623`)
- < 60%: red (`#e94560`) + warning banner

### `gui/student/attendance_history.py` — `AttendanceHistoryPanel`
Detailed per-class attendance breakdown.

**Layout:**
- Class selector dropdown at top
- Summary row: X present / Y total sessions = Z%
- `ProgressBar` showing attendance percentage
- `DataTable`: Date | Day | Time | Status | Recognition Method
  - Status: "Present ✓" (green) or "Absent ✗" (red/grey)
  - Recognition Method: "Face Recognition" or "Manual" (shows badge)
- Calendar heatmap (optional visual): mini month grid, green = present, red = absent, grey = no class
- "Download My Records" button → exports personal CSV

### `gui/student/enrollment.py` — `EnrollmentPanel`
The most technically impressive student-facing screen.

**5-step wizard:**

#### Step 1 — Introduction
```
┌─────────────────────────────────────────────┐
│  📷  Face Enrollment                         │
│  ─────────────────────────────────────────  │
│  To be recognized automatically in class,   │
│  you need to register your face.            │
│                                             │
│  What we need:                              │
│  • 5 clear photos of your face              │
│  • Good, even lighting                      │
│  • No sunglasses or hats                    │
│  • Different angles (optional but better)   │
│                                             │
│  Your photos are stored securely on-site    │
│  and never shared externally.               │
│                                             │
│  [  Begin Enrollment  ]                     │
└─────────────────────────────────────────────┘
```

#### Step 2 — Photo Collection
Two modes (tab toggle):
- **Upload Photos**: file picker (multi-select, .jpg/.png), shows thumbnails in a 5-slot grid
- **Capture Live**: opens camera, "Capture" button per slot, 5 slots to fill

Slot states: empty (grey placeholder), filled (thumbnail), validated ✓ / rejected ✗

#### Step 3 — Validation
For each uploaded/captured photo:
- Runs `face_detector.detect_faces()` to confirm a face exists
- Checks face region size (rejects if < 60×60 px — too far away)
- Runs blur detection (`cv2.Laplacian` variance — rejects if < 100)
- Shows per-photo result:
  - ✅ "Face detected (confidence: high)"
  - ⚠ "Face detected but image is blurry — retake recommended"
  - ❌ "No face detected — please retake this photo"

Requires minimum 3 valid photos to proceed (ideally 5).

#### Step 4 — Recognition Test (Impressive Differentiator)
```
┌─────────────────────────────────────────────┐
│  Let's test if we can recognize you          │
│  ─────────────────────────────────────────  │
│                                             │
│  [Camera feed — live]                       │
│                                             │
│  Status: Scanning...                        │
│                                             │
│  [  Run Recognition Test  ]                 │
│                                             │
│  Result:  ✅  Recognized as: Alice Kamara   │
│           Confidence: 92%                   │
│                                             │
│  [  Confirm & Enroll  ]  [  Retake Photos ] │
└─────────────────────────────────────────────┘
```

- Temporarily saves the enrollment photos to `data/known_faces/{student_id}/`
- Rebuilds face encoder with new data (in a thread to avoid UI freeze)
- Grabs a live frame and attempts recognition
- Shows recognized name + confidence
- If recognized correctly: enable "Confirm & Enroll"
- If not recognized: show "Try retaking in better lighting" + "Retake Photos" option

#### Step 5 — Confirmation
- Cleans up temp files, moves photos to permanent location
- Updates `users.face_enrolled = 1` in DB
- Shows success screen with confetti animation (canvas-based)
- "Go to Dashboard" button

## Acceptance Criteria
- [ ] Student dashboard shows correct stats from DB
- [ ] Low attendance warning shown when class < 75%
- [ ] Attendance history shows correct per-class breakdown
- [ ] Enrollment wizard flows through all 5 steps
- [ ] Photo validation correctly detects and rejects blurry/no-face images
- [ ] Recognition test uses real face encoder against submitted photos
- [ ] On success, `face_enrolled = 1` is set in DB and photos saved
