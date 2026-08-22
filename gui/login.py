"""
AttendIQ — Login Screen.

Animated split-panel login with role-routing.
Left panel: app branding + animated scan ring canvas.
Right panel: credentials form.
"""

import tkinter as tk
from tkinter import ttk
import math
import time

from gui.components import (
    PALETTE, FONTS, apply_dark_theme,
)


class LoginScreen(tk.Frame):
    """
    Full-window login frame.
    On successful authentication, calls on_success(user_dict).
    """

    def __init__(self, parent: tk.Misc,
                 db,       # DatabaseManager
                 config,   # Config
                 on_success):
        super().__init__(parent, bg=PALETTE["BG"])
        self.pack(fill=tk.BOTH, expand=True)

        self._db = db
        self._config = config
        self._on_success = on_success
        self._angle = 0
        self._slide_x = 60  # form starts offset for slide-in

        self._build()
        self._start_animations()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        # Two-column grid
        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(0, weight=1)

        self._build_left_panel()
        self._build_right_panel()

    def _build_left_panel(self):
        left = tk.Frame(self, bg=PALETTE["PANEL"])
        left.grid(row=0, column=0, sticky="nsew")

        inner = tk.Frame(left, bg=PALETTE["PANEL"])
        inner.place(relx=0.5, rely=0.5, anchor="center")

        # App name
        tk.Label(inner, text="AttendIQ",
                 font=("Segoe UI", 36, "bold"),
                 bg=PALETTE["PANEL"], fg=PALETTE["ACCENT"]).pack()

        tk.Label(inner, text="Facial Recognition\nAttendance System",
                 font=("Segoe UI", 13),
                 bg=PALETTE["PANEL"], fg=PALETTE["SUBTEXT"],
                 justify="center").pack(pady=(4, 30))

        # Animated scan ring canvas
        self._canvas = tk.Canvas(inner, width=180, height=180,
                                 bg=PALETTE["PANEL"],
                                 highlightthickness=0)
        self._canvas.pack()

        self._draw_scan_ring()

        # Tagline
        tk.Label(inner,
                 text="Smarter Attendance.\nFairer Recognition.",
                 font=("Segoe UI", 10, "italic"),
                 bg=PALETTE["PANEL"], fg=PALETTE["MUTED"],
                 justify="center").pack(pady=(24, 0))

    def _build_right_panel(self):
        right = tk.Frame(self, bg=PALETTE["BG"])
        right.grid(row=0, column=1, sticky="nsew")

        # Form container — will be animated in
        self._form_frame = tk.Frame(right, bg=PALETTE["BG"])
        self._form_frame.place(relx=0.5, rely=0.5, anchor="center",
                               width=360)

        tk.Label(self._form_frame, text="Welcome back",
                 font=("Segoe UI", 24, "bold"),
                 bg=PALETTE["BG"], fg=PALETTE["WHITE"]).pack(anchor="w")

        tk.Label(self._form_frame, text="Sign in to your account",
                 font=FONTS["BODY"],
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(
            anchor="w", pady=(4, 28)
        )

        # Username
        tk.Label(self._form_frame, text="USERNAME",
                 font=("Segoe UI", 9, "bold"),
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(anchor="w")

        self._username_var = tk.StringVar()
        self._username_entry = ttk.Entry(
            self._form_frame, textvariable=self._username_var,
            font=FONTS["BODY"], width=32
        )
        self._username_entry.pack(fill=tk.X, pady=(4, 16))

        # Password
        tk.Label(self._form_frame, text="PASSWORD",
                 font=("Segoe UI", 9, "bold"),
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(anchor="w")

        pwd_row = tk.Frame(self._form_frame, bg=PALETTE["BG"])
        pwd_row.pack(fill=tk.X, pady=(4, 0))

        self._password_var = tk.StringVar()
        self._show_pwd = tk.BooleanVar(value=False)

        self._pwd_entry = ttk.Entry(
            pwd_row, textvariable=self._password_var,
            font=FONTS["BODY"], show="●"
        )
        self._pwd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._eye_btn = tk.Label(pwd_row, text="👁",
                                 font=("Segoe UI", 12),
                                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"],
                                 cursor="hand2", padx=6)
        self._eye_btn.pack(side=tk.LEFT)
        self._eye_btn.bind("<Button-1>", self._toggle_password)

        # Error label (hidden initially)
        self._error_var = tk.StringVar()
        self._error_label = tk.Label(
            self._form_frame, textvariable=self._error_var,
            font=FONTS["SMALL"],
            bg=PALETTE["BG"], fg=PALETTE["DANGER"]
        )
        self._error_label.pack(anchor="w", pady=(6, 0))

        # Sign-in button
        tk.Frame(self._form_frame, bg=PALETTE["BG"],
                 height=20).pack()  # spacer

        self._signin_btn = ttk.Button(
            self._form_frame, text="Sign In  →",
            style="Primary.TButton",
            command=self._attempt_login
        )
        self._signin_btn.pack(fill=tk.X, ipady=4)

        # Hint
        tk.Label(self._form_frame,
                 text="Default: admin / admin",
                 font=("Segoe UI", 8),
                 bg=PALETTE["BG"], fg=PALETTE["MUTED"]).pack(pady=(10, 0))

        # Bind Enter key
        self._username_entry.bind("<Return>", lambda e: self._attempt_login())
        self._pwd_entry.bind("<Return>", lambda e: self._attempt_login())

        # Focus
        self._username_entry.focus_set()

    # ------------------------------------------------------------------
    # Animations
    # ------------------------------------------------------------------

    def _draw_scan_ring(self):
        """Draw the animated face-scan ring on the canvas."""
        self._canvas.delete("all")
        cx, cy, r = 90, 90, 60
        # Background circle
        self._canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                  outline=PALETTE["BORDER"], width=2)

        # Face silhouette (simple circle for head + oval for body)
        self._canvas.create_oval(cx - 22, cy - 28, cx + 22, cy + 22,
                                  outline=PALETTE["MUTED"], width=1.5)
        self._canvas.create_oval(cx - 5, cy - 10, cx + 5, cy,
                                  fill=PALETTE["MUTED"], outline="")
        self._canvas.create_oval(cx - 18, cy + 20, cx + 18, cy + 50,
                                  outline=PALETTE["MUTED"], width=1.5)

        # Corner brackets
        br = r + 12
        blen = 16
        thick = 2
        corners = [
            (cx - br, cy - br, cx - br + blen, cy - br,
             cx - br, cy - br + blen),
            (cx + br, cy - br, cx + br - blen, cy - br,
             cx + br, cy - br + blen),
            (cx - br, cy + br, cx - br + blen, cy + br,
             cx - br, cy + br - blen),
            (cx + br, cy + br, cx + br - blen, cy + br,
             cx + br, cy + br - blen),
        ]
        for x1, y1, x2, y2, x3, y3 in corners:
            self._canvas.create_line(x1, y1, x2, y2,
                                      fill=PALETTE["ACCENT"], width=thick)
            self._canvas.create_line(x1, y1, x3, y3,
                                      fill=PALETTE["ACCENT"], width=thick)

        # Rotating arc
        a = self._angle
        extent = 60
        self._canvas.create_arc(
            cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6,
            start=a, extent=extent,
            outline=PALETTE["ACCENT"], width=3, style="arc"
        )
        self._canvas.create_arc(
            cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6,
            start=a + 180, extent=extent,
            outline=PALETTE["ACCENT2"], width=2, style="arc"
        )

        # Scan line (horizontal sweep)
        sweep_y = int(cy - r + ((self._angle % 120) / 120.0) * (r * 2))
        sweep_y = max(cy - r, min(cy + r, sweep_y))
        self._canvas.create_line(cx - r + 6, sweep_y, cx + r - 6, sweep_y,
                                   fill=PALETTE["SUCCESS"],
                                   width=1, dash=(4, 4))

    def _start_animations(self):
        self._animate_ring()
        self._animate_slide()

    def _animate_ring(self):
        self._angle = (self._angle + 3) % 360
        self._draw_scan_ring()
        self.after(30, self._animate_ring)

    def _animate_slide(self):
        """Slide the form panel in from the right over 400ms."""
        if self._slide_x > 0:
            self._slide_x = max(0, self._slide_x - 4)
            try:
                self._form_frame.place(relx=0.5 + self._slide_x / 1000,
                                       rely=0.5, anchor="center", width=360)
            except tk.TclError:
                return
            self.after(10, self._animate_slide)
        else:
            self._form_frame.place(relx=0.5, rely=0.5,
                                   anchor="center", width=360)

    def _shake(self):
        """Shake the sign-in button on error."""
        original_x = 0.5
        offsets = [0.505, 0.495, 0.507, 0.493, 0.502, 0.5]
        delay = 0

        def _step(idx=0):
            if idx >= len(offsets):
                return
            try:
                self._form_frame.place(relx=offsets[idx], rely=0.5,
                                       anchor="center", width=360)
            except tk.TclError:
                return
            self.after(40, lambda: _step(idx + 1))

        _step()

    # ------------------------------------------------------------------
    # Auth logic
    # ------------------------------------------------------------------

    def _toggle_password(self, _event=None):
        if self._show_pwd.get():
            self._show_pwd.set(False)
            self._pwd_entry.configure(show="●")
            self._eye_btn.configure(fg=PALETTE["SUBTEXT"])
        else:
            self._show_pwd.set(True)
            self._pwd_entry.configure(show="")
            self._eye_btn.configure(fg=PALETTE["ACCENT"])

    def _attempt_login(self):
        self._error_var.set("")
        username = self._username_var.get().strip()
        password = self._password_var.get().strip()

        if not username or not password:
            self._error_var.set("Please enter both username and password.")
            self._shake()
            return

        # Disable button to prevent double-click
        self._signin_btn.configure(state=tk.DISABLED, text="Signing in…")
        self.after(100, lambda: self._do_authenticate(username, password))

    def _do_authenticate(self, username: str, password: str):
        user = self._db.authenticate(username, password)
        self._signin_btn.configure(state=tk.NORMAL, text="Sign In  →")

        if user:
            self._error_var.set("")
            self._on_success(user)
        else:
            self._error_var.set("Invalid username or password. Please try again.")
            self._shake()
            self._password_var.set("")
            self._pwd_entry.focus_set()
