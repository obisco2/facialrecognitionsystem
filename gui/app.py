"""
AttendIQ — Application Root.

Creates the root Tk window, bootstraps the database and config,
shows the login screen, and routes to the correct role dashboard
on successful authentication.
"""

import tkinter as tk
from tkinter import messagebox
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.config import Config
from core.database import DatabaseManager
from gui.components import apply_dark_theme, PALETTE
from gui.login import LoginScreen

logger = logging.getLogger(__name__)


class AttendIQApp:
    """Top-level application shell."""

    MIN_WIDTH  = 1200
    MIN_HEIGHT = 700
    INIT_WIDTH = 1400
    INIT_HEIGHT = 850

    def __init__(self):
        self.config = Config()
        self.config.ensure_dirs()

        # Initialise database
        self.db = DatabaseManager(self.config.db_path)

        # Build root window
        self.root = tk.Tk()
        self.root.title(self.config.app_name)
        self.root.geometry(f"{self.INIT_WIDTH}x{self.INIT_HEIGHT}")
        self.root.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Try to set taskbar icon (optional — skip if asset missing)
        self._set_icon()

        apply_dark_theme(self.root)

        # Current displayed frame reference
        self._current_frame = None

        # Show login
        self._show_login()

    def _set_icon(self):
        icon_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "assets", "icon.ico"
        )
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Screen management
    # ------------------------------------------------------------------

    def _clear_window(self):
        """Destroy all children of root (used when switching screens)."""
        for widget in self.root.winfo_children():
            widget.destroy()
        self._current_frame = None

    def _show_login(self):
        self._clear_window()
        self.root.title(self.config.app_name)
        LoginScreen(self.root, self.db, self.config, self._on_login_success)

    def _on_login_success(self, user: dict):
        """Called by LoginScreen on successful authentication."""
        logger.info("Login successful: %s (%s)", user["username"], user["role"])
        self._clear_window()
        self._route_to_dashboard(user)

    def _route_to_dashboard(self, user: dict):
        role = user.get("role", "student")
        if role == "admin":
            from gui.admin.dashboard import AdminDashboard
            self._current_frame = AdminDashboard(
                self.root, user, self.db, self.config,
                on_logout=self._show_login
            )
        elif role == "lecturer":
            from gui.lecturer.dashboard import LecturerDashboard
            self._current_frame = LecturerDashboard(
                self.root, user, self.db, self.config,
                on_logout=self._show_login
            )
        elif role == "student":
            from gui.student.dashboard import StudentDashboard
            self._current_frame = StudentDashboard(
                self.root, user, self.db, self.config,
                on_logout=self._show_login
            )
        else:
            messagebox.showerror("Error", f"Unknown role: {role}")
            self._show_login()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _on_close(self):
        """Graceful shutdown — release camera if running, close DB."""
        # Signal any running camera threads to stop
        if self._current_frame and hasattr(self._current_frame, "shutdown"):
            self._current_frame.shutdown()
        try:
            self.db.close()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    app = AttendIQApp()
    app.run()


if __name__ == "__main__":
    main()
