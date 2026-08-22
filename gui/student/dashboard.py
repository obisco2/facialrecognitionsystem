"""
AttendIQ — Student Dashboard.
Home panel with stat cards + per-class attendance bars, sidebar nav.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime
import logging

from gui.components import (
    PALETTE, FONTS, Card, StatCard, DataTable,
    AttendanceBar, Avatar, TopBar, Sidebar, Toast,
)
from gui.student.attendance_history import AttendanceHistoryPanel
from gui.student.enrollment          import EnrollmentPanel

logger = logging.getLogger(__name__)


class StudentHome(ttk.Frame):
    """Home sub-panel with greeting, stats, and class overview."""

    def __init__(self, parent, db, user: dict, root_ref):
        super().__init__(parent, style="TFrame")
        self._db   = db
        self._user = user
        self._root = root_ref
        self._build()

    def _build(self):
        # ---- Greeting row ----
        greet_row = tk.Frame(self, bg=PALETTE["BG"])
        greet_row.pack(fill=tk.X, pady=(0, 20))

        Avatar(greet_row, self._user["full_name"], size=56).pack(side=tk.LEFT, padx=(0, 14))

        greet_text = tk.Frame(greet_row, bg=PALETTE["BG"])
        greet_text.pack(side=tk.LEFT)

        hour = datetime.now().hour
        salutation = "Good morning" if hour < 12 else ("Good afternoon" if hour < 17 else "Good evening")
        tk.Label(greet_text,
                 text=f"{salutation}, {self._user['full_name'].split()[0]}!",
                 font=("Segoe UI", 20, "bold"),
                 bg=PALETTE["BG"], fg=PALETTE["WHITE"]).pack(anchor="w")

        sid_text = f"ID: {self._user.get('student_id') or 'N/A'}  •  " \
                   f"{datetime.now().strftime('%A, %d %B %Y')}"
        tk.Label(greet_text, text=sid_text,
                 font=FONTS["BODY"],
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(anchor="w")

        # ---- Stat cards ----
        summary = self._db.get_student_summary_per_class(self._user["id"])
        n_classes = len(summary)
        avg_pct   = (sum(s["percent"] for s in summary) / n_classes
                     if n_classes else 0)
        low_count = sum(1 for s in summary if s["percent"] < 75)

        enrolled_icon = "✅" if self._user.get("face_enrolled") else "❌"
        enrolled_text = "Enrolled" if self._user.get("face_enrolled") else "Not Enrolled"

        stats_row = tk.Frame(self, bg=PALETTE["BG"])
        stats_row.pack(fill=tk.X, pady=(0, 20))

        stat_defs = [
            ("Classes Enrolled",   str(n_classes),        "📚", PALETTE["INFO"]),
            ("Avg Attendance",      f"{avg_pct:.1f}%",    "📊", PALETTE["SUCCESS"] if avg_pct >= 75 else PALETTE["WARNING"]),
            ("Low Attendance",      str(low_count),        "⚠",  PALETTE["DANGER"] if low_count else PALETTE["MUTED"]),
            (f"Face  {enrolled_icon}", enrolled_text,     "👤", PALETTE["SUCCESS"] if self._user.get("face_enrolled") else PALETTE["ACCENT"]),
        ]
        for label, val, icon, colour in stat_defs:
            sc = StatCard(stats_row, label, val, icon=icon, color=colour)
            sc.pack(side=tk.LEFT, padx=(0, 12), ipadx=6, ipady=6)

        # ---- Low attendance warning banner ----
        if low_count:
            warn = tk.Frame(self, bg="#2a0d15", padx=14, pady=10)
            warn.pack(fill=tk.X, pady=(0, 14))
            tk.Label(warn,
                     text=f"⚠  You have {low_count} class(es) below 75% attendance. "
                          "Check with your lecturer.",
                     font=FONTS["BODY"],
                     bg="#2a0d15", fg=PALETTE["WARNING"]).pack(anchor="w")

        # ---- Per-class breakdown ----
        Card(self, "My Classes").pack(fill=tk.X, pady=(0, 8))

        for s in summary:
            row = tk.Frame(self, bg=PALETTE["SURFACE"], padx=14, pady=10)
            row.pack(fill=tk.X, pady=3)
            row.columnconfigure(1, weight=1)

            # Code + name
            code_lbl = tk.Label(row, text=s["class_code"],
                                 font=FONTS["LABEL"],
                                 bg=PALETTE["SURFACE"], fg=PALETTE["ACCENT"],
                                 width=8, anchor="w")
            code_lbl.grid(row=0, column=0, sticky="w")

            name_lbl = tk.Label(row, text=s["class_name"],
                                 font=FONTS["BODY"],
                                 bg=PALETTE["SURFACE"], fg=PALETTE["TEXT"],
                                 anchor="w")
            name_lbl.grid(row=0, column=1, sticky="ew", padx=(6, 0))

            # Attendance bar
            bar_frame = tk.Frame(row, bg=PALETTE["SURFACE"])
            bar_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))

            AttendanceBar(bar_frame, s["percent"]).pack(side=tk.LEFT)

            sessions_lbl = tk.Label(
                bar_frame,
                text=f"  {s['sessions_present']}/{s['total_sessions']} sessions",
                font=FONTS["SMALL"],
                bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"]
            )
            sessions_lbl.pack(side=tk.LEFT)

            # Status badge
            if s["percent"] >= 75:
                badge_text, badge_bg = "✓ OK", "#0d4a2e"
            elif s["percent"] >= 60:
                badge_text, badge_bg = "⚠ LOW", "#4a3000"
            else:
                badge_text, badge_bg = "✗ CRITICAL", "#4a0d15"

            tk.Label(row, text=badge_text,
                     font=("Segoe UI", 9, "bold"),
                     bg=badge_bg, fg=PALETTE["WHITE"],
                     padx=8, pady=3).grid(row=0, column=2, rowspan=2, padx=(12, 0))

        if not summary:
            tk.Label(self,
                     text="You are not enrolled in any classes yet.\n"
                          "Ask your lecturer to add you.",
                     font=FONTS["BODY"],
                     bg=PALETTE["BG"], fg=PALETTE["MUTED"],
                     justify="center").pack(pady=40)


class StudentDashboard(tk.Frame):
    """Full student shell with sidebar navigation."""

    NAV_ITEMS = [
        {"key": "home",     "icon": "🏠", "label": "Home"},
        {"key": "history",  "icon": "📋", "label": "My Attendance"},
        {"key": "enroll",   "icon": "📷", "label": "Enroll Face"},
    ]

    def __init__(self, parent, user: dict, db, config, on_logout):
        super().__init__(parent, bg=PALETTE["BG"])
        self.pack(fill=tk.BOTH, expand=True)
        self._user      = user
        self._db        = db
        self._config    = config
        self._on_logout = on_logout
        self._panels: dict[str, tk.Frame] = {}
        self._enrollment_panel: EnrollmentPanel | None = None
        self._build()
        self._sidebar.select("home")

    def _build(self):
        TopBar(self, self._user, self._on_logout).pack(fill=tk.X)

        body = tk.Frame(self, bg=PALETTE["BG"])
        body.pack(fill=tk.BOTH, expand=True)

        self._sidebar = Sidebar(body, self.NAV_ITEMS,
                                on_select=self._switch_panel, width=200)
        self._sidebar.pack(side=tk.LEFT, fill=tk.Y)

        self._content = tk.Frame(body, bg=PALETTE["BG"])
        self._content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True,
                           padx=20, pady=20)

        root = self.winfo_toplevel()

        self._panels["home"] = StudentHome(
            self._content, self._db, self._user, root
        )
        self._panels["history"] = AttendanceHistoryPanel(
            self._content, self._db, self._user, root
        )
        enroll = EnrollmentPanel(
            self._content, self._db, self._user, self._config, root
        )
        self._enrollment_panel = enroll
        self._panels["enroll"] = enroll

    def _switch_panel(self, key: str):
        # Refresh home each time we navigate back to it
        if key == "home":
            self._panels["home"].pack_forget()
            self._panels["home"].destroy()
            root = self.winfo_toplevel()
            self._panels["home"] = StudentHome(
                self._content, self._db, self._user, root
            )

        for panel in set(self._panels.values()):
            panel.pack_forget()
        self._panels[key].pack(fill=tk.BOTH, expand=True)

    def shutdown(self):
        if self._enrollment_panel:
            try:
                self._enrollment_panel.shutdown()
            except Exception:
                pass
