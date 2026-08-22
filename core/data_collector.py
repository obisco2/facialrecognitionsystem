"""
Data Collection Module.
Captures face images from webcam for training the recognition system.
"""

import cv2
import os
import time
import logging

logger = logging.getLogger(__name__)


class DataCollector:
    """Captures face images from webcam for building the face database."""

    def __init__(self, detector, output_dir, num_samples=100, padding=20):
        """
        Args:
            detector: FaceDetector instance.
            output_dir: Directory to save captured images.
            num_samples: Number of images to capture per person.
            padding: Padding around detected face.
        """
        self.detector = detector
        self.output_dir = output_dir
        self.num_samples = num_samples
        self.padding = padding
        os.makedirs(output_dir, exist_ok=True)

    def capture_interactive(self, person_name, camera_index=0, frame_scale=0.25):
        """
        Interactive capture session: shows live feed, saves faces on key press.

        Args:
            person_name: Name/ID for the person being captured.
            camera_index: Webcam device index.
            frame_scale: Scale factor for detection speed.

        Returns:
            Number of images captured.
        """
        person_dir = os.path.join(self.output_dir, person_name)
        os.makedirs(person_dir, exist_ok=True)

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            logger.error("Cannot open camera %d", camera_index)
            return 0

        count = 0
        logger.info("Capturing for '%s'. Press SPACE to capture, ESC to stop.", person_name)

        while count < self.num_samples:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Failed to read frame from camera")
                break

            small = cv2.resize(frame, (0, 0), fx=frame_scale, fy=frame_scale)
            face_locations = self.detector.detect_faces(small)

            for (top, right, bottom, left) in face_locations:
                top, right, bottom, left = [int(v / frame_scale) for v in (top, right, bottom, left)]
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.putText(frame, f"{count}/{self.num_samples}", (left, top - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.putText(frame, f"Press SPACE to capture ({count}/{self.num_samples})", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.imshow("Capture Data - Press SPACE to save, ESC to quit", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break
            elif key == 32:  # SPACE
                if face_locations:
                    largest = self.detector.get_largest_face(
                        [(t, r, b, l) for t, r, b, l in face_locations]
                    )
                    t, r, b, l = face_locations[largest]
                    t, r, b, l = [int(v / frame_scale) for v in (t, r, b, l)]
                    face_crop = self.detector.crop_face(frame, (t, r, b, l), self.padding)
                    if face_crop is not None and face_crop.size > 0:
                        filepath = os.path.join(person_dir, f"{person_name}_{count:04d}.jpg")
                        cv2.imwrite(filepath, face_crop)
                        count += 1
                        logger.info("Saved image %d for %s", count, person_name)

        cap.release()
        cv2.destroyAllWindows()
        logger.info("Captured %d images for '%s'", count, person_name)
        return count

    def capture_auto(self, person_name, camera_index=0, frame_scale=0.25, delay=0.3):
        """
        Automatic capture: saves every detected face without user interaction.

        Args:
            person_name: Name/ID for the person.
            camera_index: Webcam device index.
            frame_scale: Scale factor for detection.
            delay: Seconds between captures.

        Returns:
            Number of images captured.
        """
        person_dir = os.path.join(self.output_dir, person_name)
        os.makedirs(person_dir, exist_ok=True)

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            logger.error("Cannot open camera %d", camera_index)
            return 0

        count = 0
        logger.info("Auto-capturing for '%s'. Press ESC to stop.", person_name)

        while count < self.num_samples:
            ret, frame = cap.read()
            if not ret:
                break

            small = cv2.resize(frame, (0, 0), fx=frame_scale, fy=frame_scale)
            face_locations = self.detector.detect_faces(small)

            if face_locations:
                largest = self.detector.get_largest_face(face_locations)
                t, r, b, l = face_locations[largest]
                t, r, b, l = [int(v / frame_scale) for v in (t, r, b, l)]
                face_crop = self.detector.crop_face(frame, (t, r, b, l), self.padding)
                if face_crop is not None and face_crop.size > 0:
                    filepath = os.path.join(person_dir, f"{person_name}_{count:04d}.jpg")
                    cv2.imwrite(filepath, face_crop)
                    count += 1
                    logger.info("Auto-saved %d/%d for %s", count, self.num_samples, person_name)
                    cv2.imshow("Auto Capture", face_crop)
                    if cv2.waitKey(int(delay * 1000)) & 0xFF == 27:
                        break

        cap.release()
        cv2.destroyAllWindows()
        logger.info("Auto-captured %d images for '%s'", count, person_name)
        return count

    def list_captured(self):
        """List all captured persons and their image counts."""
        persons = {}
        if not os.path.exists(self.output_dir):
            return persons
        for name in os.listdir(self.output_dir):
            person_dir = os.path.join(self.output_dir, name)
            if os.path.isdir(person_dir):
                imgs = [f for f in os.listdir(person_dir)
                        if f.lower().endswith((".jpg", ".jpeg", ".png"))]
                persons[name] = len(imgs)
        return persons

    def delete_person(self, person_name):
        """Delete all images for a person."""
        import shutil
        person_dir = os.path.join(self.output_dir, person_name)
        if os.path.exists(person_dir):
            shutil.rmtree(person_dir)
            logger.info("Deleted data for '%s'", person_name)
