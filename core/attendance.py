"""
Attendance Manager.
Handles recording, storing, and exporting attendance records.
"""

import csv
import os
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AttendanceManager:
    """Manages attendance records with CSV storage and session deduplication."""

    def __init__(self, attendance_dir, duplicate_prevention=True):
        """
        Args:
            attendance_dir: Directory to store attendance CSV files.
            duplicate_prevention: If True, prevent duplicate entries per session.
        """
        self.attendance_dir = attendance_dir
        self.duplicate_prevention = duplicate_prevention
        self.session_log = set()
        self.current_subject = None
        self.current_date = None
        os.makedirs(attendance_dir, exist_ok=True)

    def start_session(self, subject):
        """
        Start a new attendance session.

        Args:
            subject: Subject/class name for this session.
        """
        self.current_subject = subject
        self.current_date = datetime.now().strftime("%Y-%m-%d")
        self.session_log = set()
        logger.info("Session started: %s on %s", subject, self.current_date)

    def mark_attendance(self, name):
        """
        Record attendance for a person.

        Args:
            name: Person's name/ID.

        Returns:
            True if attendance was recorded, False if duplicate/prevented.
        """
        if self.duplicate_prevention and name in self.session_log:
            return False

        now = datetime.now()
        timestamp = now.strftime("%H:%M:%S")
        date_str = now.strftime("%Y-%m-%d")

        self.session_log.add(name)
        self._write_csv(name, date_str, timestamp)
        logger.info("Attendance recorded: %s at %s %s", name, date_str, timestamp)
        return True

    def _write_csv(self, name, date, time_str):
        """Write a single attendance record to CSV."""
        if not self.current_subject:
            logger.warning("No active session")
            return

        filename = f"{self.current_subject}_{self.current_date}.csv"
        filepath = os.path.join(self.attendance_dir, filename)

        file_exists = os.path.exists(filepath)
        with open(filepath, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Name", "Date", "Time"])
            writer.writerow([name, date, time_str])

    def get_session_log(self):
        """Get current session attendance as a list of dicts."""
        records = []
        for name in sorted(self.session_log):
            records.append({
                "name": name,
                "subject": self.current_subject,
                "date": self.current_date,
            })
        return records

    def get_attendance_file(self, subject=None, date=None):
        """
        Get the path to an attendance CSV file.

        Args:
            subject: Subject name (uses current if None).
            date: Date string (uses today if None).

        Returns:
            Path to the CSV file.
        """
        subject = subject or self.current_subject
        date = date or self.current_date
        filename = f"{subject}_{date}.csv"
        return os.path.join(self.attendance_dir, filename)

    def read_attendance(self, filepath):
        """
        Read an attendance CSV file.

        Args:
            filepath: Path to CSV file.

        Returns:
            List of dicts with attendance records.
        """
        records = []
        if not os.path.exists(filepath):
            return records

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)
        return records

    def get_summary(self, subject=None, date=None):
        """
        Get attendance summary statistics.

        Returns:
            Dict with total_present, unique_names, records.
        """
        filepath = self.get_attendance_file(subject, date)
        records = self.read_attendance(filepath)
        names = [r["Name"] for r in records if "Name" in r]
        return {
            "total_present": len(names),
            "unique_names": len(set(names)),
            "records": records,
        }

    def export_to_csv(self, filepath):
        """Export current session log to a specific file."""
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Name", "Subject", "Date"])
            for name in sorted(self.session_log):
                writer.writerow([name, self.current_subject, self.current_date])
        logger.info("Exported attendance to %s", filepath)

    def clear_session(self):
        """Clear the current session log."""
        self.session_log.clear()
        logger.info("Session log cleared")
