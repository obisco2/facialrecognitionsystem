"""
AttendIQ — Admin Dashboard.

Four-tab panel:
  1. Users     — create / edit / delete / reset-password for all accounts
  2. Classes   — read-only overview + lecturer reassignment
  3. System    — recognition settings, DB stats, logs
  4. Bias      — run bias evaluation, view fairness report
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, simpledialog
import threading
import os
import logging

from gui.components import (
    PALETTE, FONTS, Card, StatCard, DataTable,
    Sidebar, TopBar, Toast, ConfirmDialog, FormDialog,
    LoadingOverlay, SectionHeader,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User form dialog
# ---------------------------------------------------------------------------

class UserFormDialog(FormDialog):
    def __init__(self, parent, db, user_data: dict = None):
        self._db = db
        self._edit_user = user_data
        title = "Edit User" if user_data else "Add User"
        super().__init__(parent, title, width=460, height=440)

    def build_fields(self):
        d = self._edit_user or {}
        row = 0

        self._full_name = self._labeled_entry("Full Name", tk.StringVar(value=d.get("full_name", "")), row=row)
        row += 1
        self._username = self._labeled_entry("Username", tk.StringVar(value=d.get("username", "")), row=row)
        row += 1

        if not self._edit_user:
            self._password = self._labeled_entry("Password", row=row, show="●")
            row += 1

        self._role = self._labeled_combo(
            "Role", ["student", "lecturer", "admin"],
            tk.StringVar(value=d.get("role", "student")), row=row
        )
        row += 1
        self._student_id = self._labeled_entry("Student ID", tk.StringVar(value=d.get("student_id") or ""), row=row)
        row += 1
        self._email = self._labeled_entry("Email", tk.StringVar(value=d.get("email") or ""), row=row)

        # Dynamically show/hide student_id field based on role
        self._role.trace_add("write", lambda *_: self._toggle_student_id(row - 1))

    def _toggle_student_id(self, student_row):
        pass  # optional UX refinement — always show for simplicity

    def _on_save(self):
        full_name = self._full_name.get().strip()
        username  = self._username.get().strip()
        role      = self._role.get()
        student_id = self._student_id.get().strip() or None
        email     = self._email.get().strip() or None

        if not full_name or not username:
            messagebox.showwarning("Validation", "Full name and username are required.", parent=self)
            return

        if self._edit_user:
            self.submit({
                "full_name": full_name, "username": username,
                "role": role, "student_id": student_id, "email": email,
            })
        else:
            password = self._password.get().strip()
            if not password:
                messagebox.showwarning("Validation", "Password is required for new users.", parent=self)
                return
            self.submit({
                "full_name": full_name, "username": username,
                "role": role, "student_id": student_id, "email": email,
                "password": password,
            })


# ---------------------------------------------------------------------------
# Users Tab
# ---------------------------------------------------------------------------

class UsersTab(ttk.Frame):
    COLUMNS = [
        {"key": "id",       "label": "ID",          "width": 45,  "anchor": "center"},
        {"key": "username", "label": "Username",     "width": 130, "stretch": True},
        {"key": "full_name","label": "Full Name",    "width": 180, "stretch": True},
        {"key": "role",     "label": "Role",         "width": 80,  "anchor": "center"},
        {"key": "sid",      "label": "Student ID",   "width": 110},
        {"key": "enrolled", "label": "Face Enrolled","width": 90,  "anchor": "center"},
        {"key": "created",  "label": "Created",      "width": 110},
    ]

    def __init__(self, parent, db, root_ref):
        super().__init__(parent, style="TFrame")
        self._db = db
        self._root = root_ref
        self._selected_user: dict | None = None
        self._build()
        self.refresh()

    def _build(self):
        # Toolbar
        toolbar = tk.Frame(self, bg=PALETTE["BG"])
        toolbar.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(toolbar, text="＋ Add User",
                   style="Primary.TButton",
                   command=self._add_user).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="✎ Edit",
                   command=self._edit_user).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="🔑 Reset Password",
                   command=self._reset_password).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="✕ Delete",
                   style="Danger.TButton",
                   command=self._delete_user).pack(side=tk.LEFT, padx=(0, 6))

        # Search
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self.refresh())
        ttk.Entry(toolbar, textvariable=self._search_var,
                  width=22).pack(side=tk.RIGHT, padx=(0, 4))
        tk.Label(toolbar, text="🔍", font=("Segoe UI", 11),
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(side=tk.RIGHT)

        # Table
        self._table = DataTable(self, columns=self.COLUMNS, height=20)
        self._table.pack(fill=tk.BOTH, expand=True)
        self._table.bind_select(self._on_select)
        self._table.bind_double_click(lambda e: self._edit_user())

    def refresh(self):
        users = self._db.get_users()
        q = self._search_var.get().lower() if hasattr(self, "_search_var") else ""
        if q:
            users = [u for u in users if q in u["full_name"].lower()
                     or q in u["username"].lower()
                     or (u.get("student_id") or "").lower().find(q) >= 0]

        role_tags = {"admin": "danger", "lecturer": "warning", "student": ""}
        rows, tags = [], []
        for u in users:
            rows.append((
                u["id"], u["username"], u["full_name"],
                u["role"].capitalize(),
                u.get("student_id") or "—",
                "✓" if u.get("face_enrolled") else "✕",
                (u.get("created_at") or "")[:10],
            ))
            tags.append(role_tags.get(u["role"], ""))

        self._table.load(rows, tags)
        self._users_cache = users

    def _on_select(self, _event=None):
        sel = self._table.get_selected_index()
        if sel >= 0 and hasattr(self, "_users_cache"):
            if sel < len(self._users_cache):
                self._selected_user = self._users_cache[sel]

    def _add_user(self):
        dlg = UserFormDialog(self._root, self._db)
        self._root.wait_window(dlg)
        result = dlg.get_result()
        if result:
            try:
                self._db.create_user(
                    result["username"], result["password"], result["role"],
                    result["full_name"], result.get("student_id"), result.get("email")
                )
                self.refresh()
                Toast(self._root, f"User '{result['full_name']}' created.", "success")
            except ValueError as e:
                messagebox.showerror("Error", str(e))

    def _edit_user(self):
        if not self._selected_user:
            messagebox.showinfo("Select User", "Select a user from the table first.")
            return
        dlg = UserFormDialog(self._root, self._db, self._selected_user)
        self._root.wait_window(dlg)
        result = dlg.get_result()
        if result:
            self._db.update_user(self._selected_user["id"], **{
                k: v for k, v in result.items() if k != "password"
            })
            self.refresh()
            Toast(self._root, "User updated.", "success")

    def _reset_password(self):
        if not self._selected_user:
            messagebox.showinfo("Select User", "Select a user first.")
            return
        new_pwd = tk.simpledialog.askstring(
            "Reset Password",
            f"New password for {self._selected_user['full_name']}:",
            parent=self._root, show="*"
        )
        if new_pwd:
            self._db.update_password(self._selected_user["id"], new_pwd)
            Toast(self._root, "Password reset.", "success")

    def _delete_user(self):
        if not self._selected_user:
            messagebox.showinfo("Select User", "Select a user first.")
            return
        dlg = ConfirmDialog(
            self._root,
            "Delete User",
            f"Delete '{self._selected_user['full_name']}'? "
            "This also removes their attendance records.",
            confirm_text="Delete", danger=True
        )
        if dlg.result:
            self._db.delete_user(self._selected_user["id"])
            self._selected_user = None
            self.refresh()
            Toast(self._root, "User deleted.", "info")


# ---------------------------------------------------------------------------
# Classes Tab (read-only for admin)
# ---------------------------------------------------------------------------

class ClassesTab(ttk.Frame):
    COLUMNS = [
        {"key": "code",      "label": "Code",     "width": 90},
        {"key": "name",      "label": "Class Name","width": 200, "stretch": True},
        {"key": "lecturer",  "label": "Lecturer",  "width": 160},
        {"key": "schedule",  "label": "Schedule",  "width": 140},
        {"key": "room",      "label": "Room",      "width": 80},
        {"key": "students",  "label": "Students",  "width": 70, "anchor": "center"},
        {"key": "sessions",  "label": "Sessions",  "width": 70, "anchor": "center"},
    ]

    def __init__(self, parent, db, root_ref):
        super().__init__(parent, style="TFrame")
        self._db = db
        self._root = root_ref
        self._build()
        self.refresh()

    def _build(self):
        toolbar = tk.Frame(self, bg=PALETTE["BG"])
        toolbar.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(toolbar, text="↻ Refresh",
                   command=self.refresh).pack(side=tk.LEFT)

        self._table = DataTable(self, columns=self.COLUMNS, height=22)
        self._table.pack(fill=tk.BOTH, expand=True)

    def refresh(self):
        classes = self._db.get_classes()
        rows = []
        for c in classes:
            sessions = len(self._db.get_attendance_dates(c["id"]))
            rows.append((
                c["code"], c["name"],
                c.get("lecturer_name") or "Unassigned",
                c.get("schedule") or "—",
                c.get("room") or "—",
                c.get("enrolled_count", 0),
                sessions,
            ))
        self._table.load(rows)


# ---------------------------------------------------------------------------
# System Tab
# ---------------------------------------------------------------------------

class SystemTab(ttk.Frame):
    def __init__(self, parent, db, config, root_ref):
        super().__init__(parent, style="TFrame")
        self._db = db
        self._config = config
        self._root = root_ref
        self._build()

    def _build(self):
        canvas = tk.Canvas(self, bg=PALETTE["BG"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=PALETTE["BG"])
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        col1 = tk.Frame(inner, bg=PALETTE["BG"])
        col2 = tk.Frame(inner, bg=PALETTE["BG"])
        col1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8), pady=8)
        col2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=8)

        self._build_recognition(col1)
        self._build_db_stats(col2)
        self._build_security(col1)
        self._build_log_viewer(col2)

    def _build_recognition(self, parent):
        card = Card(parent, "Recognition Settings")
        card.pack(fill=tk.X, pady=(0, 12))

        # Engine
        row = tk.Frame(card, bg=PALETTE["SURFACE"])
        row.pack(fill=tk.X, pady=3)
        tk.Label(row, text="Engine", font=FONTS["LABEL"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"], width=16, anchor="w").pack(side=tk.LEFT)
        self._engine_var = tk.StringVar(value=self._config.recognition_engine)
        ttk.Combobox(row, textvariable=self._engine_var,
                     values=["auto", "dlib", "lbph"],
                     state="readonly", width=12).pack(side=tk.LEFT)

        # Tolerance slider
        row2 = tk.Frame(card, bg=PALETTE["SURFACE"])
        row2.pack(fill=tk.X, pady=3)
        tk.Label(row2, text="Tolerance", font=FONTS["LABEL"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"], width=16, anchor="w").pack(side=tk.LEFT)
        self._tol_var = tk.DoubleVar(value=self._config.tolerance)
        ttk.Scale(row2, from_=0.3, to=0.8, variable=self._tol_var,
                  length=120).pack(side=tk.LEFT, padx=(0, 8))
        self._tol_label = tk.Label(row2, text=f"{self._config.tolerance:.2f}",
                                    font=FONTS["MONO"],
                                    bg=PALETTE["SURFACE"], fg=PALETTE["ACCENT"])
        self._tol_label.pack(side=tk.LEFT)
        self._tol_var.trace_add("write", lambda *_: self._tol_label.configure(
            text=f"{self._tol_var.get():.2f}"
        ))

        # Camera source
        row3 = tk.Frame(card, bg=PALETTE["SURFACE"])
        row3.pack(fill=tk.X, pady=3)
        tk.Label(row3, text="Camera Index", font=FONTS["LABEL"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"], width=16, anchor="w").pack(side=tk.LEFT)
        self._cam_var = tk.StringVar(value=str(self._config.camera_index))
        ttk.Entry(row3, textvariable=self._cam_var, width=6).pack(side=tk.LEFT)

        # RTSP URL
        row4 = tk.Frame(card, bg=PALETTE["SURFACE"])
        row4.pack(fill=tk.X, pady=3)
        tk.Label(row4, text="RTSP URL", font=FONTS["LABEL"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"], width=16, anchor="w").pack(side=tk.LEFT)
        self._rtsp_var = tk.StringVar(value=self._config.stream_url)
        ttk.Entry(row4, textvariable=self._rtsp_var, width=30).pack(side=tk.LEFT)

        # Buttons
        btn_row = tk.Frame(card, bg=PALETTE["SURFACE"])
        btn_row.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_row, text="Save Settings",
                   style="Primary.TButton",
                   command=self._save_recognition).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_row, text="Rebuild Face DB",
                   command=self._rebuild_db).pack(side=tk.LEFT)

    def _build_db_stats(self, parent):
        card = Card(parent, "Database Statistics")
        card.pack(fill=tk.X, pady=(0, 12))

        stats = self._db.get_system_stats()
        items = [
            ("Total Users",       stats["total_users"]),
            ("Students",          stats["total_students"]),
            ("Lecturers",         stats["total_lecturers"]),
            ("Classes",           stats["total_classes"]),
            ("Attendance Records",stats["total_attendance"]),
            ("Face-Enrolled",     stats["enrolled_faces"]),
        ]
        for label, val in items:
            row = tk.Frame(card, bg=PALETTE["SURFACE"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label, font=FONTS["BODY"],
                     bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"],
                     width=20, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=str(val), font=FONTS["LABEL"],
                     bg=PALETTE["SURFACE"], fg=PALETTE["WHITE"]).pack(side=tk.LEFT)

        ttk.Button(card, text="Export Full Database",
                   command=self._export_db).pack(anchor="w", pady=(10, 0))

    def _build_security(self, parent):
        card = Card(parent, "Security")
        card.pack(fill=tk.X, pady=(0, 12))

        tk.Label(card, text="Change Admin Password",
                 font=FONTS["BODY"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"]).pack(anchor="w")

        row = tk.Frame(card, bg=PALETTE["SURFACE"])
        row.pack(fill=tk.X, pady=(6, 0))
        self._new_pwd_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._new_pwd_var,
                  show="●", width=22).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(row, text="Update",
                   command=self._change_password).pack(side=tk.LEFT)

    def _build_log_viewer(self, parent):
        card = Card(parent, "Live Log Viewer")
        card.pack(fill=tk.BOTH, expand=True)

        self._log_text = scrolledtext.ScrolledText(
            card, height=14, bg=PALETTE["PANEL"], fg=PALETTE["TEXT"],
            font=FONTS["MONO"], state=tk.DISABLED, wrap=tk.WORD,
            insertbackground=PALETTE["TEXT"]
        )
        self._log_text.pack(fill=tk.BOTH, expand=True)

        ttk.Button(card, text="↻ Refresh Logs",
                   command=self._load_logs).pack(anchor="w", pady=(6, 0))
        self._load_logs()

    def _load_logs(self):
        log_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "face_recog.log"
        )
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.delete(1.0, tk.END)
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            tail = "".join(lines[-200:])
            self._log_text.insert(tk.END, tail)
            self._log_text.see(tk.END)
        else:
            self._log_text.insert(tk.END, "No log file found.")
        self._log_text.configure(state=tk.DISABLED)

    def _save_recognition(self):
        self._config.set("Recognition", "ENGINE", self._engine_var.get())
        self._config.set("Recognition", "TOLERANCE", f"{self._tol_var.get():.2f}")
        try:
            self._config.set("Camera", "CAMERA_INDEX", self._cam_var.get())
        except Exception:
            pass
        self._config.set("Camera", "STREAM_URL", self._rtsp_var.get().strip())
        Toast(self._root, "Settings saved.", "success")

    def _rebuild_db(self):
        from core.face_detector import FaceDetector
        from core.face_encoder import FaceEncoder
        overlay = LoadingOverlay(self._root, "Rebuilding face database…")

        def worker():
            try:
                encoder = FaceEncoder(engine=self._config.recognition_engine,
                                      tolerance=self._config.tolerance)
                count = encoder.load_known_faces(self._config.known_faces_dir)
                self._root.after(0, overlay.close)
                self._root.after(0, lambda: Toast(
                    self._root, f"Database rebuilt: {len(count[1])} persons.", "success"
                ))
            except Exception as e:
                self._root.after(0, overlay.close)
                self._root.after(0, lambda: Toast(self._root, str(e), "error"))

        threading.Thread(target=worker, daemon=True).start()

    def _change_password(self):
        pwd = self._new_pwd_var.get().strip()
        if len(pwd) < 4:
            Toast(self._root, "Password must be at least 4 characters.", "warning")
            return
        # Find admin user (first admin account)
        admins = self._db.get_users(role="admin")
        if admins:
            self._db.update_password(admins[0]["id"], pwd)
            self._new_pwd_var.set("")
            Toast(self._root, "Password updated.", "success")

    def _export_db(self):
        import csv, zipfile
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP archive", "*.zip")],
            initialfile="attendiq_export.zip",
        )
        if not path:
            return
        try:
            with zipfile.ZipFile(path, "w") as zf:
                for table, getter in [
                    ("users", lambda: self._db.get_users()),
                    ("classes", lambda: self._db.get_classes()),
                ]:
                    rows = getter()
                    if not rows:
                        continue
                    import io
                    buf = io.StringIO()
                    w = csv.DictWriter(buf, fieldnames=rows[0].keys())
                    w.writeheader()
                    w.writerows(rows)
                    zf.writestr(f"{table}.csv", buf.getvalue())
            Toast(self._root, f"Exported to {os.path.basename(path)}", "success")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))


# ---------------------------------------------------------------------------
# Bias Report Tab
# ---------------------------------------------------------------------------

class BiasTab(ttk.Frame):
    def __init__(self, parent, config, root_ref):
        super().__init__(parent, style="TFrame")
        self._config = config
        self._root = root_ref
        self._build()

    def _build(self):
        header = tk.Frame(self, bg=PALETTE["BG"])
        header.pack(fill=tk.X, pady=(0, 16))

        tk.Label(header, text="Bias & Fairness Evaluation",
                 font=FONTS["HEADING"],
                 bg=PALETTE["BG"], fg=PALETTE["WHITE"]).pack(side=tk.LEFT)

        ttk.Button(header, text="▶ Run Evaluation",
                   style="Primary.TButton",
                   command=self._run_evaluation).pack(side=tk.RIGHT)

        self._status_label = tk.Label(
            self, text="Click 'Run Evaluation' to analyse recognition fairness.",
            font=FONTS["BODY"], bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"],
            wraplength=700, justify="left"
        )
        self._status_label.pack(anchor="w", pady=(0, 16))

        # Results area
        self._results_frame = tk.Frame(self, bg=PALETTE["BG"])
        self._results_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(self._results_frame,
                 text="No evaluation has been run yet.",
                 font=FONTS["BODY"],
                 bg=PALETTE["BG"], fg=PALETTE["MUTED"]).pack(pady=40)

    def _run_evaluation(self):
        overlay = LoadingOverlay(self._root, "Running bias evaluation…")

        def worker():
            try:
                from core.face_detector import FaceDetector
                from core.face_encoder import FaceEncoder
                from core.recognizer import Recognizer
                from bias.evaluator import BiasEvaluator
                import os

                detector = FaceDetector(model="haar")
                encoder  = FaceEncoder(engine=self._config.recognition_engine,
                                       tolerance=self._config.tolerance)
                recognizer = Recognizer(detector, encoder)
                recognizer.load_database(self._config.known_faces_dir)

                evaluator = BiasEvaluator(recognizer)
                dataset_dir  = os.path.join(self._config.base_dir,
                                            "data", "evaluation_dataset")
                annotations  = os.path.join(dataset_dir, "annotations.csv")

                if not os.path.exists(annotations):
                    self._root.after(0, overlay.close)
                    self._root.after(0, lambda: self._show_no_dataset())
                    return

                metrics = evaluator.evaluate(dataset_dir, annotations)
                self._root.after(0, overlay.close)
                self._root.after(0, lambda m=metrics: self._render_results(m))
            except Exception as e:
                logger.exception("Bias evaluation error")
                self._root.after(0, overlay.close)
                self._root.after(0, lambda: Toast(self._root, str(e), "error"))

        threading.Thread(target=worker, daemon=True).start()

    def _show_no_dataset(self):
        for w in self._results_frame.winfo_children():
            w.destroy()
        tk.Label(self._results_frame,
                 text="⚠  No evaluation dataset found.\n\n"
                      "Place labelled face images in:\n"
                      "  data/evaluation_dataset/<Type>/<image.jpg>\n"
                      "and create an annotations.csv with columns:\n"
                      "  filename, skin_type, gender, identity",
                 font=FONTS["BODY"], bg=PALETTE["BG"], fg=PALETTE["WARNING"],
                 justify="left").pack(pady=20, padx=20, anchor="w")

    def _render_results(self, metrics: dict):
        for w in self._results_frame.winfo_children():
            w.destroy()

        if not metrics:
            tk.Label(self._results_frame, text="Evaluation returned no results.",
                     font=FONTS["BODY"], bg=PALETTE["BG"],
                     fg=PALETTE["SUBTEXT"]).pack(pady=20)
            return

        overall = metrics.get("overall", {})
        detection  = overall.get("detection_rate", 0)
        accuracy   = overall.get("recognition_accuracy", 0)

        # Overall stats
        stats_row = tk.Frame(self._results_frame, bg=PALETTE["BG"])
        stats_row.pack(fill=tk.X, pady=(0, 20))

        for label, val, colour in [
            ("Detection Rate",     f"{detection:.1%}",   PALETTE["INFO"]),
            ("Recognition Accuracy", f"{accuracy:.1%}", PALETTE["SUCCESS"]),
        ]:
            sc = StatCard(stats_row, label, val, color=colour)
            sc.pack(side=tk.LEFT, padx=(0, 12))

        # By skin type
        skin_card = Card(self._results_frame, "Accuracy by Skin Type (Fitzpatrick Scale)")
        skin_card.pack(fill=tk.X, pady=(0, 12))

        for st, m in metrics.get("by_skin_type", {}).items():
            pct = m.get("accuracy", 0) * 100
            self._bar_row(skin_card, f"Type {st}", pct, m.get("count", 0))

        # By gender
        gen_card = Card(self._results_frame, "Accuracy by Gender")
        gen_card.pack(fill=tk.X, pady=(0, 12))

        for g, m in metrics.get("by_gender", {}).items():
            pct = m.get("accuracy", 0) * 100
            self._bar_row(gen_card, g, pct, m.get("count", 0))

        # Disparity note
        try:
            from core.recognizer import Recognizer
            from core.face_detector import FaceDetector
            from core.face_encoder import FaceEncoder
            from bias.evaluator import BiasEvaluator
            encoder   = FaceEncoder(engine=self._config.recognition_engine)
            detector  = FaceDetector()
            recognizer = Recognizer(detector, encoder)
            evaluator = BiasEvaluator(recognizer)
            evaluator._metrics = metrics
            disparity = evaluator.get_disparity_report()
            if disparity:
                disp_card = Card(self._results_frame, "Disparity Report")
                disp_card.pack(fill=tk.X)
                sd = disparity.get("skin_type_disparity", {})
                if sd:
                    gap = sd.get("gap", 0)
                    colour = PALETTE["DANGER"] if gap > 0.1 else PALETTE["SUCCESS"]
                    tk.Label(disp_card,
                             text=f"Skin-type accuracy gap: {gap:.1%}  "
                                  f"({sd.get('worst_group','?')} → {sd.get('best_group','?')})",
                             font=FONTS["BODY"], bg=PALETTE["SURFACE"],
                             fg=colour).pack(anchor="w", pady=2)
                gd = disparity.get("gender_disparity", {})
                if gd:
                    gap = gd.get("gap", 0)
                    colour = PALETTE["DANGER"] if gap > 0.1 else PALETTE["SUCCESS"]
                    tk.Label(disp_card,
                             text=f"Gender accuracy gap:    {gap:.1%}  "
                                  f"({gd.get('worst_group','?')} → {gd.get('best_group','?')})",
                             font=FONTS["BODY"], bg=PALETTE["SURFACE"],
                             fg=colour).pack(anchor="w", pady=2)
        except Exception:
            pass

    def _bar_row(self, parent, label: str, pct: float, count: int):
        row = tk.Frame(parent, bg=PALETTE["SURFACE"])
        row.pack(fill=tk.X, pady=3)

        tk.Label(row, text=label, font=FONTS["BODY"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["TEXT"],
                 width=14, anchor="w").pack(side=tk.LEFT)

        style = "TProgressbar" if pct >= 75 else (
            "Warning.TProgressbar" if pct >= 60 else "Danger.TProgressbar"
        )
        bar = ttk.Progressbar(row, value=pct, maximum=100,
                              style=style, length=260)
        bar.pack(side=tk.LEFT, padx=(0, 8))

        colour = PALETTE["SUCCESS"] if pct >= 75 else (
            PALETTE["WARNING"] if pct >= 60 else PALETTE["DANGER"]
        )
        tk.Label(row, text=f"{pct:.1f}%  (n={count})",
                 font=FONTS["MONO"], bg=PALETTE["SURFACE"],
                 fg=colour).pack(side=tk.LEFT)


# ---------------------------------------------------------------------------
# Admin Dashboard shell
# ---------------------------------------------------------------------------

class AdminDashboard(tk.Frame):
    """Full admin panel with sidebar + tabbed content."""

    NAV_ITEMS = [
        {"key": "users",   "icon": "👤", "label": "Users"},
        {"key": "classes", "icon": "📚", "label": "Classes"},
        {"key": "system",  "icon": "⚙",  "label": "System"},
        {"key": "bias",    "icon": "📊", "label": "Bias Report"},
    ]

    def __init__(self, parent, user: dict, db, config, on_logout):
        super().__init__(parent, bg=PALETTE["BG"])
        self.pack(fill=tk.BOTH, expand=True)
        self._user = user
        self._db   = db
        self._config = config
        self._on_logout = on_logout
        self._panels: dict[str, tk.Frame] = {}
        self._build()
        self._sidebar.select("users")

    def _build(self):
        # Top bar
        TopBar(self, self._user, self._on_logout).pack(fill=tk.X)

        # Body
        body = tk.Frame(self, bg=PALETTE["BG"])
        body.pack(fill=tk.BOTH, expand=True)

        self._sidebar = Sidebar(body, self.NAV_ITEMS,
                                on_select=self._switch_panel, width=200)
        self._sidebar.pack(side=tk.LEFT, fill=tk.Y)

        self._content = tk.Frame(body, bg=PALETTE["BG"])
        self._content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                           padx=20, pady=20)

        # Instantiate all panels (only one visible at a time)
        self._panels["users"]   = UsersTab(self._content, self._db, self.winfo_toplevel())
        self._panels["classes"] = ClassesTab(self._content, self._db, self.winfo_toplevel())
        self._panels["system"]  = SystemTab(self._content, self._db, self._config, self.winfo_toplevel())
        self._panels["bias"]    = BiasTab(self._content, self._config, self.winfo_toplevel())

    def _switch_panel(self, key: str):
        for panel in self._panels.values():
            panel.pack_forget()
        self._panels[key].pack(fill=tk.BOTH, expand=True)

    def shutdown(self):
        pass  # nothing to release in admin panel
