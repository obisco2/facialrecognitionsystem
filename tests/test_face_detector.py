"""Tests for core.face_detector — FaceDetector with Haar cascade."""

import numpy as np
import cv2
import pytest
from core.face_detector import FaceDetector


@pytest.fixture
def detector():
    """Create a Haar cascade detector for testing."""
    return FaceDetector(model="haar")


@pytest.fixture
def blank_image():
    """Create a blank 640x480 BGR image (no faces)."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def face_image():
    """Create an image with a synthetic face-like pattern."""
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    # Draw a face-like oval
    cv2.ellipse(img, (150, 150), (80, 100), 0, 0, 360, (200, 180, 160), -1)
    # Eyes
    cv2.circle(img, (120, 130), 10, (50, 50, 50), -1)
    cv2.circle(img, (180, 130), 10, (50, 50, 50), -1)
    # Mouth
    cv2.ellipse(img, (150, 190), (30, 15), 0, 0, 180, (50, 50, 50), 2)
    return img


class TestFaceDetectorInit:
    def test_haar_model_creation(self, detector):
        assert detector.model == "haar"
        assert detector._haar_cascade is not None

    def test_dnn_model_creation(self):
        det = FaceDetector(model="dnn")
        # DNN may not have model file, but should not crash
        assert det.model in ("dnn", "haar")

    def test_find_haar_cascade_returns_valid_path(self):
        path = FaceDetector._find_haar_cascade()
        assert path.endswith(".xml")


class TestFaceDetection:
    def test_detect_faces_returns_list(self, detector, blank_image):
        results = detector.detect_faces(blank_image)
        assert isinstance(results, list)

    def test_no_faces_in_blank_image(self, detector, blank_image):
        results = detector.detect_faces(blank_image)
        assert len(results) == 0

    def test_detect_faces_returns_tuples(self, detector, blank_image):
        results = detector.detect_faces(blank_image)
        for r in results:
            assert len(r) == 4  # (top, right, bottom, left)

    def test_detect_faces_with_landmarks(self, detector, blank_image):
        faces, landmarks = detector.detect_faces_with_landmarks(blank_image)
        assert isinstance(faces, list)
        assert isinstance(landmarks, list)


class TestHelperMethods:
    def test_get_largest_face_empty(self, detector):
        idx = detector.get_largest_face([])
        assert idx == -1

    def test_get_largest_face_single(self, detector):
        faces = [(10, 100, 200, 50)]
        idx = detector.get_largest_face(faces)
        assert idx == 0

    def test_get_largest_face_multiple(self, detector):
        faces = [(10, 50, 50, 10), (0, 200, 300, 0)]  # second is larger
        idx = detector.get_largest_face(faces)
        assert idx == 1

    def test_crop_face(self, detector, blank_image):
        face_loc = (50, 200, 200, 50)
        cropped = detector.crop_face(blank_image, face_loc, padding=10)
        assert cropped.size > 0
        assert cropped.shape[0] > 0
        assert cropped.shape[1] > 0

    def test_draw_faces(self, detector, blank_image):
        faces = [(50, 200, 200, 50)]
        names = ["TestPerson"]
        result = detector.draw_faces(blank_image, faces, names)
        assert result.shape == blank_image.shape
