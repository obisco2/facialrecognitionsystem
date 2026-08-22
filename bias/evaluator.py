"""
Bias Evaluation Module.
Measures facial recognition accuracy across demographic groups.
Based on the Gender Shades methodology by Joy Buolamwini.
"""

import os
import csv
import numpy as np
import cv2
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BiasEvaluator:
    """
    Evaluates facial recognition system bias across demographic groups.

    Uses the Fitzpatrick skin type scale and gender categories to measure
    disparities in recognition accuracy, false positives, and false negatives.

    Reference: "Gender Shades: Intersectional Accuracy Disparities in
    Commercial Gender Classification" by Joy Buolamwini (2018).
    """

    SKIN_TYPES = {
        "Type I": "Very Light",
        "Type II": "Light",
        "Type III": "Medium",
        "Type IV": "Olive",
        "Type V": "Dark",
        "Type VI": "Very Dark",
    }

    GENDERS = ["Male", "Female", "Non-Binary"]

    def __init__(self, recognizer):
        """
        Args:
            recognizer: Recognizer instance with loaded face database.
        """
        self.recognizer = recognizer
        self.results = []
        self.demographic_data = {}

    def annotate_dataset(self, dataset_dir, annotations_file):
        """
        Create or load demographic annotations for a dataset.

        Expected CSV format:
            filename,skin_type,gender,identity

        Args:
            dataset_dir: Path to face images.
            annotations_file: Path to annotations CSV.
        """
        if os.path.exists(annotations_file):
            return self._load_annotations(annotations_file)

        logger.info("Creating annotation template at %s", annotations_file)
        annotations = []
        for root, _, files in os.walk(dataset_dir):
            for f in files:
                if f.lower().endswith((".jpg", ".jpeg", ".png")):
                    rel_path = os.path.relpath(os.path.join(root, f), dataset_dir)
                    annotations.append({
                        "filename": rel_path,
                        "skin_type": "Type III",  # default, needs manual annotation
                        "gender": "Unknown",
                        "identity": os.path.splitext(f)[0],
                    })

        with open(annotations_file, "w", newline="", encoding="utf-8") as csvf:
            writer = csv.DictWriter(csvf, fieldnames=["filename", "skin_type", "gender", "identity"])
            writer.writeheader()
            writer.writerows(annotations)

        logger.info("Annotation template created with %d entries. Please fill in demographics.",
                     len(annotations))
        return annotations

    def _load_annotations(self, filepath):
        """Load annotations from CSV."""
        annotations = []
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                annotations.append(row)
        return annotations

    def evaluate(self, dataset_dir, annotations_file, tolerance=None):
        """
        Run bias evaluation on a labeled dataset.

        Args:
            dataset_dir: Path to face images organized by identity.
            annotations_file: Path to demographic annotations CSV.
            tolerance: Override tolerance for this evaluation.

        Returns:
            Dict with overall and per-group metrics.
        """
        if tolerance is not None:
            self.recognizer.encoder.tolerance = tolerance

        annotations = self._load_annotations(annotations_file)
        if not annotations:
            logger.error("No annotations found")
            return {}

        self.results = []
        for ann in annotations:
            img_path = os.path.join(dataset_dir, ann["filename"])
            if not os.path.exists(img_path):
                continue

            image = cv2.imread(img_path)
            if image is None:
                continue

            locations = self.recognizer.detector.detect_faces(image)
            if not locations:
                self.results.append({
                    **ann,
                    "detected": False,
                    "correct": False,
                    "predicted": None,
                    "distance": None,
                })
                continue

            encodings = self.recognizer.encoder.compute_encodings_batch(
                [image]
            )

            if encodings:
                enc, _ = encodings[0]
                predicted, distance = self.recognizer.encoder.identify(enc)
                correct = predicted == ann["identity"]
                self.results.append({
                    **ann,
                    "detected": True,
                    "correct": correct,
                    "predicted": predicted,
                    "distance": distance,
                })
            else:
                self.results.append({
                    **ann,
                    "detected": False,
                    "correct": False,
                    "predicted": None,
                    "distance": None,
                })

        return self._compute_metrics()

    def _compute_metrics(self):
        """Compute overall and per-group metrics from evaluation results."""
        if not self.results:
            return {}

        total = len(self.results)
        detected = sum(1 for r in self.results if r["detected"])
        correct = sum(1 for r in self.results if r["correct"])

        overall = {
            "total_images": total,
            "detection_rate": detected / total if total > 0 else 0,
            "recognition_accuracy": correct / detected if detected > 0 else 0,
            "false_negatives": detected - correct,
            "false_negative_rate": (detected - correct) / detected if detected > 0 else 0,
        }

        # Per skin type
        skin_metrics = {}
        for skin_type in self.SKIN_TYPES:
            group = [r for r in self.results if r.get("skin_type") == skin_type]
            if group:
                g_detected = sum(1 for r in group if r["detected"])
                g_correct = sum(1 for r in group if r["correct"])
                skin_metrics[skin_type] = {
                    "count": len(group),
                    "detection_rate": g_detected / len(group) if group else 0,
                    "accuracy": g_correct / g_detected if g_detected > 0 else 0,
                }

        # Per gender
        gender_metrics = {}
        for gender in self.GENDERS:
            group = [r for r in self.results if r.get("gender") == gender]
            if group:
                g_detected = sum(1 for r in group if r["detected"])
                g_correct = sum(1 for r in group if r["correct"])
                gender_metrics[gender] = {
                    "count": len(group),
                    "detection_rate": g_detected / len(group) if group else 0,
                    "accuracy": g_correct / g_detected if g_detected > 0 else 0,
                }

        # Intersectional (skin type x gender)
        intersectional = {}
        for skin_type in self.SKIN_TYPES:
            for gender in self.GENDERS:
                key = f"{skin_type} {gender}"
                group = [r for r in self.results
                         if r.get("skin_type") == skin_type and r.get("gender") == gender]
                if group:
                    g_detected = sum(1 for r in group if r["detected"])
                    g_correct = sum(1 for r in group if r["correct"])
                    intersectional[key] = {
                        "count": len(group),
                        "detection_rate": g_detected / len(group) if group else 0,
                        "accuracy": g_correct / g_detected if g_detected > 0 else 0,
                    }

        metrics = {
            "overall": overall,
            "by_skin_type": skin_metrics,
            "by_gender": gender_metrics,
            "intersectional": intersectional,
            "timestamp": datetime.now().isoformat(),
            "tolerance": self.recognizer.encoder.tolerance,
        }

        self.demographic_data = metrics
        return metrics

    def get_disparity_report(self):
        """
        Compute the accuracy gap between best and worst performing groups.

        Returns:
            Dict with disparity analysis.
        """
        if not self.demographic_data:
            return {}

        skin_accs = {k: v["accuracy"] for k, v in self.demographic_data.get("by_skin_type", {}).items()}
        gender_accs = {k: v["accuracy"] for k, v in self.demographic_data.get("by_gender", {}).items()}

        report = {"skin_type_disparity": {}, "gender_disparity": {}}

        if skin_accs:
            best = max(skin_accs, key=skin_accs.get)
            worst = min(skin_accs, key=skin_accs.get)
            report["skin_type_disparity"] = {
                "best_group": best,
                "best_accuracy": skin_accs[best],
                "worst_group": worst,
                "worst_accuracy": skin_accs[worst],
                "gap": skin_accs[best] - skin_accs[worst],
            }

        if gender_accs:
            best = max(gender_accs, key=gender_accs.get)
            worst = min(gender_accs, key=gender_accs.get)
            report["gender_disparity"] = {
                "best_group": best,
                "best_accuracy": gender_accs[best],
                "worst_group": worst,
                "worst_accuracy": gender_accs[worst],
                "gap": gender_accs[best] - gender_accs[worst],
            }

        return report

    def save_results(self, filepath):
        """Save evaluation results to CSV."""
        if not self.results:
            return

        fieldnames = ["filename", "skin_type", "gender", "identity",
                       "detected", "correct", "predicted", "distance"]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.results)

        logger.info("Results saved to %s", filepath)

    def save_metrics(self, filepath):
        """Save computed metrics to a JSON file."""
        import json
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.demographic_data, f, indent=2, default=str)
        logger.info("Metrics saved to %s", filepath)
