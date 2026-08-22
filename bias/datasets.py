"""
Dataset Helper Module.
Provides utilities for managing face datasets for bias evaluation.
"""

import os
import csv
import cv2
import logging

logger = logging.getLogger(__name__)


class DatasetHelper:
    """Utilities for dataset preparation and management."""

    def __init__(self, base_dir):
        """
        Args:
            base_dir: Root directory for datasets.
        """
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def create_sample_dataset(self):
        """
        Create a sample dataset structure with placeholder README files.

        Expected structure:
            dataset/
            ├── Type_I_Male/
            ├── Type_I_Female/
            ├── Type_II_Male/
            ...
            └── annotations.csv
        """
        skin_types = ["Type_I", "Type_II", "Type_III", "Type_IV", "Type_V", "Type_VI"]
        genders = ["Male", "Female"]

        for skin in skin_types:
            for gender in genders:
                dirpath = os.path.join(self.base_dir, f"{skin}_{gender}")
                os.makedirs(dirpath, exist_ok=True)

        logger.info("Sample dataset structure created at %s", self.base_dir)

    def count_images(self):
        """Count images per demographic group."""
        counts = {}
        for group_dir in os.listdir(self.base_dir):
            group_path = os.path.join(self.base_dir, group_dir)
            if os.path.isdir(group_path):
                images = [f for f in os.listdir(group_path)
                          if f.lower().endswith((".jpg", ".jpeg", ".png"))]
                counts[group_dir] = len(images)
        return counts

    def validate_dataset(self):
        """
        Validate dataset integrity.

        Returns:
            Dict with validation results.
        """
        issues = []
        counts = self.count_images()

        for group, count in counts.items():
            if count == 0:
                issues.append(f"No images in {group}")
            elif count < 10:
                issues.append(f"Only {count} images in {group} (recommend at least 10)")

            for img_file in os.listdir(os.path.join(self.base_dir, group)):
                if not img_file.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                img_path = os.path.join(self.base_dir, group, img_file)
                img = cv2.imread(img_path)
                if img is None:
                    issues.append(f"Corrupted image: {group}/{img_file}")
                    continue

                face_locations = cv2.CascadeClassifier(
                    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                ).detectMultiScale(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 1.3, 5)
                if len(face_locations) == 0:
                    issues.append(f"No face detected: {group}/{img_file}")

        return {
            "total_images": sum(counts.values()),
            "groups": counts,
            "issues": issues,
            "valid": len(issues) == 0,
        }

    def generate_annotations_template(self, output_path):
        """
        Generate a CSV template for demographic annotations.

        Args:
            output_path: Path for the output CSV file.
        """
        rows = []
        for group_dir in os.listdir(self.base_dir):
            group_path = os.path.join(self.base_dir, group_dir)
            if not os.path.isdir(group_path):
                continue

            parts = group_dir.rsplit("_", 1)
            skin_type = parts[0].replace("_", " ") if len(parts) == 2 else "Unknown"
            gender = parts[1] if len(parts) == 2 else "Unknown"

            for img_file in os.listdir(group_path):
                if img_file.lower().endswith((".jpg", ".jpeg", ".png")):
                    rows.append({
                        "filename": f"{group_dir}/{img_file}",
                        "skin_type": skin_type,
                        "gender": gender,
                        "identity": os.path.splitext(img_file)[0],
                    })

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["filename", "skin_type", "gender", "identity"])
            writer.writeheader()
            writer.writerows(rows)

        logger.info("Generated annotations template with %d entries at %s",
                     len(rows), output_path)
