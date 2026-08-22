# Face Recognition Attendance System with Bias Evaluation

A bias-aware facial recognition system for automated attendance tracking, built as a final year project. This system integrates the best components from three existing implementations and adds a novel bias evaluation module based on the **Gender Shades** methodology.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Motivation & Problem Statement](#motivation--problem-statement)
3. [System Architecture](#system-architecture)
4. [Module Breakdown](#module-breakdown)
5. [Installation & Setup](#installation--setup)
6. [Usage Guide](#usage-guide)
7. [Bias Evaluation Framework](#bias-evaluation-framework)
8. [Configuration](#configuration)
9. [Project Structure](#project-structure)
10. [Technical Decisions](#technical-decisions)
11. [Known Limitations](#known-limitations)
12. [Future Work](#future-work)
13. [References](#references)
14. [License](#license)

---

## Project Overview

This system automates attendance tracking using real-time facial recognition via webcam. It features:

- **Real-time face detection and recognition** using OpenCV (Haar Cascade + LBPH face recognizer)
- **Interactive GUI** with live camera feed, attendance logging, and enrollment controls
- **Configurable parameters** via external INI configuration file
- **Bias evaluation module** to measure recognition accuracy across skin tones and genders
- **CSV-based attendance export** with session deduplication

### Key Differentiator: Bias Evaluation

Unlike standard facial recognition attendance systems, this project includes a **bias evaluation framework** that measures accuracy disparities across the **Fitzpatrick skin type scale** (Types I-VI) and gender categories. This is based on the groundbreaking **Gender Shades** research by Joy Buolamwini (MIT Media Lab, 2018), which exposed significant accuracy gaps in commercial face recognition systems.

---

## Motivation & Problem Statement

### The Problem
Traditional attendance systems (manual roll call, ID cards, fingerprints) are time-consuming, prone to proxy attendance, and unhygienic. Facial recognition offers a contactless, automated alternative.

### The Bias Problem
However, facial recognition systems are not equally accurate across all demographics. Research has shown:
- Higher error rates for darker-skinned individuals
- Disparities between male and female recognition accuracy
- Intersectional biases (e.g., darker-skinned women have the highest error rates)

### Our Approach
This project builds a functional attendance system **and** quantifies its biases, providing transparency about where the system performs well and where it needs improvement.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    MAIN APPLICATION                      │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   GUI Layer  │  │  Data Layer  │  │ Config Layer │ │
│  │  (Tkinter)   │  │   (CSV/OS)   │  │  (INI file)  │ │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘ │
│         │                 │                             │
│  ┌──────┴─────────────────┴───────┐                    │
│  │         CORE ENGINE            │                    │
│  │                                │                    │
│  │  ┌────────────┐ ┌───────────┐ │                    │
│  │  │  Detector   │ │  Encoder  │ │                    │
│  │  │  (Haar)    │ │ (LBPH)   │ │                    │
│  │  └──────┬─────┘ └─────┬─────┘ │                    │
│  │         │              │       │                    │
│  │  ┌──────┴──────────────┴─────┐ │                    │
│  │  │      Recognizer Engine    │ │                    │
│  │  │  (Detection + Encoding +  │ │                    │
│  │  │   Best-Match Algorithm)   │ │                    │
│  │  └───────────────────────────┘ │                    │
│  └────────────────────────────────┘                    │
│                                                         │
│  ┌────────────────────────────────┐                    │
│  │      BIAS EVALUATION MODULE    │                    │
│  │  (Gender Shades Methodology)   │                    │
│  │  - Skin Type Analysis (I-VI)   │                    │
│  │  - Gender Analysis             │                    │
│  │  - Intersectional Metrics      │                    │
│  └────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
Webcam → Frame Capture → Downscale (25%) → Face Detection (HOG)
    → Face Encoding (128-D) → Match Against Database
    → Identity + Confidence → Attendance Record (CSV)
    → GUI Display (bounding boxes + names)
```

---

## Module Breakdown

### 1. Configuration Module (`core/config.py`)
**Source:** Adapted from Smart-Attendance-System-Using-OpenCV's `config.ini` concept

- Singleton pattern for centralized configuration
- Reads from `config.ini` with sensible defaults
- Type-safe getters (`getint`, `getfloat`, `getboolean`)
- Auto-creates default config if missing
- Auto-creates required directories

### 2. Face Detection Module (`core/face_detector.py`)
**Source:** Adapted from Attendance-System-Using-OpenCv's detection approach (now using pure OpenCV)

- HOG-based detector (CPU) or CNN-based (GPU)
- Face landmark detection support
- Bounding box drawing with name labels
- Face cropping with configurable padding
- Largest face selection for single-face capture

### 3. Face Encoding Module (`core/face_encoder.py`)
**Source:** Adapted from Attendance-System-Using-OpenCv's encoding approach (LBPH-based)

- 128-dimensional face encoding computation
- Batch encoding for multiple images
- Known faces database management (load/save/add/remove)
- Best-match identification with configurable tolerance
- Supports both flat and hierarchical directory structures

### 4. Data Collection Module (`core/data_collector.py`)
**Source:** Merged from AMS's `take_img()` and Attendance-System's `Face Classifier.py`

- **Interactive mode:** User presses SPACE to capture (from Project 1)
- **Auto mode:** Automatically captures detected faces (from Project 2)
- Live preview with face bounding boxes
- Configurable number of samples and padding
- Per-person subdirectory organization

### 5. Recognition Engine (`core/recognizer.py`)
**Source:** Merged from Attendance-System's encoding matching + Smart-System's best-match

- Combines detector and encoder for end-to-end recognition
- Frame downscaling for real-time performance (25% scale)
- Best-match algorithm using `face_distance()` + `argmin()`
- Single-frame and continuous loop modes
- Thread-safe camera management

### 6. Attendance Manager (`core/attendance.py`)
**Source:** Merged from AMS's dual output + Smart-System's session dedup

- CSV-based attendance storage
- Session-based duplicate prevention
- Automatic file naming (Subject_Date.csv)
- ISO-8601 timestamps
- Summary statistics and export

### 7. GUI Application (`gui/app.py`)
**Source:** Merged from AMS's panel layout + Smart-System's threaded camera

- Live camera feed in Tkinter using PIL
- Threaded camera processing (GUI stays responsive)
- Control panels: Start/Stop, Register, Session, Export
- Real-time session log display
- Status bar with current state

### 8. Bias Evaluation Module (`bias/evaluator.py`)
**Source:** NEW - Gender Shades methodology

- Fitzpatrick skin type classification (Types I-VI)
- Per-group accuracy metrics
- Intersectional analysis (skin type × gender)
- Disparity gap calculation
- Results export to CSV and JSON

---

## Installation & Setup

### Prerequisites

- Python 3.8+
- Webcam
- Windows/Linux/macOS

### Step 1: Install Dependencies

```bash
cd facialrecognitionsystem
pip install -r requirements.txt
```

> **Note:** This system uses pure OpenCV — no C++ compiler or CMake needed.

### Step 2: Verify Installation

```bash
python -c "import cv2; print('OpenCV', cv2.__version__)"
python -c "import cv2.face; print('LBPH available')"
```

### Step 3: Configure (Optional)

Edit `config.ini` to adjust camera index, recognition tolerance, or paths.

---

## Usage Guide

### Launch GUI Mode

```bash
python main.py
```

1. Click **"Register New Person"** to enroll faces
2. Enter a subject name (e.g., "CS101")
3. Click **"Start Camera"** to begin recognition
4. Attendance is logged automatically
5. Click **"Export Attendance"** to save

### Data Collection Mode

```bash
python main.py --collect
```

Interactive CLI for batch face enrollment without the GUI.

### Test Mode

```bash
python main.py --test
```

Quick webcam test to verify recognition works.

### Bias Evaluation Mode

```bash
python main.py --evaluate
```

Sets up the evaluation dataset structure and runs metrics.

---

## Bias Evaluation Framework

### Methodology: Gender Shades

Based on Joy Buolamwini's research at MIT Media Lab (2018):

1. **Fitzpatrick Skin Type Scale** - Classifies skin into 6 types:
   - Type I: Very Light (always burns)
   - Type II: Light (usually burns)
   - Type III: Medium (sometimes burns)
   - Type IV: Olive (rarely burns)
   - Type V: Dark (very rarely burns)
   - Type VI: Very Dark (never burns)

2. **Gender Categories** - Male, Female, Non-Binary

3. **Metrics Measured:**
   - **Detection Rate:** % of faces successfully detected
   - **Recognition Accuracy:** % of detected faces correctly identified
   - **False Negative Rate:** % of known faces not recognized
   - **Disparity Gap:** Accuracy difference between best and worst performing groups

### Running an Evaluation

1. Place face images in `data/evaluation_dataset/` organized by demographic group
2. Fill in `annotations.csv` with correct skin type and gender labels
3. Run: `python main.py --evaluate`
4. Review the disparity report

### Expected Output

```
--- Overall Metrics ---
  Detection Rate:     95.0%
  Recognition Accuracy: 87.3%
  False Negatives:    12

--- By Skin Type ---
  Type I: accuracy=94.2% (n=50)
  Type II: accuracy=92.1% (n=48)
  Type III: accuracy=89.5% (n=52)
  Type IV: accuracy=85.3% (n=47)
  Type V: accuracy=78.6% (n=51)
  Type VI: accuracy=72.4% (n=49)

--- Disparity Report ---
  Skin Type Gap: 21.8% (Type VI → Type I)
  Gender Gap:    8.3% (Female → Male)
```

---

## Configuration

### `config.ini`

```ini
[Paths]
KNOWN_FACES_DIR = data/known_faces
TRAINING_DIR = data/training
ATTENDANCE_DIR = data/attendance
MODELS_DIR = models

[Camera]
CAMERA_INDEX = 0
FRAME_SCALE = 0.25
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

[Recognition]
TOLERANCE = 0.6
MODEL = haar
NUMBER_OF_SAMPLES = 100
FACE_PADDING = 20

[Attendance]
SESSION_TIMEOUT = 60
DUPLICATE_PREVENTION = true
EXPORT_FORMAT = csv

[Security]
ADMIN_PASSWORD = admin

[Logging]
LEVEL = INFO
FILE = face_recog.log
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `TOLERANCE` | Match threshold (lower = stricter) | 0.6 |
| `FRAME_SCALE` | Detection downscale factor | 0.25 |
| `MODEL` | Detection model (`haar`/`dnn`) | haar |
| `NUMBER_OF_SAMPLES` | Images per person for enrollment | 100 |
| `DUPLICATE_PREVENTION` | Prevent double-marking per session | true |

---

## Project Structure

```
FaceRecogSystem/
├── main.py                 # Entry point with CLI modes
├── config.ini              # Externalized configuration
├── requirements.txt        # Python dependencies
│
├── core/                   # Core business logic
│   ├── __init__.py
│   ├── config.py           # Configuration manager (singleton)
│   ├── face_detector.py    # Face detection (Haar/DNN)
│   ├── face_encoder.py     # Face encoding (128-D vectors)
│   ├── data_collector.py   # Training data capture
│   ├── recognizer.py       # Recognition engine
│   └── attendance.py       # Attendance record management
│
├── gui/                    # User interface
│   ├── __init__.py
│   └── app.py              # Tkinter GUI application
│
├── bias/                   # Bias evaluation framework
│   ├── __init__.py
│   ├── evaluator.py        # Bias metrics computation
│   └── datasets.py         # Dataset management helpers
│
├── data/                   # Runtime data
│   ├── known_faces/        # Known face images (by person)
│   ├── training/           # Captured training images
│   └── attendance/         # Attendance CSV files
│
└── models/                 # Saved models (future use)
```

---

## Technical Decisions

### Why Pure OpenCV (no dlib)?

| Aspect | face_recognition (dlib) | Pure OpenCV |
|--------|------------------------|-------------|
| Installation | Requires CMake + C++ compiler | `pip install` only |
| Accuracy | Higher (~95%+) | Good (~85-90% with LBPH) |
| Training Required | No (encoding-based) | Yes (LBPH training) |
| Enrollment Speed | Fast (1 image) | Needs multiple images |
| Cross-platform | Compilation issues on Windows | Works everywhere |
| Dependencies | dlib (heavy) | opencv-contrib-python (light) |

We chose pure OpenCV because:
1. No compilation issues — works on any system with `pip install`
2. LBPH is well-studied for bias research (lighter skin bias documented)
3. Training step provides explicit control over the recognition model
4. OpenCV's face module is mature and well-documented

### Why Threaded Camera?

- Tkinter is single-threaded; camera processing blocks the event loop
- Threading keeps the GUI responsive during frame processing
- `root.after()` is used for thread-safe GUI updates

### Why CSV over SQLite?

- Simpler for a final year project demonstration
- Easy to open in Excel/Google Sheets for analysis
- Human-readable for presentation to markers
- Can be upgraded to SQLite later (architecture supports it)

---

## Known Limitations

1. **Frontal face only** — HOG detector struggles with profiles and occlusions
2. **No liveness detection** — Photos/videos can fool the system
3. **Single reference image** — Multiple images per person would improve accuracy
4. **No GPU acceleration** — CNN mode available but not default
5. **Lighting sensitivity** — Performance degrades in poor lighting
6. **CSV race conditions** — Multiple concurrent sessions could corrupt files
7. **No encryption** — Face data stored as plain images

---

## Future Work

1. **Deep learning models** — Add FaceNet/ArcFace for higher accuracy
2. **Liveness detection** — Add blink detection or 3D depth analysis
3. **Multiple reference images** — Average encodings across multiple poses
4. **SQLite backend** — Replace CSV for better data integrity
5. **Web dashboard** — Flask/FastAPI interface for attendance reports
6. **Mobile app** — Cross-platform with React Native or Flutter
7. **Bias mitigation** — Implement re-weighting or domain adaptation techniques
8. **GDPR compliance** — Add consent management and data retention policies

---

## References

1. **Buolamwini, J. & Gebru, T.** (2018). "Gender Shades: Intersectional Accuracy Disparities in Commercial Gender Classification." *Proceedings of Machine Learning Research*, 81, 1-15.

2. **King, D.E.** (2009). "Dlib-ml: A Machine Learning Toolkit." *Journal of Machine Learning Research*, 10, 1755-1758.

3. **Face Recognition with Python** — https://github.com/ageitgey/face_recognition

4. **OpenCV Documentation** — https://docs.opencv.org/

5. **Fitzpatrick Skin Type Scale** — Fitzpatrick, T.B. (1975). "Soleil et peau." *Journal de Médecine Esthétique*, 2, 33-34.

---

## License

MIT License — See LICENSE file for details.

---

## Acknowledgments

This project builds upon three open-source attendance systems:
- **Attendace_management_system** — Tkinter GUI and end-to-end workflow
- **Attendance-System-Using-OpenCv** — Detection and encoding patterns
- **Smart-Attendance-System-Using-OpenCV** — Configuration and threading patterns

The bias evaluation framework is inspired by the **Gender Shades** project at MIT Media Lab.
