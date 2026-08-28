"""Tests for bias.evaluator — BiasEvaluator metrics and disparity reporting."""

import os
import csv
import tempfile
import pytest
from unittest.mock import MagicMock, patch
import numpy as np
import cv2

from bias.evaluator import BiasEvaluator


@pytest.fixture
def mock_recognizer():
    """Create a mock Recognizer with controllable behavior."""
    recognizer = MagicMock()
    recognizer.detector = MagicMock()
    recognizer.encoder = MagicMock()
    recognizer.encoder.tolerance = 0.6
    return recognizer


@pytest.fixture
def evaluator(mock_recognizer):
    return BiasEvaluator(mock_recognizer)


@pytest.fixture
def sample_annotations(tmp_path):
    """Create a sample annotations CSV."""
    annotations = [
        {"filename": "img1.jpg", "skin_type": "Type I", "gender": "Male", "identity": "person_a"},
        {"filename": "img2.jpg", "skin_type": "Type III", "gender": "Female", "identity": "person_b"},
        {"filename": "img3.jpg", "skin_type": "Type VI", "gender": "Male", "identity": "person_a"},
        {"filename": "img4.jpg", "skin_type": "Type I", "gender": "Female", "identity": "person_b"},
        {"filename": "img5.jpg", "skin_type": "Type IV", "gender": "Male", "identity": "person_a"},
        {"filename": "img6.jpg", "skin_type": "Type VI", "gender": "Female", "identity": "person_b"},
    ]
    csv_path = tmp_path / "annotations.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "skin_type", "gender", "identity"])
        writer.writeheader()
        writer.writerows(annotations)
    return str(csv_path), annotations


class TestBiasEvaluatorInit:
    def test_init_stores_recognizer(self, mock_recognizer):
        ev = BiasEvaluator(mock_recognizer)
        assert ev.recognizer is mock_recognizer

    def test_init_empty_results(self, evaluator):
        assert evaluator.results == []

    def test_init_empty_demographic_data(self, evaluator):
        assert evaluator.demographic_data == {}


class TestAnnotationLoading:
    def test_load_annotations(self, evaluator, sample_annotations):
        csv_path, expected = sample_annotations
        annotations = evaluator._load_annotations(csv_path)
        assert len(annotations) == 6
        assert annotations[0]["skin_type"] == "Type I"

    def test_annotate_dataset_creates_template(self, evaluator, tmp_path):
        dataset_dir = str(tmp_path / "dataset")
        os.makedirs(dataset_dir)
        # Create a dummy image
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(os.path.join(dataset_dir, "test_face.jpg"), img)

        annotations_file = str(tmp_path / "annotations.csv")
        result = evaluator.annotate_dataset(dataset_dir, annotations_file)
        assert os.path.exists(annotations_file)
        assert len(result) == 1


class TestMetricsComputation:
    def test_compute_metrics_empty_results(self, evaluator):
        result = evaluator._compute_metrics()
        assert result == {}

    def test_compute_metrics_with_results(self, evaluator):
        evaluator.results = [
            {"detected": True, "correct": True, "skin_type": "Type I", "gender": "Male", "identity": "a"},
            {"detected": True, "correct": False, "skin_type": "Type I", "gender": "Male", "identity": "b"},
            {"detected": True, "correct": True, "skin_type": "Type VI", "gender": "Female", "identity": "a"},
            {"detected": False, "correct": False, "skin_type": "Type VI", "gender": "Female", "identity": "c"},
        ]
        metrics = evaluator._compute_metrics()

        assert metrics["overall"]["total_images"] == 4
        assert metrics["overall"]["detection_rate"] == 0.75  # 3/4 detected
        assert metrics["overall"]["recognition_accuracy"] == pytest.approx(2 / 3)  # 2/3 correct of detected

    def test_compute_metrics_by_skin_type(self, evaluator):
        evaluator.results = [
            {"detected": True, "correct": True, "skin_type": "Type I", "gender": "Male", "identity": "a"},
            {"detected": True, "correct": True, "skin_type": "Type I", "gender": "Male", "identity": "a"},
            {"detected": True, "correct": False, "skin_type": "Type VI", "gender": "Female", "identity": "b"},
        ]
        metrics = evaluator._compute_metrics()

        assert "Type I" in metrics["by_skin_type"]
        assert metrics["by_skin_type"]["Type I"]["accuracy"] == 1.0
        assert "Type VI" in metrics["by_skin_type"]
        assert metrics["by_skin_type"]["Type VI"]["accuracy"] == 0.0

    def test_compute_metrics_intersectional(self, evaluator):
        evaluator.results = [
            {"detected": True, "correct": True, "skin_type": "Type I", "gender": "Male", "identity": "a"},
            {"detected": True, "correct": True, "skin_type": "Type I", "gender": "Female", "identity": "b"},
        ]
        metrics = evaluator._compute_metrics()
        assert "Type I Male" in metrics["intersectional"]
        assert "Type I Female" in metrics["intersectional"]


class TestDisparityReport:
    def test_disparity_report_empty(self, evaluator):
        report = evaluator.get_disparity_report()
        assert report == {}

    def test_disparity_report_computes_gap(self, evaluator):
        evaluator.demographic_data = {
            "by_skin_type": {
                "Type I": {"accuracy": 0.98},
                "Type VI": {"accuracy": 0.85},
            },
            "by_gender": {
                "Male": {"accuracy": 0.95},
                "Female": {"accuracy": 0.90},
            },
        }
        report = evaluator.get_disparity_report()

        assert report["skin_type_disparity"]["best_group"] == "Type I"
        assert report["skin_type_disparity"]["worst_group"] == "Type VI"
        assert report["skin_type_disparity"]["gap"] == pytest.approx(0.13)
        assert report["gender_disparity"]["gap"] == pytest.approx(0.05)


class TestSaveResults:
    def test_save_results_csv(self, evaluator, tmp_path):
        evaluator.results = [
            {"filename": "test.jpg", "skin_type": "Type I", "gender": "Male",
             "identity": "a", "detected": True, "correct": True, "predicted": "a", "distance": 0.4},
        ]
        filepath = str(tmp_path / "results.csv")
        evaluator.save_results(filepath)
        assert os.path.exists(filepath)
        with open(filepath) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["detected"] == "True"

    def test_save_metrics_json(self, evaluator, tmp_path):
        evaluator.demographic_data = {"overall": {"total_images": 10}}
        filepath = str(tmp_path / "metrics.json")
        evaluator.save_metrics(filepath)
        assert os.path.exists(filepath)
        import json
        with open(filepath) as f:
            data = json.load(f)
            assert data["overall"]["total_images"] == 10

    def test_save_results_empty(self, evaluator, tmp_path):
        evaluator.results = []
        filepath = str(tmp_path / "empty.csv")
        evaluator.save_results(filepath)
        assert not os.path.exists(filepath)  # Should not create file
