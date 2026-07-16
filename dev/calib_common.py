"""Shared primitives for the threshold-calibration toolchain (dev/ scripts).

Spec: docs/superpowers/specs/2026-07-16-threshold-calibration-design.md
"""
import csv
import re
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


DETECTION_KEYS = ("ear_threshold", "mar_threshold",
                  "yaw_threshold", "pitch_threshold")

_KEY_LINE_RE = re.compile(r"^(\s+)([A-Za-z_]\w*):\s*(-?[\d.]+)\s*(#.*)?$")


def _detection_block_span(lines):
    """Return (start, end) line indices of the detection: block. end is exclusive."""
    start = None
    for i, ln in enumerate(lines):
        if re.match(r"^detection:\s*(#.*)?$", ln):
            start = i
            break
    if start is None:
        raise ValueError("no 'detection:' section found in config text")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^[A-Za-z_]", lines[j]):  # next top-level key
            end = j
            break
    return start, end


def parse_detection_thresholds(config_text):
    lines = config_text.splitlines()
    start, end = _detection_block_span(lines)
    found = {}
    for i in range(start + 1, end):
        m = _KEY_LINE_RE.match(lines[i])
        if m and m.group(2) in DETECTION_KEYS:
            found[m.group(2)] = float(m.group(3))
    missing = set(DETECTION_KEYS) - set(found)
    if missing:
        raise ValueError(f"detection block is missing keys: {sorted(missing)}")
    return found


def edit_detection_thresholds(config_text, updates, note):
    """Targeted line edit: change only the given keys inside detection:.

    Preserves every other byte of the file (hand-written comments included).
    """
    ends_with_nl = config_text.endswith("\n")
    lines = config_text.splitlines()
    start, end = _detection_block_span(lines)
    applied = set()
    for i in range(start + 1, end):
        m = _KEY_LINE_RE.match(lines[i])
        if not m:
            continue
        indent, key, old, _comment = m.groups()
        if key in updates:
            lines[i] = (f"{indent}{key}: {updates[key]}"
                        f"  # calibrated {note} (was {old})")
            applied.add(key)
    missing = set(updates) - applied
    if missing:
        raise ValueError(f"keys not found in detection block: {sorted(missing)}")
    return "\n".join(lines) + ("\n" if ends_with_nl else "")


def preprocess_bgr(frame, config):
    """Replicate the live server's preprocess_frame (frame_processor.py:219-230)."""
    import cv2

    rf = float((config.get("performance") or {}).get("resize_factor", 1.0))
    if rf != 1.0:
        frame = cv2.resize(frame, None, fx=rf, fy=rf)

    cl = config.get("clahe") or {}
    if cl.get("enabled", True):
        clahe = cv2.createCLAHE(
            clipLimit=float(cl.get("clip_limit", 2.0)),
            tileGridSize=tuple(int(t) for t in cl.get("base_tile_grid_size", [8, 8])),
        )
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        frame = cv2.cvtColor(cv2.merge((clahe.apply(l), a, b)), cv2.COLOR_LAB2BGR)
    return frame


def is_grayscale_like(frame):
    """True if effectively monochrome (IR stored as RGB): channel spread <= 8."""
    import numpy as np

    if frame.ndim == 2 or frame.shape[2] == 1:
        return True
    spread = frame.max(axis=2).astype(np.int16) - frame.min(axis=2).astype(np.int16)
    return bool(spread.max() <= 8)
