# Phase 2 — Lecturer UI

## Goal
Full lecturer workflow: manage classes, run live face-recognition attendance sessions (including RTSP/IP camera), view history, and export reports.

## Files to Create

### `gui/lecturer/dashboard.py` — `LecturerDashboard`
Top-level lecturer shell with sidebar navigation.

**Layout:**
```
┌──────────┬───────────────────────────────────────────┐
│          │  [top bar: greeting + logout]              │
│ SIDEBAR  ├───────────────────────────────────────────┤
│          │                                            │
│ 🏠 Home  │  [content frame — swapped by sidebar nav] │
│ 📚 Classes│                                            │
│ 📷 Live  │                                            │
│ 📋 History│                                           │
│ 📤 Export│                                            │
│          │                                            │
│ [Logout] │                                            │
└──────────┴───────────────────────────────────────────┘
```

**Home sub-panel:**
- 3 stat cards: "My Classes", "Sessions Today", "Students Enrolled"
- Recent activity table (last 5 attendance sessions)

### `gui/lecturer/class_manager.py` — `ClassManagerPanel`
Embedded in the "Classes" sidebar item.

**Features:**
- `DataTable` showing: Code | Name | Schedule | Room | Students | Actions
- "New Class" button → modal dialog with fields: name, code, schedule, room
- Edit button per row → same modal pre-filled
- Delete button → confirmation dialog
- "Manage Students" per class → opens a sub-panel:
  - Left: all students in system (searchable)
  - Right: enrolled students in this class
  - Add/Remove buttons

### `gui/lecturer/attendance_viewer.py` — `AttendanceViewerPanel`
The centerpiece of the whole system. Split into two tabs: **Live Session** and **History**.

#### Live Session tab:
```
┌─────────────────────────────┬─────────────────────────┐
│  CAMERA FEED (640×480)      │  Session Controls        │
│                             │  Class: [dropdown]       │
│  [face boxes + name labels] │  Date:  [auto today]     │
│                             │                          │
│                             │  Camera Source:          │
│                             │  ○ Webcam  [index: 0]    │
│                             │  ○ IP/RTSP [url field]   │
│                             │                          │
│                             │  [▶ START SESSION]       │
│                             │  [⏹ STOP SESSION]        │
│                             ├─────────────────────────┤
│                             │  Present (live list)     │
│                             │  ┌───────────────────┐  │
│                             │  │ 09:14 Alice K.  ✓ │  │
│                             │  │ 09:15 Bob M.    ✓ │  │
│                             │  └───────────────────┘  │
│                             │  [+ Add Manually]        │
└─────────────────────────────┴─────────────────────────┘
```

**Behaviour:**
- Camera source toggle: local index (int) or RTSP/HTTP URL (string)
  - `cv2.VideoCapture(0)` vs `cv2.VideoCapture("rtsp://...")`
- Session must be started before attendance is recorded
- Each recognized face: logs to `attendance_log` table with confidence score
- Manual add: dropdown of enrolled students → adds with `method='manual'`
- Live list animates new entries (green flash)
- FPS counter in camera feed corner
- "Unknown face" counter — shows how many unrecognized faces were seen

**IP Camera support:**
- URL field with validation (must start with `rtsp://`, `http://`, or be numeric)
- "Test Connection" button — attempts to open stream and grab one frame, shows preview
- Saves last-used URL to config

#### History tab:
- Class selector + date picker (`tkcalendar.DateEntry`)
- `DataTable`: Student ID | Name | Time | Method | Confidence
- Confidence column colour-coded: green (< 0.4), yellow (0.4–0.6), red (> 0.6 = uncertain)
- Edit row: change method, remove record
- Summary bar: "X / Y students present (Z%)"

### `gui/lecturer/export_manager.py` — `ExportManagerPanel`

**Features:**
- Class selector + date range (from/to date pickers)
- Format selector: CSV | Excel (.xlsx)
- Preview table of what will be exported
- Export button → file save dialog
- "Full Report" mode: exports one sheet per class with summary stats header
- Summary stats included: total sessions, average attendance %, best/worst session

**CSV structure exported:**
```
Class: CS101 - Introduction to Computing
Lecturer: Dr. Jane Smith
Period: 2026-08-01 to 2026-08-15
---
Student ID, Name, Sessions Present, Total Sessions, Attendance %
STU001, Alice Kamara, 8, 10, 80%
...
```

## Acceptance Criteria
- [ ] Lecturer can create, edit, and delete a class
- [ ] Lecturer can enroll/unenroll students in a class
- [ ] Live session starts, camera feed shows, recognized faces are logged
- [ ] RTSP URL accepted and stream opened when valid
- [ ] History tab shows correct records for selected class + date
- [ ] CSV export downloads a correctly formatted file
- [ ] Confidence scores stored in DB and colour-coded in history view
