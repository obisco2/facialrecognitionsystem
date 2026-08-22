"""
AttendIQ — Shared UI Component Library.

All screens import from here to guarantee visual consistency.
Palette, typography, and component classes are defined once.
"""

import tkinter as tk
from tkinter import ttk
import threading
import time

# ---------------------------------------------------------------------------
# Design Tokens
# ---------------------------------------------------------------------------

PALETTE = {
    "BG":       "#0f0f1a",   # deepest background
    "SURFACE":  "#1a1a2e",   # card / panel surface
    "PANEL":    "#16213e",   # sidebar / secondary surface
    "BORDER":   "#2a2a4a",   # subtle border
    "ACCENT":   "#e94560",   # primary CTA — red
    "ACCENT2":  "#0f3460",   # secondary accent — navy
    "SUCCESS":  "#16c79a",   # green — present / ok
    "WARNING":  "#f5a623",   # amber — low attendance
    "DANGER":   "#e94560",   # red — error / absent
    "INFO":     "#4fc3f7",   # light blue — informational
    "TEXT":     "#e8e8f0",   # primary text
    "SUBTEXT":  "#8888aa",   # secondary / label text
    "MUTED":    "#44445a",   # disabled / placeholder
    "WHITE":    "#ffffff",
}

FONTS = {
    "TITLE":    ("Segoe UI", 22, "bold"),
    "HEADING":  ("Segoe UI", 15, "bold"),
    "SUBHEAD":  ("Segoe UI", 12, "bold"),
    "BODY":     ("Segoe UI", 10),
    "SMALL":    ("Segoe UI", 9),
    "MONO":     ("Consolas", 9),
    "LABEL":    ("Segoe UI", 10, "bold"),
}


# ---------------------------------------------------------------------------
# Theme bootstrap
# ---------------------------------------------------------------------------

def apply_dark_theme(root: tk.Tk):
    """Apply the AttendIQ dark theme to a root Tk window."""
    root.configure(bg=PALETTE["BG"])

    style = ttk.Style(root)
    style.theme_use("clam")

    # ---- Base frames & labels ----
    style.configure("TFrame",       background=PALETTE["BG"])
    style.configure("Surface.TFrame", background=PALETTE["SURFACE"])
    style.configure("Panel.TFrame",   background=PALETTE["PANEL"])
    style.configure("TLabel",
                    background=PALETTE["BG"],
                    foreground=PALETTE["TEXT"],
                    font=FONTS["BODY"])
    style.configure("Surface.TLabel",
                    background=PALETTE["SURFACE"],
                    foreground=PALETTE["TEXT"],
                    font=FONTS["BODY"])
    style.configure("Title.TLabel",
                    background=PALETTE["BG"],
                    foreground=PALETTE["WHITE"],
                    font=FONTS["TITLE"])
    style.configure("Heading.TLabel",
                    background=PALETTE["SURFACE"],
                    foreground=PALETTE["WHITE"],
                    font=FONTS["HEADING"])
    style.configure("Subhead.TLabel",
                    background=PALETTE["SURFACE"],
                    foreground=PALETTE["TEXT"],
                    font=FONTS["SUBHEAD"])
    style.configure("Accent.TLabel",
                    background=PALETTE["BG"],
                    foreground=PALETTE["ACCENT"],
                    font=FONTS["SUBHEAD"])
    style.configure("Success.TLabel",
                    background=PALETTE["SURFACE"],
                    foreground=PALETTE["SUCCESS"],
                    font=FONTS["BODY"])
    style.configure("Warning.TLabel",
                    background=PALETTE["SURFACE"],
                    foreground=PALETTE["WARNING"],
                    font=FONTS["BODY"])
    style.configure("Danger.TLabel",
                    background=PALETTE["SURFACE"],
                    foreground=PALETTE["DANGER"],
                    font=FONTS["BODY"])
    style.configure("Muted.TLabel",
                    background=PALETTE["SURFACE"],
                    foreground=PALETTE["SUBTEXT"],
                    font=FONTS["SMALL"])

    # ---- Buttons ----
    style.configure("TButton",
                    background=PALETTE["ACCENT2"],
                    foreground=PALETTE["TEXT"],
                    font=FONTS["BODY"],
                    padding=(12, 6),
                    relief="flat",
                    borderwidth=0)
    style.map("TButton",
              background=[("active", "#1a4080"), ("pressed", "#0d2a5e")],
              foreground=[("active", PALETTE["WHITE"])])

    style.configure("Primary.TButton",
                    background=PALETTE["ACCENT"],
                    foreground=PALETTE["WHITE"],
                    font=FONTS["LABEL"],
                    padding=(16, 8))
    style.map("Primary.TButton",
              background=[("active", "#c73050"), ("pressed", "#a02040")],
              foreground=[("active", PALETTE["WHITE"])])

    style.configure("Success.TButton",
                    background=PALETTE["SUCCESS"],
                    foreground=PALETTE["BG"],
                    font=FONTS["LABEL"],
                    padding=(12, 6))
    style.map("Success.TButton",
              background=[("active", "#12a07e")])

    style.configure("Danger.TButton",
                    background="#8b1a2a",
                    foreground=PALETTE["WHITE"],
                    font=FONTS["BODY"],
                    padding=(12, 6))
    style.map("Danger.TButton",
              background=[("active", "#a02030")])

    style.configure("Ghost.TButton",
                    background=PALETTE["SURFACE"],
                    foreground=PALETTE["SUBTEXT"],
                    font=FONTS["BODY"],
                    padding=(10, 5))
    style.map("Ghost.TButton",
              background=[("active", PALETTE["BORDER"])],
              foreground=[("active", PALETTE["TEXT"])])

    # ---- Entry ----
    style.configure("TEntry",
                    fieldbackground=PALETTE["PANEL"],
                    foreground=PALETTE["TEXT"],
                    insertcolor=PALETTE["TEXT"],
                    bordercolor=PALETTE["BORDER"],
                    lightcolor=PALETTE["BORDER"],
                    darkcolor=PALETTE["BORDER"],
                    font=FONTS["BODY"],
                    padding=6)
    style.map("TEntry",
              bordercolor=[("focus", PALETTE["ACCENT"])],
              lightcolor=[("focus", PALETTE["ACCENT"])],
              darkcolor=[("focus", PALETTE["ACCENT"])])

    # ---- Combobox ----
    style.configure("TCombobox",
                    fieldbackground=PALETTE["PANEL"],
                    foreground=PALETTE["TEXT"],
                    selectbackground=PALETTE["ACCENT2"],
                    selectforeground=PALETTE["WHITE"],
                    background=PALETTE["PANEL"],
                    arrowcolor=PALETTE["SUBTEXT"],
                    font=FONTS["BODY"])
    style.map("TCombobox",
              fieldbackground=[("readonly", PALETTE["PANEL"])],
              foreground=[("readonly", PALETTE["TEXT"])])

    # ---- Notebook tabs ----
    style.configure("TNotebook",
                    background=PALETTE["BG"],
                    borderwidth=0,
                    tabmargins=[0, 0, 0, 0])
    style.configure("TNotebook.Tab",
                    background=PALETTE["PANEL"],
                    foreground=PALETTE["SUBTEXT"],
                    font=FONTS["BODY"],
                    padding=(16, 8),
                    borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", PALETTE["SURFACE"]),
                          ("active", PALETTE["BORDER"])],
              foreground=[("selected", PALETTE["WHITE"]),
                          ("active", PALETTE["TEXT"])])

    # ---- Treeview (DataTable) ----
    style.configure("Treeview",
                    background=PALETTE["SURFACE"],
                    foreground=PALETTE["TEXT"],
                    fieldbackground=PALETTE["SURFACE"],
                    borderwidth=0,
                    rowheight=30,
                    font=FONTS["BODY"])
    style.configure("Treeview.Heading",
                    background=PALETTE["PANEL"],
                    foreground=PALETTE["SUBTEXT"],
                    font=FONTS["SMALL"],
                    relief="flat",
                    borderwidth=0)
    style.map("Treeview",
              background=[("selected", PALETTE["ACCENT2"])],
              foreground=[("selected", PALETTE["WHITE"])])
    style.map("Treeview.Heading",
              background=[("active", PALETTE["BORDER"])])

    # ---- Scrollbar ----
    style.configure("TScrollbar",
                    background=PALETTE["PANEL"],
                    troughcolor=PALETTE["BG"],
                    bordercolor=PALETTE["BG"],
                    arrowcolor=PALETTE["MUTED"],
                    relief="flat")
    style.map("TScrollbar",
              background=[("active", PALETTE["BORDER"])])

    # ---- Separator ----
    style.configure("TSeparator", background=PALETTE["BORDER"])

    # ---- Scale ----
    style.configure("TScale",
                    background=PALETTE["SURFACE"],
                    troughcolor=PALETTE["BORDER"],
                    slidercolor=PALETTE["ACCENT"])

    # ---- Checkbutton / Radiobutton ----
    style.configure("TCheckbutton",
                    background=PALETTE["SURFACE"],
                    foreground=PALETTE["TEXT"],
                    font=FONTS["BODY"])
    style.configure("TRadiobutton",
                    background=PALETTE["SURFACE"],
                    foreground=PALETTE["TEXT"],
                    font=FONTS["BODY"])

    # ---- Progressbar ----
    style.configure("TProgressbar",
                    troughcolor=PALETTE["PANEL"],
                    background=PALETTE["SUCCESS"],
                    thickness=8)
    style.configure("Warning.TProgressbar",
                    background=PALETTE["WARNING"])
    style.configure("Danger.TProgressbar",
                    background=PALETTE["DANGER"])
    style.configure("Accent.TProgressbar",
                    background=PALETTE["ACCENT"])


# ---------------------------------------------------------------------------
# Reusable Widget Components
# ---------------------------------------------------------------------------

class Card(ttk.Frame):
    """Padded surface panel — the building block for dashboard sections."""

    def __init__(self, parent, title: str = None, padding: int = 16, **kwargs):
        super().__init__(parent, style="Surface.TFrame",
                         padding=padding, **kwargs)
        if title:
            ttk.Label(self, text=title, style="Heading.TLabel").pack(
                anchor="w", pady=(0, 10)
            )


class StatCard(ttk.Frame):
    """
    Mini stats card — used on dashboard home panels.
    Shows an icon, a large value, and a label underneath.
    """

    def __init__(self, parent, label: str, value: str,
                 icon: str = "●", color: str = None, **kwargs):
        super().__init__(parent, style="Surface.TFrame", padding=16, **kwargs)
        color = color or PALETTE["ACCENT"]

        # Icon circle
        icon_label = tk.Label(self, text=icon, font=("Segoe UI", 20),
                              bg=PALETTE["SURFACE"], fg=color)
        icon_label.pack(anchor="w")

        # Value
        val_label = tk.Label(self, text=str(value),
                             font=("Segoe UI", 26, "bold"),
                             bg=PALETTE["SURFACE"], fg=PALETTE["WHITE"])
        val_label.pack(anchor="w", pady=(4, 0))

        # Label
        tk.Label(self, text=label, font=FONTS["SMALL"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"]).pack(anchor="w")

        self._val_label = val_label

    def update_value(self, new_value: str):
        self._val_label.configure(text=str(new_value))


class SectionHeader(ttk.Frame):
    """Labelled horizontal divider."""

    def __init__(self, parent, text: str, **kwargs):
        super().__init__(parent, style="TFrame", **kwargs)
        tk.Label(self, text=text, font=FONTS["SUBHEAD"],
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Separator(self, orient="horizontal").pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )


class DataTable(ttk.Frame):
    """
    Scrollable Treeview table with alternating row colours and
    optional column sort on header click.
    """

    ROW_EVEN = PALETTE["SURFACE"]
    ROW_ODD  = "#1e1e35"

    def __init__(self, parent, columns: list[dict], height: int = 14, **kwargs):
        """
        Args:
            columns: List of dicts with keys:
                     'key'   — internal column id
                     'label' — header text
                     'width' — pixel width (optional, default 120)
                     'anchor'— text alignment ('w'/'center'/'e', default 'w')
        """
        super().__init__(parent, style="TFrame", **kwargs)

        col_keys = [c["key"] for c in columns]
        self.tree = ttk.Treeview(
            self, columns=col_keys, show="headings",
            height=height, selectmode="browse"
        )

        # Configure columns
        for col in columns:
            self.tree.heading(
                col["key"], text=col["label"],
                command=lambda k=col["key"]: self._sort_column(k)
            )
            self.tree.column(
                col["key"],
                width=col.get("width", 120),
                anchor=col.get("anchor", "w"),
                stretch=col.get("stretch", False),
            )

        # Alternating row tags
        self.tree.tag_configure("even", background=self.ROW_EVEN,
                                foreground=PALETTE["TEXT"])
        self.tree.tag_configure("odd",  background=self.ROW_ODD,
                                foreground=PALETTE["TEXT"])
        self.tree.tag_configure("success", background="#0d2a1e",
                                foreground=PALETTE["SUCCESS"])
        self.tree.tag_configure("warning", background="#2a1e00",
                                foreground=PALETTE["WARNING"])
        self.tree.tag_configure("danger",  background="#2a0d15",
                                foreground=PALETTE["DANGER"])

        # Scrollbars
        vsb = ttk.Scrollbar(self, orient="vertical",
                            command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal",
                            command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set,
                            xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._sort_state: dict[str, bool] = {}

    def load(self, rows: list[tuple | list], tags: list[str] = None):
        """
        Replace table contents with new rows.

        Args:
            rows: Sequence of tuples/lists, one per row.
            tags: Optional list of tag names (same length as rows).
                  Tags override the default alternating-row style.
        """
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(rows):
            if tags and i < len(tags):
                tag = tags[i]
            else:
                tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", tk.END, values=tuple(row), tags=(tag,))

    def get_selected(self) -> tuple | None:
        """Return the values tuple of the currently selected row, or None."""
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0], "values")

    def get_selected_index(self) -> int:
        """Return the 0-based index of the selected row, or -1."""
        sel = self.tree.selection()
        if not sel:
            return -1
        return self.tree.index(sel[0])

    def clear(self):
        self.tree.delete(*self.tree.get_children())

    def bind_select(self, callback):
        """Bind a callback to row selection change."""
        self.tree.bind("<<TreeviewSelect>>", callback)

    def bind_double_click(self, callback):
        self.tree.bind("<Double-1>", callback)

    def _sort_column(self, col_key: str):
        """Sort the table by clicking a column header."""
        reverse = self._sort_state.get(col_key, False)
        items = [(self.tree.set(child, col_key), child)
                 for child in self.tree.get_children("")]
        try:
            items.sort(key=lambda x: float(x[0]) if x[0].replace('.', '', 1).replace('%', '').isdigit() else x[0].lower(),
                       reverse=reverse)
        except Exception:
            items.sort(key=lambda x: x[0].lower(), reverse=reverse)

        for idx, (_, child) in enumerate(items):
            self.tree.move(child, "", idx)
            tag = "even" if idx % 2 == 0 else "odd"
            self.tree.item(child, tags=(tag,))

        self._sort_state[col_key] = not reverse


class Sidebar(tk.Frame):
    """
    Vertical navigation rail — icon + label items with active highlight.
    """

    def __init__(self, parent, items: list[dict], on_select,
                 width: int = 200, **kwargs):
        """
        Args:
            items: List of dicts with 'icon', 'label', 'key'.
            on_select: Callback(key: str) when an item is clicked.
        """
        super().__init__(parent, bg=PALETTE["PANEL"],
                         width=width, **kwargs)
        self.pack_propagate(False)
        self._on_select = on_select
        self._buttons: dict[str, tk.Label] = {}
        self._active_key: str = None

        for item in items:
            self._add_item(item)

    def _add_item(self, item: dict):
        key = item["key"]
        frame = tk.Frame(self, bg=PALETTE["PANEL"], cursor="hand2")
        frame.pack(fill=tk.X, pady=1)

        icon_lbl = tk.Label(frame, text=item.get("icon", "●"),
                            font=("Segoe UI", 14),
                            bg=PALETTE["PANEL"], fg=PALETTE["SUBTEXT"],
                            width=3, anchor="center")
        icon_lbl.pack(side=tk.LEFT, padx=(8, 4), pady=8)

        text_lbl = tk.Label(frame, text=item["label"],
                            font=FONTS["BODY"],
                            bg=PALETTE["PANEL"], fg=PALETTE["SUBTEXT"],
                            anchor="w")
        text_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=8)

        for widget in (frame, icon_lbl, text_lbl):
            widget.bind("<Button-1>", lambda e, k=key: self.select(k))
            widget.bind("<Enter>",
                        lambda e, f=frame, il=icon_lbl, tl=text_lbl:
                        self._hover(f, il, tl, True))
            widget.bind("<Leave>",
                        lambda e, k=key, f=frame, il=icon_lbl, tl=text_lbl:
                        self._hover_end(k, f, il, tl))

        self._buttons[key] = {
            "frame": frame, "icon": icon_lbl, "text": text_lbl
        }

    def select(self, key: str):
        if self._active_key and self._active_key in self._buttons:
            old = self._buttons[self._active_key]
            old["frame"].configure(bg=PALETTE["PANEL"])
            old["icon"].configure(bg=PALETTE["PANEL"], fg=PALETTE["SUBTEXT"])
            old["text"].configure(bg=PALETTE["PANEL"], fg=PALETTE["SUBTEXT"])

        if key in self._buttons:
            new = self._buttons[key]
            new["frame"].configure(bg=PALETTE["ACCENT2"])
            new["icon"].configure(bg=PALETTE["ACCENT2"], fg=PALETTE["WHITE"])
            new["text"].configure(bg=PALETTE["ACCENT2"], fg=PALETTE["WHITE"])

        self._active_key = key
        self._on_select(key)

    def _hover(self, frame, icon, text, entering):
        if frame.cget("bg") != PALETTE["ACCENT2"]:
            bg = PALETTE["BORDER"] if entering else PALETTE["PANEL"]
            fg = PALETTE["TEXT"] if entering else PALETTE["SUBTEXT"]
            frame.configure(bg=bg)
            icon.configure(bg=bg, fg=fg)
            text.configure(bg=bg, fg=fg)

    def _hover_end(self, key, frame, icon, text):
        self._hover(frame, icon, text, False)


class Avatar(tk.Canvas):
    """Circular avatar with initials when no photo is available."""

    COLOURS = ["#e94560", "#0f3460", "#16c79a", "#f5a623",
               "#4fc3f7", "#7c4dff", "#ff7043"]

    def __init__(self, parent, name: str, size: int = 48, **kwargs):
        super().__init__(parent, width=size, height=size,
                         bg=PALETTE["SURFACE"], highlightthickness=0, **kwargs)
        self._size = size
        self.set_name(name)

    def set_name(self, name: str):
        self.delete("all")
        initials = "".join(w[0].upper() for w in name.split()[:2]) if name else "?"
        colour = self.COLOURS[sum(ord(c) for c in name) % len(self.COLOURS)]
        s = self._size
        self.create_oval(2, 2, s - 2, s - 2, fill=colour, outline="")
        font_size = max(10, s // 3)
        self.create_text(s // 2, s // 2, text=initials,
                         font=("Segoe UI", font_size, "bold"),
                         fill=PALETTE["WHITE"])


class AttendanceBar(ttk.Frame):
    """Attendance percentage bar with colour-coded label."""

    def __init__(self, parent, percent: float, show_label: bool = True, **kwargs):
        super().__init__(parent, style="Surface.TFrame", **kwargs)
        self._bar_style = self._style_for(percent)
        bar = ttk.Progressbar(self, value=percent, maximum=100,
                              style=self._bar_style, length=160)
        bar.pack(side=tk.LEFT, padx=(0, 8))
        if show_label:
            color = self._color_for(percent)
            tk.Label(self, text=f"{percent:.0f}%",
                     font=FONTS["SMALL"], bg=PALETTE["SURFACE"],
                     fg=color).pack(side=tk.LEFT)

    @staticmethod
    def _style_for(p: float) -> str:
        if p >= 75:
            return "TProgressbar"
        if p >= 60:
            return "Warning.TProgressbar"
        return "Danger.TProgressbar"

    @staticmethod
    def _color_for(p: float) -> str:
        if p >= 75:
            return PALETTE["SUCCESS"]
        if p >= 60:
            return PALETTE["WARNING"]
        return PALETTE["DANGER"]


class Toast:
    """
    Temporary overlay notification.
    Appears in the bottom-right corner of the root window, fades after 2.5 s.
    """

    _BG = {
        "success": PALETTE["SUCCESS"],
        "error":   PALETTE["DANGER"],
        "info":    PALETTE["INFO"],
        "warning": PALETTE["WARNING"],
    }
    _FG = {
        "success": PALETTE["BG"],
        "error":   PALETTE["WHITE"],
        "info":    PALETTE["BG"],
        "warning": PALETTE["BG"],
    }
    _ICONS = {
        "success": "✓",
        "error":   "✕",
        "info":    "ℹ",
        "warning": "⚠",
    }

    def __init__(self, root: tk.Misc, message: str, kind: str = "info",
                 duration_ms: int = 2800):
        self._root = root
        bg = self._BG.get(kind, PALETTE["INFO"])
        fg = self._FG.get(kind, PALETTE["BG"])
        icon = self._ICONS.get(kind, "ℹ")

        self._win = tk.Toplevel(root)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.configure(bg=bg)

        frame = tk.Frame(self._win, bg=bg, padx=14, pady=10)
        frame.pack()
        tk.Label(frame, text=icon, font=("Segoe UI", 13, "bold"),
                 bg=bg, fg=fg).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(frame, text=message, font=FONTS["BODY"],
                 bg=bg, fg=fg, wraplength=280).pack(side=tk.LEFT)

        self._win.update_idletasks()
        self._position()
        root.after(duration_ms, self._dismiss)

    def _position(self):
        root_x = self._root.winfo_rootx()
        root_y = self._root.winfo_rooty()
        root_w = self._root.winfo_width()
        root_h = self._root.winfo_height()
        w = self._win.winfo_width()
        h = self._win.winfo_height()
        x = root_x + root_w - w - 20
        y = root_y + root_h - h - 40
        self._win.geometry(f"+{x}+{y}")

    def _dismiss(self):
        try:
            self._win.destroy()
        except tk.TclError:
            pass


class ConfirmDialog:
    """Modal yes/no dialog. Returns True if user confirms."""

    def __init__(self, parent, title: str, message: str,
                 confirm_text: str = "Confirm",
                 danger: bool = False) -> None:
        self.result = False
        self._win = tk.Toplevel(parent)
        self._win.title(title)
        self._win.configure(bg=PALETTE["SURFACE"])
        self._win.resizable(False, False)
        self._win.grab_set()
        self._win.transient(parent)

        frame = tk.Frame(self._win, bg=PALETTE["SURFACE"], padx=28, pady=24)
        frame.pack()

        tk.Label(frame, text=title, font=FONTS["HEADING"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["WHITE"]).pack(anchor="w")
        tk.Label(frame, text=message, font=FONTS["BODY"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["TEXT"],
                 wraplength=340, justify="left").pack(anchor="w", pady=(10, 20))

        btn_frame = tk.Frame(frame, bg=PALETTE["SURFACE"])
        btn_frame.pack(anchor="e")

        ttk.Button(btn_frame, text="Cancel",
                   style="Ghost.TButton",
                   command=self._cancel).pack(side=tk.LEFT, padx=(0, 8))

        btn_style = "Danger.TButton" if danger else "Primary.TButton"
        ttk.Button(btn_frame, text=confirm_text,
                   style=btn_style,
                   command=self._confirm).pack(side=tk.LEFT)

        self._win.bind("<Return>", lambda e: self._confirm())
        self._win.bind("<Escape>", lambda e: self._cancel())

        # Centre over parent
        parent.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 200) // 2
        self._win.geometry(f"400x200+{x}+{y}")
        self._win.wait_window()

    def _confirm(self):
        self.result = True
        self._win.destroy()

    def _cancel(self):
        self.result = False
        self._win.destroy()


class FormDialog(tk.Toplevel):
    """
    Generic modal form dialog.
    Subclass and override build_fields() to add form content.
    Call get_result() after wait_window() to retrieve values.
    """

    def __init__(self, parent, title: str, width: int = 440,
                 height: int = None):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=PALETTE["SURFACE"])
        self.resizable(False, False)
        self.grab_set()
        self.transient(parent)
        self._result: dict | None = None

        outer = tk.Frame(self, bg=PALETTE["SURFACE"], padx=28, pady=24)
        outer.pack(fill=tk.BOTH, expand=True)

        tk.Label(outer, text=title, font=FONTS["HEADING"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["WHITE"]).pack(
            anchor="w", pady=(0, 16)
        )

        self.form_frame = tk.Frame(outer, bg=PALETTE["SURFACE"])
        self.form_frame.pack(fill=tk.BOTH, expand=True)

        self.build_fields()

        ttk.Separator(outer).pack(fill=tk.X, pady=16)

        btn_frame = tk.Frame(outer, bg=PALETTE["SURFACE"])
        btn_frame.pack(anchor="e")
        ttk.Button(btn_frame, text="Cancel",
                   style="Ghost.TButton",
                   command=self.destroy).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="Save",
                   style="Primary.TButton",
                   command=self._on_save).pack(side=tk.LEFT)

        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Return>",  lambda e: self._on_save())

        # Centre
        parent.update_idletasks()
        w = width
        h = height or self.winfo_reqheight() + 20
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{max(0,x)}+{max(0,y)}")

    def build_fields(self):
        """Override in subclass to add form widgets to self.form_frame."""
        pass

    def _on_save(self):
        """Override in subclass to validate and collect values, then call self.submit()."""
        self.submit({})

    def submit(self, result: dict):
        self._result = result
        self.destroy()

    def get_result(self) -> dict | None:
        return self._result

    # Helpers for building common field types

    def _labeled_entry(self, label: str, var: tk.StringVar = None,
                       row: int = 0, show: str = None) -> tk.StringVar:
        var = var or tk.StringVar()
        tk.Label(self.form_frame, text=label, font=FONTS["LABEL"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"]).grid(
            row=row, column=0, sticky="w", pady=4
        )
        entry = ttk.Entry(self.form_frame, textvariable=var,
                          show=show or "", width=30)
        entry.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=4)
        self.form_frame.columnconfigure(1, weight=1)
        return var

    def _labeled_combo(self, label: str, options: list,
                       var: tk.StringVar = None,
                       row: int = 0) -> tk.StringVar:
        var = var or tk.StringVar()
        tk.Label(self.form_frame, text=label, font=FONTS["LABEL"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"]).grid(
            row=row, column=0, sticky="w", pady=4
        )
        cb = ttk.Combobox(self.form_frame, textvariable=var,
                          values=options, state="readonly", width=28)
        cb.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=4)
        if options:
            var.set(options[0])
        self.form_frame.columnconfigure(1, weight=1)
        return var


class LoadingOverlay(tk.Toplevel):
    """
    Animated modal loading overlay.
    Usage:
        overlay = LoadingOverlay(root, "Loading database...")
        # ... do work ...
        overlay.close()
    """

    def __init__(self, parent, message: str = "Loading…"):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=PALETTE["SURFACE"])
        self.grab_set()

        frame = tk.Frame(self, bg=PALETTE["SURFACE"], padx=40, pady=28)
        frame.pack()

        self._dot_label = tk.Label(frame, text="●●●",
                                   font=("Segoe UI", 20),
                                   bg=PALETTE["SURFACE"],
                                   fg=PALETTE["ACCENT"])
        self._dot_label.pack()
        tk.Label(frame, text=message, font=FONTS["BODY"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["TEXT"]).pack(pady=(8, 0))

        self.update_idletasks()
        w, h = 220, 100
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{px}+{py}")

        self._running = True
        self._animate()

    def _animate(self):
        dots = ["●○○", "○●○", "○○●", "○●○"]
        self._step = getattr(self, "_step", 0)
        if self._running:
            try:
                self._dot_label.configure(text=dots[self._step % len(dots)])
                self._step += 1
                self.after(300, self._animate)
            except tk.TclError:
                pass

    def close(self):
        self._running = False
        try:
            self.grab_release()
            self.destroy()
        except tk.TclError:
            pass


class TopBar(tk.Frame):
    """
    Top navigation bar shared across all dashboards.
    Shows the app name, current user info, and a logout button.
    """

    def __init__(self, parent, user: dict, on_logout, **kwargs):
        super().__init__(parent, bg=PALETTE["PANEL"],
                         height=56, **kwargs)
        self.pack_propagate(False)

        # App name
        tk.Label(self, text="AttendIQ",
                 font=("Segoe UI", 16, "bold"),
                 bg=PALETTE["PANEL"], fg=PALETTE["ACCENT"]).pack(
            side=tk.LEFT, padx=20
        )

        # Logout on right
        ttk.Button(self, text="Logout ⏏",
                   style="Ghost.TButton",
                   command=on_logout).pack(side=tk.RIGHT, padx=16)

        # Role badge
        role_colours = {
            "admin":    PALETTE["ACCENT"],
            "lecturer": PALETTE["INFO"],
            "student":  PALETTE["SUCCESS"],
        }
        role = user.get("role", "student")
        role_bg = role_colours.get(role, PALETTE["MUTED"])
        tk.Label(self, text=role.capitalize(),
                 font=FONTS["SMALL"],
                 bg=role_bg, fg=PALETTE["BG"],
                 padx=8, pady=3).pack(side=tk.RIGHT, padx=8)

        # User name
        tk.Label(self, text=user.get("full_name", "User"),
                 font=FONTS["BODY"],
                 bg=PALETTE["PANEL"], fg=PALETTE["TEXT"]).pack(
            side=tk.RIGHT, padx=4
        )
