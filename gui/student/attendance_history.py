"""
AttendIQ — Student Attendance History Panel.
Per-class breakdown table with percentage bar and CSV download.
"""

import tkinter as tk
from tkinter import ttk, filedialog
import csv
import os
from datetime import datetime
import logging

from gui.components import (
    PALETTE, FONTS, Card, DataTable, AttendanceBar, Toast,
)

logger = logging.getLogger(__name__)


class AttendanceHistoryPanel(ttk.Frame):

    def __init__(self, parent, db, user: dict, root_ref):
        super().__init__(parent, style="TFrame")
        self._db      = db
        self._user    = user
        self._root    = root_ref
        self._records_cache: list[dict] = []
        self._build()
        self._refresh_classes()

    # ------------------------------------------------------------------
    def _build(self):
        # ---- Filter bar ----
        filter_bar = tk.Frame(self, bg=PALETTE["BG"])
        filter_bar.pack(fill=tk.X, pady=(0, 8))

        tk.Label(filter_bar, text="Class:",
                 font=FONTS["LABEL"],
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(side=tk.LEFT)

        self._class_var = tk.StringVar()
        self._class_cb  = ttk.Combobox(filter_bar, textvariable=self._class_var,
                                        state="readonly", width=36)
        self._class_cb.pack(side=tk.LEFT, padx=(6, 0))
        self._class_cb.bind("<<ComboboxSelected>>", lambda e: self._load())

        ttk.Button(filter_bar, text="⬇ Download CSV",
                   command=self._export_csv).pack(side=tk.RIGHT)

        # ---- Summary row ----
        summary_frame = tk.Frame(self, bg=PALETTE["BG"])
        summary_frame.pack(fill=tk.X, pady=(0, 8))

        self._summary_var = tk.StringVar(value="Select a class to view attendance.")
        tk.Label(summary_frame, textvariable=self._summary_var,
                 font=FONTS["BODY"],
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(side=tk.LEFT)

        self._bar_frame = tk.Frame(summary_frame, bg=PALETTE["BG"])
        self._bar_frame.pack(side=tk.LEFT, padx=(16, 0))

        # ---- Table ----
        cols = [
            {"key": "date",   "label": "Date",   "width": 110},
            {"key": "day",    "label": "Day",    "width": 90},
            {"key": "time",   "label": "Time",   "width": 80},
            {"key": "status", "label": "Status", "width": 110, "anchor": "center"},
            {"key": "method", "label": "Recorded By","width": 130, "anchor": "center"},
        ]
        self._table = DataTable(self, columns=cols, height=22)
        self._table.pack(fill=tk.BOTH, expand=True)

    # ------------------------------------------------------------------
    def _refresh_classes(self):
        classes = self._db.get_student_classes(self._user["id"])
        self._classes = {f"{c['class_code']} — {c['class_name']}": c
                         for c in classes}
        self._class_cb["values"] = list(self._classes.keys())
        if self._classes:
            self._class_cb.current(0)
            self._load()

    def _load(self):
        key = self._class_var.get()
        if not key or key not in self._classes:
            return
        cls = self._classes[key]
        records = self._db.get_student_attendance(
            self._user["id"], class_id=cls["class_id"]
        )
        self._records_cache = records

        # Build full session date list (all dates class ran)
        all_dates = set(self._db.get_attendance_dates(cls["class_id"]))
        present_dates = {r["session_date"] for r in records}

        rows, tags = [], []

        # Show present rows first
        for r in records:
            try:
                d = datetime.strptime(r["session_date"], "%Y-%m-%d")
                day_name = d.strftime("%A")
            except ValueError:
                day_name = ""
            method_label = "Face Recognition" if r["method"] == "face" else "Manual"
            rows.append((
                r["session_date"], day_name,
                r["timestamp"],
                "Present  ✓",
                method_label,
            ))
            tags.append("success")

        # Show absent rows
        for d_str in sorted(all_dates - present_dates, reverse=True):
            try:
                d = datetime.strptime(d_str, "%Y-%m-%d")
                day_name = d.strftime("%A")
            except ValueError:
                day_name = ""
            rows.append((d_str, day_name, "—", "Absent  ✗", "—"))
            tags.append("danger")

        # Sort all by date descending
        rows_tagged = sorted(zip(rows, tags), key=lambda x: x[0][0], reverse=True)
        rows  = [r for r, _ in rows_tagged]
        tags  = [t for _, t in rows_tagged]

        self._table.load(rows, tags)

        # Summary
        total  = len(all_dates)
        present = len(present_dates)
        pct    = (present / total * 100) if total > 0 else 0
        self._summary_var.set(
            f"  {present} / {total} sessions attended  "
            f"({'%.1f' % pct}%)"
        )

        # Replace attendance bar
        for w in self._bar_frame.winfo_children():
            w.destroy()
        AttendanceBar(self._bar_frame, pct).pack()

    # ------------------------------------------------------------------
    def _export_csv(self):
        if not self._records_cache:
            Toast(self._root, "No records to export.", "info")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"my_attendance_{self._user.get('student_id','')}.csv",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Student", self._user["full_name"]])
                w.writerow(["Exported", datetime.now().strftime("%Y-%m-%d %H:%M")])
                w.writerow([])
                w.writerow(["Date", "Class", "Time", "Method"])
                for r in self._records_cache:
                    w.writerow([
                        r["session_date"],
                        r.get("class_name", ""),
                        r["timestamp"],
                        r["method"],
                    ])
            Toast(self._root, f"Saved: {os.path.basename(path)}", "success")
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Export Error", str(e))
