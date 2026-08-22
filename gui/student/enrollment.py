"""
AttendIQ — Student Face Enrollment Wizard.

5-step guided wizard:
  Step 1 — Introduction / instructions
  Step 2 — Photo collection (upload files OR live capture)
  Step 3 — Validation (face detection + blur check per photo)
  Step 4 — Recognition test (live camera test using submitted photos)
  Step 5 — Success confirmation with confetti animation
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import shutil
import os
import cv2
import time
import logging
from PIL import Image, ImageTk

from gui.components import (
    PALETTE, FONTS, Card, Toast, LoadingOverlay,
)

logger = logging.getLogger(__name__)

# Number of photo slots
NUM_SLOTS = 5
THUMB_SIZE = (120, 110)
MIN_VALID  = 3
BLUR_THRESHOLD = 80.0
MIN_FACE_PX    = 50


class PhotoSlot(tk.Frame):
    """Single photo slot — empty / filled / validated / rejected."""

    STATE_EMPTY    = "empty"
    STATE_FILLED   = "filled"
    STATE_VALID    = "valid"
    STATE_INVALID  = "invalid"
    STATE_WARN     = "warn"

    def __init__(self, parent, index: int, on_retake, on_delete=None, **kwargs):
        super().__init__(parent, bg=PALETTE["SURFACE"],
                         width=THUMB_SIZE[0]+8, height=THUMB_SIZE[1]+56,
                         relief="flat", bd=0, **kwargs)
        self.pack_propagate(False)
        self._index    = index
        self._on_retake = on_retake
        self._on_delete = on_delete
        self._filepath: str | None = None
        self._state    = self.STATE_EMPTY
        self._imgtk    = None
        self._build()

    def _build(self):
        # Thumbnail area
        self._canvas = tk.Canvas(self, width=THUMB_SIZE[0], height=THUMB_SIZE[1],
                                  bg=PALETTE["PANEL"],
                                  highlightthickness=1,
                                  highlightbackground=PALETTE["BORDER"])
        self._canvas.pack(padx=4, pady=(4, 2))
        self._canvas.create_text(THUMB_SIZE[0]//2, THUMB_SIZE[1]//2,
                                  text=f"Photo {self._index+1}",
                                  font=FONTS["SMALL"],
                                  fill=PALETTE["MUTED"])

        # Status label
        self._status_label = tk.Label(self, text="Empty",
                                       font=("Segoe UI", 8),
                                       bg=PALETTE["SURFACE"],
                                       fg=PALETTE["MUTED"])
        self._status_label.pack()

        # Button row: Retake + Delete
        btn_row = tk.Frame(self, bg=PALETTE["SURFACE"])
        btn_row.pack()
        self._retake_btn = ttk.Button(btn_row, text="Retake",
                                       style="Ghost.TButton",
                                       command=lambda: self._on_retake(self._index))
        self._delete_btn = ttk.Button(btn_row, text="✕",
                                       style="Ghost.TButton",
                                       command=lambda: self._on_delete(self._index) if self._on_delete else None)
        # Only shown when filled

    def set_image(self, filepath: str):
        self._filepath = filepath
        img = Image.open(filepath).resize(THUMB_SIZE, Image.LANCZOS)
        self._imgtk = ImageTk.PhotoImage(img)
        self._canvas.delete("all")
        self._canvas.create_image(THUMB_SIZE[0]//2, THUMB_SIZE[1]//2,
                                   image=self._imgtk)
        self._set_state(self.STATE_FILLED)
        self._retake_btn.pack(side=tk.LEFT, ipady=0)
        if self._on_delete:
            self._delete_btn.pack(side=tk.LEFT, ipady=0, padx=(2, 0))

    def set_validation(self, state: str, message: str):
        """state: 'valid' | 'invalid' | 'warn'"""
        self._set_state(state)
        self._status_label.configure(text=message)

    def clear(self):
        self._filepath = None
        self._imgtk    = None
        self._canvas.delete("all")
        self._canvas.create_text(THUMB_SIZE[0]//2, THUMB_SIZE[1]//2,
                                  text=f"Photo {self._index+1}",
                                  font=FONTS["SMALL"],
                                  fill=PALETTE["MUTED"])
        self._retake_btn.pack_forget()
        self._delete_btn.pack_forget()
        self._set_state(self.STATE_EMPTY)

    def _set_state(self, state: str):
        self._state = state
        colours = {
            self.STATE_EMPTY:   (PALETTE["BORDER"],  PALETTE["MUTED"],    "Empty"),
            self.STATE_FILLED:  (PALETTE["ACCENT2"],  PALETTE["TEXT"],     "Uploaded"),
            self.STATE_VALID:   ("#0d4a2e",           PALETTE["SUCCESS"],  "✓ Valid"),
            self.STATE_INVALID: ("#4a0d15",           PALETTE["DANGER"],   "✗ Invalid"),
            self.STATE_WARN:    ("#4a3000",           PALETTE["WARNING"],  "⚠ Blurry"),
        }
        border, fg, default_text = colours.get(state, colours[self.STATE_EMPTY])
        self._canvas.configure(highlightbackground=border)
        self._status_label.configure(fg=fg)
        if state == self.STATE_EMPTY:
            self._status_label.configure(text=default_text)

    @property
    def filepath(self) -> str | None:
        return self._filepath

    @property
    def is_filled(self) -> bool:
        return self._filepath is not None

    @property
    def state(self) -> str:
        return self._state


class EnrollmentPanel(ttk.Frame):
    """The 5-step enrollment wizard."""

    def __init__(self, parent, db, user: dict, config, root_ref):
        super().__init__(parent, style="TFrame")
        self._db         = db
        self._user       = user
        self._config     = config
        self._root       = root_ref
        self._step       = 0
        self._temp_dir   = os.path.join(
            config.known_faces_dir, f"__temp_{user['id']}__"
        )
        self._final_dir  = os.path.join(
            config.known_faces_dir, user["full_name"]
        )
        self._upload_slots: list[PhotoSlot] = []
        self._capture_slots: list[PhotoSlot] = []
        self._recognizer = None
        self._camera_running = False
        self._capture_thread = None
        self._nb = None

        self._container = tk.Frame(self, bg=PALETTE["BG"])
        self._container.pack(fill=tk.BOTH, expand=True)

        self._show_step(1)

    @property
    def _slots(self) -> list[PhotoSlot]:
        if self._nb is not None:
            try:
                active_idx = self._nb.index("current")
                if active_idx == 1:
                    return self._capture_slots
            except Exception:
                pass
        return self._upload_slots

    # ------------------------------------------------------------------
    # Step routing
    # ------------------------------------------------------------------

    def _clear(self):
        for w in self._container.winfo_children():
            w.destroy()

    def _show_step(self, step: int):
        self._step = step
        self._clear()
        steps = {
            1: self._build_step1,
            2: self._build_step2,
            3: self._build_step3,
            4: self._build_step4,
            5: self._build_step5,
        }
        steps[step]()

    def _progress_bar(self, parent):
        bar = tk.Frame(parent, bg=PALETTE["BG"])
        bar.pack(fill=tk.X, pady=(0, 20))
        labels = ["Intro", "Photos", "Validate", "Test", "Done"]
        for i, label in enumerate(labels, 1):
            active = (i == self._step)
            done   = (i < self._step)
            fg = PALETTE["ACCENT"] if active else (PALETTE["SUCCESS"] if done else PALETTE["MUTED"])
            dot = tk.Label(bar, text="●",
                            font=("Segoe UI", 14),
                            bg=PALETTE["BG"], fg=fg)
            dot.pack(side=tk.LEFT)
            tk.Label(bar, text=label,
                     font=("Segoe UI", 9, "bold") if active else FONTS["SMALL"],
                     bg=PALETTE["BG"], fg=fg).pack(side=tk.LEFT, padx=(2, 12))

    # ------------------------------------------------------------------
    # Step 1 — Introduction
    # ------------------------------------------------------------------

    def _build_step1(self):
        c = self._container
        self._progress_bar(c)

        card = Card(c, padding=32)
        card.pack(fill=tk.BOTH, expand=True, padx=40, pady=(0, 40))

        tk.Label(card, text="📷  Face Enrollment",
                 font=("Segoe UI", 22, "bold"),
                 bg=PALETTE["SURFACE"], fg=PALETTE["WHITE"]).pack(pady=(0, 12))

        body = (
            "To be automatically recognised during class attendance, "
            "you need to register your face with the system.\n\n"
            "What you'll need:\n"
            "  • 5 clear photos of your face\n"
            "  • Good, even lighting (avoid harsh shadows or backlighting)\n"
            "  • Face clearly visible — no sunglasses, hats, or heavy filters\n"
            "  • Different angles are welcome for better accuracy\n\n"
            "Your photos are stored securely on the institution's server "
            "and are never shared with third parties."
        )
        tk.Label(card, text=body,
                 font=FONTS["BODY"],
                 bg=PALETTE["SURFACE"], fg=PALETTE["TEXT"],
                 justify="left", wraplength=520).pack(anchor="w", pady=(0, 28))

        # Check if already enrolled
        if self._user.get("face_enrolled"):
            tk.Label(card,
                     text="✓  You are already enrolled. Re-enrolling will replace your existing photos.",
                     font=FONTS["SMALL"],
                     bg=PALETTE["SURFACE"], fg=PALETTE["WARNING"]).pack(
                anchor="w", pady=(0, 16)
            )

        ttk.Button(card, text="Begin Enrollment  →",
                   style="Primary.TButton",
                   command=lambda: self._show_step(2)).pack(anchor="w", ipady=4)

    # ------------------------------------------------------------------
    # Step 2 — Photo collection
    # ------------------------------------------------------------------

    def _build_step2(self):
        c = self._container
        self._progress_bar(c)

        tk.Label(c, text="Add Your Photos",
                 font=FONTS["HEADING"],
                 bg=PALETTE["BG"], fg=PALETTE["WHITE"]).pack(anchor="w", pady=(0, 4))
        tk.Label(c,
                 text=f"Provide {NUM_SLOTS} photos. At least {MIN_VALID} must pass validation.",
                 font=FONTS["BODY"],
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(anchor="w", pady=(0, 16))

        # Tab: Upload vs Capture
        nb = ttk.Notebook(c)
        nb.pack(fill=tk.BOTH, expand=True)
        self._nb = nb

        upload_frame  = ttk.Frame(nb, style="TFrame")
        capture_frame = ttk.Frame(nb, style="TFrame")
        nb.add(upload_frame,  text="  ⬆ Upload Files  ")
        nb.add(capture_frame, text="  📷 Capture Live  ")

        self._build_upload_tab(upload_frame)
        self._build_capture_tab(capture_frame)

        # Bottom nav
        nav = tk.Frame(c, bg=PALETTE["BG"])
        nav.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(nav, text="← Back",
                   style="Ghost.TButton",
                   command=lambda: self._show_step(1)).pack(side=tk.LEFT)
        ttk.Button(nav, text="Validate Photos  →",
                   style="Primary.TButton",
                   command=self._go_to_validate).pack(side=tk.RIGHT)

    def _build_upload_tab(self, parent):
        inner = tk.Frame(parent, bg=PALETTE["BG"])
        inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        ttk.Button(inner, text="Browse Images…",
                   style="Primary.TButton",
                   command=self._browse_files).pack(anchor="w", pady=(0, 12))

        slots_row = tk.Frame(inner, bg=PALETTE["BG"])
        slots_row.pack(fill=tk.X)
        self._upload_slots = []
        for i in range(NUM_SLOTS):
            slot = PhotoSlot(slots_row, i, on_retake=self._retake_slot, on_delete=self._delete_slot)
            slot.pack(side=tk.LEFT, padx=(0, 8))
            self._upload_slots.append(slot)

    def _build_capture_tab(self, parent):
        inner = tk.Frame(parent, bg=PALETTE["BG"])
        inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        top = tk.Frame(inner, bg=PALETTE["BG"])
        top.pack(fill=tk.X, pady=(0, 8))

        # Target slot indicator
        self._capture_target_var = tk.StringVar(value="Capturing slot 1 of 5")
        tk.Label(top, textvariable=self._capture_target_var,
                 font=FONTS["SUBHEAD"],
                 bg=PALETTE["BG"], fg=PALETTE["TEXT"]).pack(side=tk.LEFT)

        ttk.Button(top, text="📷 Capture",
                   style="Success.TButton",
                   command=self._capture_photo).pack(side=tk.RIGHT)

        # Feed
        self._capture_placeholder = ImageTk.PhotoImage(Image.new("RGB", (320, 240), PALETTE["PANEL"]))
        self._capture_label = tk.Label(inner, image=self._capture_placeholder, bg=PALETTE["PANEL"])
        self._capture_label.imgtk = self._capture_placeholder
        self._capture_label.pack()

        # Slot strip below feed
        strip = tk.Frame(inner, bg=PALETTE["BG"])
        strip.pack(fill=tk.X, pady=(8, 0))

        self._capture_slots = []
        for i in range(NUM_SLOTS):
            slot = PhotoSlot(strip, i, on_retake=self._retake_slot, on_delete=self._delete_slot)
            slot.pack(side=tk.LEFT, padx=(0, 6))
            self._capture_slots.append(slot)

        ttk.Button(inner, text="Open Camera",
                   command=self._open_capture_camera).pack(anchor="w", pady=(8, 0))

    def _browse_files(self):
        paths = filedialog.askopenfilenames(
            title="Select 5 face photos",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")],
        )
        if not paths:
            return
        for i, path in enumerate(paths[:NUM_SLOTS]):
            self._slots[i].set_image(path)

    def _retake_slot(self, index: int):
        self._slots[index].clear()
        paths = filedialog.askopenfilenames(
            title=f"Replace photo {index+1}",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")],
        )
        if paths:
            self._slots[index].set_image(paths[0])

    def _delete_slot(self, index: int):
        slot = self._slots[index]
        if slot.filepath and os.path.exists(slot.filepath):
            try:
                os.remove(slot.filepath)
            except Exception:
                pass
        slot.clear()
        Toast(self._root, f"Photo {index+1} removed", "info")

    def _open_capture_camera(self):
        if self._camera_running:
            return
        source = (self._config.stream_url
                  if self._config.stream_url
                  else self._config.camera_index)
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            Toast(self._root, "Cannot open camera.", "error")
            return
        self._cap = cap
        self._camera_running = True
        self._capture_thread = threading.Thread(
            target=self._capture_feed_loop, daemon=True
        )
        self._capture_thread.start()
        self._update_capture_target()

    def _capture_feed_loop(self):
        while self._camera_running:
            ret, frame = self._cap.read()
            if not ret:
                break
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img   = Image.fromarray(rgb).resize((320, 240), Image.LANCZOS)
            imgtk = ImageTk.PhotoImage(image=img)
            try:
                self._root.after(0, lambda i=imgtk: self._update_capture_frame(i))
                self._latest_frame = frame
            except Exception:
                break
            time.sleep(0.04)

    def _update_capture_frame(self, imgtk):
        try:
            self._capture_label.imgtk = imgtk
            self._capture_label.configure(image=imgtk)
        except tk.TclError:
            pass

    def _capture_photo(self):
        frame = getattr(self, "_latest_frame", None)
        if frame is None:
            Toast(self._root, "Open the camera first.", "warning")
            return
        # Find first empty slot
        target = next((i for i, s in enumerate(self._slots) if not s.is_filled), None)
        if target is None:
            Toast(self._root, "All slots are filled. Retake one if needed.", "info")
            return
        os.makedirs(self._temp_dir, exist_ok=True)
        path = os.path.join(self._temp_dir, f"capture_{target}.jpg")
        cv2.imwrite(path, frame)
        self._slots[target].set_image(path)
        self._update_capture_target()

    def _update_capture_target(self):
        next_empty = next((i for i, s in enumerate(self._slots) if not s.is_filled), None)
        if next_empty is not None:
            self._capture_target_var.set(f"Capturing slot {next_empty+1} of {NUM_SLOTS}")
        else:
            self._capture_target_var.set("All slots filled ✓")
            self._camera_running = False

    def _stop_capture_camera(self):
        self._camera_running = False
        if hasattr(self, "_cap") and self._cap:
            self._cap.release()
            self._cap = None
        self._capture_label.configure(image=self._capture_placeholder)

    def _go_to_validate(self):
        filled = [s for s in self._slots if s.is_filled]
        if len(filled) < MIN_VALID:
            Toast(self._root,
                  f"Add at least {MIN_VALID} photos before proceeding.",
                  "warning")
            return
        self._stop_capture_camera()
        self._show_step(3)

    # ------------------------------------------------------------------
    # Step 3 — Validation
    # ------------------------------------------------------------------

    def _build_step3(self):
        c = self._container
        self._progress_bar(c)

        tk.Label(c, text="Validating Your Photos",
                 font=FONTS["HEADING"],
                 bg=PALETTE["BG"], fg=PALETTE["WHITE"]).pack(anchor="w", pady=(0, 4))
        tk.Label(c,
                 text="Checking each photo for a clear, detectable face.",
                 font=FONTS["BODY"],
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(anchor="w", pady=(0, 16))

        # Results grid
        grid = tk.Frame(c, bg=PALETTE["BG"])
        grid.pack(fill=tk.X, pady=(0, 16))

        self._val_labels: list[tk.Label] = []
        for i, slot in enumerate(self._slots):
            if not slot.is_filled:
                continue
            row = tk.Frame(grid, bg=PALETTE["SURFACE"], padx=12, pady=8)
            row.pack(fill=tk.X, pady=3)

            # Tiny thumbnail
            try:
                img = Image.open(slot.filepath).resize((48, 44), Image.LANCZOS)
                imgtk = ImageTk.PhotoImage(img)
                lbl = tk.Label(row, image=imgtk, bg=PALETTE["SURFACE"])
                lbl.imgtk = imgtk
                lbl.pack(side=tk.LEFT, padx=(0, 10))
            except Exception:
                pass

            tk.Label(row, text=f"Photo {i+1}",
                     font=FONTS["LABEL"],
                     bg=PALETTE["SURFACE"], fg=PALETTE["TEXT"],
                     width=8, anchor="w").pack(side=tk.LEFT)

            result_lbl = tk.Label(row, text="Checking…",
                                   font=FONTS["BODY"],
                                   bg=PALETTE["SURFACE"],
                                   fg=PALETTE["SUBTEXT"])
            result_lbl.pack(side=tk.LEFT, padx=(8, 0))
            self._val_labels.append((i, slot, result_lbl))

        # Summary label
        self._val_summary_var = tk.StringVar(value="Running validation…")
        tk.Label(c, textvariable=self._val_summary_var,
                 font=FONTS["SUBHEAD"],
                 bg=PALETTE["BG"], fg=PALETTE["TEXT"]).pack(anchor="w", pady=(0, 12))

        # Nav
        nav = tk.Frame(c, bg=PALETTE["BG"])
        nav.pack(fill=tk.X)
        ttk.Button(nav, text="← Back",
                   style="Ghost.TButton",
                   command=lambda: self._show_step(2)).pack(side=tk.LEFT)
        self._next_btn3 = ttk.Button(nav, text="Test Recognition  →",
                                      style="Primary.TButton",
                                      command=lambda: self._show_step(4),
                                      state=tk.DISABLED)
        self._next_btn3.pack(side=tk.RIGHT)

        # Run validation asynchronously
        threading.Thread(target=self._run_validation, daemon=True).start()

    def _run_validation(self):
        from core.face_detector import FaceDetector
        from core.face_encoder  import FaceEncoder

        detector = FaceDetector(model="haar")
        encoder  = FaceEncoder(engine=self._config.recognition_engine)

        valid_count = 0
        results: list[tuple[int, str, str, str]] = []  # (idx, state, msg, filepath)

        for slot_idx, slot, _ in self._val_labels:
            path = slot.filepath
            img  = cv2.imread(path)
            if img is None:
                results.append((slot_idx, "invalid", "Cannot read image", path))
                continue

            # Face detection
            small   = cv2.resize(img, (0, 0), fx=0.5, fy=0.5)
            locs    = detector.detect_faces(small)
            if not locs:
                results.append((slot_idx, "invalid", "✗ No face detected", path))
                continue

            # Face size check
            t, r, b, l = locs[0]
            face_h = (b - t) * 2; face_w = (r - l) * 2
            if face_h < MIN_FACE_PX or face_w < MIN_FACE_PX:
                results.append((slot_idx, "invalid",
                                 "✗ Face too small — stand closer", path))
                continue

            # Blur check
            blur = encoder.blur_score(img)
            if blur < BLUR_THRESHOLD:
                results.append((slot_idx, "warn",
                                 f"⚠ Blurry (score {blur:.0f}) — retake if possible",
                                 path))
                valid_count += 1
            else:
                results.append((slot_idx, "valid",
                                 f"✓ Face detected  (blur {blur:.0f})", path))
                valid_count += 1

        self._root.after(0, lambda r=results, v=valid_count:
                         self._show_validation_results(r, v))

    def _show_validation_results(self, results, valid_count: int):
        colour_map = {
            "valid":   PALETTE["SUCCESS"],
            "warn":    PALETTE["WARNING"],
            "invalid": PALETTE["DANGER"],
        }
        for slot_idx, state, msg, path in results:
            for idx, slot, lbl in self._val_labels:
                if idx == slot_idx:
                    lbl.configure(text=msg, fg=colour_map.get(state, PALETTE["TEXT"]))
                    slot.set_validation(state, msg)
                    break

        can_proceed = valid_count >= MIN_VALID
        if can_proceed:
            self._val_summary_var.set(
                f"✓  {valid_count} valid photo(s) — ready to test recognition."
            )
            self._next_btn3.configure(state=tk.NORMAL)
            # Stage valid photos to temp dir
            self._stage_photos(results)
        else:
            self._val_summary_var.set(
                f"✗  Only {valid_count} valid photo(s). Need at least {MIN_VALID}. "
                "Go back and retake the invalid photos."
            )

    def _stage_photos(self, results):
        """Copy valid/warn photos to temp dir for recognition test."""
        os.makedirs(self._temp_dir, exist_ok=True)
        # Clear existing
        for f in os.listdir(self._temp_dir):
            try:
                os.remove(os.path.join(self._temp_dir, f))
            except Exception:
                pass
        count = 0
        for _, state, _, path in results:
            if state in ("valid", "warn") and path:
                dest = os.path.join(self._temp_dir,
                                     f"{self._user['full_name']}_{count:04d}.jpg")
                shutil.copy2(path, dest)
                count += 1
        logger.info("Staged %d photos to %s", count, self._temp_dir)

    # ------------------------------------------------------------------
    # Step 4 — Recognition test
    # ------------------------------------------------------------------

    def _build_step4(self):
        c = self._container
        self._progress_bar(c)

        tk.Label(c, text="Recognition Test",
                 font=FONTS["HEADING"],
                 bg=PALETTE["BG"], fg=PALETTE["WHITE"]).pack(anchor="w", pady=(0, 4))
        tk.Label(c,
                 text="Let's verify the system can recognise you before saving.",
                 font=FONTS["BODY"],
                 bg=PALETTE["BG"], fg=PALETTE["SUBTEXT"]).pack(anchor="w", pady=(0, 16))

        body = tk.Frame(c, bg=PALETTE["BG"])
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # Camera feed
        left = tk.Frame(body, bg=PALETTE["BG"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        self._test_placeholder = ImageTk.PhotoImage(Image.new("RGB", (400, 300), PALETTE["PANEL"]))
        self._test_feed = tk.Label(left, image=self._test_placeholder, bg=PALETTE["PANEL"])
        self._test_feed.imgtk = self._test_placeholder
        self._test_feed.pack(expand=True)

        # Controls
        right = tk.Frame(body, bg=PALETTE["BG"])
        right.grid(row=0, column=1, sticky="nsew")

        self._test_status_var = tk.StringVar(
            value="Click 'Run Test' to load your photos and test recognition."
        )
        tk.Label(right, textvariable=self._test_status_var,
                 font=FONTS["BODY"],
                 bg=PALETTE["BG"], fg=PALETTE["TEXT"],
                 wraplength=240, justify="left").pack(anchor="w", pady=(0, 16))

        self._test_result_var = tk.StringVar(value="")
        self._test_result_lbl = tk.Label(
            right, textvariable=self._test_result_var,
            font=("Segoe UI", 16, "bold"),
            bg=PALETTE["BG"], fg=PALETTE["SUCCESS"],
            wraplength=240, justify="left"
        )
        self._test_result_lbl.pack(anchor="w", pady=(0, 16))

        ttk.Button(right, text="▶  Run Test",
                   style="Success.TButton",
                   command=self._run_recognition_test).pack(anchor="w", pady=(0, 8))
        ttk.Button(right, text="↩ Retake Photos",
                   style="Ghost.TButton",
                   command=self._go_back_to_photos).pack(anchor="w")

        nav = tk.Frame(c, bg=PALETTE["BG"])
        nav.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(nav, text="← Back",
                   style="Ghost.TButton",
                   command=lambda: self._show_step(3)).pack(side=tk.LEFT)
        self._confirm_btn = ttk.Button(
            nav, text="✓  Confirm & Enroll",
            style="Primary.TButton",
            command=self._confirm_enrollment,
            state=tk.DISABLED
        )
        self._confirm_btn.pack(side=tk.RIGHT)

        # Start live test feed
        self._test_camera_running = False
        self._test_recognizer = None

    def _run_recognition_test(self):
        if self._test_camera_running:
            return
        self._test_status_var.set("Loading face database…")
        self._test_result_var.set("")
        overlay = LoadingOverlay(self._root, "Preparing recognition test…")

        def _load():
            try:
                from core.face_detector import FaceDetector
                from core.face_encoder  import FaceEncoder
                from core.recognizer    import Recognizer

                # Organize staged photos into person-named subdirectory
                # so the encoder can load them correctly.
                # _temp_dir contains files like "{name}_0000.jpg" directly.
                # We need: _temp_dir/{name}/image.jpg
                person_dir = os.path.join(self._temp_dir, self._user["full_name"])
                os.makedirs(person_dir, exist_ok=True)
                for f in os.listdir(self._temp_dir):
                    fpath = os.path.join(self._temp_dir, f)
                    if os.path.isfile(fpath) and f.lower().endswith((".jpg", ".jpeg", ".png")):
                        shutil.move(fpath, os.path.join(person_dir, f))

                det  = FaceDetector(model="haar")
                enc  = FaceEncoder(engine=self._config.recognition_engine,
                                   tolerance=self._config.tolerance)

                # Load ONLY the staged photos (not existing enrolled faces)
                enc.load_known_faces(self._temp_dir)

                rec = Recognizer(det, enc)
                source = (self._config.stream_url
                          if self._config.stream_url
                          else self._config.camera_index)
                opened = rec.start_camera(source)

                self._root.after(0, overlay.close)
                if not opened:
                    self._root.after(0, lambda: Toast(
                        self._root, "Cannot open camera.", "error"
                    ))
                    return

                self._test_recognizer = rec
                self._test_camera_running = True
                threading.Thread(
                    target=self._test_feed_loop, daemon=True
                ).start()
                self._root.after(0, lambda: self._test_status_var.set(
                    "Camera running — look at the camera."
                ))
            except Exception as e:
                logger.exception("Test load error")
                self._root.after(0, overlay.close)
                self._root.after(0, lambda: Toast(self._root, str(e), "error"))

        threading.Thread(target=_load, daemon=True).start()

    def _test_feed_loop(self):
        scale = self._config.frame_scale
        match_frames = 0
        total_frames  = 0

        while self._test_camera_running and self._test_recognizer:
            ret, frame = self._test_recognizer.read_frame()
            if not ret or frame is None:
                time.sleep(0.02)
                continue

            total_frames += 1
            locs, names, dists = self._test_recognizer.process_frame(frame, scale)

            for (t, r, b, l), name, dist in zip(locs, names, dists):
                t2, r2, b2, l2 = [int(v/scale) for v in (t, r, b, l)]
                is_match = (name == self._user["full_name"])
                colour   = (0, 200, 100) if is_match else (40, 100, 220)
                cv2.rectangle(frame, (l2, t2), (r2, b2), colour, 2)
                conf_str = f"{dist:.2f}" if dist else "?"
                label = f"{name}  {conf_str}" if name != "Unknown" else "Unknown"
                cv2.putText(frame, label, (l2+4, t2-8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                            (255, 255, 255), 1)
                if is_match:
                    match_frames += 1

            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img   = Image.fromarray(rgb).resize((400, 300), Image.LANCZOS)
            imgtk = ImageTk.PhotoImage(image=img)
            try:
                self._root.after(0, lambda i=imgtk: self._update_test_feed(i))
            except Exception:
                break

            # After 60 frames (~3s), show result
            if total_frames >= 60:
                self._test_camera_running = False
                confidence = match_frames / total_frames
                self._root.after(0, lambda c=confidence: self._show_test_result(c))
                break

            time.sleep(0.05)

    def _update_test_feed(self, imgtk):
        try:
            self._test_feed.imgtk = imgtk
            self._test_feed.configure(image=imgtk)
        except tk.TclError:
            pass

    def _show_test_result(self, confidence: float):
        if self._test_recognizer:
            self._test_recognizer.stop_camera()
            self._test_recognizer = None
        self._test_feed.configure(image=self._test_placeholder)
        pct = confidence * 100
        if pct >= 40:
            self._test_result_var.set(
                f"✅  Recognised as:\n{self._user['full_name']}\n\n"
                f"Match rate: {pct:.0f}%"
            )
            self._test_result_lbl.configure(fg=PALETTE["SUCCESS"])
            self._confirm_btn.configure(state=tk.NORMAL)
            self._test_status_var.set("Recognition successful! Click Confirm to save.")
        else:
            self._test_result_var.set(
                f"❌  Not recognised\n\nMatch rate: {pct:.0f}%\n"
                "Try retaking in better lighting."
            )
            self._test_result_lbl.configure(fg=PALETTE["DANGER"])
            self._test_status_var.set("Try retaking photos with better lighting.")

    def _go_back_to_photos(self):
        self._test_camera_running = False
        if self._test_recognizer:
            try:
                self._test_recognizer.stop_camera()
            except Exception:
                pass
            self._test_recognizer = None
        self._show_step(2)

    # ------------------------------------------------------------------
    # Step 5 — Confirm & success
    # ------------------------------------------------------------------

    def _confirm_enrollment(self):
        self._test_camera_running = False
        if self._test_recognizer:
            try:
                self._test_recognizer.stop_camera()
            except Exception:
                pass

        overlay = LoadingOverlay(self._root, "Saving enrollment…")

        def _save():
            try:
                # Move temp photos to final known_faces directory
                if os.path.exists(self._final_dir):
                    shutil.rmtree(self._final_dir)
                shutil.copytree(self._temp_dir, self._final_dir)

                # Clean up temp dir
                shutil.rmtree(self._temp_dir, ignore_errors=True)

                # Mark enrolled in DB
                self._db.set_face_enrolled(self._user["id"], True)

                self._root.after(0, overlay.close)
                self._root.after(0, lambda: self._show_step(5))
            except Exception as e:
                logger.exception("Save enrollment error")
                self._root.after(0, overlay.close)
                self._root.after(0, lambda: Toast(self._root, str(e), "error"))

        threading.Thread(target=_save, daemon=True).start()

    # ------------------------------------------------------------------
    # Step 5 — Success
    # ------------------------------------------------------------------

    def _build_step5(self):
        c = self._container
        self._progress_bar(c)

        # Confetti canvas
        canvas = tk.Canvas(c, width=500, height=180,
                            bg=PALETTE["BG"], highlightthickness=0)
        canvas.pack()
        self._confetti_canvas = canvas
        self._confetti_particles: list[dict] = []
        self._init_confetti()
        self._animate_confetti()

        tk.Label(c, text="🎉  Enrollment Complete!",
                 font=("Segoe UI", 26, "bold"),
                 bg=PALETTE["BG"], fg=PALETTE["SUCCESS"]).pack(pady=(8, 4))

        tk.Label(c,
                 text=f"Welcome, {self._user['full_name']}.\n"
                      "Your face has been registered successfully.\n"
                      "You'll be recognised automatically in class.",
                 font=FONTS["BODY"],
                 bg=PALETTE["BG"], fg=PALETTE["TEXT"],
                 justify="center").pack(pady=(0, 28))

        ttk.Button(c, text="Go to Dashboard  →",
                   style="Primary.TButton",
                   command=self._go_to_dashboard,
                   width=24).pack(ipady=4)

    def _init_confetti(self):
        import random
        colours = [PALETTE["ACCENT"], PALETTE["SUCCESS"],
                   PALETTE["INFO"], PALETTE["WARNING"], "#ffffff"]
        self._confetti_particles = []
        for _ in range(60):
            self._confetti_particles.append({
                "x":  random.uniform(20, 480),
                "y":  random.uniform(-20, 160),
                "vx": random.uniform(-1.5, 1.5),
                "vy": random.uniform(1.2, 3.5),
                "colour": random.choice(colours),
                "size": random.randint(4, 9),
                "id": None,
            })

    def _animate_confetti(self):
        if not hasattr(self, "_confetti_canvas"):
            return
        try:
            cv = self._confetti_canvas
            for p in self._confetti_particles:
                if p["id"]:
                    cv.delete(p["id"])
                p["y"] += p["vy"]
                p["x"] += p["vx"]
                if p["y"] > 180:
                    p["y"] = -10
                s = p["size"]
                p["id"] = cv.create_oval(
                    p["x"], p["y"],
                    p["x"] + s, p["y"] + s,
                    fill=p["colour"], outline=""
                )
            self._root.after(40, self._animate_confetti)
        except tk.TclError:
            pass

    def _go_to_dashboard(self):
        # Refresh student dashboard — force parent to reload home panel
        parent = self.master
        if hasattr(parent, "_switch_panel"):
            parent._switch_panel("home")

    def shutdown(self):
        self._stop_capture_camera()
        self._test_camera_running = False
        if self._test_recognizer:
            try:
                self._test_recognizer.stop_camera()
            except Exception:
                pass
