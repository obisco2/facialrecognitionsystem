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
import secrets
from datetime import datetime, date

logger = logging.getLogger(__name__)

# Password hashing constants
_HASH_ITERATIONS = 260_000  # OWASP 2023 recommendation for PBKDF2-SHA256
_HASH_KEYLEN = 32
_HASH_DIGEST = "sha256"

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS faculties (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS departments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER REFERENCES faculties(id) ON DELETE CASCADE,
    name       TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK(role IN ('admin','lecturer','student')),
    full_name     TEXT    NOT NULL,
    title         TEXT,
    student_id    TEXT,
    email         TEXT,
    faculty       TEXT,
    department    TEXT,
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
    department  TEXT,
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
    faculty         VARCHAR(100),
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

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT    NOT NULL UNIQUE,
    jti        TEXT    NOT NULL UNIQUE,
    expires_at TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_hash ON refresh_tokens(token_hash);

CREATE TABLE IF NOT EXISTS class_blocks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id   INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blocked_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    reason     TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(class_id, student_id)
);
CREATE INDEX IF NOT EXISTS idx_block_class ON class_blocks(class_id);
CREATE INDEX IF NOT EXISTS idx_block_student ON class_blocks(student_id);
"""


def _hash(password: str, salt: str = None) -> str:
    # PBKDF2-SHA256, 260k rounds — OWASP 2023. Salt is hex, stored as salt:digest.
    # Tobi: keep verify compatible with old bare sha256 hashes from early prototype.
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        _HASH_DIGEST,
        password.encode("utf-8"),
        bytes.fromhex(salt),
        _HASH_ITERATIONS,
        _HASH_KEYLEN,
    )
    return f"{salt}:{digest.hex()}"


def _verify(password: str, stored_hash: str) -> bool:
    """
    Verify a password against a stored "salt:digest" hash.

    Also handles legacy bare SHA-256 hashes for backward compatibility.
    """
    if ":" in stored_hash:
        salt, _ = stored_hash.split(":", 1)
        return secrets.compare_digest(_hash(password, salt), stored_hash)
    # Legacy: bare SHA-256 hash without salt (backward compatible)
    return secrets.compare_digest(
        hashlib.sha256(password.encode("utf-8")).hexdigest(),
        stored_hash,
    )


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
            # Self-healing migrations: add any expected column missing from
            # pre-existing DB files (old installs predate title/security/etc).
            expected = {
                "users": {
                    "title": "TEXT",
                    "student_id": "TEXT",
                    "email": "TEXT",
                    "faculty": "TEXT",
                    "department": "TEXT",
                    "face_enrolled": "INTEGER NOT NULL DEFAULT 0",
                    "security_question": "TEXT",
                    "security_answer_hash": "TEXT",
                    "emergency_pin_hash": "TEXT",
                },
                "students": {"faculty": "VARCHAR(100)"},
                "classes": {"department": "TEXT"},
            }
            for tbl, cols in expected.items():
                try:
                    existing = {r[1] for r in self._conn.execute(f"PRAGMA table_info({tbl})").fetchall()}
                except sqlite3.OperationalError:
                    continue  # table missing entirely; executescript above should have made it
                for col, coltype in cols.items():
                    if col not in existing:
                        try:
                            self._conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {coltype}")
                            logger.info("Migrated %s: added column %s", tbl, col)
                        except sqlite3.OperationalError:
                            pass  # raced or already exists

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

        # Seed UNILAG faculties and departments if empty
        cur = self._conn.execute("SELECT COUNT(*) FROM faculties")
        if cur.fetchone()[0] == 0:
            unilag_data = {
                "Faculty of Engineering": [
                    "Computer Engineering",
                    "Electrical & Electronics Engineering",
                    "Mechanical Engineering",
                    "Civil & Environmental Engineering",
                    "Chemical & Polymer Engineering",
                    "Metallurgical & Materials Engineering",
                    "Systems Engineering",
                ],
                "Faculty of Science": [
                    "Computer Science",
                    "Mathematics",
                    "Physics",
                    "Chemistry",
                    "Cell Biology & Genetics",
                    "Microbiology",
                    "Biochemistry",
                    "Marine Sciences",
                    "Botany",
                ],
                "Faculty of Social Sciences": [
                    "Economics",
                    "Mass Communication",
                    "Sociology",
                    "Psychology",
                    "Geography",
                    "Political Science",
                ],
                "Faculty of Arts": [
                    "English",
                    "History & Strategic Studies",
                    "Linguistics",
                    "Creative Arts",
                    "Philosophy",
                ],
                "Faculty of Environmental Sciences": [
                    "Architecture",
                    "Estate Management",
                    "Quantity Surveying",
                    "Urban & Regional Planning",
                    "Building",
                ],
                "Faculty of Law": [
                    "Private and Property Law",
                    "Public Law",
                    "Commercial and Industrial Law",
                    "Jurisprudence and International Law",
                ],
                "College of Medicine": [
                    "Medicine and Surgery",
                    "Dentistry",
                    "Pharmacy",
                    "Nursing Science",
                    "Physiotherapy",
                    "Medical Laboratory Science",
                    "Physiology",
                ],
                "Faculty of Management Sciences": [
                    "Accounting",
                    "Finance",
                    "Actuarial Science",
                    "Business Administration",
                    "Industrial Relations and Personnel Management",
                ],
            }
            with self._conn:
                for fac, depts in unilag_data.items():
                    self._conn.execute("INSERT OR IGNORE INTO faculties (name) VALUES (?)", (fac,))
                    fac_row = self._conn.execute("SELECT id FROM faculties WHERE name = ?", (fac,)).fetchone()
                    if fac_row:
                        fac_id = fac_row[0]
                        for dept in depts:
                            self._conn.execute("INSERT OR IGNORE INTO departments (faculty_id, name) VALUES (?, ?)", (fac_id, dept))
            logger.info("Default UNILAG faculties and departments seeded successfully")

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
                    email: str = None, title: str = None,
                    department: str = None, level: str = None,
                    faculty: str = None) -> int:
        """
        Create a new user account.

        Returns:
            New user's integer ID.

        Raises:
            ValueError: If username already exists, or if student_id/email missing for students.
        """
        if full_name:
            full_name = full_name.strip()

        # Enforce compulsory fields for students
        if role == "student":
            if not student_id or not student_id.strip():
                raise ValueError("Matric number (Student ID) is required for students.")
            if not email or not email.strip():
                raise ValueError("Email address is required for students.")
            username = student_id.strip()

        # Check for duplicate username
        existing_username = self._conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if existing_username:
            raise ValueError(f"Username '{username}' is already taken.")

        # Check for duplicate student_id / matric_number
        if student_id:
            student_id = student_id.strip()
            # Check users table
            existing_user_sid = self._conn.execute("SELECT id FROM users WHERE student_id = ?", (student_id,)).fetchone()
            if existing_user_sid:
                raise ValueError(f"Matric number (Student ID) '{student_id}' is already registered.")
            # Check students table
            existing_stud_sid = self._conn.execute("SELECT student_id FROM students WHERE matric_number = ?", (student_id,)).fetchone()
            if existing_stud_sid:
                raise ValueError(f"Matric number (Student ID) '{student_id}' is already registered.")

        # Check for duplicate email
        if email:
            email = email.strip()
            existing_email = self._conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing_email:
                raise ValueError(f"Email '{email}' is already registered.")

        try:
            with self._conn:
                cur = self._conn.execute(
                    """INSERT INTO users
                       (username, password_hash, role, full_name, title, student_id, email, faculty, department)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (username, _hash(password), role, full_name, title, student_id, email, faculty, department),
                )
                user_id = cur.lastrowid
                
                # Mirror to students table if role is student
                if role == "student":
                    matric = student_id if student_id else username
                    dept = department if department else "Computer Engineering"
                    lvl = level if level else "500 Level"
                    fac = faculty if faculty else "Faculty of Engineering"
                    self._conn.execute(
                        """INSERT INTO students
                           (full_name, matric_number, department, level, faculty)
                           VALUES (?, ?, ?, ?, ?)""",
                        (full_name, matric, dept, lvl, fac)
                    )
            logger.info("Created user '%s' (role=%s)", username, role)
            return user_id
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Registration failed: duplicate key or integrity error ({e})")

    def authenticate(self, identifier: str, password: str) -> dict | None:
        """
        Validate credentials using matric number, email, or username.

        Args:
            identifier: Matric number, email address, or username.
            password: Plain-text password.

        Returns:
            User dict on success, None on failure.
        """
        row = self._conn.execute(
            """SELECT * FROM users
               WHERE username = ? OR student_id = ? OR email = ?""",
            (identifier, identifier, identifier),
        ).fetchone()
        if row is None:
            return None
        stored_hash = row["password_hash"]
        if not _verify(password, stored_hash):
            return None
        # Upgrade legacy hash to salted PBKDF2 on successful login
        if ":" not in stored_hash:
            new_hash = _hash(password)
            self._conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (new_hash, row["id"]),
            )
            self._conn.commit()
            logger.info("Upgraded password hash for user '%s' to PBKDF2", row["username"])
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
        allowed = {"username", "role", "full_name", "title", "student_id", "email", "face_enrolled", "faculty", "department"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if "full_name" in updates and updates["full_name"]:
            updates["full_name"] = updates["full_name"].strip()
        if not updates:
            return False
        
        user_before = self.get_user(user_id)
        if user_before and user_before["role"] == "student" and "student_id" in updates:
            updates["username"] = updates["student_id"]

        cols = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [user_id]
        with self._conn:
            self._conn.execute(f"UPDATE users SET {cols} WHERE id = ?", vals)
            
            # Sync to students table if student
            if user_before and user_before["role"] == "student":
                orig_matric = user_before["student_id"] if user_before["student_id"] else user_before["username"]
                stud_updates = {}
                if "full_name" in updates:
                    stud_updates["full_name"] = updates["full_name"]
                if "student_id" in updates:
                    stud_updates["matric_number"] = updates["student_id"]
                if "department" in updates:
                    stud_updates["department"] = updates["department"]
                if "faculty" in updates:
                    stud_updates["faculty"] = updates["faculty"]
                
                if stud_updates:
                    s_cols = ", ".join(f"{k} = ?" for k in stud_updates)
                    s_vals = list(stud_updates.values()) + [orig_matric]
                    self._conn.execute(f"UPDATE students SET {s_cols} WHERE matric_number = ?", s_vals)
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
                     schedule: str = None, room: str = None, department: str = None) -> int:
        with self._conn:
            cur = self._conn.execute(
                """INSERT INTO classes (name, code, lecturer_id, schedule, room, department)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, code, lecturer_id, schedule, room, department),
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

    def get_classes(self, lecturer_id: int = None, department: str = None, faculty_id: int = None) -> list:
        """Return all classes, optionally filtered by lecturer / department / faculty."""
        clauses, params = [], []
        if lecturer_id:
            clauses.append("c.lecturer_id = ?")
            params.append(lecturer_id)
        if department:
            clauses.append("c.department = ?")
            params.append(department)
        if faculty_id:
            clauses.append("d.faculty_id = ?")
            params.append(faculty_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"""SELECT c.*, u.full_name AS lecturer_name,
                       f.name AS faculty_name,
                       (SELECT COUNT(*) FROM enrollments WHERE class_id = c.id) AS enrolled_count
                FROM classes c
                LEFT JOIN users u ON c.lecturer_id = u.id
                LEFT JOIN departments d ON d.name = c.department
                LEFT JOIN faculties f ON f.id = d.faculty_id
                {where}
                ORDER BY c.code""",
            tuple(params),
        ).fetchall()
        return self._rows_to_list(rows)

    def get_browse_classes(self, student_id: int, department: str = None, faculty_id: int = None) -> list:
        """All classes with per-student enrolled flag, for course registration."""
        clauses, params = [], []
        if department:
            clauses.append("c.department = ?")
            params.append(department)
        if faculty_id:
            clauses.append("d.faculty_id = ?")
            params.append(faculty_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        # NOTE: student_id placeholder comes first (SELECT clause precedes WHERE)
        params = [student_id, *params]
        rows = self._conn.execute(
            f"""SELECT c.*, u.full_name AS lecturer_name,
                       f.name AS faculty_name,
                       (SELECT COUNT(*) FROM enrollments WHERE class_id = c.id) AS enrolled_count,
                       EXISTS(SELECT 1 FROM enrollments WHERE class_id = c.id AND student_id = ?) AS is_enrolled
                FROM classes c
                LEFT JOIN users u ON c.lecturer_id = u.id
                LEFT JOIN departments d ON d.name = c.department
                LEFT JOIN faculties f ON f.id = d.faculty_id
                {where}
                ORDER BY c.code""",
            tuple(params),
        ).fetchall()
        out = []
        for r in self._rows_to_list(rows):
            r["is_enrolled"] = bool(r.pop("is_enrolled"))
            out.append(r)
        return out

    def update_class(self, class_id: int, **fields) -> bool:
        allowed = {"name", "code", "lecturer_id", "schedule", "room", "department"}
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

    def get_roster(self, lecturer_id: int = None) -> list:
        """Students with the courses they take. Scoped to a lecturer's
        classes when lecturer_id is given, otherwise the whole school."""
        clauses, params = ["u.role = 'student'"], []
        if lecturer_id:
            clauses.append("c.lecturer_id = ?")
            params.append(lecturer_id)
        where = f"WHERE {' AND '.join(clauses)}"
        rows = self._conn.execute(
            f"""SELECT u.id, u.full_name, u.student_id, u.email, u.department,
                       u.face_enrolled, c.id AS cid, c.code AS ccode, c.name AS cname
                FROM users u
                JOIN enrollments e ON e.student_id = u.id
                JOIN classes c ON c.id = e.class_id
                {where}
                ORDER BY u.full_name, c.code""",
            tuple(params),
        ).fetchall()
        grouped: dict = {}
        for r in rows:
            sid = r["id"]
            if sid not in grouped:
                grouped[sid] = {
                    "id": sid,
                    "full_name": r["full_name"],
                    "student_id": r["student_id"],
                    "email": r["email"],
                    "department": r["department"],
                    "face_enrolled": r["face_enrolled"],
                    "classes": [],
                }
            grouped[sid]["classes"].append({"id": r["cid"], "code": r["ccode"], "name": r["cname"]})
        return list(grouped.values())

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

    # ------------------------------------------------------------------ #
    #  Faculties & Departments CRUD                                       #
    # ------------------------------------------------------------------ #

    def get_faculties(self) -> list:
        rows = self._conn.execute("SELECT * FROM faculties ORDER BY name").fetchall()
        return self._rows_to_list(rows)

    def get_departments(self, faculty_id: int = None) -> list:
        if faculty_id:
            rows = self._conn.execute("SELECT * FROM departments WHERE faculty_id = ? ORDER BY name", (faculty_id,)).fetchall()
        else:
            rows = self._conn.execute(
                """SELECT d.*, f.name as faculty_name 
                   FROM departments d 
                   JOIN faculties f ON d.faculty_id = f.id 
                   ORDER BY f.name, d.name"""
            ).fetchall()
        return self._rows_to_list(rows)

    def create_faculty(self, name: str) -> int:
        with self._conn:
            cur = self._conn.execute("INSERT INTO faculties (name) VALUES (?)", (name.strip(),))
            return cur.lastrowid

    def create_department(self, faculty_id: int, name: str) -> int:
        with self._conn:
            cur = self._conn.execute("INSERT INTO departments (faculty_id, name) VALUES (?, ?)", (faculty_id, name.strip()))
            return cur.lastrowid

    def delete_faculty(self, id: int):
        with self._conn:
            self._conn.execute("DELETE FROM faculties WHERE id = ?", (id,))

    def delete_department(self, id: int):
        with self._conn:
            self._conn.execute("DELETE FROM departments WHERE id = ?", (id,))

    # ------------------------------------------------------------------ #
    #  Class blocks (lecturer-controlled)                                  #
    # ------------------------------------------------------------------ #

    def block_student(self, class_id: int, student_id: int, blocked_by: int, reason: str = None) -> bool:
        try:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO class_blocks (class_id, student_id, blocked_by, reason) VALUES (?, ?, ?, ?)",
                    (class_id, student_id, blocked_by, reason),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def unblock_student(self, class_id: int, student_id: int) -> bool:
        with self._conn:
            cur = self._conn.execute("DELETE FROM class_blocks WHERE class_id = ? AND student_id = ?", (class_id, student_id))
            return cur.rowcount > 0

    def is_blocked(self, class_id: int, student_id: int) -> bool:
        row = self._conn.execute("SELECT id FROM class_blocks WHERE class_id = ? AND student_id = ?", (class_id, student_id)).fetchone()
        return row is not None

    def get_blocked(self, class_id: int) -> list:
        rows = self._conn.execute(
            """SELECT b.*, u.full_name, u.student_id AS matric, ub.full_name AS blocked_by_name
               FROM class_blocks b JOIN users u ON b.student_id=u.id
               LEFT JOIN users ub ON b.blocked_by=ub.id WHERE b.class_id=? ORDER BY b.created_at DESC""",
            (class_id,)
        ).fetchall()
        return self._rows_to_list(rows)

    # ------------------------------------------------------------------ #
    #  Lecturer assignment                                                 #
    # ------------------------------------------------------------------ #

    def assign_lecturer(self, class_id: int, lecturer_id: int) -> bool:
        with self._conn:
            self._conn.execute("UPDATE classes SET lecturer_id=? WHERE id=?", (lecturer_id, class_id))
        return True

    def get_unassigned_classes(self) -> list:
        rows = self._conn.execute("SELECT * FROM classes WHERE lecturer_id IS NULL ORDER BY code").fetchall()
        return self._rows_to_list(rows)

    # ------------------------------------------------------------------ #
    #  Security Q / emergency PIN (hashed, admin-opaque)                    #
    # ------------------------------------------------------------------ #

    def set_security(self, user_id: int, question: str, answer: str, pin: str) -> bool:
        # Hash both with random salt via _hash
        answer_hash = _hash(answer.strip().lower()) if answer else None
        pin_hash = _hash(pin.strip()) if pin else None
        q = question.strip() if question else None
        with self._conn:
            self._conn.execute(
                "UPDATE users SET security_question=?, security_answer_hash=?, emergency_pin_hash=? WHERE id=?",
                (q, answer_hash, pin_hash, user_id),
            )
        return True

    def has_security(self, user_id: int) -> bool:
        row = self._conn.execute("SELECT security_question, security_answer_hash, emergency_pin_hash FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return False
        return bool(row["security_question"] or row["emergency_pin_hash"])

    def verify_security(self, identifier: str, answer: str = None, pin: str = None) -> dict | None:
        row = self._conn.execute("SELECT * FROM users WHERE username=? OR student_id=? OR email=?", (identifier, identifier, identifier)).fetchone()
        if not row:
            return None
        # Check answer or pin (either suffices)
        if answer and row["security_answer_hash"]:
            if _verify(answer.strip().lower(), row["security_answer_hash"]):
                return self._row_to_dict(row)
        if pin and row["emergency_pin_hash"]:
            if _verify(pin.strip(), row["emergency_pin_hash"]):
                return self._row_to_dict(row)
        return None

    def reset_password_via_security(self, identifier: str, new_password: str, answer: str = None, pin: str = None) -> bool:
        user = self.verify_security(identifier, answer, pin)
        if not user:
            return False
        self.update_password(user["id"], new_password)
        return True
