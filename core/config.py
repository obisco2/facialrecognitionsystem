"""
Configuration Manager for Face Recognition System.
Loads settings from config.ini with sensible defaults.
"""

import os
import configparser


class Config:
    """Centralized configuration loader with fallback defaults."""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        self._config = configparser.ConfigParser()
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.ini")
        if os.path.exists(config_path):
            self._config.read(config_path)
        else:
            self._create_default(config_path)

    def _create_default(self, path):
        self._config["Paths"] = {
            "KNOWN_FACES_DIR": "data/known_faces",
            "TRAINING_DIR": "data/training",
            "ATTENDANCE_DIR": "data/attendance",
            "MODELS_DIR": "models",
        }
        self._config["Database"] = {
            "DB_PATH": "data/users.db",
        }
        self._config["Camera"] = {
            "CAMERA_INDEX": "0",
            "FRAME_SCALE": "0.25",
            "FRAME_WIDTH": "640",
            "FRAME_HEIGHT": "480",
            "STREAM_URL": "",
        }
        self._config["Recognition"] = {
            "TOLERANCE": "0.6",
            "MODEL": "hog",
            "ENGINE": "auto",
            "NUMBER_OF_SAMPLES": "100",
            "FACE_PADDING": "20",
            "MIN_ENROLLMENT_PHOTOS": "5",
        }
        self._config["Attendance"] = {
            "SESSION_TIMEOUT": "60",
            "DUPLICATE_PREVENTION": "true",
            "EXPORT_FORMAT": "csv",
        }
        self._config["Security"] = {"ADMIN_PASSWORD": "admin"}
        self._config["UI"] = {"THEME": "dark", "APP_NAME": "AttendIQ"}
        self._config["Logging"] = {"LEVEL": "INFO", "FILE": "face_recog.log"}
        with open(path, "w") as f:
            self._config.write(f)

    def get(self, section, key, fallback=None):
        return self._config.get(section, key, fallback=fallback)

    def getint(self, section, key, fallback=0):
        return self._config.getint(section, key, fallback=fallback)

    def getfloat(self, section, key, fallback=0.0):
        return self._config.getfloat(section, key, fallback=fallback)

    def getboolean(self, section, key, fallback=False):
        return self._config.getboolean(section, key, fallback=fallback)

    @property
    def base_dir(self):
        return os.path.dirname(os.path.dirname(__file__))

    @property
    def known_faces_dir(self):
        return os.path.join(self.base_dir, self.get("Paths", "KNOWN_FACES_DIR"))

    @property
    def training_dir(self):
        return os.path.join(self.base_dir, self.get("Paths", "TRAINING_DIR"))

    @property
    def attendance_dir(self):
        return os.path.join(self.base_dir, self.get("Paths", "ATTENDANCE_DIR"))

    @property
    def models_dir(self):
        return os.path.join(self.base_dir, self.get("Paths", "MODELS_DIR"))

    @property
    def camera_index(self):
        return self.getint("Camera", "CAMERA_INDEX", 0)

    @property
    def frame_scale(self):
        return self.getfloat("Camera", "FRAME_SCALE", 0.25)

    @property
    def tolerance(self):
        return self.getfloat("Recognition", "TOLERANCE", 0.6)

    @property
    def recognition_model(self):
        return self.get("Recognition", "MODEL", "hog")

    @property
    def num_samples(self):
        return self.getint("Recognition", "NUMBER_OF_SAMPLES", 100)

    @property
    def face_padding(self):
        return self.getint("Recognition", "FACE_PADDING", 20)

    @property
    def session_timeout(self):
        return self.getint("Attendance", "SESSION_TIMEOUT", 60)

    @property
    def admin_password(self):
        return self.get("Security", "ADMIN_PASSWORD", "admin")

    @property
    def jwt_secret(self):
        import os
        return os.getenv("JWT_SECRET") or self.get("Security", "JWT_SECRET", "dev-insecure-change-me")

    @property
    def jwt_refresh_secret(self):
        import os
        return os.getenv("JWT_REFRESH_SECRET") or self.get("Security", "JWT_REFRESH_SECRET", "dev-insecure-refresh-change-me")

    @property
    def access_token_expire_minutes(self):
        return self.getint("Security", "ACCESS_TOKEN_EXPIRE_MINUTES", 15)

    @property
    def refresh_token_expire_days(self):
        return self.getint("Security", "REFRESH_TOKEN_EXPIRE_DAYS", 7)

    @property
    def db_path(self):
        return os.path.join(self.base_dir, self.get("Database", "DB_PATH", "data/users.db"))

    @property
    def stream_url(self):
        return self.get("Camera", "STREAM_URL", "").strip()

    @property
    def recognition_engine(self):
        return self.get("Recognition", "ENGINE", "auto")

    @property
    def min_enrollment_photos(self):
        return self.getint("Recognition", "MIN_ENROLLMENT_PHOTOS", 5)

    @property
    def app_name(self):
        return self.get("UI", "APP_NAME", "AttendIQ")

    def set(self, section: str, key: str, value: str):
        """Persist a config value to disk."""
        if not self._config.has_section(section):
            self._config.add_section(section)
        self._config.set(section, key, value)
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.ini")
        with open(config_path, "w") as f:
            self._config.write(f)

    def ensure_dirs(self):
        for d in [self.known_faces_dir, self.training_dir, self.attendance_dir, self.models_dir]:
            os.makedirs(d, exist_ok=True)
        # Ensure DB directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
