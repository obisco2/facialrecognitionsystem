"""Tests for core.config — Config singleton and property access."""

import os
import tempfile
import pytest
from core.config import Config


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the Config singleton before each test."""
    Config._instance = None
    Config._config = None
    yield
    Config._instance = None
    Config._config = None


class TestConfigSingleton:
    def test_singleton_returns_same_instance(self):
        c1 = Config()
        c2 = Config()
        assert c1 is c2

    def test_singleton_has_config_loaded(self):
        c = Config()
        assert c._config is not None


class TestConfigDefaults:
    def test_default_db_path(self):
        c = Config()
        assert "users.db" in c.db_path

    def test_default_tolerance(self):
        c = Config()
        assert c.tolerance == 0.6

    def test_default_frame_scale(self):
        c = Config()
        assert c.frame_scale == 0.25

    def test_default_camera_index(self):
        c = Config()
        assert c.camera_index == 0

    def test_default_recognition_engine(self):
        c = Config()
        assert c.recognition_engine == "auto"

    def test_default_app_name(self):
        c = Config()
        assert c.app_name == "AttendIQ"

    def test_default_admin_password(self):
        c = Config()
        assert c.admin_password == "admin"


class TestConfigGetSet:
    def test_get_returns_value(self):
        c = Config()
        val = c.get("Camera", "CAMERA_INDEX", fallback="0")
        assert val is not None

    def test_get_with_fallback(self):
        c = Config()
        val = c.get("Nonexistent", "KEY", fallback="default")
        assert val == "default"

    def test_set_and_get(self):
        c = Config()
        c.set("TestSection", "TestKey", "test_value")
        val = c.get("TestSection", "TestKey")
        assert val == "test_value"


class TestConfigProperties:
    def test_base_dir_exists(self):
        c = Config()
        assert os.path.isdir(c.base_dir)

    def test_known_faces_dir_is_absolute(self):
        c = Config()
        assert os.path.isabs(c.known_faces_dir)

    def test_ensure_dirs_creates_directories(self):
        c = Config()
        c.ensure_dirs()
        assert os.path.isdir(c.known_faces_dir)
        assert os.path.isdir(c.training_dir)
        assert os.path.isdir(c.attendance_dir)
