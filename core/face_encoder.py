"""
Face Encoding / Recognition Module — AttendIQ.

Primary engine: dlib face_recognition (128-d HOG-SVM embeddings).
Fallback engine: OpenCV LBPH (Local Binary Patterns Histogram).

The module auto-detects which engine is available at import time.
The active engine can be overridden via the 'engine' constructor arg:
    'auto'  — dlib if available, LBPH otherwise (default)
    'dlib'  — force dlib (raises ImportError if not installed)
    'lbph'  — force LBPH

Recognition accuracy:
    dlib  — ~99.3% on LFW benchmark; robust to lighting + pose variation
    LBPH  — adequate for controlled classroom conditions; faster on CPU
"""

import cv2
import numpy as np
import os
import pickle
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dlib / face_recognition availability check
# ---------------------------------------------------------------------------
try:
    import face_recognition as _fr
    _DLIB_AVAILABLE = True
    logger.info("face_recognition (dlib) available — using 128-d embeddings")
except ImportError:
    _DLIB_AVAILABLE = False
    logger.warning(
        "face_recognition not installed — falling back to OpenCV LBPH. "
        "Install with: pip install face_recognition"
    )


class FaceEncoder:
    """
    Unified face encoding and identification interface.

    Supports two backends:
      - dlib face_recognition: 128-dimensional embeddings, euclidean distance matching
      - OpenCV LBPH: grayscale histogram matching, confidence-based threshold

    Both backends expose the same public API so the rest of the system
    is completely agnostic to which engine is running.
    """

    def __init__(self, model: str = "haar", tolerance: float = 0.6,
                 engine: str = "auto"):
        """
        Args:
            model:     Legacy CV model hint ('haar' / 'dnn'). Passed through for
                       compatibility; does not affect dlib engine selection.
            tolerance: For dlib: euclidean distance threshold (default 0.6 per
                       face_recognition docs; lower = stricter).
                       For LBPH: normalised confidence threshold.
            engine:    'auto' | 'dlib' | 'lbph'
        """
        self.model = model
        self.tolerance = tolerance

        # Resolve active engine
        if engine == "dlib":
            if not _DLIB_AVAILABLE:
                raise ImportError("face_recognition (dlib) is not installed.")
            self._engine = "dlib"
        elif engine == "lbph":
            self._engine = "lbph"
        else:  # auto
            self._engine = "dlib" if _DLIB_AVAILABLE else "lbph"

        logger.info("FaceEncoder using engine: %s (tolerance=%.2f)",
                    self._engine, tolerance)

        # Shared storage — both engines populate these
        self.known_encodings: list = []   # numpy arrays (128-d or 100×100 gray)
        self.known_names: list[str] = []

        # LBPH-specific state
        self._lbph_recognizer = None
        self._lbph_labels: dict[int, str] = {}
        self._label_counter: int = 0

    # ------------------------------------------------------------------
    # Public API — engine-agnostic
    # ------------------------------------------------------------------

    @property
    def engine(self) -> str:
        return self._engine

    @property
    def is_dlib(self) -> bool:
        return self._engine == "dlib"

    def compute_encoding(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Compute a face encoding for a cropped face image.

        Args:
            image: BGR numpy array (ideally a tight face crop).

        Returns:
            128-d float32 array (dlib) or 100×100 uint8 grayscale (LBPH),
            or None if encoding fails.
        """
        if image is None or image.size == 0:
            return None
        if self._engine == "dlib":
            return self._encode_dlib(image)
        return self._encode_lbph(image)

    def compute_encoding_full(self, full_image: np.ndarray, box: tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """Compute face encoding using full image context to ensure landmark accuracy."""
        if full_image is None or full_image.size == 0:
            return None
        if self._engine == "dlib":
            rgb = cv2.cvtColor(full_image, cv2.COLOR_BGR2RGB)
            encodings = _fr.face_encodings(rgb, known_face_locations=[box])
            return np.array(encodings[0]) if encodings else None
        top, right, bottom, left = box
        crop = full_image[top:bottom, left:right]
        return self._encode_lbph(crop)

    def identify(self, face_encoding: np.ndarray) -> tuple[str, Optional[float]]:
        """
        Match a face encoding against the loaded known-faces database.

        Returns:
            (name, distance) — name is "Unknown" if no match found.
            Distance: euclidean (dlib) or normalised LBPH confidence.
            Lower distance = more confident match.
        """
        if self._engine == "dlib":
            return self._identify_dlib(face_encoding)
        return self._identify_lbph(face_encoding)

    def load_known_faces(self, directory: str) -> tuple[list, list]:
        """
        Load and encode all known faces from a directory tree.

        Expected structure:
            known_faces/
                Alice Kamara/
                    img_0000.jpg
                    img_0001.jpg
                Bob Mensah/
                    img_0000.jpg

        The subdirectory name becomes the identity label.
        Also accepts student_id as directory name — the system stores
        full_name as the folder label so face recognition returns a name
        that can be looked up in the database.

        Returns:
            (encodings, names) — parallel lists.
        """
        self.known_encodings = []
        self.known_names = []
        self._lbph_labels = {}
        self._label_counter = 0

        all_gray: list[np.ndarray] = []
        all_labels: list[int] = []

        if not os.path.exists(directory):
            logger.warning("Known faces directory does not exist: %s", directory)
            return self.known_encodings, self.known_names

        for person_name in sorted(os.listdir(directory)):
            person_dir = os.path.join(directory, person_name)
            if not os.path.isdir(person_dir):
                continue

            label_id = self._label_counter
            self._lbph_labels[label_id] = person_name
            self._label_counter += 1

            img_count = 0
            for img_file in sorted(os.listdir(person_dir)):
                if not img_file.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                img_path = os.path.join(person_dir, img_file)
                image = cv2.imread(img_path)
                if image is None:
                    continue

                if self._engine == "dlib":
                    enc = self._encode_dlib_from_file(img_path)
                    if enc is not None:
                        self.known_encodings.append(enc)
                        self.known_names.append(person_name)
                        img_count += 1
                else:
                    gray = self._bgr_to_gray100(image)
                    self.known_encodings.append(gray)
                    self.known_names.append(person_name)
                    all_gray.append(gray)
                    all_labels.append(label_id)
                    img_count += 1

            logger.debug("Loaded %d images for '%s'", img_count, person_name)

        # Train LBPH on the full dataset in one pass
        if self._engine == "lbph" and all_gray:
            self._train_lbph(all_gray, all_labels)

        logger.info(
            "Loaded %d encodings for %d persons [engine=%s]",
            len(self.known_encodings),
            len(set(self.known_names)),
            self._engine,
        )
        return self.known_encodings, self.known_names

    def load_single_images(self, directory: str) -> tuple[list, list]:
        """
        Load from a flat directory (one image per person).
        Filename without extension = identity label.
        """
        self.known_encodings = []
        self.known_names = []
        self._lbph_labels = {}
        self._label_counter = 0

        all_gray: list[np.ndarray] = []
        all_labels: list[int] = []

        if not os.path.exists(directory):
            return self.known_encodings, self.known_names

        for img_file in sorted(os.listdir(directory)):
            if not img_file.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            img_path = os.path.join(directory, img_file)
            name = os.path.splitext(img_file)[0]

            label_id = self._label_counter
            self._lbph_labels[label_id] = name
            self._label_counter += 1

            if self._engine == "dlib":
                enc = self._encode_dlib_from_file(img_path)
                if enc is not None:
                    self.known_encodings.append(enc)
                    self.known_names.append(name)
            else:
                image = cv2.imread(img_path)
                if image is None:
                    continue
                gray = self._bgr_to_gray100(image)
                self.known_encodings.append(gray)
                self.known_names.append(name)
                all_gray.append(gray)
                all_labels.append(label_id)

        if self._engine == "lbph" and all_gray:
            self._train_lbph(all_gray, all_labels)

        return self.known_encodings, self.known_names

    def encode_image_file(self, filepath: str) -> Optional[np.ndarray]:
        """
        Encode a single image file.
        Used by the enrollment module to validate uploaded photos.

        Returns:
            Encoding array, or None if no face detected in the image.
        """
        if self._engine == "dlib":
            return self._encode_dlib_from_file(filepath)
        image = cv2.imread(filepath)
        if image is None:
            return None
        return self._encode_lbph(image)

    def identify_batch(self, encodings: list) -> list[tuple[str, Optional[float]]]:
        """Identify multiple face encodings at once."""
        return [self.identify(enc) for enc in encodings]

    def add_known_face(self, encoding: np.ndarray, name: str):
        """
        Add a single face encoding to the in-memory database.
        Call load_known_faces() to rebuild from disk for persistence.
        """
        self.known_encodings.append(encoding)
        self.known_names.append(name)

        if self._engine == "lbph":
            # Rebuild LBPH with the new data
            label_map: dict[str, int] = {}
            labels: list[int] = []
            counter = 0
            for n in self.known_names:
                if n not in label_map:
                    label_map[n] = counter
                    counter += 1
                labels.append(label_map[n])
            self._lbph_labels = {v: k for k, v in label_map.items()}
            self._label_counter = counter
            if self.known_encodings:
                self._train_lbph(self.known_encodings, labels)

    def remove_known_face(self, name: str):
        """Remove all encodings for a given name from memory."""
        indices = [i for i, n in enumerate(self.known_names) if n == name]
        for i in sorted(indices, reverse=True):
            self.known_encodings.pop(i)
            self.known_names.pop(i)

    def save_encodings(self, filepath: str):
        """Persist encodings and model state to disk."""
        data = {
            "engine": self._engine,
            "encodings": self.known_encodings,
            "names": self.known_names,
            "lbph_labels": self._lbph_labels,
            "tolerance": self.tolerance,
        }
        with open(filepath, "wb") as f:
            pickle.dump(data, f)

        if self._engine == "lbph" and self._lbph_recognizer:
            yml_path = filepath.replace(".pkl", "_lbph.yml")
            self._lbph_recognizer.save(yml_path)

        logger.info("Encodings saved to %s", filepath)

    def load_encodings(self, filepath: str) -> bool:
        """Load encodings from disk."""
        if not os.path.exists(filepath):
            return False
        with open(filepath, "rb") as f:
            data = pickle.load(f)

        self.known_encodings = data.get("encodings", [])
        self.known_names = data.get("names", [])
        self._lbph_labels = data.get("lbph_labels", {})
        self.tolerance = data.get("tolerance", self.tolerance)

        if self._engine == "lbph":
            yml_path = filepath.replace(".pkl", "_lbph.yml")
            if os.path.exists(yml_path):
                self._lbph_recognizer = cv2.face.LBPHFaceRecognizer_create()
                self._lbph_recognizer.read(yml_path)
            elif self.known_encodings:
                labels = [
                    next((lid for lid, n in self._lbph_labels.items() if n == name), 0)
                    for name in self.known_names
                ]
                self._train_lbph(self.known_encodings, labels)

        logger.info("Loaded %d encodings from %s", len(self.known_encodings), filepath)
        return True

    # ------------------------------------------------------------------
    # Blur / quality check (used by enrollment validation)
    # ------------------------------------------------------------------

    @staticmethod
    def blur_score(image: np.ndarray) -> float:
        """
        Laplacian variance blur metric.
        Higher = sharper. < 100 is generally considered blurry.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # ------------------------------------------------------------------
    # dlib / face_recognition internals
    # ------------------------------------------------------------------

    def _encode_dlib(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Compute a 128-d dlib embedding from a BGR numpy array.
        Converts to RGB as required by face_recognition.
        """
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        # face_recognition expects the full image and finds faces internally
        boxes = _fr.face_locations(rgb, model="hog")
        if not boxes:
            # Try treating the whole image as a face crop
            boxes = [(0, rgb.shape[1], rgb.shape[0], 0)]
        encodings = _fr.face_encodings(rgb, known_face_locations=boxes)
        return np.array(encodings[0]) if encodings else None

    def _encode_dlib_from_file(self, filepath: str) -> Optional[np.ndarray]:
        """Load an image file and return its dlib 128-d encoding."""
        try:
            image = _fr.load_image_file(filepath)  # returns RGB
            boxes = _fr.face_locations(image, model="hog")
            if not boxes:
                boxes = [(0, image.shape[1], image.shape[0], 0)]
            encodings = _fr.face_encodings(image, known_face_locations=boxes)
            return np.array(encodings[0]) if encodings else None
        except Exception as e:
            logger.warning("Failed to encode %s: %s", filepath, e)
            return None

    def _identify_dlib(self, face_encoding: np.ndarray
                        ) -> tuple[str, Optional[float]]:
        """
        Match a 128-d encoding against known encodings using euclidean distance.
        face_recognition.compare_faces uses tolerance as threshold.
        """
        if not self.known_encodings:
            return "Unknown", None

        known = np.array(self.known_encodings)
        distances = _fr.face_distance(known, face_encoding)
        best_idx = int(np.argmin(distances))
        best_dist = float(distances[best_idx])

        if best_dist <= self.tolerance:
            return self.known_names[best_idx], round(best_dist, 4)
        return "Unknown", round(best_dist, 4)

    # ------------------------------------------------------------------
    # LBPH internals (OpenCV)
    # ------------------------------------------------------------------

    @staticmethod
    def _bgr_to_gray100(image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        return cv2.resize(gray, (100, 100))

    def _encode_lbph(self, image: np.ndarray) -> Optional[np.ndarray]:
        if image is None or image.size == 0:
            return None
        return self._bgr_to_gray100(image)

    def _train_lbph(self, images: list, labels: list):
        self._lbph_recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=1, neighbors=8, grid_x=8, grid_y=8
        )
        self._lbph_recognizer.train(images, np.array(labels, dtype=np.int32))
        logger.debug("LBPH trained on %d images", len(images))

    def _identify_lbph(self, face_encoding: np.ndarray
                        ) -> tuple[str, Optional[float]]:
        if not self.known_encodings or self._lbph_recognizer is None:
            return self._identify_template(face_encoding)

        gray = face_encoding if len(face_encoding.shape) == 2 else \
            cv2.cvtColor(face_encoding, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (100, 100))

        try:
            label_id, confidence = self._lbph_recognizer.predict(resized)
            distance = confidence / 100.0
            if distance <= self.tolerance:
                name = self._lbph_labels.get(label_id, "Unknown")
                return name, round(distance, 4)
        except cv2.error as e:
            logger.warning("LBPH predict error: %s", e)

        return "Unknown", None

    def _identify_template(self, face_encoding: np.ndarray
                            ) -> tuple[str, Optional[float]]:
        """Fallback: normalized cross-correlation template matching."""
        if not self.known_encodings:
            return "Unknown", None

        gray = face_encoding if len(face_encoding.shape) == 2 else \
            cv2.cvtColor(face_encoding, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, (100, 100)).astype(np.float32)

        best_name = "Unknown"
        best_dist = 1.0

        for enc, name in zip(self.known_encodings, self.known_names):
            score = float(
                cv2.matchTemplate(resized, enc.astype(np.float32),
                                  cv2.TM_CCOEFF_NORMED)[0][0]
            )
            dist = 1.0 - score
            if dist < best_dist:
                best_dist = dist
                best_name = name

        if best_dist <= self.tolerance:
            return best_name, round(best_dist, 4)
        return "Unknown", round(best_dist, 4)

    # ------------------------------------------------------------------
    # Compute encodings for batch of raw images (used by enrollment)
    # ------------------------------------------------------------------

    def compute_encodings_batch(self, images: list) -> list:
        """
        Compute encodings for a list of images.

        Returns:
            List of (encoding, index) for successful encodings.
        """
        results = []
        for i, img in enumerate(images):
            enc = self.compute_encoding(img)
            if enc is not None:
                results.append((enc, i))
        return results
