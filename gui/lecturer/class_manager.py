"""
AttendIQ — Lecturer Class Manager.
Create / edit / delete classes and manage student enrolments.
"""

import tkinter as tk
from tkinter import ttk, messagebox

from gui.components import (
    PALETTE, FONTS, Card, DataTable, Toast,
    ConfirmDialog, FormDialog, SectionHeader,
)


class ClassFormDialog(FormDialog):
    def __init__(self, parent, class_data: dict = None):
        self._edit = class_data
        title = "Edit Class" if class_data else "New Class"
        super().__init__(parent, title, width=460, height=380)

    def build_fields(self):
        d = self._edit or {}
        self._class_name = self._labeled_entry("Class Name", tk.StringVar(value=d.get("name", "")),     row=0)
        self._code       = self._labeled_entry("Class Code", tk.StringVar(value=d.get("code", "")),     row=1)
        self._schedule   = self._labeled_entry("Schedule",   tk.StringVar(value=d.get("schedule") or ""), row=2)
        self._room       = self._labeled_entry("Room",       tk.StringVar(value=d.get("room") or ""),   row=3)

    def _on_save(self):
        name = self._class_name.get().strip()
        code = self._code.get().strip()
        if not name or not code:
            messagebox.showwarning("Validation", "Name and code are required.", parent=self)
            return
        self.submit({
            "name": name, "code": code,
            "schedule": self._schedule.get().strip() or None,
            "room":     self._room.get().strip() or None,
        })


class EnrollmentSubPanel(tk.Toplevel):
    """Pop-up for managing student enrollments in a single class."""

    def __init__(self, parent, db, class_data: dict):
        super().__init__(parent)
        self.title(f"Manage Students — {class_data['name']}")
        self.configure(bg=PALETTE["SURFACE"])
        self.grab_set()
        self.transient(parent)
        self.geometry("800x520")
        self._db = db
        self._class = class_data

        self._build()
        self._refresh()

    def _build(self):
        frame = tk.Frame(self, bg=PALETTE["SURFACE"], padx=20, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text=f"Students — {self._class['name']} ({self._class['code']})",
                 font=FONTS["HEADING"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["WHITE"]).pack(anchor="w", pady=(0, 12))

        body = tk.Frame(frame, bg=PALETTE["SURFACE"])
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(2, weight=1)
        body.rowconfigure(0, weight=1)

        # Left: all students
        left = tk.Frame(body, bg=PALETTE["SURFACE"])
        left.grid(row=0, column=0, sticky="nsew")
        tk.Label(left, text="All Students", font=FONTS["SUBHEAD"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"]).pack(anchor="w")

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._refresh())
        ttk.Entry(left, textvariable=self._search_var,
                  width=28).pack(fill=tk.X, pady=(4, 6))

        all_cols = [
            {"key": "id",   "label": "ID",   "width": 40,  "anchor": "center"},
            {"key": "name", "label": "Name",  "width": 180, "stretch": True},
            {"key": "sid",  "label": "Stu ID","width": 90},
        ]
        self._all_table = DataTable(left, columns=all_cols, height=14)
        self._all_table.pack(fill=tk.BOTH, expand=True)

        # Centre: action buttons
        mid = tk.Frame(body, bg=PALETTE["SURFACE"], padx=10)
        mid.grid(row=0, column=1, sticky="ns")
        tk.Frame(mid, bg=PALETTE["SURFACE"]).pack(expand=True)
        ttk.Button(mid, text="Enroll  →",
                   style="Success.TButton",
                   command=self._enroll).pack(pady=6, fill=tk.X)
        ttk.Button(mid, text="← Remove",
                   style="Danger.TButton",
                   command=self._unenroll).pack(pady=6, fill=tk.X)
        tk.Frame(mid, bg=PALETTE["SURFACE"]).pack(expand=True)

        # Right: enrolled students
        right = tk.Frame(body, bg=PALETTE["SURFACE"])
        right.grid(row=0, column=2, sticky="nsew")
        tk.Label(right, text="Enrolled", font=FONTS["SUBHEAD"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"]).pack(anchor="w")
        tk.Frame(right, height=32, bg=PALETTE["SURFACE"]).pack()  # spacer aligns with search box

        enrolled_cols = [
            {"key": "id",   "label": "ID",   "width": 40,  "anchor": "center"},
            {"key": "name", "label": "Name",  "width": 180, "stretch": True},
            {"key": "face", "label": "Face ✓","width": 60,  "anchor": "center"},
        ]
        self._enrolled_table = DataTable(right, columns=enrolled_cols, height=14)
        self._enrolled_table.pack(fill=tk.BOTH, expand=True)

    def _refresh(self):
        q = (self._search_var.get().lower()
             if hasattr(self, "_search_var") else "")
        all_students = self._db.get_users(role="student")
        enrolled = self._db.get_enrolled_students(self._class["id"])
        enrolled_ids = {s["id"] for s in enrolled}

        available = [s for s in all_students if s["id"] not in enrolled_ids]
        if q:
            available = [s for s in available
                         if q in s["full_name"].lower() or
                         q in (s.get("student_id") or "").lower()]

        self._all_cache = available
        self._enrolled_cache = enrolled

        self._all_table.load([
            (s["id"], s["full_name"], s.get("student_id") or "—")
            for s in available
        ])
        self._enrolled_table.load([
            (s["id"], s["full_name"], "✓" if s.get("face_enrolled") else "✕")
            for s in enrolled
        ])

    def _enroll(self):
        sel = self._all_table.get_selected_index()
        if sel < 0 or sel >= len(self._all_cache):
            return
        student = self._all_cache[sel]
        self._db.enroll_student(student["id"], self._class["id"])
        self._refresh()

    def _unenroll(self):
        sel = self._enrolled_table.get_selected_index()
        if sel < 0 or sel >= len(self._enrolled_cache):
            return
        student = self._enrolled_cache[sel]
        dlg = ConfirmDialog(
            self, "Remove Student",
            f"Remove {student['full_name']} from {self._class['name']}?",
            confirm_text="Remove", danger=True
        )
        if dlg.result:
            self._db.unenroll_student(student["id"], self._class["id"])
            self._refresh()


class ClassManagerPanel(ttk.Frame):
    """Lecturer class list with create / edit / delete / manage-students."""

    COLUMNS = [
        {"key": "code",     "label": "Code",      "width": 90},
        {"key": "name",     "label": "Class Name", "width": 220, "stretch": True},
        {"key": "schedule", "label": "Schedule",   "width": 150},
        {"key": "room",     "label": "Room",       "width": 80},
        {"key": "students", "label": "Students",   "width": 70, "anchor": "center"},
    ]

    def __init__(self, parent, db, user: dict, root_ref):
        super().__init__(parent, style="TFrame")
        self._db = db
        self._user = user
        self._root = root_ref
        self._selected: dict | None = None
        self._build()
        self.refresh()

    def _build(self):
        toolbar = tk.Frame(self, bg=PALETTE["BG"])
        toolbar.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(toolbar, text="＋ New Class",
                   style="Primary.TButton",
                   command=self._new_class).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="✎ Edit",
                   command=self._edit_class).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="👥 Manage Students",
                   command=self._manage_students).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(toolbar, text="✕ Delete",
                   style="Danger.TButton",
                   command=self._delete_class).pack(side=tk.LEFT)

        self._table = DataTable(self, columns=self.COLUMNS, height=22)
        self._table.pack(fill=tk.BOTH, expand=True)
        self._table.bind_select(self._on_select)
        self._table.bind_double_click(lambda e: self._manage_students())

        self._classes_cache: list[dict] = []

    def refresh(self):
        self._classes_cache = self._db.get_classes(lecturer_id=self._user["id"])
        rows = []
        for c in self._classes_cache:
            rows.append((
                c["code"], c["name"],
                c.get("schedule") or "—",
                c.get("room") or "—",
                c.get("enrolled_count", 0),
            ))
        self._table.load(rows)

    def _on_select(self, _=None):
        idx = self._table.get_selected_index()
        if 0 <= idx < len(self._classes_cache):
            self._selected = self._classes_cache[idx]

    def _new_class(self):
        dlg = ClassFormDialog(self._root)
        self._root.wait_window(dlg)
        result = dlg.get_result()
        if result:
            self._db.create_class(
                result["name"], result["code"],
                self._user["id"],
                result.get("schedule"), result.get("room")
            )
            self.refresh()
            Toast(self._root, f"Class '{result['name']}' created.", "success")

    def _edit_class(self):
        if not self._selected:
            messagebox.showinfo("Select", "Select a class first.")
            return
        dlg = ClassFormDialog(self._root, self._selected)
        self._root.wait_window(dlg)
        result = dlg.get_result()
        if result:
            self._db.update_class(self._selected["id"], **result)
            self.refresh()
            Toast(self._root, "Class updated.", "success")

    def _delete_class(self):
        if not self._selected:
            messagebox.showinfo("Select", "Select a class first.")
            return
        dlg = ConfirmDialog(
            self._root, "Delete Class",
            f"Delete '{self._selected['name']}'? All attendance records will be lost.",
            confirm_text="Delete", danger=True
        )
        if dlg.result:
            self._db.delete_class(self._selected["id"])
            self._selected = None
            self.refresh()
            Toast(self._root, "Class deleted.", "info")

    def _manage_students(self):
        if not self._selected:
            messagebox.showinfo("Select", "Select a class first.")
            return
        EnrollmentSubPanel(self._root, self._db, self._selected)
