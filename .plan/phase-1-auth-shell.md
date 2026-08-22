# Phase 1 — Auth Shell

## Goal
Build the login screen, top-level router, shared component library, and update `main.py`. After this phase the app boots, shows a login form, and routes to a placeholder dashboard based on role.

## Files to Create / Modify

### NEW: `gui/components.py`
Shared styled widget library. All screens import from here for visual consistency.

**Components:**
- `PALETTE` dict — all hex colours in one place (`BG`, `PANEL`, `ACCENT`, `SUCCESS`, `TEXT`, `SUBTEXT`, `BORDER`)
- `apply_dark_theme(root)` — sets `ttk.Style` with clam, configures all widget defaults
- `Card(parent, title, **kwargs)` — a `ttk.Frame` with a title label, rounded feel via padx/pady
- `StatCard(parent, label, value, icon="")` — mini card for dashboard stats (e.g. "85% Attendance")
- `DataTable(parent, columns, data)` — `ttk.Treeview` with alternating row colours + scrollbars
- `PrimaryButton(parent, text, command)` — styled accent button
- `SecondaryButton(parent, text, command)` — styled secondary button  
- `DangerButton(parent, text, command)` — red destructive button
- `Toast(root, message, kind="info")` — temporary overlay notification (appears bottom-right, fades after 2.5s)
- `SectionHeader(parent, text)` — bold section label with bottom border
- `Avatar(parent, name, size=48)` — coloured circle with initials (when no photo)
- `ProgressBar(parent, value, max_value)` — styled progress bar for attendance percentage
- `Sidebar(parent, items, on_select)` — vertical nav rail with icon + label items

### NEW: `gui/login.py`
Login screen — the first thing the user sees.

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  [left panel 40%]          [right panel 60%]         │
│                                                       │
│  Logo + App name           AttendIQ                  │
│  "Facial Recognition       ──────────────            │
│   Attendance System"       Username  [          ]    │
│                            Password  [          ]    │
│  Animated face scan                                  │
│  illustration (canvas)     [  Sign In  ]             │
│                                                       │
│                            Role: ○ Admin ○ Lecturer  │
│                                  ○ Student           │
└─────────────────────────────────────────────────────┘
```

**Behaviour:**
- On "Sign In": call `db.authenticate(username, password)`
- If success: destroy login window, instantiate correct dashboard based on `user['role']`
- If fail: shake animation on the form + red error label "Invalid credentials"
- `Enter` key triggers sign-in
- Password field masks input
- Show/hide password toggle (eye icon via unicode)
- Role radio buttons are cosmetic only (for UX clarity) — actual role comes from DB

**Animations:**
- Canvas-based animated "scan ring" that pulses around a face silhouette icon
- Login form slides in from right on load

### REFACTORED: `gui/app.py`
No longer a recognition app itself. Becomes `AttendIQApp` — the root `Tk` window manager.

**Responsibilities:**
- Create the root `tk.Tk()` window (1400×850, resizable, minimum 1200×700)
- Apply the dark theme via `components.apply_dark_theme()`
- Instantiate `DatabaseManager` and `Config` and pass them down
- Instantiate `LoginScreen(root, db, config, on_login_success)`
- `on_login_success(user)` callback: destroy login frame, mount correct dashboard
- Hold references to prevent GC on images/frames
- `main()` function that creates and runs `AttendIQApp`

**Dashboard routing:**
```python
def on_login_success(self, user):
    if user['role'] == 'admin':
        from gui.admin.dashboard import AdminDashboard
        AdminDashboard(self.root, user, self.db, self.config)
    elif user['role'] == 'lecturer':
        from gui.lecturer.dashboard import LecturerDashboard
        LecturerDashboard(self.root, user, self.db, self.config)
    elif user['role'] == 'student':
        from gui.student.dashboard import StudentDashboard
        StudentDashboard(self.root, user, self.db, self.config)
```

### UPDATED: `main.py`
- Remove old CLI flags (keep `--evaluate` for bias module)
- Default: `python main.py` → boots `AttendIQApp`
- `python main.py --evaluate` → bias evaluation CLI (unchanged)

## Acceptance Criteria
- [ ] `python main.py` opens the login window without errors
- [ ] Correct username/password routes to the correct (placeholder) dashboard
- [ ] Wrong credentials shows error message
- [ ] Window is 1400×850, dark themed, title is "AttendIQ"
- [ ] All shared components importable: `from gui.components import Toast, DataTable`
