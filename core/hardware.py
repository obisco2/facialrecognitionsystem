"""
Hardware hooks for AttendIQ — Tobi.
Buzzer beep on verification, PIR motion-sensor input, second-camera slot.

Everything here is safe to run with NO hardware attached: all calls are
guarded and degrade to log lines. Wire real devices later:
  - buzzer: Raspberry Pi GPIO pin (gpiozero.Buzzer) or USB relay
  - motion: PIR sensor HTTP webhook -> POST /api/hardware/motion
  - camera 2: entrance/exit camera (index or RTSP URL in config.ini)
"""
import logging
import platform
import time

logger = logging.getLogger(__name__)


def beep(duration_ms: int = 180, freq_hz: int = 880) -> bool:
    """Short verification beep on the machine running the server.

    Returns True if a beep was actually emitted, False if no audio
    device path exists (headless VPS, CI). Never raises.
    """
    try:
        if platform.system() == "Windows":
            import winsound
            winsound.Beep(freq_hz, duration_ms)
            return True
        # Linux/macOS: terminal bell as fallback; a Pi buzzer can
        # replace this branch (gpiozero.Buzzer(pin).beep(...)).
        print("\a", end="", flush=True)
        return False
    except Exception as e:
        logger.debug("beep skipped: %s", e)
        return False


class MotionSensor:
    """Placeholder PIR motion sensor.

    Real deployment: PIR module posts to POST /api/hardware/motion
    (or GPIO edge callback calls report_motion()). Until then,
    last_motion_at stays None and presence falls back to face sightings.
    """

    def __init__(self):
        self.last_motion_at: float | None = None
        self.events_total = 0

    def report_motion(self) -> dict:
        self.last_motion_at = time.time()
        self.events_total += 1
        return {"motion": True, "at": self.last_motion_at, "total": self.events_total}

    def seconds_since_motion(self) -> float | None:
        if self.last_motion_at is None:
            return None
        return time.time() - self.last_motion_at

    def status(self) -> dict:
        return {
            "attached": self.last_motion_at is not None or self.events_total > 0,
            "last_motion_at": self.last_motion_at,
            "seconds_since_motion": self.seconds_since_motion(),
            "events_total": self.events_total,
            "note": "Placeholder — POST /api/hardware/motion to feed a PIR sensor.",
        }


class SecondCamera:
    """Placeholder second camera (exit/entrance coverage).

    Configure in config.ini [Hardware]: SECOND_CAMERA_INDEX (int, -1
    disables) or SECOND_STREAM_URL (RTSP/HTTP). The streamer does not
    open it yet — this stub reserves config + status surface so the
    frontend can show 'Camera 2: planned' instead of silently ignoring it.
    """

    def __init__(self, get_config):
        self._get_config = get_config

    def status(self) -> dict:
        try:
            cfg = self._get_config()
            index = cfg.getint("Hardware", "SECOND_CAMERA_INDEX", -1)
            url = cfg.get("Hardware", "SECOND_STREAM_URL", "").strip()
        except Exception:
            index, url = -1, ""
        configured = bool(url) or index >= 0
        return {
            "configured": configured,
            "active": False,
            "index": index,
            "url_set": bool(url),
            "note": "Placeholder — second-camera capture not yet wired into CameraStreamer.",
        }


motion_sensor = MotionSensor()
