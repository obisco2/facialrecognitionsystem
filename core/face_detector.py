"""
Face Detection Module.
Uses OpenCV DNN or Haar Cascade for face detection.
"""

import cv2
import numpy as np
import os


class FaceDetector:
    """Detects faces in images using OpenCV."""

    def __init__(self, model="haar"):
        """
        Args:
            model: 'haar' for Haar Cascade (fast, CPU),
                   'dnn' for DNN-based detector (more accurate).
        """
        self.model = model
        self._haar_cascade = None
        self._dnn_net = None
        self._dnn_proto = None

        if model == "haar":
            cascade_path = self._find_haar_cascade()
            self._haar_cascade = cv2.CascadeClassifier(cascade_path)
        elif model == "dnn":
            self._init_dnn()

    @staticmethod
    def _find_haar_cascade() -> str:
        """Locate the haar cascade XML, checking multiple paths."""
        name = "haarcascade_frontalface_default.xml"
        candidates = [
            cv2.data.haarcascades + name,
            os.path.join(os.path.dirname(__file__), name),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", name),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
        # Last resort — return the default path (will raise if truly missing)
        return cv2.data.haarcascades + name

    def _init_dnn(self):
        """Initialize DNN face detector with OpenCV's pre-trained model."""
        model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")
        os.makedirs(model_dir, exist_ok=True)

        proto_file = os.path.join(model_dir, "deploy.prototxt")
        model_file = os.path.join(model_dir, "res10_300x300_ssd_iter_140000.caffemodel")

        if not os.path.exists(proto_file) or not os.path.exists(model_file):
            print("Downloading DNN face detector model...")
            self._download_dnn_model(model_dir)

        if os.path.exists(proto_file) and os.path.exists(model_file):
            self._dnn_net = cv2.dnn.readNetFromCaffe(proto_file, model_file)
        else:
            print("DNN model not available, falling back to Haar Cascade")
            self.model = "haar"
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._haar_cascade = cv2.CascadeClassifier(cascade_path)

    def _download_dnn_model(self, model_dir):
        """Download OpenCV's pre-trained DNN face detector."""
        proto_url = "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
        model_url = "https://www.dropbox.com/s/2e5btlm2bqpb9jy/res10_300x300_ssd_iter_140000.caffemodel?dl=1"

        try:
            import urllib.request
            proto_path = os.path.join(model_dir, "deploy.prototxt")
            urllib.request.urlretrieve(proto_url, proto_path)

            model_path = os.path.join(model_dir, "res10_300x300_ssd_iter_140000.caffemodel")
            if not os.path.exists(model_path):
                print("Note: DNN model file needs manual download.")
                print(f"Place res10_300x300_ssd_iter_140000.caffemodel in {model_dir}")
        except Exception as e:
            print(f"Could not download DNN model: {e}")

    def detect_faces(self, image):
        """
        Detect faces in an image.

        Args:
            image: BGR numpy array (OpenCV format).

        Returns:
            List of (top, right, bottom, left) bounding box tuples.
        """
        if self.model == "dnn" and self._dnn_net is not None:
            return self._detect_dnn(image)
        return self._detect_haar(image)

    def _detect_haar(self, image):
        """Detect faces using Haar Cascade."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self._haar_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        results = []
        for (x, y, w, h) in faces:
            # Convert (x, y, w, h) to (top, right, bottom, left)
            results.append((y, x + w, y + h, x))
        return results

    def _detect_dnn(self, image):
        """Detect faces using DNN model."""
        h, w = image.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(image, (300, 300)), 1.0, (300, 300),
            (104.0, 177.0, 123.0)
        )
        self._dnn_net.setInput(blob)
        detections = self._dnn_net.forward()

        results = []
        confidence_threshold = 0.5
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > confidence_threshold:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype("int")
                # Clamp to image bounds
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(w, x2)
                y2 = min(h, y2)
                # Convert to (top, right, bottom, left)
                results.append((y1, x2, y2, x1))
        return results

    def detect_faces_with_landmarks(self, image):
        """
        Detect faces (landmarks not available with Haar/DNN, returns empty).

        Returns:
            Tuple of (face_locations, empty_landmarks).
        """
        return self.detect_faces(image), []

    def draw_faces(self, image, face_locations, names=None, colors=None):
        """
        Draw bounding boxes and optional names on detected faces.
        """
        if names is None:
            names = ["Unknown"] * len(face_locations)
        if colors is None:
            colors = [(0, 255, 0)] * len(face_locations)

        for (top, right, bottom, left), name, color in zip(face_locations, names, colors):
            cv2.rectangle(image, (left, top), (right, bottom), color, 2)
            cv2.rectangle(image, (left, bottom - 25), (right, bottom), color, cv2.FILLED)
            font = cv2.FONT_HERSHEY_DUPLEX
            cv2.putText(image, name, (left + 6, bottom - 6), font, 0.6, (255, 255, 255), 1)

        return image

    def get_largest_face(self, face_locations):
        """Get the largest detected face by bounding box area."""
        if not face_locations:
            return -1
        areas = [(r - l) * (b - t) for t, r, b, l in face_locations]
        return int(np.argmax(areas))

    def crop_face(self, image, face_location, padding=20):
        """Crop a face from an image with optional padding."""
        h, w = image.shape[:2]
        top, right, bottom, left = face_location
        top = max(0, top - padding)
        left = max(0, left - padding)
        bottom = min(h, bottom + padding)
        right = min(w, right + padding)
        return image[top:bottom, left:right]
