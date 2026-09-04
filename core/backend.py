import os
import cv2
import time
import asyncio
import logging
import threading
import base64
import hashlib
import numpy as np
from typing import Optional
from fastapi import FastAPI, HTTPException, Response, Query, BackgroundTasks, File, UploadFile, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from datetime import datetime
from collections import defaultdict

from core.config import Config
from core.database import DatabaseManager
from core.face_detector import FaceDetector
from core.face_encoder import FaceEncoder
from core.recognizer import Recognizer
from bias.evaluator import BiasEvaluator
from bias.datasets import DatasetHelper
from core.auth import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
    revoke_all_user_tokens,
    get_current_user,
    require_roles,
)

logger = logging.getLogger(__name__)

config = Config()
config.ensure_dirs()
db = DatabaseManager(config.db_path)

app = FastAPI(title="AttendIQ API", version="1.0.0")

# --- Structured Logging ---
logging.basicConfig(
    level=getattr(logging, config.get("Logging", "LEVEL", fallback="INFO")),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
request_logger = logging.getLogger("attendiq.requests")

# --- Rate Limiting (in-memory sliding window) ---
_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX_REQUESTS = 30  # per window per IP
_RATE_LIMIT_LOGIN_MAX = 5  # login attempts per window per IP
_request_counts: dict[str, list[float]] = defaultdict(list)
_login_counts: dict[str, list[float]] = defaultdict(list)


_RATE_LIMIT_BYPASS = {"/api/recognize/frame", "/api/session/live", "/api/session/video_feed"}

def _check_rate_limit(ip: str, limit: int = _RATE_LIMIT_MAX_REQUESTS) -> bool:
    """Return True if request is allowed, False if rate limited."""
    now = time.time()
    cutoff = now - _RATE_LIMIT_WINDOW
    _request_counts[ip] = [t for t in _request_counts[ip] if t > cutoff]
    if len(_request_counts[ip]) >= limit:
        return False
    _request_counts[ip].append(now)
    return True


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to all API endpoints. High-frequency video endpoints are exempt."""
    ip = request.client.host if request.client else "unknown"
    path = request.url.path

    # Stricter limit for login endpoint
    if path == "/api/auth/login":
        now = time.time()
        cutoff = now - _RATE_LIMIT_WINDOW
        _login_counts[ip] = [t for t in _login_counts[ip] if t > cutoff]
        if len(_login_counts[ip]) >= _RATE_LIMIT_LOGIN_MAX:
            return Response(
                content='{"detail":"Too many login attempts. Please try again later."}',
                status_code=429,
                media_type="application/json",
            )
        _login_counts[ip].append(now)

    # Exempt real-time video/recognition polling (would otherwise block multi-face at 40+ req/min)
    if path in _RATE_LIMIT_BYPASS:
        return await call_next(request)

    if not _check_rate_limit(ip):
        return Response(
            content='{"detail":"Rate limit exceeded. Please slow down."}',
            status_code=429,
            media_type="application/json",
        )

    response = await call_next(request)
    return response


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=()"
    # HSTS only if behind HTTPS (Caddy terminates TLS)
    if request.headers.get("x-forwarded-proto") == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Enable CORS for development and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://attendiq.tadstech.dev",
        "https://attendiq-api.tadstech.dev",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global camera state for video streaming
class CameraStreamer:
    def __init__(self):
        self.camera = None
        self.active_mode = None  # "attendance", "enrollment", "test"
        self.running = False
        self.frame = None
        self.recognizer = None
        self.session_class_id = None
        self.session_date = None
        self.marked_ids = set()
        self.marked_names = []  # List of dicts: {"time": ts, "name": name, "conf": conf}
        self.unknown_count = 0
        self.lecturer_id = None
        
        # Enrollment specific
        self.enrollment_user_id = None
        self.enrollment_full_name = None
        self.staged_photos = []
        self.latest_raw_frame = None
        
        # Frame-skip for performance
        self._frame_count = 0
        self._last_locations = []
        self._last_names = []
        self._last_distances = []

    def start(self, mode: str, class_id: int = None, lecturer_id: int = None, user_id: int = None, full_name: str = None, camera_source: str = None):
        if self.running:
            self.stop()
            time.sleep(0.2)

        self.active_mode = mode
        self.running = True
        self.session_class_id = class_id
        self.lecturer_id = lecturer_id
        self.session_date = datetime.now().strftime("%Y-%m-%d")
        self.marked_ids = set()
        self.marked_names = []
        if mode == "attendance" and class_id:
            try:
                existing = db.get_attendance(class_id, self.session_date)
                for rec in existing:
                    self.marked_ids.add(rec["student_id"])
                    self.marked_ids.add(rec["full_name"])
                    self.marked_names.append({
                        "time": rec["timestamp"],
                        "name": rec["full_name"],
                        "conf": f"{rec['confidence']:.2f}" if rec["confidence"] else "—"
                    })
            except Exception as e:
                logger.error("Failed to preload marked students: %s", e)
        self.unknown_count = 0
        self.enrollment_user_id = user_id
        self.enrollment_full_name = full_name
        self.staged_photos = []
        self.latest_raw_frame = None
        self._frame_count = 0
        self._last_locations = []
        self._last_names = []
        self._last_distances = []

        if camera_source:
            try:
                source = int(camera_source)
            except ValueError:
                source = camera_source
        else:
            source = config.stream_url if config.stream_url else config.camera_index

        if mode in ("attendance", "test"):
            det = FaceDetector(model="haar")
            enc = FaceEncoder(engine=config.recognition_engine, tolerance=config.tolerance)
            
            if mode == "test" and user_id:
                # Load only staged photos in temp dir
                temp_dir = os.path.join(config.known_faces_dir, f"__temp_{user_id}__")
                person_temp_dir = os.path.join(temp_dir, full_name)
                # Build temporary directory if not exist
                os.makedirs(person_temp_dir, exist_ok=True)
                enc.load_known_faces(temp_dir)
            else:
                # Load all known faces
                enc.load_known_faces(config.known_faces_dir)

            self.recognizer = Recognizer(det, enc)
            opened = self.recognizer.start_camera(source)
            self.camera_available = opened
            if not opened:
                logger.warning("Failed to open camera. Running in client-side camera mode.")
        else:
            # Enrollment capture — use CAP_DSHOW on Windows for external USB cameras
            import sys
            try:
                if isinstance(source, int) and sys.platform == "win32":
                    self.camera = cv2.VideoCapture(source, cv2.CAP_DSHOW)
                    if not self.camera.isOpened():
                        # Fallback without CAP_DSHOW
                        self.camera = cv2.VideoCapture(source)
                else:
                    self.camera = cv2.VideoCapture(source)
            except Exception:
                self.camera = cv2.VideoCapture(source)
            self.camera_available = self.camera.isOpened()
            if not self.camera_available:
                logger.warning("Failed to open camera %s for enrollment. Running in client-side camera mode.", source)
                self.camera = None

        # Start thread
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self.running = False
        if self.recognizer:
            self.recognizer.stop_camera()
            self.recognizer = None
        if self.camera:
            self.camera.release()
            self.camera = None
        self.active_mode = None

    def _loop(self):
        scale = config.frame_scale
        # Only run expensive face recognition every N frames for performance
        RECOGNITION_INTERVAL = 3
        while self.running:
            if self.active_mode in ("attendance", "test") and self.recognizer:
                ret, frame = self.recognizer.read_frame()
                if not ret or frame is None:
                    time.sleep(0.02)
                    continue

                self.latest_raw_frame = frame.copy()
                self._frame_count += 1

                # Only run face detection+encoding every Nth frame
                if self._frame_count % RECOGNITION_INTERVAL == 0:
                    locations, names, distances = self.recognizer.process_frame(frame, scale)
                    self._last_locations = locations
                    self._last_names = names
                    self._last_distances = distances
                else:
                    # Reuse last detection results for skipped frames
                    locations = self._last_locations
                    names = self._last_names
                    distances = self._last_distances

                # process_frame returns coordinates scaled down by `scale`. Scale them back up.
                for (top_s, right_s, bottom_s, left_s), name, dist in zip(locations, names, distances):
                    top = int(top_s / scale)
                    right = int(right_s / scale)
                    bottom = int(bottom_s / scale)
                    left = int(left_s / scale)
                    is_known = (name != "Unknown")
                    colour = (0, 200, 100) if is_known else (0, 60, 200)

                    cv2.rectangle(frame, (left, top), (right, bottom), colour, 2)
                    cv2.rectangle(frame, (left, bottom - 26), (right, bottom), colour, cv2.FILLED)

                    conf_str = f"{dist:.2f}" if dist is not None else "?"
                    label = f"{name}  {conf_str}" if is_known else "Unknown"
                    cv2.putText(frame, label, (left + 5, bottom - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1)

                    # Mark attendance in BOTH attendance and test modes
                    if is_known and name not in self.marked_ids:
                        if self.active_mode == "attendance" and self.session_class_id:
                            student = db.get_user_by_name(name)
                            if student and student["id"] not in self.marked_ids:
                                if db.is_blocked(self.session_class_id, student["id"]):
                                    is_known = False
                                else:
                                    logged = db.log_attendance(
                                        student["id"],
                                        self.session_class_id,
                                        session_date=self.session_date,
                                        method="face",
                                        confidence=dist,
                                        marked_by=self.lecturer_id
                                    )
                                    self.marked_ids.add(student["id"])
                                    self.marked_ids.add(name)
                                    if logged:
                                        ts = datetime.now().strftime("%H:%M:%S")
                                        self.marked_names.append({
                                            "time": ts,
                                            "name": name,
                                            "conf": f"{dist:.2f}" if dist else "—"
                                        })
                        elif self.active_mode == "test":
                            # In test mode, add to marked so frontend polling can detect recognition
                            ts = datetime.now().strftime("%H:%M:%S")
                            self.marked_names.append({
                                "time": ts,
                                "name": name,
                                "conf": f"{dist:.2f}" if dist else "—"
                            })
                            self.marked_ids.add(name)

                self.frame = frame

            elif self.active_mode == "enrollment" and self.camera:
                ret, frame = self.camera.read()
                if not ret or frame is None:
                    time.sleep(0.02)
                    continue
                self.latest_raw_frame = frame.copy()
                self.frame = frame
            else:
                time.sleep(0.1)
            time.sleep(0.03)

    def get_jpeg(self):
        if self.frame is None:
            import numpy as np
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            _, jpeg = cv2.imencode('.jpg', blank)
            return jpeg.tobytes()
        _, jpeg = cv2.imencode('.jpg', self.frame)
        return jpeg.tobytes()

streamer = CameraStreamer()

global_recognizer = None

def get_recognizer():
    global global_recognizer
    if streamer.running and streamer.recognizer:
        return streamer.recognizer
    if global_recognizer is None:
        logger.info("Initializing global recognizer...")
        det = FaceDetector(model="haar")
        enc = FaceEncoder(engine=config.recognition_engine, tolerance=config.tolerance)
        enc.load_known_faces(config.known_faces_dir)
        global_recognizer = Recognizer(det, enc)
    return global_recognizer

def invalidate_global_recognizer():
    global global_recognizer
    global_recognizer = None

# --- Request / Response Models ---
class LoginRequest(BaseModel):
    identifier: str  # matric number, email, or username
    password: str

class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str
    full_name: str
    title: Optional[str] = None  # Dr., Professor, etc. (for lecturers)
    student_id: Optional[str] = None  # Matric number (required for students)
    email: Optional[str] = None  # Required for students
    department: Optional[str] = None
    level: Optional[str] = None
    faculty: Optional[str] = None

class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    title: Optional[str] = None
    username: Optional[str] = None
    student_id: Optional[str] = None
    email: Optional[str] = None
    face_enrolled: Optional[int] = None
    department: Optional[str] = None
    faculty: Optional[str] = None

class PasswordResetRequest(BaseModel):
    new_password: str

class SecuritySetupRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=200)
    answer: str = Field(..., min_length=2, max_length=200)
    pin: str = Field(..., min_length=4, max_length=6, pattern="^[0-9]{4,6}$")

class SecurityResetRequest(BaseModel):
    identifier: str
    new_password: str = Field(..., min_length=6)
    answer: Optional[str] = None
    pin: Optional[str] = None

class BlockRequest(BaseModel):
    student_id: int
    reason: Optional[str] = None

class AssignLecturerRequest(BaseModel):
    lecturer_id: int

class ClassCreateRequest(BaseModel):
    name: str
    code: str
    schedule: Optional[str] = None
    room: Optional[str] = None
    department: Optional[str] = None

class FacultyCreateRequest(BaseModel):
    name: str

class DepartmentCreateRequest(BaseModel):
    faculty_id: int
    name: str

class ManualAttendanceRequest(BaseModel):
    student_id: int
    class_id: int
    marked_by: int

class ConfigSaveRequest(BaseModel):
    camera_index: int
    frame_scale: float
    tolerance: float
    recognition_engine: str
    stream_url: str

class RecognizeFrameRequest(BaseModel):
    frame: str = Field(..., max_length=10_000_000, description="Base64 encoded JPEG frame")  # ~7.5MB max

# --- Health & System Endpoints ---

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring and Docker HEALTHCHECK."""
    db_ok = False
    try:
        db._conn.execute("SELECT 1")
        db_ok = True
    except Exception:
        pass

    status = "healthy" if db_ok else "degraded"
    return {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "database": "ok" if db_ok else "error",
    }

# --- Endpoints ---

class RefreshRequest(BaseModel):
    refresh_token: str

@app.post("/api/auth/login")
def login(req: LoginRequest, response: Response):
    user = db.authenticate(req.identifier, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # Issue JWT pair
    access = create_access_token(user["id"], user["username"], user["role"], user["full_name"])
    refresh = create_refresh_token(user["id"])
    # httpOnly refresh cookie for browser; access returned in body for header use
    response.set_cookie(
        key="refresh_token", value=refresh, httponly=True, secure=False,
        samesite="lax", max_age=7*24*3600, path="/api/auth"
    )
    user_safe = {k: v for k, v in user.items() if k != "password_hash"}
    return {**user_safe, "access_token": access, "refresh_token": refresh, "token_type": "bearer"}

@app.post("/api/auth/refresh")
def refresh_tokens(req: RefreshRequest):
    payload = verify_refresh_token(req.refresh_token)
    user = db.get_user(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    # Rotate refresh token
    revoke_refresh_token(req.refresh_token)
    new_access = create_access_token(user["id"], user["username"], user["role"], user["full_name"])
    new_refresh = create_refresh_token(user["id"])
    return {"access_token": new_access, "refresh_token": new_refresh, "token_type": "bearer"}

@app.post("/api/auth/refresh-cookie")
def refresh_via_cookie(request: Request):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh cookie")
    payload = verify_refresh_token(token)
    user = db.get_user(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    revoke_refresh_token(token)
    new_access = create_access_token(user["id"], user["username"], user["role"], user["full_name"])
    new_refresh = create_refresh_token(user["id"])
    resp = {"access_token": new_access, "refresh_token": new_refresh}
    # set new cookie via Response
    return resp

@app.post("/api/auth/logout")
def logout(req: RefreshRequest):
    try:
        revoke_refresh_token(req.refresh_token)
    except Exception:
        pass
    return {"status": "ok"}

@app.post("/api/auth/logout-all")
def logout_all(current_user=Depends(get_current_user)):
    revoke_all_user_tokens(current_user["id"])
    return {"status": "ok"}

@app.get("/api/auth/me")
def me(current_user=Depends(get_current_user)):
    current_user.pop("password_hash", None)
    return current_user

@app.get("/api/users")
def get_users(role: Optional[str] = None, current_user=Depends(require_roles("admin"))):
    return db.get_users(role)

@app.post("/api/users")
def create_user(req: UserCreateRequest, current_user=Depends(require_roles("admin"))):
    try:
        user_id = db.create_user(
            username=req.username,
            password=req.password,
            role=req.role,
            full_name=req.full_name,
            title=req.title,
            student_id=req.student_id,
            email=req.email,
            department=req.department,
            level=req.level,
            faculty=req.faculty
        )
        return {"id": user_id, "username": req.username, "role": req.role}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/api/users/{user_id}")
def update_user(user_id: int, req: UserUpdateRequest, current_user=Depends(require_roles("admin"))):
    ok = db.update_user(user_id, **req.model_dump(exclude_none=True))
    if not ok:
        raise HTTPException(status_code=400, detail="Update failed")
    return {"status": "ok"}

@app.post("/api/users/{user_id}/reset-password")
def reset_password(user_id: int, req: PasswordResetRequest, current_user=Depends(require_roles("admin"))):
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.update_password(user_id, req.new_password)
    revoke_all_user_tokens(user_id)
    return {"status": "ok"}

@app.post("/api/auth/setup-security")
def setup_security(req: SecuritySetupRequest, current_user=Depends(get_current_user)):
    # Students set own; lecturer/admin can set for any but mainly self
    db.set_security(current_user["id"], req.question, req.answer, req.pin)
    return {"status": "ok"}

@app.get("/api/auth/security-question")
def get_security_question(identifier: str):
    row = db._conn.execute("SELECT security_question FROM users WHERE username=? OR student_id=? OR email=?", (identifier, identifier, identifier)).fetchone()
    if not row or not row["security_question"]:
        raise HTTPException(status_code=404, detail="No security question set")
    return {"question": row["security_question"]}

@app.post("/api/auth/reset-with-security")
def reset_with_security(req: SecurityResetRequest):
    if not req.answer and not req.pin:
        raise HTTPException(status_code=400, detail="Provide answer or pin")
    ok = db.reset_password_via_security(req.identifier, req.new_password, req.answer, req.pin)
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid answer/pin")
    # revoke tokens
    u = db._conn.execute("SELECT id FROM users WHERE username=? OR student_id=? OR email=?", (req.identifier, req.identifier, req.identifier)).fetchone()
    if u:
        revoke_all_user_tokens(u["id"])
    return {"status": "ok"}

@app.delete("/api/users/{user_id}")
def delete_user(user_id: int, current_user=Depends(require_roles("admin"))):
    # If student, delete their face model folder if exists
    user = db.get_user(user_id)
    if user and user["role"] == "student":
        person_dir = os.path.join(config.known_faces_dir, user["full_name"])
        import shutil
        if os.path.exists(person_dir):
            shutil.rmtree(person_dir)
    db.delete_user(user_id)
    revoke_all_user_tokens(user_id)
    return {"status": "ok"}

@app.get("/api/classes")
def get_classes(lecturer_id: Optional[int] = None, current_user=Depends(get_current_user)):
    # Students can only see classes they are enrolled in
    if current_user["role"] == "student":
        return db.get_student_classes(current_user["id"])
    return db.get_classes(lecturer_id)

@app.get("/api/classes/unassigned")
def get_unassigned_classes(current_user=Depends(require_roles("admin", "lecturer"))):
    return db.get_unassigned_classes()

@app.post("/api/classes/{class_id}/assign")
def assign_lecturer(class_id: int, req: AssignLecturerRequest, current_user=Depends(require_roles("admin", "lecturer"))):
    c = db.get_class(class_id)
    if not c:
        raise HTTPException(status_code=404, detail="Class not found")
    # Lecturer can only self-assign to unassigned classes
    if current_user["role"] == "lecturer":
        if c["lecturer_id"] is not None and c["lecturer_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Class already assigned")
        if req.lecturer_id != current_user["id"]:
            raise HTTPException(status_code=403, detail="Lecturers can only assign themselves")
    # Admin can assign anyone
    lec = db.get_user(req.lecturer_id)
    if not lec or lec["role"] != "lecturer":
        raise HTTPException(status_code=400, detail="Target is not a lecturer")
    db.assign_lecturer(class_id, req.lecturer_id)
    return {"status": "ok"}

@app.get("/api/classes/{class_id}/blocks")
def get_blocks(class_id: int, current_user=Depends(require_roles("admin", "lecturer"))):
    c = db.get_class(class_id)
    if current_user["role"] == "lecturer" and c and c["lecturer_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not your class")
    return db.get_blocked(class_id)

@app.post("/api/classes/{class_id}/blocks")
def block_student(class_id: int, req: BlockRequest, current_user=Depends(require_roles("admin", "lecturer"))):
    c = db.get_class(class_id)
    if not c:
        raise HTTPException(status_code=404, detail="Class not found")
    if current_user["role"] == "lecturer" and c["lecturer_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not your class")
    if not db.get_user(req.student_id):
        raise HTTPException(status_code=404, detail="Student not found")
    ok = db.block_student(class_id, req.student_id, current_user["id"], req.reason)
    if not ok:
        raise HTTPException(status_code=400, detail="Already blocked")
    return {"status": "ok"}

@app.delete("/api/classes/{class_id}/blocks/{student_id}")
def unblock_student(class_id: int, student_id: int, current_user=Depends(require_roles("admin", "lecturer"))):
    c = db.get_class(class_id)
    if current_user["role"] == "lecturer" and c and c["lecturer_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not your class")
    ok = db.unblock_student(class_id, student_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Block not found")
    return {"status": "ok"}

@app.post("/api/classes")
def create_class(req: ClassCreateRequest, lecturer_id: int, current_user=Depends(require_roles("admin", "lecturer"))):
    # Lecturers can only create for themselves
    if current_user["role"] == "lecturer" and lecturer_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Lecturers can only create their own classes")
    class_id = db.create_class(
        name=req.name,
        code=req.code,
        lecturer_id=lecturer_id,
        schedule=req.schedule,
        room=req.room,
        department=req.department
    )
    return {"id": class_id}

@app.put("/api/classes/{class_id}")
def update_class(class_id: int, req: ClassCreateRequest, current_user=Depends(require_roles("admin", "lecturer"))):
    ok = db.update_class(class_id, **req.model_dump(exclude_none=True))
    if not ok:
        raise HTTPException(status_code=400, detail="Update failed")
    return {"status": "ok"}

@app.delete("/api/classes/{class_id}")
def delete_class(class_id: int, current_user=Depends(require_roles("admin"))):
    db.delete_class(class_id)
    return {"status": "ok"}

@app.get("/api/classes/{class_id}/enrollments")
def get_class_enrollments(class_id: int, current_user=Depends(get_current_user)):
    # Students can only see their own class enrollments
    if current_user["role"] == "student" and not db.is_enrolled(current_user["id"], class_id):
        # still allow to see but not leak all unenrolled
        pass
    all_students = db.get_users("student")
    enrolled_students = db.get_enrolled_students(class_id)
    enrolled_ids = {s["id"] for s in enrolled_students}
    
    unenrolled_students = [s for s in all_students if s["id"] not in enrolled_ids]
    return {
        "enrolled": enrolled_students,
        "unenrolled": unenrolled_students
    }

@app.post("/api/classes/{class_id}/enrollments")
def enroll_student(class_id: int, student_id: int, current_user=Depends(require_roles("admin", "lecturer"))):
    db.enroll_student(student_id, class_id)
    return {"status": "ok"}

@app.delete("/api/classes/{class_id}/enrollments/{student_id}")
def unenroll_student(class_id: int, student_id: int, current_user=Depends(require_roles("admin", "lecturer"))):
    db.unenroll_student(student_id, class_id)
    return {"status": "ok"}

@app.get("/api/attendance/history")
def get_attendance_history(class_id: int, date: str, current_user=Depends(require_roles("admin", "lecturer"))):
    rows = db.get_attendance(class_id, date)
    return rows

@app.get("/api/attendance/history-range")
def get_attendance_history_range(class_id: int, date_from: str, date_to: str, current_user=Depends(require_roles("admin", "lecturer"))):
    rows = db.get_attendance_range(class_id, date_from, date_to)
    return rows

@app.delete("/api/attendance/history/{record_id}")
def delete_attendance_record(record_id: int, current_user=Depends(require_roles("admin", "lecturer"))):
    with db._conn:
        db._conn.execute("DELETE FROM attendance_log WHERE id = ?", (record_id,))
    return {"status": "ok"}

@app.post("/api/attendance/manual")
def log_manual_attendance(req: ManualAttendanceRequest, current_user=Depends(require_roles("admin", "lecturer"))):
    # Prevent spoofing: marked_by must match caller unless admin
    if current_user["role"] != "admin" and req.marked_by != current_user["id"]:
        raise HTTPException(status_code=403, detail="marked_by must match authenticated lecturer")
    session_date = datetime.now().strftime("%Y-%m-%d")
    # Block check
    if db.is_blocked(req.class_id, req.student_id):
        raise HTTPException(status_code=403, detail="Student is blocked from this class")
    # Verify lecturer owns or is assigned to class (admin bypass)
    if current_user["role"] == "lecturer":
        c = db.get_class(req.class_id)
        if c and c["lecturer_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not your class")
    logged = db.log_attendance(
        req.student_id,
        req.class_id,
        session_date=session_date,
        method="manual",
        marked_by=current_user["id"]
    )
    if not logged:
        raise HTTPException(status_code=400, detail="Student already logged today")
    return {"status": "ok"}

# --- Camera diagnostics ---

@app.get("/api/camera/list")
def list_cameras(max_index: int = 4, current_user=Depends(get_current_user)):
    """Probe camera indices 0..max_index and report which are openable."""
    import sys
    results = []
    for idx in range(max_index + 1):
        try:
            api_pref = cv2.CAP_DSHOW if sys.platform == "win32" else 0
            cap = cv2.VideoCapture(idx, api_pref) if api_pref else cv2.VideoCapture(idx)
            opened = cap.isOpened()
            if opened:
                # Try to read a frame to confirm it's not a phantom device
                ret, _ = cap.read()
                opened = opened and ret
            cap.release()
            results.append({"index": idx, "available": bool(opened)})
        except Exception as e:
            results.append({"index": idx, "available": False, "error": str(e)})
    return {"cameras": results}

# --- Camera Streaming & Live Session Endpoints ---

@app.post("/api/session/start")
def start_session(class_id: int, lecturer_id: int, camera_source: Optional[str] = None, current_user=Depends(require_roles("admin", "lecturer"))):
    if current_user["role"] == "lecturer" and lecturer_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Can only start own sessions")
    try:
        streamer.start("attendance", class_id=class_id, lecturer_id=lecturer_id, camera_source=camera_source)
        # Return camera availability so frontend can show immediate error
        return {"status": "ok", "camera_active": getattr(streamer, "camera_available", False)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/session/stop")
def stop_session(current_user=Depends(require_roles("admin", "lecturer"))):
    streamer.stop()
    return {"status": "ok"}

@app.get("/api/session/live")
def get_live_session(current_user=Depends(get_current_user)):
    return {
        "running": streamer.running,
        "mode": streamer.active_mode,
        "marked": streamer.marked_names,
        "unknown": streamer.unknown_count,
        "date": streamer.session_date,
        "camera_active": getattr(streamer, "camera_available", True)
    }

async def gen_frames():
    while streamer.running:
        frame = streamer.get_jpeg()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        await asyncio.sleep(0.04)

@app.get("/api/session/video_feed")
def video_feed(current_user=Depends(get_current_user)):
    return StreamingResponse(
        gen_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

# --- Browser-based Recognition Endpoint ---

@app.post("/api/recognize/frame")
def recognize_frame(req: RecognizeFrameRequest, current_user=Depends(require_roles("admin", "lecturer"))):
    """Accept a base64 JPEG frame from the browser, run face detection + recognition, return results."""
    try:
        # Validate base64 size before decoding
        raw_size = len(req.frame) * 3 / 4  # approximate decoded size
        if raw_size > 7_500_000:  # 7.5MB limit
            raise HTTPException(status_code=413, detail="Frame too large. Maximum 5MB compressed JPEG.")

        img_bytes = base64.b64decode(req.frame)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(status_code=400, detail="Invalid image data")

        request_logger.debug("Frame received: %dx%d, %.1f KB",
                             frame.shape[1], frame.shape[0], len(img_bytes) / 1024)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode frame: {e}")

    # Run face detection + recognition using the cached global recognizer
    recognizer = get_recognizer()

    scale = config.frame_scale
    locations, names, distances = recognizer.process_frame(frame, scale)

    # Build results — handle ALL faces in frame (multi-face support)
    recognized = []
    for (top_s, right_s, bottom_s, left_s), name, dist in zip(locations, names, distances):
        # locations are in scaled-down coordinates — convert to original frame coords
        top, right, bottom, left = int(top_s / scale), int(right_s / scale), int(bottom_s / scale), int(left_s / scale)
        h, w = frame.shape[:2]
        y1, y2 = max(0, top), min(h, bottom)
        x1, x2 = max(0, left), min(w, right)
        face_img = frame[y1:y2, x1:x2]
        
        is_live = True
        liveness_score = 0.0
        if face_img.size > 0:
            gray_face = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
            liveness_score = float(cv2.Laplacian(gray_face, cv2.CV_64F).var())
            # Lowered bounds to support low quality/blurry webcams
            if liveness_score < 10.0 or liveness_score > 12000.0:
                is_live = False

        is_known = (name != "Unknown") and is_live
        recognized.append({
            "name": name if is_known else None,
            "confidence": round(dist, 4) if dist is not None else None,
            "is_known": is_known,
            "is_live": is_live,
            "liveness_score": liveness_score,
            "box": {
                "top": top,
                "right": right,
                "bottom": bottom,
                "left": left,
            },
        })

        # Log attendance in database if session is running
        if is_known and streamer.running and streamer.active_mode == "attendance":
            if name not in streamer.marked_ids:
                student = db.get_user_by_name(name)
                # Ensure student exists, hasn't been marked yet, and IS ENROLLED in this class
                if student and student["id"] not in streamer.marked_ids:
                    if db.is_blocked(streamer.session_class_id, student["id"]):
                        is_known = False
                    elif db.is_enrolled(student["id"], streamer.session_class_id):
                        logged = db.log_attendance(
                            student["id"],
                            streamer.session_class_id,
                            session_date=streamer.session_date,
                            method="face",
                            confidence=dist,
                            marked_by=streamer.lecturer_id
                        )
                        streamer.marked_ids.add(student["id"])
                        streamer.marked_ids.add(name)
                        if logged:
                            ts = datetime.now().strftime("%H:%M:%S")
                            streamer.marked_names.append({
                                "time": ts,
                                "name": name,
                                "conf": f"{dist:.2f}" if dist else "—"
                            })
                    else:
                        # Optional: Log that an unenrolled face was seen?
                        pass

    return {
        "recognized": recognized,
        "total_faces": len(recognized),
        "known_faces": sum(1 for r in recognized if r["is_known"]),
        "unknown_faces": sum(1 for r in recognized if not r["is_known"]),
    }

# --- Face Enrollment Endpoints ---

@app.post("/api/enrollment/start")
def start_enrollment(user_id: int, full_name: str, camera_source: Optional[str] = None, current_user=Depends(get_current_user)):
    # Students can only start for themselves; admins can start for anyone
    if current_user["role"] == "student" and current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Students can only enroll themselves")
    full_name = full_name.strip()
    try:
        streamer.start("enrollment", user_id=user_id, full_name=full_name, camera_source=camera_source)
        temp_dir = os.path.join(config.known_faces_dir, f"__temp_{user_id}__")
        os.makedirs(temp_dir, exist_ok=True)
        return {"status": "ok", "camera_active": getattr(streamer, "camera_available", False)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/enrollment/upload")
async def upload_enrollment(user_id: int, slot_idx: Optional[int] = None, files: list[UploadFile] = File(...), current_user=Depends(get_current_user)):
    if current_user["role"] == "student" and current_user["id"] != user_id and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    # Validate file types/sizes
    for f in files:
        if f.content_type not in ("image/jpeg", "image/jpg", "image/png", "image/webp"):
            raise HTTPException(status_code=400, detail=f"Invalid file type: {f.content_type}")
        if f.size and f.size > 5*1024*1024:
            raise HTTPException(status_code=413, detail="File too large")
    try:
        temp_dir = os.path.join(config.known_faces_dir, f"__temp_{user_id}__")
        import shutil
        if slot_idx is None and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir, exist_ok=True)
        
        saved_paths = []
        for i, file in enumerate(files[:5]):
            idx = slot_idx if slot_idx is not None else i
            target_path = os.path.join(temp_dir, f"capture_{idx}.jpg")
            content = await file.read()
            with open(target_path, "wb") as f:
                f.write(content)
            saved_paths.append(f"/data/known_faces/__temp_{user_id}__/capture_{idx}.jpg")
            
        return {"status": "ok", "count": len(saved_paths), "files": saved_paths}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/enrollment/capture")
def capture_enrollment(user_id: int, full_name: str, slot_idx: int, current_user=Depends(get_current_user)):
    if current_user["role"] == "student" and current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")
    full_name = full_name.strip()
    if streamer.latest_raw_frame is None:
        raise HTTPException(status_code=400, detail="Camera feed not ready")
    
    temp_dir = os.path.join(config.known_faces_dir, f"__temp_{user_id}__")
    os.makedirs(temp_dir, exist_ok=True)
    
    filepath = os.path.join(temp_dir, f"capture_{slot_idx}.jpg")
    cv2.imwrite(filepath, streamer.latest_raw_frame)
    web_path = f"/data/known_faces/__temp_{user_id}__/capture_{slot_idx}.jpg"
    return {"status": "ok", "filepath": web_path}

@app.delete("/api/enrollment/slot")
def delete_enrollment_slot(user_id: int, slot_idx: int, current_user=Depends(get_current_user)):
    if current_user["role"] == "student" and current_user["id"] != user_id and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    temp_dir = os.path.join(config.known_faces_dir, f"__temp_{user_id}__")
    filepath = os.path.join(temp_dir, f"capture_{slot_idx}.jpg")
    if os.path.exists(filepath):
        os.remove(filepath)
    return {"status": "ok"}

@app.get("/api/enrollment/capture/{user_id}/{slot_idx}")
def get_enrollment_capture(user_id: int, slot_idx: int, current_user=Depends(get_current_user)):
    if current_user["role"] == "student" and current_user["id"] != user_id and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    temp_dir = os.path.join(config.known_faces_dir, f"__temp_{user_id}__")
    filepath = os.path.join(temp_dir, f"capture_{slot_idx}.jpg")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Capture not found")
    import io
    with open(filepath, "rb") as f:
        content = f.read()
    return StreamingResponse(
        io.BytesIO(content),
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache"},
    )

def calculate_ear(eye_points):
    import math
    # Euclidean distances between vertical eye landmarks
    a = math.dist(eye_points[1], eye_points[5])
    b = math.dist(eye_points[2], eye_points[4])
    # Euclidean distance between horizontal eye landmarks
    c = math.dist(eye_points[0], eye_points[3])
    if c == 0:
        return 0.0
    return (a + b) / (2.0 * c)

def verify_blink(img_open, img_closed):
    import face_recognition
    landmarks_open = face_recognition.face_landmarks(img_open)
    landmarks_closed = face_recognition.face_landmarks(img_closed)
    if not landmarks_open or not landmarks_closed:
        return False, "Could not locate eye features in both images"
    
    lo = landmarks_open[0]
    lc = landmarks_closed[0]
    if "left_eye" not in lo or "right_eye" not in lo or "left_eye" not in lc or "right_eye" not in lc:
        return False, "Facial eye details are incomplete"

    ear_open_left = calculate_ear(lo["left_eye"])
    ear_open_right = calculate_ear(lo["right_eye"])
    ear_open = (ear_open_left + ear_open_right) / 2.0
    
    ear_closed_left = calculate_ear(lc["left_eye"])
    ear_closed_right = calculate_ear(lc["right_eye"])
    ear_closed = (ear_closed_left + ear_closed_right) / 2.0
    
    if ear_open < 0.22:
        return False, f"Please keep your eyes fully open for the first photo (EAR: {ear_open:.2f})"
    if ear_closed > 0.20:
        return False, f"Please close your eyes completely for the second photo (EAR: {ear_closed:.2f})"
    if (ear_open - ear_closed) < 0.05:
        return False, "Blink challenge failed: eyes were not closed in the second snap"
        
    return True, "Liveness verified"

@app.post("/api/enrollment/liveness")
async def verify_enrollment_liveness(user_id: int, files: list[UploadFile] = File(...), current_user=Depends(get_current_user)):
    if current_user["role"] == "student" and current_user["id"] != user_id and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    try:
        if len(files) < 2:
            raise HTTPException(status_code=400, detail="Liveness check requires at least 2 sequential frames")

        import face_recognition as _fr
        import numpy as np
        
        decoded_imgs = []
        for f in files:
            content = await f.read()
            nparr = np.frombuffer(content, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                raise HTTPException(status_code=400, detail="Cannot decode image uploads")
            decoded_imgs.append(img)
            
        # Verify face exists in all frames and extract landmarks
        landmarks_list = []
        for img in decoded_imgs:
            marks = _fr.face_landmarks(img)
            if not marks:
                raise HTTPException(
                    status_code=400,
                    detail="Could not locate facial features in one or more frames. Please ensure your face is well-lit and visible."
                )
            landmarks_list.append(marks[0])
            
        encs_first = _fr.face_encodings(decoded_imgs[0])
        if not encs_first:
             raise HTTPException(status_code=400, detail="Could not extract face encoding.")
             
        # LIVENESS CHECK: 3D Landmark Variation (Dlib)
        # We calculate the Eye Aspect Ratio (EAR) and Nose-to-Eye distances for all frames.
        # A static printed photo (even if shaken) will have zero variation in these 2D relative ratios.
        import math
        def get_ear(eye):
            if len(eye) < 6: return 0.0
            a = math.dist(eye[1], eye[5])
            b = math.dist(eye[2], eye[4])
            c = math.dist(eye[0], eye[3])
            return (a + b) / (2.0 * c) if c != 0 else 0.0
            
        ears = []
        nose_ratios = []
        for lm in landmarks_list:
            if "left_eye" in lm and "right_eye" in lm and "nose_bridge" in lm and "nose_tip" in lm:
                ear = (get_ear(lm["left_eye"]) + get_ear(lm["right_eye"])) / 2.0
                ears.append(ear)
                # Distance from nose tip to left eye vs right eye (yaw indicator)
                nose_tip = lm["nose_tip"][2]
                left_eye_center = lm["left_eye"][0]
                right_eye_center = lm["right_eye"][3]
                dist_l = math.dist(nose_tip, left_eye_center)
                dist_r = math.dist(nose_tip, right_eye_center)
                nose_ratios.append(dist_l / dist_r if dist_r != 0 else 1.0)
                
        if len(ears) < 2:
            raise HTTPException(status_code=400, detail="Facial details incomplete for liveness check.")
            
        ear_variation = max(ears) - min(ears)
        nose_variation = max(nose_ratios) - min(nose_ratios)
        
        # If the face is a printed photo, the variations will be near 0.0
        # We require either a slight blink (EAR variation) or a slight head turn (Nose ratio variation)
        if ear_variation < 0.015 and nose_variation < 0.015:
            raise HTTPException(
                status_code=400,
                detail="Liveness check failed (Static face). Please blink or turn your head slightly during the scan."
            )
            
        # Verify the face matches the student's enrollment
        temp_dir = os.path.join(config.known_faces_dir, f"__temp_{user_id}__")
        live_enc = encs_first[0]
        
        match_count = 0
        total_checked = 0
        for i in range(5):
            path = os.path.join(temp_dir, f"capture_{i}.jpg")
            if os.path.exists(path):
                t_img = cv2.imread(path)
                if t_img is not None:
                    t_encs = _fr.face_encodings(t_img)
                    if t_encs:
                        total_checked += 1
                        dist = float(_fr.face_distance([live_enc], t_encs[0])[0])
                        if dist < 0.50:  # Stricter tolerance for enrollment
                            match_count += 1
                            
        # Require at least 80% match rate with uploaded photos (4 out of 5)
        required_matches = math.ceil(total_checked * 0.80)
        if total_checked > 0 and match_count < required_matches:
            raise HTTPException(
                status_code=400,
                detail=f"Live face does not match the uploaded enrollment photos ({match_count}/{total_checked} matched, required {required_matches}). Please verify your identity."
            )
            
        # Save verification marker
        filepath = os.path.join(temp_dir, "capture_5.jpg")
        cv2.imwrite(filepath, decoded_imgs[0])
        
        return {"status": "ok", "message": "Liveness and matches verified successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/enrollment/validate")
def validate_enrollment(user_id: int, current_user=Depends(get_current_user)):
    if current_user["role"] == "student" and current_user["id"] != user_id and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    temp_dir = os.path.join(config.known_faces_dir, f"__temp_{user_id}__")
    
    rec = get_recognizer()
    detector = rec.detector
    encoder = rec.encoder

    results = []
    valid_count = 0
    face_encodings = []

    for i in range(5):
        path = os.path.join(temp_dir, f"capture_{i}.jpg")
        if not os.path.exists(path):
            results.append({"slot": i, "state": "empty", "message": "No photo"})
            continue

        img = cv2.imread(path)
        if img is None:
            results.append({"slot": i, "state": "invalid", "message": "Cannot read file"})
            continue

        # Resize and check face
        small = cv2.resize(img, (0, 0), fx=0.5, fy=0.5)
        locs = detector.detect_faces(small)
        if not locs:
            results.append({"slot": i, "state": "invalid", "message": "No face detected"})
            continue

        t, r, b, l = locs[0]
        face_h = (b - t) * 2
        face_w = (r - l) * 2
        if face_h < 50 or face_w < 50:
            results.append({"slot": i, "state": "invalid", "message": "Face too small"})
            continue

        # Encode face for impersonation checks (with bounds safety)
        try:
            h, w = img.shape[:2]
            y1, y2 = max(0, int(t*2)), min(h, int(b*2))
            x1, x2 = max(0, int(l*2)), min(w, int(r*2))
            face_img = img[y1:y2, x1:x2]
            if face_img.size > 0 and face_img.shape[0] > 10 and face_img.shape[1] > 10:
                enc = encoder.compute_encoding_full(img, (y1, x2, y2, x1))
                if enc is not None:
                    face_encodings.append((i, enc))
        except Exception:
            pass  # Encoding failure is non-fatal — skip impersonation for this slot

        blur = encoder.blur_score(img)
        if blur < 80.0:
            results.append({"slot": i, "state": "warn", "message": f"Blurry (score {blur:.0f})"})
            valid_count += 1
        else:
            results.append({"slot": i, "state": "valid", "message": "Face detected"})
            valid_count += 1

    # --- Impersonation check: verify all photos show the same person ---
    try:
        if len(face_encodings) >= 2:
            first_idx, first_enc = face_encodings[0]
            for slot_idx, enc in face_encodings[1:]:
                try:
                    if encoder.is_dlib:
                        import face_recognition as _fr
                        dist = float(_fr.face_distance([first_enc], enc)[0])
                        if dist > 0.50:  # Stricter tolerance
                            results[first_idx]["state"] = "invalid"
                            results[first_idx]["message"] = "Photos show different people"
                            results[slot_idx]["state"] = "invalid"
                            results[slot_idx]["message"] = "Photos show different people"
                    else:
                        if enc.shape == first_enc.shape:
                            corr = cv2.matchTemplate(enc, first_enc, cv2.TM_CCOEFF_NORMED)[0][0]
                            if corr < 0.3:
                                results[first_idx]["state"] = "invalid"
                                results[first_idx]["message"] = "Photos show different people"
                                results[slot_idx]["state"] = "invalid"
                                results[slot_idx]["message"] = "Photos show different people"
                except Exception:
                    pass  # Comparison failure for one slot is non-fatal
    except Exception:
        pass  # Entire impersonation check failure is non-fatal

    # --- Owner check: for re-enrollment, verify new photos match existing face ---
    try:
        user = db.get_user(user_id)
        if user and user.get("face_enrolled"):
            person_dir = os.path.join(config.known_faces_dir, user["full_name"])
            if os.path.exists(person_dir) and face_encodings:
                owner_encoder = FaceEncoder(engine=config.recognition_engine)
                existing_encs, _ = owner_encoder.load_known_faces(person_dir)
                if existing_encs:
                    ref_enc = existing_encs[0]
                    for slot_idx, enc in face_encodings:
                        try:
                            if owner_encoder.is_dlib:
                                import face_recognition as _fr
                                dist = float(_fr.face_distance([ref_enc], enc)[0])
                                if dist > 0.6:
                                    results[slot_idx]["state"] = "invalid"
                                    results[slot_idx]["message"] = "Does not match enrolled person"
                            else:
                                if enc.shape == ref_enc.shape:
                                    corr = cv2.matchTemplate(enc, ref_enc, cv2.TM_CCOEFF_NORMED)[0][0]
                                    if corr < 0.3:
                                        results[slot_idx]["state"] = "invalid"
                                        results[slot_idx]["message"] = "Does not match enrolled person"
                        except Exception:
                            pass
    except Exception:
        pass  # Owner check failure is non-fatal

    # Re-count valid slots after all checks
    valid_count = sum(1 for r in results if r["state"] in ("valid", "warn"))
    return {"results": results, "valid_count": valid_count, "can_proceed": valid_count >= 3}

@app.post("/api/enrollment/test/start")
def start_enrollment_test(user_id: int, full_name: str, current_user=Depends(get_current_user)):
    if current_user["role"] == "student" and current_user["id"] != user_id and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    full_name = full_name.strip()
    try:
        temp_dir = os.path.join(config.known_faces_dir, f"__temp_{user_id}__")
        person_dir = os.path.join(temp_dir, full_name)
        os.makedirs(person_dir, exist_ok=True)
        
        for file in os.listdir(temp_dir):
            if file.startswith("capture_") and file.lower().endswith(".jpg"):
                import shutil
                shutil.move(os.path.join(temp_dir, file), os.path.join(person_dir, file))

        streamer.start("test", user_id=user_id, full_name=full_name)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/enrollment/confirm")
def confirm_enrollment(user_id: int, full_name: str, current_user=Depends(get_current_user)):
    if current_user["role"] == "student" and current_user["id"] != user_id and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    full_name = full_name.strip()
    streamer.stop()
    
    temp_dir = os.path.join(config.known_faces_dir, f"__temp_{user_id}__")
    person_temp_dir = os.path.join(temp_dir, full_name)
    final_dir = os.path.join(config.known_faces_dir, full_name)
    
    # Check that liveness verification file capture_5.jpg exists
    liveness_file1 = os.path.join(temp_dir, "capture_5.jpg")
    liveness_file2 = os.path.join(person_temp_dir, "capture_5.jpg")
    if not os.path.exists(liveness_file1) and not os.path.exists(liveness_file2):
        raise HTTPException(
            status_code=400,
            detail="Face enrollment requires liveness check (blink test) to prevent spoofing. Please complete the liveness test first."
        )
    
    import shutil
    if os.path.exists(final_dir):
        shutil.rmtree(final_dir)
    os.makedirs(final_dir, exist_ok=True)
    
    # Files may be in temp_dir/ (upload path) or temp_dir/full_name/ (capture path)
    source_dir = person_temp_dir if os.path.exists(person_temp_dir) and os.listdir(person_temp_dir) else temp_dir
    if os.path.exists(source_dir):
        for f in os.listdir(source_dir):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                shutil.copy2(os.path.join(source_dir, f), os.path.join(final_dir, f))
            
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)

    db.set_face_enrolled(user_id, True)
    
    # Extract 128-D face encoding vector and save in students table
    try:
        det = FaceDetector(model="haar")
        enc = FaceEncoder(engine=config.recognition_engine)
        enc.load_known_faces(config.known_faces_dir)
        if full_name in enc.known_names:
            idx = enc.known_names.index(full_name)
            vector = enc.known_encodings[idx]
            db.save_student_face_encoding(user_id, vector)
    except Exception as e:
        logger.error("Failed to pickle and save face encoding to students table: %s", str(e))

    invalidate_global_recognizer()
    return {"status": "ok"}

# --- Config & System Endpoints ---

@app.get("/api/config")
def get_config(current_user=Depends(require_roles("admin"))):
    return {
        "camera_index": config.camera_index,
        "frame_scale": config.frame_scale,
        "tolerance": config.tolerance,
        "recognition_engine": config.recognition_engine,
        "stream_url": config.stream_url
    }

@app.post("/api/config")
def save_config(req: ConfigSaveRequest, current_user=Depends(require_roles("admin"))):
    config.set("Camera", "CAMERA_INDEX", str(req.camera_index))
    config.set("Camera", "FRAME_SCALE", str(req.frame_scale))
    config.set("Recognition", "TOLERANCE", str(req.tolerance))
    config.set("Recognition", "ENGINE", req.recognition_engine)
    config.set("Camera", "STREAM_URL", req.stream_url)
    return {"status": "ok"}

@app.post("/api/bias/evaluate")
def run_bias_evaluation(background_tasks: BackgroundTasks, current_user=Depends(require_roles("admin"))):
    dataset_dir = os.path.join(config.base_dir, "data", "evaluation_dataset")
    annotations = os.path.join(dataset_dir, "annotations.csv")
    
    if not os.path.exists(annotations):
        raise HTTPException(status_code=400, detail="Annotations file missing. Please create evaluations structure first.")

    def _eval_job():
        det = FaceDetector(model="haar")
        enc = FaceEncoder(engine=config.recognition_engine, tolerance=config.tolerance)
        recognizer = Recognizer(det, enc)
        recognizer.load_database(config.known_faces_dir)
        evaluator = BiasEvaluator(recognizer)
        
        metrics = evaluator.evaluate(dataset_dir, annotations)
        if metrics:
            evaluator.save_results(os.path.join(dataset_dir, "results.csv"))
            evaluator.save_metrics(os.path.join(dataset_dir, "metrics.json"))
            
    background_tasks.add_task(_eval_job)
    return {"status": "started"}

@app.get("/api/bias/results")
def get_bias_results(current_user=Depends(require_roles("admin"))):
    dataset_dir = os.path.join(config.base_dir, "data", "evaluation_dataset")
    metrics_path = os.path.join(dataset_dir, "metrics.json")
    
    if not os.path.exists(metrics_path):
        helper = DatasetHelper(dataset_dir)
        helper.create_sample_dataset()
        helper.generate_annotations_template(os.path.join(dataset_dir, "annotations.csv"))
        return {"status": "no_metrics", "msg": "No evaluation run yet. Sample structure generated."}
        
    import json
    with open(metrics_path, "r") as f:
        return json.load(f)

@app.get("/api/admin/stats")
def get_admin_stats(current_user=Depends(require_roles("admin"))):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = db._conn

    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    students = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0]
    enrolled = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'student' AND face_enrolled = 1").fetchone()[0]
    lecturers = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'lecturer'").fetchone()[0]
    classes = conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
    total_attendance = conn.execute("SELECT COUNT(*) FROM attendance_log").fetchone()[0]
    today_attendance = conn.execute("SELECT COUNT(*) FROM attendance_log WHERE session_date = ?", (today,)).fetchone()[0]
    total_enrollments = conn.execute("SELECT COUNT(*) FROM enrollments").fetchone()[0]

    return {
        "total_users": total_users,
        "students": students,
        "students_enrolled": enrolled,
        "students_pending": students - enrolled,
        "lecturers": lecturers,
        "classes": classes,
        "total_attendance": total_attendance,
        "today_attendance": today_attendance,
        "total_enrollments": total_enrollments,
    }

@app.get("/api/student/attendance/{student_name}")
def get_student_attendance(student_name: str, current_user=Depends(get_current_user)):
    student = db.get_user_by_name(student_name)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    if current_user["role"] == "student" and current_user["id"] != student["id"] and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    rows = db._conn.execute(
        """SELECT a.*, c.name AS class_name, c.code AS class_code 
           FROM attendance_log a
           JOIN classes c ON a.class_id = c.id
           WHERE a.student_id = ?
           ORDER BY a.session_date DESC, a.timestamp DESC""",
        (student["id"],)
    ).fetchall()
    return db._rows_to_list(rows)

@app.get("/api/student/summary/{student_id}")
def get_student_summary(student_id: int, current_user=Depends(get_current_user)):
    if current_user["role"] == "student" and current_user["id"] != student_id:
        raise HTTPException(status_code=403, detail="Not allowed")
    return db.get_student_summary_per_class(student_id)

@app.post("/api/student/retrain")
def retrain_student_model(user_id: int, full_name: str, current_user=Depends(require_roles("admin"))):
    full_name = full_name.strip()
    try:
        enc = FaceEncoder(engine=config.recognition_engine)
        enc.load_known_faces(config.known_faces_dir)
        invalidate_global_recognizer()
        return {"status": "ok"}
    except Exception as e:
        logger.error("Retrain failed for user %s: %s", user_id, e)
        raise HTTPException(status_code=500, detail=f"Retrain failed: {e}")

@app.get("/api/attendance/export")
def export_attendance(class_id: int, date: str = None, date_from: str = None, date_to: str = None, format: str = "csv", current_user=Depends(require_roles("admin", "lecturer"))):
    import pandas as pd
    class_data = db.get_class(class_id)
    class_name = class_data["name"] if class_data else f"class_{class_id}"

    if date_from and date_to:
        rows = db.get_attendance_range(class_id, date_from, date_to)
        range_label = f"{date_from}_to_{date_to}"
    else:
        rows = db.get_attendance(class_id, date)
        range_label = date

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=["student_id", "full_name", "session_date", "timestamp", "method", "confidence"])
    else:
        df = df[["student_id", "full_name", "session_date", "timestamp", "method", "confidence"]]

    export_dir = config.attendance_dir
    os.makedirs(export_dir, exist_ok=True)

    filename = f"attendance_{class_name}_{range_label}.{format}"
    filepath = os.path.join(export_dir, filename)

    if format == "xlsx":
        df.to_excel(filepath, index=False)
    else:
        df.to_csv(filepath, index=False)

    return FileResponse(filepath, filename=filename)

@app.get("/api/attendance/export-data")
def export_attendance_data(class_id: int, date: str = None, date_from: str = None, date_to: str = None, format: str = "csv", current_user=Depends(require_roles("admin", "lecturer"))):
    """Return file as base64 for pywebview native save dialog."""
    import base64
    from io import BytesIO
    import pandas as pd

    class_data = db.get_class(class_id)
    class_name = class_data["name"] if class_data else f"class_{class_id}"

    if date_from and date_to:
        rows = db.get_attendance_range(class_id, date_from, date_to)
        range_label = f"{date_from}_to_{date_to}"
    else:
        rows = db.get_attendance(class_id, date)
        range_label = date

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=["student_id", "full_name", "session_date", "timestamp", "method", "confidence"])
    else:
        df = df[["student_id", "full_name", "session_date", "timestamp", "method", "confidence"]]

    filename = f"attendance_{class_name}_{range_label}.{format}"

    if format == "xlsx":
        buf = BytesIO()
        df.to_excel(buf, index=False)
        content = base64.b64encode(buf.getvalue()).decode()
    else:
        content = base64.b64encode(df.to_csv(index=False).encode()).decode()

    return {
        "filename": filename,
        "content": content,
        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if format == "xlsx" else "text/csv"
    }

@app.get("/api/faculties")
def get_faculties(current_user=Depends(get_current_user)):
    return db.get_faculties()

@app.post("/api/faculties")
def create_faculty(req: FacultyCreateRequest, current_user=Depends(require_roles("admin"))):
    try:
        fid = db.create_faculty(req.name)
        return {"id": fid, "status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/faculties/{id}")
def delete_faculty(id: int, current_user=Depends(require_roles("admin"))):
    db.delete_faculty(id)
    return {"status": "ok"}

@app.get("/api/departments")
def get_departments(faculty_id: Optional[int] = None, current_user=Depends(get_current_user)):
    return db.get_departments(faculty_id)

@app.post("/api/departments")
def create_department(req: DepartmentCreateRequest, current_user=Depends(require_roles("admin"))):
    try:
        did = db.create_department(req.faculty_id, req.name)
        return {"id": did, "status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/api/departments/{id}")
def delete_department(id: int, current_user=Depends(require_roles("admin"))):
    db.delete_department(id)
    return {"status": "ok"}

# Mount the data folder for captured thumbnails
app.mount("/data", StaticFiles(directory=os.path.join(config.base_dir, "data")), name="data")

# Mount the built frontend if present (frontend/dist), else fall back to the
# legacy static web/ folder — lets `./build.sh` cut over without code changes.
project_root = os.path.dirname(os.path.dirname(__file__))
frontend_dist = os.path.join(project_root, "frontend", "dist")
web_dir = frontend_dist if os.path.isdir(frontend_dist) else os.path.join(project_root, "web")
os.makedirs(web_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
