"""Shared primitives for the threshold-calibration toolchain (dev/ scripts).

Spec: docs/superpowers/specs/2026-07-16-threshold-calibration-design.md
"""
import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = REPO_ROOT / "dataset"
RAW_DIR = REPO_ROOT / "dataset_raw"
CALIB_DIR = REPO_ROOT / "test_results" / "calibration"
ANNOTATIONS_CSV = DATASET_DIR / "annotations.csv"
CONFIG_YAML = REPO_ROOT / "config.yaml"

IMAGE_EXTS = (".jpg", ".jpeg", ".png")

CSV_FIELDS = [
    "relpath", "split", "behavior", "label", "face_detected",
    "landmarks_detected", "ear", "left_ear", "right_ear", "mar",
    "yaw", "pitch", "width", "height", "grayscale_like",
]

BEHAVIORS = {
    "drowsy": {"pos": "is_drowsy", "neg": "not_drowsy"},
    "yawning": {"pos": "is_yawning", "neg": "no_yawn"},
    "distracted": {"pos": "is_distracted", "neg": "safe_driving"},
}

CLASS_TO_BEHAVIOR = {}
for _behavior, _spec in BEHAVIORS.items():
    CLASS_TO_BEHAVIOR[_spec["pos"]] = (_behavior, 1)
    CLASS_TO_BEHAVIOR[_spec["neg"]] = (_behavior, 0)

CLASS_DIRS = tuple(CLASS_TO_BEHAVIOR)

_FLOAT_FIELDS = ("ear", "left_ear", "right_ear", "mar", "yaw", "pitch")
_INT_FIELDS = ("label", "width", "height")
_BOOL_FIELDS = ("face_detected", "landmarks_detected", "grayscale_like")


def every_nth(items, k):
    """Deterministic, RNG-free spread sample: sort, pick k evenly spaced."""
    items = sorted(items)
    n = len(items)
    if k <= 0:
        return []
    if n <= k:
        return items
    return [items[(i * n) // k] for i in range(k)]


def load_annotations(csv_path):
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            row = dict(raw)
            for k in _FLOAT_FIELDS:
                row[k] = float(raw[k]) if raw.get(k) not in (None, "") else None
            for k in _INT_FIELDS:
                row[k] = int(raw[k]) if raw.get(k) not in (None, "") else None
            for k in _BOOL_FIELDS:
                row[k] = raw.get(k) == "1"
            rows.append(row)
    return rows


def valid_rows(rows):
    return [r for r in rows if r["face_detected"] and r["landmarks_detected"]]


def rows_for(rows, split, behavior):
    pos = [r for r in rows if r["split"] == split
           and r["behavior"] == behavior and r["label"] == 1]
    neg = [r for r in rows if r["split"] == split
           and r["behavior"] == behavior and r["label"] == 0]
    return pos, neg


def predict_row(behavior, row, th):
    """Instantaneous detection predicate — mirrors improved_detection.py:383-393."""
    if behavior == "drowsy":
        return row["ear"] < th["ear_threshold"]
    if behavior == "yawning":
        return row["mar"] > th["mar_threshold"]
    if behavior == "distracted":
        return (abs(row["yaw"]) > th["yaw_threshold"]
                or abs(row["pitch"]) > th["pitch_threshold"])
    raise ValueError(f"unknown behavior: {behavior}")
