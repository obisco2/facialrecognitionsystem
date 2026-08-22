"""
AttendIQ — Lecturer Dashboard.
Sidebar navigation shell hosting Class Manager, Attendance Viewer, and Export.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime
import logging

from gui.components import (
    PALETTE, FONTS, Card, StatCard, TopBar, Sidebar, Toast,
)
from gui.lecturer.class_manager    import ClassManagerPanel
from gui.lecturer.attendance_viewer import AttendanceViewerPanel
from gui.lecturer.export_manager   import ExportManagerPanel

logger = logging.getLogger(__name__)


class LecturerHome(ttk.Frame):
    """Home sub-panel showing quick stats and recent activity."""

    def __init__(self, parent, db, user: dict, root_ref):
        super().__init__(parent, style="TFrame")
        self._db   = db
        self._user = user
        self._root = root_ref
        self._build()

    def _build(self):
        greeting = f"Good {self._time_of_day()}, {self._user['full_name'].split()[0]}."
        tk.Label(self, text=greeting,
                 font=("Segoe UI", 20, "bold"),
                 bg=PALETTE["BG"], fg=PALETTE["WHITE"]).pack(anchor="w", pady=(0, 4))
        tk.Label(self, text=datetime.now().strftime("%A, %d %B %Y"),
                 font=FONTS["BODY"],
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(anchor="w", pady=(0, 20))

        # Stat cards
        stats_row = tk.Frame(self, bg=PALETTE["BG"])
        stats_row.pack(fill=tk.X, pady=(0, 20))

        classes    = self._db.get_classes(lecturer_id=self._user["id"])
        n_classes  = len(classes)

        # Sessions today (classes with attendance today)
        today = datetime.now().strftime("%Y-%m-%d")
        sessions_today = sum(
            1 for c in classes
            if today in self._db.get_attendance_dates(c["id"])
        )

        # Total enrolled across all classes
        total_enrolled = sum(c.get("enrolled_count", 0) for c in classes)

        for label, val, icon, colour in [
            ("My Classes",       n_classes,      "📚", PALETTE["ACCENT"]),
            ("Sessions Today",   sessions_today, "📷", PALETTE["INFO"]),
            ("Students Enrolled",total_enrolled, "👥", PALETTE["SUCCESS"]),
        ]:
            sc = StatCard(stats_row, label, str(val), icon=icon, color=colour)
            sc.pack(side=tk.LEFT, padx=(0, 12), ipadx=8, ipady=8)

        # Recent sessions
        Card(self, "Recent Attendance Sessions").pack(
            fill=tk.X, pady=(0, 8)
        )

        from gui.components import DataTable
        recent_cols = [
            {"key": "date",    "label": "Date",    "width": 110},
            {"key": "class",   "label": "Class",   "width": 200, "stretch": True},
            {"key": "present", "label": "Present", "width": 80, "anchor": "center"},
            {"key": "total",   "label": "Enrolled","width": 80, "anchor": "center"},
            {"key": "pct",     "label": "%",       "width": 70, "anchor": "center"},
        ]
        table = DataTable(self, columns=recent_cols, height=10)
        table.pack(fill=tk.X)

        rows, tags = [], []
        for cls in classes:
            dates = self._db.get_attendance_dates(cls["id"])[:5]
            for d in dates:
                summary = self._db.get_attendance_summary(cls["id"], d)
                pct = summary["percent"]
                tag = "success" if pct >= 75 else ("warning" if pct >= 60 else "danger")
                rows.append((d, f"{cls['code']} — {cls['name']}",
                              summary["present"], summary["total_enrolled"],
                              f"{pct:.0f}%"))
                tags.append(tag)

        rows.sort(key=lambda r: r[0], reverse=True)
        table.load(rows[:10], tags[:10])

    @staticmethod
    def _time_of_day() -> str:
        h = datetime.now().hour
        if h < 12:
            return "morning"
        if h < 17:
            return "afternoon"
        return "evening"


class LecturerDashboard(tk.Frame):
    """Full lecturer shell with sidebar navigation."""

    NAV_ITEMS = [
        {"key": "home",      "icon": "🏠", "label": "Home"},
        {"key": "classes",   "icon": "📚", "label": "My Classes"},
        {"key": "live",      "icon": "📷", "label": "Live Attendance"},
        {"key": "history",   "icon": "📋", "label": "Attendance History"},
        {"key": "export",    "icon": "📤", "label": "Export"},
    ]

    def __init__(self, parent, user: dict, db, config, on_logout):
        super().__init__(parent, bg=PALETTE["BG"])
        self.pack(fill=tk.BOTH, expand=True)
        self._user      = user
        self._db        = db
        self._config    = config
        self._on_logout = on_logout
        self._panels: dict[str, tk.Frame] = {}
        self._attendance_viewer: AttendanceViewerPanel | None = None
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

        self._panels["home"] = LecturerHome(
            self._content, self._db, self._user, root
        )

        class_mgr = ClassManagerPanel(
            self._content, self._db, self._user, root
        )
        self._panels["classes"] = class_mgr

        # Attendance viewer is shared between Live and History tabs
        self._attendance_viewer = AttendanceViewerPanel(
            self._content, self._db, self._user, self._config, root
        )
        self._panels["live"]    = self._attendance_viewer
        self._panels["history"] = self._attendance_viewer  # same widget, different tab

        self._panels["export"]  = ExportManagerPanel(
            self._content, self._db, self._user, root
        )

    def _switch_panel(self, key: str):
        for panel in set(self._panels.values()):
            panel.pack_forget()

        panel = self._panels[key]
        panel.pack(fill=tk.BOTH, expand=True)

        # If switching to history tab inside the attendance viewer, jump to it
        if key == "history" and self._attendance_viewer:
            try:
                nb = self._attendance_viewer.winfo_children()[0]
                if hasattr(nb, "select"):
                    nb.select(1)  # index 1 = History tab
            except Exception:
                pass
        elif key == "live" and self._attendance_viewer:
            try:
                nb = self._attendance_viewer.winfo_children()[0]
                if hasattr(nb, "select"):
                    nb.select(0)  # index 0 = Live tab
            except Exception:
                pass

    def shutdown(self):
        if self._attendance_viewer:
            self._attendance_viewer.shutdown()
