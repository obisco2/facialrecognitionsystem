"""
Recognition Engine.
Combines face detection and encoding for real-time identification.
"""

import cv2
import numpy as np
import time
import logging

from .face_detector import FaceDetector
from .face_encoder import FaceEncoder

logger = logging.getLogger(__name__)


class Recognizer:
    """Real-time face recognition engine with threaded camera support."""

    def __init__(self, detector=None, encoder=None, tolerance=0.6, model="haar"):
        """
        Args:
            detector: FaceDetector instance (created if None).
            encoder: FaceEncoder instance (created if None).
            tolerance: Match threshold (lower = stricter).
            model: Detection model ('haar' or 'dnn').
        """
        self.detector = detector or FaceDetector(model=model)
        self.encoder = encoder or FaceEncoder(model=model, tolerance=tolerance)
        self.camera = None
        self.camera_running = False
        self._frame = None
        self._face_locations = []
        self._face_names = []
        self._face_distances = []

    def load_database(self, directory, flat=False):
        """
        Load known faces from directory.

        Args:
            directory: Path to known faces directory.
            flat: If True, treat as flat directory (one image per person).
        """
        if flat:
            encs, names = self.encoder.load_single_images(directory)
        else:
            encs, names = self.encoder.load_known_faces(directory)
        logger.info("Loaded %d encodings for %d unique persons",
                     len(encs), len(set(names)) if names else 0)
        return len(encs)

    def start_camera(self, camera_index=0):
        """Open the webcam."""
        self.camera = cv2.VideoCapture(camera_index)
        if not self.camera.isOpened():
            logger.error("Cannot open camera %d", camera_index)
            return False
        self.camera_running = True
        logger.info("Camera %d opened", camera_index)
        return True

    def stop_camera(self):
        """Release the webcam."""
        self.camera_running = False
        if self.camera:
            self.camera.release()
            self.camera = None
        cv2.destroyAllWindows()
        logger.info("Camera released")

    def process_frame(self, frame, scale=0.25):
        """
        Process a single frame: detect and identify faces.

        Args:
            frame: BGR numpy array.
            scale: Downscale factor for faster detection.

        Returns:
            Tuple of (face_locations, face_names, face_distances).
        """
        small = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
        face_locations = self.detector.detect_faces(small)

        names = []
        distances = []
        for (top, right, bottom, left) in face_locations:
            # Scale back to original coordinates
            top_o = int(top / scale)
            right_o = int(right / scale)
            bottom_o = int(bottom / scale)
            left_o = int(left / scale)

            # Ensure bounds
            h, w = frame.shape[:2]
            top_o = max(0, min(top_o, h - 1))
            right_o = max(0, min(right_o, w - 1))
            bottom_o = max(0, min(bottom_o, h))
            left_o = max(0, min(left_o, w))

            face_img = frame[top_o:bottom_o, left_o:right_o]
            if face_img.size == 0:
                names.append("Unknown")
                distances.append(None)
                continue

            encoding = self.encoder.compute_encoding(face_img)
            if encoding is not None:
                name, dist = self.encoder.identify(encoding)
                names.append(name)
                distances.append(dist)
            else:
                names.append("Unknown")
                distances.append(None)

        self._face_locations = face_locations
        self._face_names = names
        self._face_distances = distances
        return face_locations, names, distances

    def read_frame(self):
        """Read a frame from the camera."""
        if not self.camera or not self.camera.isOpened():
            return False, None
        return self.camera.read()

    def run_once(self, camera_index=0, scale=0.25):
        """Single-frame capture and recognition."""
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            return None

        ret, frame = cap.read()
        cap.release()

        if not ret:
            return None

        locations, names, distances = self.process_frame(frame, scale)
        return frame, locations, names, distances

    @property
    def current_frame(self):
        return self._frame

    @property
    def current_results(self):
        return self._face_locations, self._face_names, self._face_distances
