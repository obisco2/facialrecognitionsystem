"""
AttendIQ — Lecturer Attendance Viewer.

Two tabs:
  Live Session  — camera feed + real-time face recognition + attendance list
  History       — date-filtered records with manual edit and colour-coded confidence
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import cv2
from PIL import Image, ImageTk
from datetime import datetime
import logging

from gui.components import (
    PALETTE, FONTS, Card, DataTable, Toast,
    ConfirmDialog, LoadingOverlay, SectionHeader,
)

logger = logging.getLogger(__name__)


class AttendanceViewerPanel(ttk.Frame):
    """Hosts both the Live Session and History tabs."""

    def __init__(self, parent, db, user: dict, config, root_ref):
        super().__init__(parent, style="TFrame")
        self._db      = db
        self._user    = user
        self._config  = config
        self._root    = root_ref

        # Face recognition objects (lazy-initialised on session start)
        self._recognizer     = None
        self._camera_running = False
        self._camera_thread  = None
        self._session_class  = None
        self._session_date   = None
        self._marked_ids: set[int] = set()

        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True)

        live_frame = ttk.Frame(nb, style="TFrame")
        hist_frame = ttk.Frame(nb, style="TFrame")
        nb.add(live_frame, text="  📷  Live Session  ")
        nb.add(hist_frame, text="  📋  History  ")

        self._build_live(live_frame)
        self._build_history(hist_frame)

    # ------------------------------------------------------------------
    # Live Session tab
    # ------------------------------------------------------------------

    def _build_live(self, parent):
        parent.columnconfigure(0, weight=3)
        parent.columnconfigure(1, weight=2)
        parent.rowconfigure(0, weight=1)

        # ---- Left: camera feed ----
        left = tk.Frame(parent, bg=PALETTE["BG"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=8)

        tk.Label(left, text="Camera Feed",
                 font=FONTS["SUBHEAD"],
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(anchor="w")

        self._placeholder = ImageTk.PhotoImage(Image.new("RGB", (640, 480), PALETTE["PANEL"]))
        self._video_label = tk.Label(left, image=self._placeholder, bg=PALETTE["PANEL"])
        self._video_label.imgtk = self._placeholder
        self._video_label.pack(expand=True)

        # FPS counter
        self._fps_var = tk.StringVar(value="")
        tk.Label(left, textvariable=self._fps_var,
                 font=FONTS["MONO"],
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(anchor="e")

        # ---- Right: controls ----
        right = tk.Frame(parent, bg=PALETTE["BG"])
        right.grid(row=0, column=1, sticky="nsew", pady=8, padx=(0, 8))

        # Class selector
        ctrl_card = Card(right, "Session Controls")
        ctrl_card.pack(fill=tk.X, pady=(0, 10))

        tk.Label(ctrl_card, text="Class", font=FONTS["LABEL"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"]).pack(anchor="w")
        self._class_var = tk.StringVar()
        self._class_combo = ttk.Combobox(ctrl_card, textvariable=self._class_var,
                                          state="readonly", width=30)
        self._class_combo.pack(fill=tk.X, pady=(4, 10))
        self._refresh_class_list()

        # Camera source
        tk.Label(ctrl_card, text="Camera Source",
                 font=FONTS["LABEL"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"]).pack(anchor="w")

        self._cam_mode = tk.StringVar(value="local")
        modes_row = tk.Frame(ctrl_card, bg=PALETTE["SURFACE"])
        modes_row.pack(fill=tk.X)
        ttk.Radiobutton(modes_row, text="Webcam",
                        variable=self._cam_mode, value="local",
                        command=self._toggle_cam_input).pack(side=tk.LEFT)
        ttk.Radiobutton(modes_row, text="IP / RTSP",
                        variable=self._cam_mode, value="rtsp",
                        command=self._toggle_cam_input).pack(side=tk.LEFT, padx=(10, 0))

        # Local cam index
        self._local_row = tk.Frame(ctrl_card, bg=PALETTE["SURFACE"])
        self._local_row.pack(fill=tk.X, pady=3)
        tk.Label(self._local_row, text="Index:", font=FONTS["BODY"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"]).pack(side=tk.LEFT)
        self._cam_idx_var = tk.StringVar(value=str(self._config.camera_index))
        ttk.Entry(self._local_row, textvariable=self._cam_idx_var,
                  width=5).pack(side=tk.LEFT, padx=(6, 0))

        # RTSP URL row (hidden by default)
        self._rtsp_row = tk.Frame(ctrl_card, bg=PALETTE["SURFACE"])
        self._rtsp_var = tk.StringVar(value=self._config.stream_url)
        tk.Label(self._rtsp_row, text="URL:", font=FONTS["BODY"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUBTEXT"]).pack(side=tk.LEFT)
        self._rtsp_entry = ttk.Entry(self._rtsp_row, textvariable=self._rtsp_var,
                                      width=30)
        self._rtsp_entry.pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(self._rtsp_row, text="Test",
                   command=self._test_rtsp).pack(side=tk.LEFT, padx=(6, 0))

        # Start / Stop buttons
        btn_row = tk.Frame(ctrl_card, bg=PALETTE["SURFACE"])
        btn_row.pack(fill=tk.X, pady=(12, 0))
        self._start_btn = ttk.Button(btn_row, text="▶  Start Session",
                                      style="Success.TButton",
                                      command=self._start_session)
        self._start_btn.pack(side=tk.LEFT, padx=(0, 8))
        self._stop_btn = ttk.Button(btn_row, text="⏹  Stop Session",
                                     style="Danger.TButton",
                                     command=self._stop_session,
                                     state=tk.DISABLED)
        self._stop_btn.pack(side=tk.LEFT)

        # Status
        self._status_var = tk.StringVar(value="Ready — select a class to begin.")
        tk.Label(ctrl_card, textvariable=self._status_var,
                 font=FONTS["SMALL"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["SUCCESS"],
                 wraplength=260).pack(anchor="w", pady=(8, 0))

        # Live list card
        list_card = Card(right, "Present  (live)")
        list_card.pack(fill=tk.BOTH, expand=True)

        list_cols = [
            {"key": "time", "label": "Time",   "width": 70},
            {"key": "name", "label": "Name",   "width": 160, "stretch": True},
            {"key": "conf", "label": "Conf",   "width": 55,  "anchor": "center"},
        ]
        self._live_table = DataTable(list_card, columns=list_cols, height=12)
        self._live_table.pack(fill=tk.BOTH, expand=True)

        # Manual add
        manual_row = tk.Frame(list_card, bg=PALETTE["SURFACE"])
        manual_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(manual_row, text="＋ Add Manually",
                   command=self._manual_add).pack(side=tk.LEFT)

        self._unknown_var = tk.StringVar(value="")
        tk.Label(list_card, textvariable=self._unknown_var,
                 font=FONTS["SMALL"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["MUTED"]).pack(anchor="w")

    # ------------------------------------------------------------------
    # History tab
    # ------------------------------------------------------------------

    def _build_history(self, parent):
        # Filter bar
        filter_bar = tk.Frame(parent, bg=PALETTE["BG"])
        filter_bar.pack(fill=tk.X, pady=(8, 6), padx=8)

        tk.Label(filter_bar, text="Class:", font=FONTS["LABEL"],
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(side=tk.LEFT)
        self._hist_class_var = tk.StringVar()
        self._hist_class_combo = ttk.Combobox(
            filter_bar, textvariable=self._hist_class_var,
            state="readonly", width=24
        )
        self._hist_class_combo.pack(side=tk.LEFT, padx=(6, 16))

        tk.Label(filter_bar, text="Date:", font=FONTS["LABEL"],
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(side=tk.LEFT)

        # Try tkcalendar DateEntry; fallback to ttk.Entry
        try:
            from tkcalendar import DateEntry
            self._hist_date = DateEntry(
                filter_bar, width=12, date_pattern="yyyy-mm-dd",
                background=PALETTE["ACCENT"], foreground=PALETTE["WHITE"]
            )
        except ImportError:
            self._hist_date_var = tk.StringVar(
                value=datetime.now().strftime("%Y-%m-%d")
            )
            self._hist_date = ttk.Entry(filter_bar,
                                         textvariable=self._hist_date_var,
                                         width=12)
        self._hist_date.pack(side=tk.LEFT, padx=(6, 16))

        ttk.Button(filter_bar, text="Load",
                   style="Primary.TButton",
                   command=self._load_history).pack(side=tk.LEFT)
        ttk.Button(filter_bar, text="↻ Refresh",
                   command=self._load_history).pack(side=tk.LEFT, padx=(8, 0))

        # Summary bar
        self._hist_summary_var = tk.StringVar(value="")
        tk.Label(filter_bar, textvariable=self._hist_summary_var,
                 font=FONTS["BODY"],
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(side=tk.RIGHT)

        # Table
        hist_cols = [
            {"key": "sid",    "label": "Student ID", "width": 110},
            {"key": "name",   "label": "Name",       "width": 180, "stretch": True},
            {"key": "time",   "label": "Time",        "width": 80},
            {"key": "method", "label": "Method",      "width": 90, "anchor": "center"},
            {"key": "conf",   "label": "Confidence",  "width": 90, "anchor": "center"},
        ]
        frame = tk.Frame(parent, bg=PALETTE["BG"])
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self._hist_table = DataTable(frame, columns=hist_cols, height=20)
        self._hist_table.pack(fill=tk.BOTH, expand=True)

        # Delete record
        act_row = tk.Frame(frame, bg=PALETTE["BG"])
        act_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(act_row, text="✕ Remove Selected Record",
                   style="Danger.TButton",
                   command=self._delete_record).pack(side=tk.LEFT)

        self._hist_records_cache: list[dict] = []

        self._refresh_history_classes()

    # ------------------------------------------------------------------
    # Camera source helpers
    # ------------------------------------------------------------------

    def _toggle_cam_input(self):
        if self._cam_mode.get() == "local":
            self._rtsp_row.pack_forget()
            self._local_row.pack(fill=tk.X, pady=3)
        else:
            self._local_row.pack_forget()
            self._rtsp_row.pack(fill=tk.X, pady=3)

    def _get_camera_source(self):
        """Return the camera source — int index or RTSP URL string."""
        if self._cam_mode.get() == "rtsp":
            url = self._rtsp_var.get().strip()
            if not url:
                return 0
            return url
        try:
            return int(self._cam_idx_var.get())
        except ValueError:
            return 0

    def _test_rtsp(self):
        url = self._rtsp_var.get().strip()
        if not url:
            Toast(self._root, "Enter an RTSP URL first.", "warning")
            return
        overlay = LoadingOverlay(self._root, "Testing camera connection…")

        def _check():
            cap = cv2.VideoCapture(url)
            ok = cap.isOpened()
            ret, frame = cap.read() if ok else (False, None)
            cap.release()
            self._root.after(0, overlay.close)
            if ret and frame is not None:
                self._root.after(0, lambda: Toast(
                    self._root, "✓ Camera connection successful!", "success"
                ))
                # Save URL to config
                self._config.set("Camera", "STREAM_URL", url)
            else:
                self._root.after(0, lambda: Toast(
                    self._root, "Could not connect to camera. Check URL.", "error"
                ))

        threading.Thread(target=_check, daemon=True).start()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _refresh_class_list(self):
        classes = self._db.get_classes(lecturer_id=self._user["id"])
        self._classes = {f"{c['code']} — {c['name']}": c for c in classes}
        self._class_combo["values"] = list(self._classes.keys())
        if self._classes:
            self._class_combo.current(0)

    def _start_session(self):
        class_key = self._class_var.get()
        if not class_key or class_key not in self._classes:
            Toast(self._root, "Select a class first.", "warning")
            return

        self._session_class = self._classes[class_key]
        self._session_date  = datetime.now().strftime("%Y-%m-%d")
        self._marked_ids    = set()
        self._unknown_count = 0
        self._live_rows     = []

        # Load face recognizer
        overlay = LoadingOverlay(self._root, "Loading face database…")

        def _load():
            try:
                from core.face_detector import FaceDetector
                from core.face_encoder  import FaceEncoder
                from core.recognizer    import Recognizer

                detector  = FaceDetector(model="haar")
                encoder   = FaceEncoder(
                    engine=self._config.recognition_engine,
                    tolerance=self._config.tolerance
                )
                recognizer = Recognizer(detector, encoder)
                recognizer.load_database(self._config.known_faces_dir)

                source = self._get_camera_source()
                opened = recognizer.start_camera(source)

                self._root.after(0, overlay.close)
                if not opened:
                    self._root.after(0, lambda: Toast(
                        self._root, "Cannot open camera.", "error"
                    ))
                    return

                self._recognizer    = recognizer
                self._camera_running = True
                self._camera_thread  = threading.Thread(
                    target=self._camera_loop, daemon=True
                )
                self._camera_thread.start()
                self._root.after(0, self._on_session_started)

            except Exception as e:
                logger.exception("Session start error")
                self._root.after(0, overlay.close)
                self._root.after(0, lambda: Toast(self._root, str(e), "error"))

        threading.Thread(target=_load, daemon=True).start()

    def _on_session_started(self):
        self._start_btn.configure(state=tk.DISABLED)
        self._stop_btn.configure(state=tk.NORMAL)
        self._live_table.clear()
        self._status_var.set(
            f"Session active — {self._session_class['name']}  |  {self._session_date}"
        )

    def _stop_session(self):
        self._camera_running = False
        if self._recognizer:
            self._recognizer.stop_camera()
            self._recognizer = None
        self._video_label.configure(image=self._placeholder)
        self._start_btn.configure(state=tk.NORMAL)
        self._stop_btn.configure(state=tk.DISABLED)
        count = len(self._marked_ids)
        self._status_var.set(
            f"Session ended.  {count} student(s) marked present."
        )
        Toast(self._root, f"Session ended — {count} marked present.", "info")
        self._refresh_history_classes()

    def _camera_loop(self):
        """Background thread: read frames, detect faces, mark attendance."""
        scale     = self._config.frame_scale
        fps_times = []
        unknown_count = 0

        while self._camera_running and self._recognizer:
            t0 = time.time()
            ret, frame = self._recognizer.read_frame()
            if not ret or frame is None:
                time.sleep(0.02)
                continue

            locations, names, distances = self._recognizer.process_frame(frame, scale)

            for (top, right, bottom, left), name, dist in zip(locations, names, distances):
                t = int(top / scale); r = int(right / scale)
                b = int(bottom / scale); l = int(left / scale)

                is_known = (name != "Unknown")
                colour = (0, 200, 100) if is_known else (0, 60, 200)

                cv2.rectangle(frame, (l, t), (r, b), colour, 2)
                cv2.rectangle(frame, (l, b - 26), (r, b), colour, cv2.FILLED)

                conf_str = f"{dist:.2f}" if dist is not None else "?"
                label    = f"{name}  {conf_str}" if is_known else "Unknown"
                cv2.putText(frame, label, (l + 5, b - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                            (255, 255, 255), 1)

                if is_known:
                    # Look up student in DB by full_name
                    student = self._db.get_user_by_name(name)
                    if student and student["id"] not in self._marked_ids:
                        logged = self._db.log_attendance(
                            student["id"],
                            self._session_class["id"],
                            session_date=self._session_date,
                            method="face",
                            confidence=dist,
                            marked_by=self._user["id"],
                        )
                        if logged:
                            self._marked_ids.add(student["id"])
                            ts = datetime.now().strftime("%H:%M:%S")
                            conf_display = f"{dist:.2f}" if dist else "—"
                            row = (ts, name, conf_display)
                            self._root.after(0, lambda r=row: self._append_live_row(r))
                else:
                    unknown_count += 1
                    if unknown_count % 30 == 0:  # throttle UI updates
                        self._root.after(0, lambda c=unknown_count: self._unknown_var.set(
                            f"{c} unrecognised detections this session"
                        ))

            # FPS
            fps_times.append(time.time() - t0)
            if len(fps_times) > 20:
                fps_times.pop(0)
            fps = 1.0 / (sum(fps_times) / len(fps_times)) if fps_times else 0
            fps_str = f"  {fps:.0f} fps"

            # Render frame in GUI
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img   = Image.fromarray(rgb)
            imgtk = ImageTk.PhotoImage(image=img)
            self._root.after(0, lambda i=imgtk, f=fps_str: self._update_feed(i, f))

            time.sleep(0.015)

    def _update_feed(self, imgtk, fps_str: str):
        try:
            self._video_label.imgtk = imgtk
            self._video_label.configure(image=imgtk)
            self._fps_var.set(fps_str)
        except tk.TclError:
            pass

    def _append_live_row(self, row: tuple):
        if not hasattr(self, "_live_rows"):
            self._live_rows = []
        self._live_rows.append(row)
        conf_val = float(row[2]) if row[2] not in ("—", "?", "") else 1.0
        tag = "success" if conf_val < 0.4 else ("warning" if conf_val < 0.6 else "")
        self._live_table.tree.insert("", 0, values=row, tags=(tag,))

    def _manual_add(self):
        if not self._session_class:
            Toast(self._root, "Start a session first.", "warning")
            return
        enrolled = self._db.get_enrolled_students(self._session_class["id"])
        all_students = self._db.get_users("student")
        enrolled_ids = {s["id"] for s in enrolled}
        students = enrolled + [s for s in all_students if s["id"] not in enrolled_ids]
        names = [f"{s['full_name']}  ({s.get('student_id') or 'no ID'})"
                 + ("" if s["id"] in enrolled_ids else "  [unenrolled]")
                 for s in students]
        if not names:
            Toast(self._root, "No students found.", "info")
            return

        win = tk.Toplevel(self._root)
        win.title("Add Manually")
        win.configure(bg=PALETTE["SURFACE"])
        win.grab_set()
        win.geometry("320x200")

        tk.Label(win, text="Select student:",
                 font=FONTS["LABEL"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["TEXT"]).pack(pady=(16, 6))
        var = tk.StringVar()
        cb = ttk.Combobox(win, textvariable=var, values=names,
                          state="readonly", width=32)
        cb.pack(padx=20)
        if names:
            cb.current(0)

        def _confirm():
            idx = cb.current()
            if idx < 0:
                return
            student = students[idx]
            logged = self._db.log_attendance(
                student["id"], self._session_class["id"],
                session_date=self._session_date,
                method="manual",
                marked_by=self._user["id"],
            )
            if logged:
                self._marked_ids.add(student["id"])
                ts = datetime.now().strftime("%H:%M:%S")
                self._append_live_row((ts, student["full_name"], "manual"))
                Toast(self._root, f"{student['full_name']} marked manually.", "success")
            else:
                Toast(self._root, "Already marked for today.", "info")
            win.destroy()

        ttk.Button(win, text="Confirm", style="Primary.TButton",
                   command=_confirm).pack(pady=16)

    # ------------------------------------------------------------------
    # History tab logic
    # ------------------------------------------------------------------

    def _refresh_history_classes(self):
        classes = self._db.get_classes(lecturer_id=self._user["id"])
        self._hist_classes = {f"{c['code']} — {c['name']}": c for c in classes}
        self._hist_class_combo["values"] = list(self._hist_classes.keys())
        if self._hist_classes:
            self._hist_class_combo.current(0)

    def _get_hist_date(self) -> str:
        try:
            return self._hist_date.get_date().strftime("%Y-%m-%d")
        except AttributeError:
            return self._hist_date_var.get()

    def _load_history(self):
        key = self._hist_class_var.get()
        if not key or key not in self._hist_classes:
            Toast(self._root, "Select a class.", "warning")
            return
        cls       = self._hist_classes[key]
        date_str  = self._get_hist_date()
        records   = self._db.get_attendance(cls["id"], date_str)
        self._hist_records_cache = records

        rows, tags = [], []
        for rec in records:
            conf = rec.get("confidence")
            conf_str = f"{conf:.3f}" if conf is not None else "manual"
            conf_val = conf if conf is not None else 1.0
            tag = "success" if conf_val < 0.4 else (
                "warning" if conf_val < 0.6 else ""
            )
            rows.append((
                rec.get("student_number") or "—",
                rec["full_name"],
                rec["timestamp"],
                rec["method"],
                conf_str,
            ))
            tags.append(tag)

        self._hist_table.load(rows, tags)

        # Summary
        summary = self._db.get_attendance_summary(cls["id"], date_str)
        self._hist_summary_var.set(
            f"{summary['present']} / {summary['total_enrolled']} present  "
            f"({summary['percent']:.0f}%)"
        )

    def _delete_record(self):
        idx = self._hist_table.get_selected_index()
        if idx < 0 or idx >= len(self._hist_records_cache):
            messagebox.showinfo("Select", "Select a record to remove.")
            return
        rec = self._hist_records_cache[idx]
        dlg = ConfirmDialog(
            self._root, "Remove Record",
            f"Remove attendance record for {rec['full_name']} on {rec['session_date']}?",
            confirm_text="Remove", danger=True
        )
        if dlg.result:
            self._db.delete_attendance(rec["id"])
            self._load_history()
            Toast(self._root, "Record removed.", "info")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def shutdown(self):
        self._camera_running = False
        if self._recognizer:
            try:
                self._recognizer.stop_camera()
            except Exception:
                pass
