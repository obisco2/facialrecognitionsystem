"""Tests for core.database — DatabaseManager CRUD, auth, and attendance."""

import os
import tempfile
import pytest
from core.database import DatabaseManager, _hash, _verify


@pytest.fixture
def db(tmp_path):
    """Create a fresh in-memory-like temp database for each test."""
    db_path = str(tmp_path / "test.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.close()


@pytest.fixture
def db_with_user(db):
    """Database with a test student pre-created."""
    user_id = db.create_user(
        username="teststudent",
        password="password123",
        role="student",
        full_name="Test Student",
        student_id="STU001",
    )
    return db, user_id


# --- Password Hashing ---

class TestPasswordHashing:
    def test_hash_returns_salt_and_digest(self):
        result = _hash("mypassword")
        assert ":" in result
        salt, digest = result.split(":")
        assert len(salt) == 32  # 16 bytes hex
        assert len(digest) == 64  # 32 bytes hex

    def test_hash_is_deterministic_with_same_salt(self):
        salt = "a" * 32
        h1 = _hash("password", salt)
        h2 = _hash("password", salt)
        assert h1 == h2

    def test_hash_differs_with_different_salts(self):
        h1 = _hash("password", "a" * 32)
        h2 = _hash("password", "b" * 32)
        assert h1 != h2

    def test_verify_correct_password(self):
        hashed = _hash("correct_password")
        assert _verify("correct_password", hashed) is True

    def test_verify_wrong_password(self):
        hashed = _hash("correct_password")
        assert _verify("wrong_password", hashed) is False

    def test_verify_legacy_sha256(self):
        import hashlib
        legacy = hashlib.sha256("old_password".encode()).hexdigest()
        assert _verify("old_password", legacy) is True
        assert _verify("wrong_password", legacy) is False


# --- User Management ---

class TestUserCreation:
    def test_create_user_returns_id(self, db):
        user_id = db.create_user("alice", "pass123", "student", "Alice Smith",
                                 student_id="MAT001", email="alice@unilag.edu.ng")
        assert isinstance(user_id, int)
        assert user_id > 0

    def test_create_user_stores_correctly(self, db):
        user_id = db.create_user("bob", "pass456", "lecturer", "Bob Jones", title="Dr.")
        user = db.get_user(user_id)
        assert user["username"] == "bob"
        assert user["role"] == "lecturer"
        assert user["full_name"] == "Bob Jones"
        assert user["title"] == "Dr."

    def test_create_duplicate_username_raises(self, db):
        db.create_user("charlie", "pass", "student", "Charlie",
                       student_id="MAT002", email="charlie@unilag.edu.ng")
        with pytest.raises(ValueError, match="already taken"):
            db.create_user("charlie", "pass2", "student", "Charlie 2",
                           student_id="MAT003", email="charlie2@unilag.edu.ng")

    def test_create_student_requires_matric(self, db):
        with pytest.raises(ValueError, match="Matric number"):
            db.create_user("dave", "pass", "student", "Dave Lee")

    def test_create_student_requires_email(self, db):
        with pytest.raises(ValueError, match="Email"):
            db.create_user("dave", "pass", "student", "Dave Lee", student_id="MAT004")

    def test_create_student_creates_students_table_entry(self, db):
        user_id = db.create_user("dave", "pass", "student", "Dave Lee",
                                 student_id="MAT005", email="dave@unilag.edu.ng")
        user = db.get_user(user_id)
        matric = user["student_id"]
        row = db._conn.execute(
            "SELECT * FROM students WHERE matric_number = ?", (matric,)
        ).fetchone()
        assert row is not None

    def test_create_lecturer_with_title(self, db):
        user_id = db.create_user("prof_smith", "pass", "lecturer", "John Smith", title="Prof.")
        user = db.get_user(user_id)
        assert user["title"] == "Prof."


class TestAuthentication:
    def test_authenticate_by_username(self, db):
        db.create_user("eve", "secret", "student", "Eve Davis",
                       student_id="MAT010", email="eve@unilag.edu.ng")
        result = db.authenticate("eve", "secret")
        assert result is not None
        assert result["username"] == "eve"

    def test_authenticate_by_matric_number(self, db):
        db.create_user("frank", "secret", "student", "Frank",
                       student_id="MAT011", email="frank@unilag.edu.ng")
        result = db.authenticate("MAT011", "secret")
        assert result is not None
        assert result["username"] == "frank"

    def test_authenticate_by_email(self, db):
        db.create_user("grace", "secret", "student", "Grace",
                       student_id="MAT012", email="grace@unilag.edu.ng")
        result = db.authenticate("grace@unilag.edu.ng", "secret")
        assert result is not None
        assert result["username"] == "grace"

    def test_authenticate_wrong_password(self, db):
        db.create_user("hank", "secret", "student", "Hank",
                       student_id="MAT013", email="hank@unilag.edu.ng")
        result = db.authenticate("hank", "wrong")
        assert result is None

    def test_authenticate_nonexistent_user(self, db):
        result = db.authenticate("nobody", "pass")
        assert result is None

    def test_authenticate_upgrades_legacy_hash(self, db):
        import hashlib
        # Manually insert a legacy SHA-256 hash
        legacy_hash = hashlib.sha256("mypassword".encode()).hexdigest()
        with db._conn:
            db._conn.execute(
                "INSERT INTO users (username, password_hash, role, full_name, student_id, email) VALUES (?, ?, ?, ?, ?, ?)",
                ("legacy_user", legacy_hash, "student", "Legacy User", "MAT099", "legacy@unilag.edu.ng"),
            )
        result = db.authenticate("legacy_user", "mypassword")
        assert result is not None
        # Verify hash was upgraded
        row = db._conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", ("legacy_user",)
        ).fetchone()
        assert ":" in row["password_hash"]  # Now has salt:digest format


class TestUserUpdates:
    def test_update_user_field(self, db):
        user_id = db.create_user("irene", "pass", "student", "Grace Hopper",
                                 student_id="MAT020", email="irene@unilag.edu.ng")
        db.update_user(user_id, full_name="Grace Brewster")
        user = db.get_user(user_id)
        assert user["full_name"] == "Grace Brewster"

    def test_update_password(self, db):
        user_id = db.create_user("james", "old_pass", "student", "James",
                                 student_id="MAT021", email="james@unilag.edu.ng")
        db.update_password(user_id, "new_pass")
        result = db.authenticate("james", "new_pass")
        assert result is not None

    def test_delete_user(self, db):
        user_id = db.create_user("karen", "pass", "student", "Karen",
                                 student_id="MAT022", email="karen@unilag.edu.ng")
        db.delete_user(user_id)
        user = db.get_user(user_id)
        assert user is None


# --- Class Management ---

class TestClassManagement:
    def test_create_class(self, db):
        lecturer_id = db.create_user("lect1", "pass", "lecturer", "Dr. Smith", title="Dr.")
        class_id = db.create_class("AI", "CS401", lecturer_id)
        assert class_id > 0

    def test_get_class(self, db):
        lecturer_id = db.create_user("lect2", "pass", "lecturer", "Dr. Jones", title="Dr.")
        class_id = db.create_class("ML", "CS402", lecturer_id, schedule="Mon 10am")
        cls = db.get_class(class_id)
        assert cls["name"] == "ML"
        assert cls["code"] == "CS402"

    def test_delete_class(self, db):
        lecturer_id = db.create_user("lect3", "pass", "lecturer", "Dr. Lee", title="Dr.")
        class_id = db.create_class("DL", "CS403", lecturer_id)
        db.delete_class(class_id)
        cls = db.get_class(class_id)
        assert cls is None


# --- Enrollment ---

class TestEnrollment:
    def test_enroll_student(self, db):
        student_id = db.create_user("stu1", "pass", "student", "Student One",
                                    student_id="MAT030", email="stu1@unilag.edu.ng")
        lecturer_id = db.create_user("lec1", "pass", "lecturer", "Lecturer One")
        class_id = db.create_class("Class A", "CA101", lecturer_id)
        result = db.enroll_student(student_id, class_id)
        assert result is True

    def test_enroll_duplicate_returns_false(self, db):
        student_id = db.create_user("stu2", "pass", "student", "Student Two",
                                    student_id="MAT031", email="stu2@unilag.edu.ng")
        lecturer_id = db.create_user("lec2", "pass", "lecturer", "Lecturer Two")
        class_id = db.create_class("Class B", "CB101", lecturer_id)
        db.enroll_student(student_id, class_id)
        result = db.enroll_student(student_id, class_id)
        assert result is False

    def test_get_enrolled_students(self, db):
        s1 = db.create_user("s1", "pass", "student", "Alice",
                             student_id="MAT032", email="s1@unilag.edu.ng")
        s2 = db.create_user("s2", "pass", "student", "Bob",
                             student_id="MAT033", email="s2@unilag.edu.ng")
        lec = db.create_user("l1", "pass", "lecturer", "Dr. X")
        cid = db.create_class("Test", "T101", lec)
        db.enroll_student(s1, cid)
        db.enroll_student(s2, cid)
        enrolled = db.get_enrolled_students(cid)
        assert len(enrolled) == 2


# --- Attendance ---

class TestAttendance:
    def test_log_attendance(self, db):
        s = db.create_user("att1", "pass", "student", "Att Student",
                            student_id="MAT040", email="att1@unilag.edu.ng")
        l = db.create_user("att_lec", "pass", "lecturer", "Att Lecturer")
        c = db.create_class("Att Class", "AC101", l)
        log_id = db.log_attendance(s, c, session_date="2026-01-15", method="face")
        assert log_id is not None

    def test_log_attendance_duplicate_returns_none(self, db):
        s = db.create_user("att2", "pass", "student", "Att2",
                            student_id="MAT041", email="att2@unilag.edu.ng")
        l = db.create_user("att_lec2", "pass", "lecturer", "Lec2")
        c = db.create_class("Att2", "AC201", l)
        db.log_attendance(s, c, session_date="2026-01-15")
        result = db.log_attendance(s, c, session_date="2026-01-15")
        assert result is None

    def test_get_attendance(self, db):
        s = db.create_user("att3", "pass", "student", "Att3",
                            student_id="MAT042", email="att3@unilag.edu.ng")
        l = db.create_user("att_lec3", "pass", "lecturer", "Lec3")
        c = db.create_class("Att3", "AC301", l)
        db.log_attendance(s, c, session_date="2026-01-15")
        rows = db.get_attendance(c, "2026-01-15")
        assert len(rows) == 1

    def test_get_attendance_summary(self, db):
        s = db.create_user("att4", "pass", "student", "Att4",
                            student_id="MAT043", email="att4@unilag.edu.ng")
        l = db.create_user("att_lec4", "pass", "lecturer", "Lec4")
        c = db.create_class("Att4", "AC401", l)
        db.enroll_student(s, c)
        db.log_attendance(s, c, session_date="2026-01-15")
        summary = db.get_attendance_summary(c, "2026-01-15")
        assert summary["present"] == 1
        assert summary["total_enrolled"] == 1
        assert summary["percent"] == 100.0


# --- System Stats ---

class TestSystemStats:
    def test_get_system_stats(self, db):
        stats = db.get_system_stats()
        assert "total_users" in stats
        assert "total_students" in stats
        assert stats["total_users"] >= 0
