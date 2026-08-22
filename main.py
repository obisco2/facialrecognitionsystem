"""
AttendIQ — Facial Recognition Attendance System
================================================
A bias-aware, multi-role attendance system powered by dlib face recognition.

Roles:
  admin     — user management, system config, bias evaluation
  lecturer  — class management, live attendance, export
  student   — view own attendance, self-enrol face

Usage:
    python main.py              # Launch AttendIQ (multi-role UI)
    python main.py --evaluate   # Run bias evaluation in CLI mode
    python main.py --legacy     # Launch the original single-panel GUI
"""

import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def launch_app():
    """Launch the full multi-role AttendIQ application."""
    from gui.app import main
    main()


def launch_legacy():
    """Launch the original single-window GUI (kept for reference)."""
    logging.warning(
        "Legacy GUI launched. This interface is superseded by AttendIQ."
    )
    # Import the original app — it still lives in its original form
    # but is now archived; kept for demo / fallback purposes only.
    try:
        # The original FaceRecognitionApp is no longer the default app.py,
        # so we replicate the minimal bootstrap here.
        from core.config   import Config
        from core.face_detector import FaceDetector
        from core.face_encoder  import FaceEncoder
        from core.recognizer    import Recognizer
        from core.attendance    import AttendanceManager
        print("Legacy GUI not available after refactor. Run without --legacy.")
    except Exception as e:
        print(f"Legacy GUI error: {e}")


def run_bias_evaluation():
    """Run bias evaluation on the evaluation dataset (CLI mode)."""
    from core.config      import Config
    from core.face_detector import FaceDetector
    from core.face_encoder  import FaceEncoder
    from core.recognizer    import Recognizer
    from bias.evaluator     import BiasEvaluator
    from bias.datasets      import DatasetHelper

    config = Config()
    detector   = FaceDetector(model="haar")
    encoder    = FaceEncoder(engine=config.recognition_engine,
                              tolerance=config.tolerance)
    recognizer = Recognizer(detector, encoder)
    recognizer.load_database(config.known_faces_dir)

    evaluator = BiasEvaluator(recognizer)
    helper    = DatasetHelper(os.path.join(config.base_dir,
                                            "data", "evaluation_dataset"))

    print("=" * 54)
    print("  AttendIQ — Bias & Fairness Evaluation")
    print("=" * 54)
    print()

    dataset_dir  = os.path.join(config.base_dir, "data", "evaluation_dataset")
    annotations  = os.path.join(dataset_dir, "annotations.csv")

    print("1. Creating sample dataset structure…")
    helper.create_sample_dataset()

    print("2. Generating annotations template…")
    helper.generate_annotations_template(annotations)

    print(f"\nDataset directory : {dataset_dir}")
    print(f"Annotations file  : {annotations}")
    print()
    print("NEXT STEPS:")
    print("  1. Place labelled face images in the demographic sub-folders")
    print("  2. Fill in annotations.csv with correct demographics")
    print("  3. Re-run this command to evaluate")
    print()

    if os.path.exists(annotations):
        print("Running evaluation…")
        metrics = evaluator.evaluate(dataset_dir, annotations)
        if metrics:
            o = metrics.get("overall", {})
            print(f"\n  Detection Rate      : {o.get('detection_rate', 0):.1%}")
            print(f"  Recognition Accuracy: {o.get('recognition_accuracy', 0):.1%}")

            print("\n  By Skin Type:")
            for st, m in metrics.get("by_skin_type", {}).items():
                print(f"    Type {st}: {m['accuracy']:.1%}  (n={m['count']})")

            print("\n  By Gender:")
            for g, m in metrics.get("by_gender", {}).items():
                print(f"    {g}: {m['accuracy']:.1%}  (n={m['count']})")

            results_path = os.path.join(dataset_dir, "results.csv")
            metrics_path = os.path.join(dataset_dir, "metrics.json")
            evaluator.save_results(results_path)
            evaluator.save_metrics(metrics_path)
            print(f"\n  Results → {results_path}")
            print(f"  Metrics → {metrics_path}")


def main():
    parser = argparse.ArgumentParser(
        description="AttendIQ — Facial Recognition Attendance System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--evaluate", action="store_true",
        help="Run bias evaluation (CLI mode)"
    )
    parser.add_argument(
        "--legacy", action="store_true",
        help="Launch legacy single-panel GUI"
    )
    parser.add_argument(
        "--tkinter", action="store_true",
        help="Launch the original Tkinter GUI instead of the Web UI"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable DEBUG logging"
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("face_recog.log", encoding="utf-8"),
        ],
    )

    if args.evaluate:
        run_bias_evaluation()
    elif args.legacy:
        launch_legacy()
    elif args.tkinter:
        launch_app()
    else:
        # Launch Web UI
        from main_web import find_free_port, start_backend, on_closing
        import threading
        import time
        import webview
        
        port = find_free_port()
        server_thread = threading.Thread(target=start_backend, args=(port,), daemon=True)
        server_thread.start()
        time.sleep(0.5)

        window = webview.create_window(
            title="AttendIQ — Facial Recognition Attendance System",
            url=f"http://127.0.0.1:{port}",
            width=1400,
            height=850,
            min_size=(1200, 700),
            background_color="#0f0f1a"
        )
        window.events.closing += on_closing
        webview.start(debug=True)


if __name__ == "__main__":
    main()
