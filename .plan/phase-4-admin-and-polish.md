# Phase 4 — Admin UI + Polish

## Goal
Build the admin dashboard with full system control, then apply final UI polish across all screens.

## Files to Create / Modify

### `gui/admin/dashboard.py` — `AdminDashboard`
Full system management panel. Tabbed layout.

**Layout (tabbed with sidebar):**
```
┌──────────┬──────────────────────────────────────────────┐
│          │  [top bar: "Admin Panel" + logout]            │
│ SIDEBAR  ├──────────────────────────────────────────────┤
│          │ [tab: Users] [tab: Classes] [tab: System]     │
│ 👤 Users  │  [tab: Bias Report]                          │
│ 📚 Classes│                                              │
│ ⚙ System │  [tab content]                               │
│ 📊 Bias  │                                              │
└──────────┴──────────────────────────────────────────────┘
```

#### Users Tab
- `DataTable`: ID | Name | Username | Role | Student ID | Face Enrolled | Created
- Toolbar: "Add User" | "Edit" | "Delete" | "Reset Password" | Search box
- "Add/Edit User" dialog:
  - Full name, username, password, role (dropdown), student ID (shown only for student role), email
  - Role change confirmation if existing user
- "Reset Password" → dialog to set new password
- Bulk actions: select multiple → delete, export

#### Classes Tab
- `DataTable`: Code | Name | Lecturer | Schedule | Room | Enrolled Students | Sessions
- Read-only view for admin (management is done by lecturer)
- "Assign Lecturer" action — reassign a class to different lecturer

#### System Tab
Four sub-sections:

**Recognition Settings:**
- Engine dropdown: Auto | dlib | LBPH
- Tolerance slider (0.3–0.8) with live label showing current value + meaning
- Frame scale slider (0.1–1.0)
- Camera index input + RTSP URL input
- "Test Camera" button
- "Rebuild Face Database" button → runs encoder.load_known_faces() in thread

**Database:**
- DB stats: total users, total classes, total attendance records
- "Export Full DB" → dumps all tables to CSV in a zip
- "Clear Attendance Data" → confirmation dialog (destructive)

**Security:**
- Change admin password
- Session timeout setting

**Logging:**
- Live log viewer (tails `face_recog.log`)
- Log level dropdown
- "Clear Logs" button

#### Bias Report Tab
The ethical AI differentiator — shows recognition accuracy disparities across demographics.

```
┌────────────────────────────────────────────────────────┐
│  Bias & Fairness Evaluation                            │
│  ────────────────────────────────────────────────────  │
│                                                        │
│  [Run Evaluation]  Last run: 2026-08-10                │
│                                                        │
│  Overall Accuracy: 87.3%                               │
│                                                        │
│  By Skin Type (Fitzpatrick Scale):                     │
│  Type I  ████████████░░  91%                          │
│  Type II ████████████░░  90%                          │
│  Type III██████████░░░░  82%                          │
│  Type IV ██████████░░░░  84%                          │
│  Type V  █████████░░░░░  78%                          │
│  Type VI ████████░░░░░░  74%  ⚠ Gap: 17pp             │
│                                                        │
│  By Gender:                                            │
│  Male    ████████████░░  89%                          │
│  Female  ██████████░░░░  83%  ⚠ Gap: 6pp              │
│                                                        │
│  Recommendation: collect more training data for        │
│  darker skin tones to reduce disparity.               │
└────────────────────────────────────────────────────────┘
```

- Calls `bias.evaluator.BiasEvaluator` in a thread
- Renders results as styled progress bars with percentage labels
- Disparity warnings when gap > 10pp
- "Export Bias Report" → PDF/CSV

### Polish Pass (all screens)

**Loading states:**
- All DB queries show a spinner overlay (`tk.Toplevel` with animated dots) if > 200ms
- Camera initialization shows "Connecting..." overlay
- Face database rebuild shows progress bar

**Toast notifications:**
- Attendance marked → `Toast("Alice marked present ✓", kind="success")`
- Export complete → `Toast("Report saved to Downloads/", kind="info")`
- Error → `Toast("Camera disconnected", kind="error")`

**Keyboard shortcuts:**
- `Ctrl+L` → logout from any dashboard
- `Ctrl+E` → jump to export
- `Enter` → confirm dialog
- `Escape` → close modal/dialog

**Responsive behaviour:**
- Minimum window size: 1200×700
- Sidebar collapses to icon-only mode below 1300px width
- Tables scroll horizontally when columns overflow

**Accessibility:**
- All buttons have keyboard focus ring
- Tab order follows visual layout
- Error states use both colour and text (not colour alone)

## Final Integration Checklist
- [ ] All four dashboards accessible from login
- [ ] Logout from any dashboard returns to login screen (session cleared)
- [ ] DB changes in admin panel reflected immediately in lecturer/student views
- [ ] Camera source (RTSP URL) persists to config.ini on change
- [ ] Face enrollment in student portal immediately available for lecturer sessions
- [ ] Bias report tab functional with sample or real dataset
- [ ] All `Toast` notifications working across all screens
- [ ] No threading crashes (all CV2/DB calls off main thread where needed)
- [ ] App closes cleanly (camera released, DB connection closed) on window X
