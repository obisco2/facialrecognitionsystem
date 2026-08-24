"""
Database Manager for AttendIQ.
SQLite-backed storage for users, classes, enrollments, and attendance logs.
Designed as a drop-in replacement for the flat-CSV attendance system,
while preserving backward compatibility with the CSV layer for exports.
"""

import sqlite3
import hashlib
import os
import logging
from datetime import datetime, date

logger = logging.getLogger(__name__)

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK(role IN ('admin','lecturer','student')),
    full_name     TEXT    NOT NULL,
    student_id    TEXT,
    email         TEXT,
    face_enrolled INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS classes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    code        TEXT    NOT NULL,
    lecturer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    schedule    TEXT,
    room        TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS enrollments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    class_id    INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    enrolled_at TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(student_id, class_id)
);

CREATE TABLE IF NOT EXISTS attendance_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    class_id     INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    session_date TEXT    NOT NULL,
    timestamp    TEXT    NOT NULL,
    method       TEXT    NOT NULL DEFAULT 'face' CHECK(method IN ('face','manual')),
    confidence   REAL,
    marked_by    INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS students (
    student_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       VARCHAR(100) NOT NULL,
    matric_number   VARCHAR(20) UNIQUE NOT NULL,
    department      VARCHAR(100) NOT NULL,
    level           VARCHAR(10) NOT NULL,
    face_encoding   BLOB DEFAULT NULL,
    date_registered DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS attendance (
    record_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id  INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    course_code VARCHAR(20) NOT NULL,
    date        DATE NOT NULL,
    time_in     TIME NOT NULL,
    status      VARCHAR(10) DEFAULT 'Present'
);

CREATE INDEX IF NOT EXISTS idx_attendance_class_date
    ON attendance_log(class_id, session_date);
CREATE INDEX IF NOT EXISTS idx_attendance_student
    ON attendance_log(student_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_class
    ON enrollments(class_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_student
    ON enrollments(student_id);
"""


def _hash(password: str) -> str:
    """SHA-256 hex digest of a password string."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class DatabaseManager:
    """
    Thread-safe SQLite manager.
    Uses check_same_thread=False; callers must serialize writes or use
    the provided context-manager helpers for transactions.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()
        self._seed_defaults()
        logger.info("DatabaseManager initialized at %s", db_path)

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _init_schema(self):
        with self._conn:
            self._conn.executescript(_SCHEMA)

    def _seed_defaults(self):
        """Create a default admin account on first run if no users exist."""
        cur = self._conn.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] == 0:
            self.create_user(
                username="admin",
                password="admin",
                role="admin",
                full_name="System Administrator",
            )
            logger.info("Default admin account created (admin/admin)")

    def _row_to_dict(self, row) -> dict:
        return dict(row) if row else None

    def _rows_to_list(self, rows) -> list:
        return [dict(r) for r in rows]

    def close(self):
        """Close the database connection cleanly."""
        if self._conn:
            self._conn.close()
            logger.info("Database connection closed")

    # ------------------------------------------------------------------ #
    #  User management                                                     #
    # ------------------------------------------------------------------ #

    def create_user(self, username: str, password: str, role: str,
                    full_name: str, student_id: str = None,
                    email: str = None, department: str = None, level: str = None) -> int:
        """
        Create a new user account.

        Returns:
            New user's integer ID.

        Raises:
            ValueError: If username already exists.
        """
        if full_name:
            full_name = full_name.strip()
        try:
            with self._conn:
                cur = self._conn.execute(
                    """INSERT INTO users
                       (username, password_hash, role, full_name, student_id, email)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (username, _hash(password), role, full_name, student_id, email),
                )
                user_id = cur.lastrowid
                
                # Mirror to students table if role is student
                if role == "student":
                    matric = student_id if student_id else username
                    dept = department if department else "Computer Engineering"
                    lvl = level if level else "500 Level"
                    self._conn.execute(
                        """INSERT INTO students
                           (full_name, matric_number, department, level)
                           VALUES (?, ?, ?, ?)""",
                        (full_name, matric, dept, lvl)
                    )
            logger.info("Created user '%s' (role=%s)", username, role)
            return user_id
        except sqlite3.IntegrityError:
            raise ValueError(f"Username '{username}' is already taken.")

    def authenticate(self, username: str, password: str) -> dict | None:
        """
        Validate credentials.

        Returns:
            User dict on success, None on failure.
        """
        row = self._conn.execute(
            "SELECT * FROM users WHERE username = ? AND password_hash = ?",
            (username, _hash(password)),
        ).fetchone()
        return self._row_to_dict(row)

    def get_user(self, user_id: int) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return self._row_to_dict(row)

    def get_user_by_name(self, full_name: str) -> dict | None:
        """Look up a user by their full name (used after face recognition)."""
        full_name = full_name.strip()
        row = self._conn.execute(
            "SELECT * FROM users WHERE TRIM(full_name) = ? AND role = 'student'",
            (full_name,),
        ).fetchone()
        return self._row_to_dict(row)

    def get_user_by_student_id(self, student_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM users WHERE student_id = ?", (student_id,)
        ).fetchone()
        return self._row_to_dict(row)

    def get_users(self, role: str = None) -> list:
        """Return all users, optionally filtered by role."""
        if role:
            rows = self._conn.execute(
                "SELECT * FROM users WHERE role = ? ORDER BY full_name", (role,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM users ORDER BY role, full_name"
            ).fetchall()
        return self._rows_to_list(rows)

    def update_user(self, user_id: int, **fields) -> bool:
        """
        Update arbitrary user fields. Pass keyword args matching column names.
        Use update_password() for password changes.
        """
        allowed = {"username", "role", "full_name", "student_id", "email", "face_enrolled"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if "full_name" in updates and updates["full_name"]:
            updates["full_name"] = updates["full_name"].strip()
        if not updates:
            return False
        cols = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [user_id]
        with self._conn:
            self._conn.execute(f"UPDATE users SET {cols} WHERE id = ?", vals)
        return True

    def update_password(self, user_id: int, new_password: str) -> bool:
        with self._conn:
            self._conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (_hash(new_password), user_id),
            )
        return True

    def delete_user(self, user_id: int) -> bool:
        user = self.get_user(user_id)
        if user and user["role"] == "student":
            matric = user["student_id"] if user["student_id"] else user["username"]
            with self._conn:
                self._conn.execute("DELETE FROM students WHERE matric_number = ?", (matric,))
        with self._conn:
            self._conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        logger.info("Deleted user id=%d", user_id)
        return True

    def set_face_enrolled(self, user_id: int, enrolled: bool = True):
        self.update_user(user_id, face_enrolled=1 if enrolled else 0)

    def save_student_face_encoding(self, user_id: int, encoding):
        import pickle
        user = self.get_user(user_id)
        if not user:
            return
        matric = user["student_id"] if user["student_id"] else user["username"]
        blob = pickle.dumps(encoding)
        with self._conn:
            self._conn.execute(
                "UPDATE students SET face_encoding = ? WHERE matric_number = ?",
                (sqlite3.Binary(blob), matric)
            )
        self.update_user(user_id, face_enrolled=1)

    # ------------------------------------------------------------------ #
    #  Class management                                                    #
    # ------------------------------------------------------------------ #

    def create_class(self, name: str, code: str, lecturer_id: int,
                     schedule: str = None, room: str = None) -> int:
        with self._conn:
            cur = self._conn.execute(
                """INSERT INTO classes (name, code, lecturer_id, schedule, room)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, code, lecturer_id, schedule, room),
            )
        logger.info("Created class '%s' (%s) for lecturer id=%d", name, code, lecturer_id)
        return cur.lastrowid

    def get_class(self, class_id: int) -> dict | None:
        row = self._conn.execute(
            """SELECT c.*, u.full_name AS lecturer_name
               FROM classes c
               LEFT JOIN users u ON c.lecturer_id = u.id
               WHERE c.id = ?""",
            (class_id,),
        ).fetchone()
        return self._row_to_dict(row)

    def get_classes(self, lecturer_id: int = None) -> list:
        """Return all classes, optionally filtered by lecturer."""
        if lecturer_id:
            rows = self._conn.execute(
                """SELECT c.*, u.full_name AS lecturer_name,
                          (SELECT COUNT(*) FROM enrollments WHERE class_id = c.id) AS enrolled_count
                   FROM classes c
                   LEFT JOIN users u ON c.lecturer_id = u.id
                   WHERE c.lecturer_id = ?
                   ORDER BY c.code""",
                (lecturer_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT c.*, u.full_name AS lecturer_name,
                          (SELECT COUNT(*) FROM enrollments WHERE class_id = c.id) AS enrolled_count
                   FROM classes c
                   LEFT JOIN users u ON c.lecturer_id = u.id
                   ORDER BY c.code""",
            ).fetchall()
        return self._rows_to_list(rows)

    def update_class(self, class_id: int, **fields) -> bool:
        allowed = {"name", "code", "lecturer_id", "schedule", "room"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        cols = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [class_id]
        with self._conn:
            self._conn.execute(f"UPDATE classes SET {cols} WHERE id = ?", vals)
        return True

    def delete_class(self, class_id: int) -> bool:
        with self._conn:
            self._conn.execute("DELETE FROM classes WHERE id = ?", (class_id,))
        return True

    # ------------------------------------------------------------------ #
    #  Enrollment                                                          #
    # ------------------------------------------------------------------ #

    def enroll_student(self, student_id: int, class_id: int) -> bool:
        """Enroll a student in a class. Silently ignores duplicates."""
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO enrollments (student_id, class_id) VALUES (?, ?)",
                    (student_id, class_id),
                )
            return True
        except sqlite3.IntegrityError:
            return False  # already enrolled

    def unenroll_student(self, student_id: int, class_id: int) -> bool:
        with self._conn:
            self._conn.execute(
                "DELETE FROM enrollments WHERE student_id = ? AND class_id = ?",
                (student_id, class_id),
            )
        return True

    def get_enrolled_students(self, class_id: int) -> list:
        """Return list of student user dicts enrolled in a class."""
        rows = self._conn.execute(
            """SELECT u.*
               FROM users u
               JOIN enrollments e ON u.id = e.student_id
               WHERE e.class_id = ?
               ORDER BY u.full_name""",
            (class_id,),
        ).fetchall()
        return self._rows_to_list(rows)

    def get_student_classes(self, student_id: int) -> list:
        """Return all classes a student is enrolled in."""
        rows = self._conn.execute(
            """SELECT c.*, u.full_name AS lecturer_name
               FROM classes c
               JOIN enrollments e ON c.id = e.class_id
               LEFT JOIN users u ON c.lecturer_id = u.id
               WHERE e.student_id = ?
               ORDER BY c.code""",
            (student_id,),
        ).fetchall()
        return self._rows_to_list(rows)

    def is_enrolled(self, student_id: int, class_id: int) -> bool:
        row = self._conn.execute(
            "SELECT id FROM enrollments WHERE student_id = ? AND class_id = ?",
            (student_id, class_id),
        ).fetchone()
        return row is not None

    # ------------------------------------------------------------------ #
    #  Attendance logging                                                  #
    # ------------------------------------------------------------------ #

    def log_attendance(self, student_id: int, class_id: int,
                       session_date: str = None, timestamp: str = None,
                       method: str = "face", confidence: float = None,
                       marked_by: int = None) -> int | None:
        """
        Record an attendance event.

        Args:
            student_id:   User ID of the student.
            class_id:     Class ID.
            session_date: YYYY-MM-DD string (defaults to today).
            timestamp:    HH:MM:SS string (defaults to now).
            method:       'face' or 'manual'.
            confidence:   Recognition distance (lower = more confident).
            marked_by:    Lecturer user ID who triggered the session.

        Returns:
            New attendance log ID, or None if already logged today (duplicate prevention).
        """
        now = datetime.now()
        session_date = session_date or now.strftime("%Y-%m-%d")
        timestamp = timestamp or now.strftime("%H:%M:%S")

        # Duplicate prevention — one entry per student per class per day
        existing = self._conn.execute(
            """SELECT id FROM attendance_log
               WHERE student_id = ? AND class_id = ? AND session_date = ?""",
            (student_id, class_id, session_date),
        ).fetchone()
        if existing:
            return None  # already marked

        with self._conn:
            cur = self._conn.execute(
                """INSERT INTO attendance_log
                   (student_id, class_id, session_date, timestamp, method, confidence, marked_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (student_id, class_id, session_date, timestamp, method, confidence, marked_by),
            )
            
            # Mirror to report-specified attendance table
            try:
                class_info = self.get_class(class_id)
                course_code = class_info["code"] if class_info else "UNK-101"
                
                student_user = self.get_user(student_id)
                if student_user:
                    matric = student_user["student_id"] if student_user["student_id"] else student_user["username"]
                    student_row = self._conn.execute(
                        "SELECT student_id FROM students WHERE matric_number = ?", (matric,)
                    ).fetchone()
                    if student_row:
                        s_id = student_row["student_id"]
                        self._conn.execute(
                            """INSERT INTO attendance
                               (student_id, course_code, date, time_in, status)
                               VALUES (?, ?, ?, ?, 'Present')""",
                            (s_id, course_code, session_date, timestamp)
                        )
            except Exception as e:
                logger.error("Failed to mirror attendance log to students table: %s", str(e))
                
        logger.debug("Logged attendance: student=%d, class=%d, date=%s",
                     student_id, class_id, session_date)
        return cur.lastrowid

    def delete_attendance(self, log_id: int) -> bool:
        with self._conn:
            self._conn.execute("DELETE FROM attendance_log WHERE id = ?", (log_id,))
        return True

    def get_attendance(self, class_id: int, session_date: str) -> list:
        """
        Get all attendance records for a class on a specific date.

        Returns:
            List of dicts with student info + attendance fields.
        """
        rows = self._conn.execute(
            """SELECT a.id, a.student_id, a.session_date, a.timestamp,
                      a.method, a.confidence, a.marked_by,
                      u.full_name, u.student_id AS student_id_string
               FROM attendance_log a
               JOIN users u ON a.student_id = u.id
               WHERE a.class_id = ? AND a.session_date = ?
               ORDER BY a.timestamp""",
            (class_id, session_date),
        ).fetchall()
        return self._rows_to_list(rows)

    def get_attendance_dates(self, class_id: int) -> list:
        """Return list of distinct session dates for a class (newest first)."""
        rows = self._conn.execute(
            """SELECT DISTINCT session_date
               FROM attendance_log
               WHERE class_id = ?
               ORDER BY session_date DESC""",
            (class_id,),
        ).fetchall()
        return [r["session_date"] for r in rows]

    def get_student_attendance(self, student_id: int,
                                class_id: int = None) -> list:
        """
        Get attendance records for a student.

        Args:
            student_id: Student user ID.
            class_id:   Optional — filter to one class.

        Returns:
            List of attendance dicts including class name.
        """
        if class_id:
            rows = self._conn.execute(
                """SELECT a.*, c.name AS class_name, c.code AS class_code
                   FROM attendance_log a
                   JOIN classes c ON a.class_id = c.id
                   WHERE a.student_id = ? AND a.class_id = ?
                   ORDER BY a.session_date DESC, a.timestamp DESC""",
                (student_id, class_id),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT a.*, c.name AS class_name, c.code AS class_code
                   FROM attendance_log a
                   JOIN classes c ON a.class_id = c.id
                   WHERE a.student_id = ?
                   ORDER BY a.session_date DESC, a.timestamp DESC""",
                (student_id,),
            ).fetchall()
        return self._rows_to_list(rows)

    def get_attendance_summary(self, class_id: int,
                                session_date: str = None) -> dict:
        """
        Compute attendance statistics for a class.

        Args:
            class_id:     Class to summarize.
            session_date: If provided, stats for that day only.
                          If None, stats across all sessions.

        Returns:
            Dict with keys: present, total_enrolled, percent, sessions.
        """
        total_enrolled = self._conn.execute(
            "SELECT COUNT(*) FROM enrollments WHERE class_id = ?",
            (class_id,),
        ).fetchone()[0]

        if session_date:
            present = self._conn.execute(
                """SELECT COUNT(DISTINCT student_id)
                   FROM attendance_log
                   WHERE class_id = ? AND session_date = ?""",
                (class_id, session_date),
            ).fetchone()[0]
            sessions = 1 if session_date else 0
        else:
            present = self._conn.execute(
                "SELECT COUNT(DISTINCT student_id) FROM attendance_log WHERE class_id = ?",
                (class_id,),
            ).fetchone()[0]
            sessions = self._conn.execute(
                "SELECT COUNT(DISTINCT session_date) FROM attendance_log WHERE class_id = ?",
                (class_id,),
            ).fetchone()[0]

        percent = round((present / total_enrolled * 100), 1) if total_enrolled > 0 else 0
        return {
            "present": present,
            "total_enrolled": total_enrolled,
            "percent": percent,
            "sessions": sessions,
        }

    def get_student_summary_per_class(self, student_id: int) -> list:
        """
        For the student dashboard — attendance % per enrolled class.

        Returns:
            List of dicts: class_id, class_name, class_code,
                           sessions_present, total_sessions, percent.
        """
        classes = self.get_student_classes(student_id)
        result = []
        for cls in classes:
            sessions_present = self._conn.execute(
                """SELECT COUNT(*) FROM attendance_log
                   WHERE student_id = ? AND class_id = ?""",
                (student_id, cls["id"]),
            ).fetchone()[0]

            total_sessions = self._conn.execute(
                """SELECT COUNT(DISTINCT session_date) FROM attendance_log
                   WHERE class_id = ?""",
                (cls["id"],),
            ).fetchone()[0]

            percent = round((sessions_present / total_sessions * 100), 1) if total_sessions > 0 else 0
            result.append({
                "class_id": cls["id"],
                "class_name": cls["name"],
                "class_code": cls["code"],
                "lecturer_name": cls.get("lecturer_name"),
                "schedule": cls.get("schedule"),
                "sessions_present": sessions_present,
                "total_sessions": total_sessions,
                "percent": percent,
            })
        return result

    # ------------------------------------------------------------------ #
    #  Export helpers                                                      #
    # ------------------------------------------------------------------ #

    def get_attendance_range(self, class_id: int,
                              date_from: str, date_to: str) -> list:
        """
        Get attendance records for a class within a date range.
        Used by the export manager.
        """
        rows = self._conn.execute(
            """SELECT a.id, a.student_id, a.session_date, a.timestamp, a.method, a.confidence,
                      u.full_name, u.student_id AS student_id_string
               FROM attendance_log a
               JOIN users u ON a.student_id = u.id
               WHERE a.class_id = ?
                 AND a.session_date >= ?
                 AND a.session_date <= ?
               ORDER BY a.session_date, a.timestamp""",
            (class_id, date_from, date_to),
        ).fetchall()
        return self._rows_to_list(rows)

    def get_full_report(self, class_id: int,
                         date_from: str, date_to: str) -> list:
        """
        Per-student summary over a date range.
        Returns list of dicts: student info + sessions_present + percent.
        """
        students = self.get_enrolled_students(class_id)
        total_sessions = self._conn.execute(
            """SELECT COUNT(DISTINCT session_date) FROM attendance_log
               WHERE class_id = ? AND session_date >= ? AND session_date <= ?""",
            (class_id, date_from, date_to),
        ).fetchone()[0]

        result = []
        for stu in students:
            sessions_present = self._conn.execute(
                """SELECT COUNT(*) FROM attendance_log
                   WHERE student_id = ? AND class_id = ?
                     AND session_date >= ? AND session_date <= ?""",
                (stu["id"], class_id, date_from, date_to),
            ).fetchone()[0]
            percent = round((sessions_present / total_sessions * 100), 1) if total_sessions > 0 else 0
            result.append({
                "student_id": stu["student_id"],
                "full_name": stu["full_name"],
                "sessions_present": sessions_present,
                "total_sessions": total_sessions,
                "percent": percent,
            })
        return result

    # ------------------------------------------------------------------ #
    #  System / admin stats                                                #
    # ------------------------------------------------------------------ #

    def get_system_stats(self) -> dict:
        """Overall system statistics for the admin dashboard."""
        return {
            "total_users":      self._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "total_students":   self._conn.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
            "total_lecturers":  self._conn.execute("SELECT COUNT(*) FROM users WHERE role='lecturer'").fetchone()[0],
            "total_classes":    self._conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0],
            "total_attendance": self._conn.execute("SELECT COUNT(*) FROM attendance_log").fetchone()[0],
            "enrolled_faces":   self._conn.execute("SELECT COUNT(*) FROM users WHERE face_enrolled=1").fetchone()[0],
        }
