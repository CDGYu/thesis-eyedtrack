# Data-Calibrated Detection Thresholds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Machine-annotate the driver-behavior dataset with the pipeline's own EAR/MAR/yaw/pitch values, calibrate the four `config.yaml → detection:` thresholds against proper negative classes, and rebuild a defensible evaluation harness.

**Architecture:** Five standalone CLI scripts in `dev/` share a small common module (`dev/calib_common.py`). Data flows one way: `dataset_raw/` → `prepare_dataset.py` → `dataset/` → `annotate_dataset.py` → `dataset/annotations.csv` → (`spotcheck_labels.py` human gate) → `calibrate_thresholds.py` → `config.yaml` + figures → `evaluate_dataset.py` → reports. No server code changes except the four numeric values in `config.yaml`.

**Tech Stack:** Python 3.14 (`py -3.14`), OpenCV 4.13, dlib 20.0.1, numpy (already installed); scikit-learn, matplotlib, pytest (installed by Task 1). Spec: `docs/superpowers/specs/2026-07-16-threshold-calibration-design.md`.

## Global Constraints

- Run all Python as `py -3.14`; run pytest as `py -3.14 -m pytest`.
- Images are always **BGR** `np.ndarray` (`cv2.imread` default). Never RGB.
- Use `ImprovedFaceAnalyzer` directly for metrics; **never** `OptimizedFrameProcessor` (temporal counters persist across calls; its constructor instantiates `VideoRecorder`, which creates directories).
- Annotation applies the live server preprocessing first: resize ×`performance.resize_factor` (0.75) then CLAHE on LAB-L (clip 2.5, tile 8×8), per `frame_processor.py:219-230`.
- All sampling is deterministic and RNG-free: sort, then take every Nth. No `random`, no seeds.
- `analyze_frame` returns 0.0 for EAR/MAR both as a real value and as an error sentinel — a row is usable only when `face_detected AND landmarks_detected`.
- `config.yaml` is modified only by targeted line edit inside the `detection:` block (starts at line 112) — comments elsewhere must survive byte-identical. The four keys: `ear_threshold` (now 0.27), `mar_threshold` (0.6), `yaw_threshold` (35), `pitch_threshold` (25).
- Distraction predicate is the pipeline's actual rule (`face_analysis/improved_detection.py:393`): `abs(yaw) > yaw_threshold OR abs(pitch) > pitch_threshold`.
- New code lives in `dev/` only. Test files in `dev/tests/`. Windows: multiprocessing uses spawn — workers are initialized via a pool initializer (dlib objects don't pickle).
- Behavior/class vocabulary (used everywhere): behaviors `drowsy`/`yawning`/`distracted`; class folders `is_drowsy`/`not_drowsy`/`is_yawning`/`no_yawn`/`is_distracted`/`safe_driving`.
- Commit after every task with the trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Scaffolding + `calib_common` core (paths, vocab, sampling, annotation rows)

**Files:**
- Create: `dev/requirements-dev.txt`
- Create: `dev/calib_common.py`
- Create: `dev/tests/conftest.py`
- Test: `dev/tests/test_calib_common.py`
- Modify: `.gitignore` (append block at end)

**Interfaces:**
- Consumes: nothing (first task).
- Produces (all later tasks import these from `calib_common`):
  - `REPO_ROOT, DATASET_DIR, RAW_DIR, CALIB_DIR, ANNOTATIONS_CSV, CONFIG_YAML: pathlib.Path`
  - `CSV_FIELDS: list[str]` — annotation CSV column order
  - `BEHAVIORS: dict[str, dict]` — behavior → `{"pos": class_dir, "neg": class_dir}`
  - `CLASS_TO_BEHAVIOR: dict[str, tuple[str, int]]` — class_dir → (behavior, label 1/0)
  - `CLASS_DIRS: tuple[str, ...]` — the 6 class folder names
  - `IMAGE_EXTS: tuple[str, ...]`
  - `every_nth(items, k) -> list` — deterministic spread sample of ≤k items
  - `load_annotations(csv_path) -> list[dict]` — typed rows (floats/ints/bools parsed, empty → None)
  - `valid_rows(rows) -> list[dict]` — rows with face AND landmarks detected
  - `rows_for(rows, split, behavior) -> tuple[list[dict], list[dict]]` — (positive rows, negative rows)
  - `predict_row(behavior, row, th) -> bool` — instantaneous detection predicate

- [ ] **Step 1: Install dev dependencies**

Create `dev/requirements-dev.txt`:

```
scikit-learn
matplotlib
pytest
```

Run: `py -3.14 -m pip install -r dev/requirements-dev.txt`
Expected: successful install (numpy/opencv/dlib already present).

- [ ] **Step 2: Append to `.gitignore`**

Append at the end of `.gitignore`:

```
# Calibration data (regenerable; see docs/superpowers/specs/2026-07-16-threshold-calibration-design.md)
dataset_raw/
dataset/annotations.csv
dataset/spotcheck.html
dataset/spotcheck_flags.csv
```

- [ ] **Step 3: Write the failing tests**

`dev/tests/conftest.py`:

```python
import sys
from pathlib import Path

DEV_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = DEV_DIR.parent
for p in (str(DEV_DIR), str(REPO_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
```

`dev/tests/test_calib_common.py`:

```python
import csv
from pathlib import Path

import calib_common as cc


def test_paths_point_into_repo():
    assert (cc.REPO_ROOT / "config.yaml").exists()
    assert cc.DATASET_DIR == cc.REPO_ROOT / "dataset"
    assert cc.ANNOTATIONS_CSV == cc.DATASET_DIR / "annotations.csv"


def test_vocab_is_consistent():
    assert set(cc.BEHAVIORS) == {"drowsy", "yawning", "distracted"}
    for behavior, spec in cc.BEHAVIORS.items():
        assert cc.CLASS_TO_BEHAVIOR[spec["pos"]] == (behavior, 1)
        assert cc.CLASS_TO_BEHAVIOR[spec["neg"]] == (behavior, 0)
    assert len(cc.CLASS_DIRS) == 6


def test_every_nth_spreads_and_is_deterministic():
    items = [f"img_{i:03d}.jpg" for i in range(100)]
    picked = cc.every_nth(items, 10)
    assert len(picked) == 10
    assert picked == sorted(picked)
    assert picked[0] == "img_000.jpg"
    assert cc.every_nth(list(reversed(items)), 10) == picked  # order-insensitive
    assert cc.every_nth(items, 200) == sorted(items)          # k >= n returns all
    assert cc.every_nth(items, 0) == []
    assert len(set(cc.every_nth(items, 99))) == 99            # no duplicates


def test_load_annotations_types_and_valid_rows(tmp_path):
    p = tmp_path / "ann.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cc.CSV_FIELDS)
        w.writeheader()
        w.writerow({"relpath": "train/is_drowsy/a.jpg", "split": "train",
                    "behavior": "drowsy", "label": "1", "face_detected": "1",
                    "landmarks_detected": "1", "ear": "0.21", "left_ear": "0.20",
                    "right_ear": "0.22", "mar": "0.05", "yaw": "-3.5", "pitch": "10.0",
                    "width": "640", "height": "480", "grayscale_like": "0"})
        w.writerow({"relpath": "train/not_drowsy/b.jpg", "split": "train",
                    "behavior": "drowsy", "label": "0", "face_detected": "0",
                    "landmarks_detected": "0", "ear": "", "left_ear": "", "right_ear": "",
                    "mar": "", "yaw": "", "pitch": "", "width": "", "height": "",
                    "grayscale_like": "1"})
    rows = cc.load_annotations(p)
    assert len(rows) == 2
    assert rows[0]["ear"] == 0.21 and isinstance(rows[0]["label"], int)
    assert rows[0]["face_detected"] is True
    assert rows[1]["ear"] is None and rows[1]["face_detected"] is False
    ok = cc.valid_rows(rows)
    assert [r["relpath"] for r in ok] == ["train/is_drowsy/a.jpg"]


def test_rows_for_splits_by_behavior_and_label(tmp_path):
    rows = [
        {"split": "train", "behavior": "drowsy", "label": 1, "relpath": "p1"},
        {"split": "train", "behavior": "drowsy", "label": 0, "relpath": "n1"},
        {"split": "test", "behavior": "drowsy", "label": 1, "relpath": "p2"},
        {"split": "train", "behavior": "yawning", "label": 1, "relpath": "y1"},
    ]
    pos, neg = cc.rows_for(rows, "train", "drowsy")
    assert [r["relpath"] for r in pos] == ["p1"]
    assert [r["relpath"] for r in neg] == ["n1"]


def test_predict_row_matches_pipeline_predicates():
    th = {"ear_threshold": 0.25, "mar_threshold": 0.7,
          "yaw_threshold": 25.0, "pitch_threshold": 15.0}
    assert cc.predict_row("drowsy", {"ear": 0.20}, th) is True
    assert cc.predict_row("drowsy", {"ear": 0.30}, th) is False
    assert cc.predict_row("yawning", {"mar": 0.90}, th) is True
    assert cc.predict_row("yawning", {"mar": 0.50}, th) is False
    assert cc.predict_row("distracted", {"yaw": -30.0, "pitch": 0.0}, th) is True
    assert cc.predict_row("distracted", {"yaw": 0.0, "pitch": -20.0}, th) is True
    assert cc.predict_row("distracted", {"yaw": 10.0, "pitch": 5.0}, th) is False
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `py -3.14 -m pytest dev/tests/test_calib_common.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'calib_common'`

- [ ] **Step 5: Write `dev/calib_common.py` (core half)**

```python
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
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `py -3.14 -m pytest dev/tests/test_calib_common.py -v`
Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add dev/requirements-dev.txt dev/calib_common.py dev/tests/conftest.py dev/tests/test_calib_common.py .gitignore
git commit -m "dev: calibration toolchain scaffolding + shared primitives"
```

---

### Task 2: Config line editor (comment-preserving)

**Files:**
- Modify: `dev/calib_common.py` (append functions)
- Test: `dev/tests/test_config_edit.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `DETECTION_KEYS: tuple[str, ...]` — `("ear_threshold", "mar_threshold", "yaw_threshold", "pitch_threshold")`
  - `parse_detection_thresholds(config_text: str) -> dict[str, float]` — current values of the 4 keys
  - `edit_detection_thresholds(config_text: str, updates: dict[str, float], note: str) -> str` — new text; only the updated key lines differ; each gets `# calibrated {note} (was {old})`

- [ ] **Step 1: Write the failing tests**

`dev/tests/test_config_edit.py`:

```python
import pytest

import calib_common as cc

SAMPLE = """\
camera:
  index: 0  # keep me

# a top-level comment
thresholds:
  drowsy_frames: 6     # ~0.2s at 30fps
  ear_threshold: 0.99  # decoy in wrong section — must NOT change

detection:
  use_improved_dlib: true
  # Eye aspect ratio threshold
  ear_threshold: 0.27  # raised from 0.25
  mar_threshold: 0.6   # CHANGED: Lowered from 0.7
  yaw_threshold: 35    # INCREASED
  pitch_threshold: 25  # INCREASED
"""


def test_parse_reads_only_detection_block():
    th = cc.parse_detection_thresholds(SAMPLE)
    assert th == {"ear_threshold": 0.27, "mar_threshold": 0.6,
                  "yaw_threshold": 35.0, "pitch_threshold": 25.0}


def test_edit_changes_only_target_lines():
    out = cc.edit_detection_thresholds(
        SAMPLE, {"ear_threshold": 0.238, "yaw_threshold": 27.5}, "2026-07-16")
    assert "ear_threshold: 0.238  # calibrated 2026-07-16 (was 0.27)" in out
    assert "yaw_threshold: 27.5  # calibrated 2026-07-16 (was 35)" in out
    # untouched keys keep their lines verbatim
    assert "mar_threshold: 0.6   # CHANGED: Lowered from 0.7" in out
    # decoy in thresholds: section untouched
    assert "ear_threshold: 0.99  # decoy in wrong section — must NOT change" in out
    # everything outside changed lines is byte-identical
    changed = {"ear_threshold", "yaw_threshold"}
    for old_line, new_line in zip(SAMPLE.splitlines(), out.splitlines()):
        key = old_line.strip().split(":")[0]
        if key not in changed or "decoy" in old_line:
            assert old_line == new_line
    # round-trip: parse of edited text sees new values
    th = cc.parse_detection_thresholds(out)
    assert th["ear_threshold"] == 0.238 and th["yaw_threshold"] == 27.5


def test_edit_raises_on_missing_key_or_section():
    with pytest.raises(ValueError):
        cc.edit_detection_thresholds(SAMPLE, {"nope_threshold": 1.0}, "d")
    with pytest.raises(ValueError):
        cc.edit_detection_thresholds("camera:\n  index: 0\n",
                                     {"ear_threshold": 0.2}, "d")


def test_real_config_yaml_round_trip():
    text = cc.CONFIG_YAML.read_text(encoding="utf-8")
    th = cc.parse_detection_thresholds(text)
    assert set(th) == set(cc.DETECTION_KEYS)
    out = cc.edit_detection_thresholds(text, dict(th), "test")
    assert cc.parse_detection_thresholds(out) == th
    # exactly 4 lines differ
    diffs = [1 for a, b in zip(text.splitlines(), out.splitlines()) if a != b]
    assert len(diffs) == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.14 -m pytest dev/tests/test_config_edit.py -v`
Expected: FAIL with `AttributeError: ... 'parse_detection_thresholds'`

- [ ] **Step 3: Append implementation to `dev/calib_common.py`**

```python
import re

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
```

(The `import re` goes at the top of the file with the other imports.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3.14 -m pytest dev/tests/test_config_edit.py dev/tests/test_calib_common.py -v`
Expected: all passed (the real-config test proves the editor works on the actual `config.yaml`).

- [ ] **Step 5: Commit**

```bash
git add dev/calib_common.py dev/tests/test_config_edit.py
git commit -m "dev: comment-preserving config.yaml detection-threshold editor"
```

---

### Task 3: Image preprocessing + grayscale detection helpers

**Files:**
- Modify: `dev/calib_common.py` (append functions)
- Test: `dev/tests/test_preprocess.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `preprocess_bgr(frame: np.ndarray, config: dict) -> np.ndarray` — replicates `frame_processor.py:219-230` (resize ×`performance.resize_factor`, CLAHE on LAB-L per `clahe:` config)
  - `is_grayscale_like(frame: np.ndarray) -> bool` — max per-pixel channel spread ≤ 8

- [ ] **Step 1: Write the failing tests**

`dev/tests/test_preprocess.py`:

```python
import numpy as np

import calib_common as cc

CFG = {"performance": {"resize_factor": 0.75},
       "clahe": {"enabled": True, "clip_limit": 2.5,
                 "base_tile_grid_size": [8, 8]}}


def _gradient_bgr(h=480, w=640):
    """Deterministic synthetic color image (no RNG)."""
    y = np.linspace(0, 255, h, dtype=np.uint8)[:, None]
    x = np.linspace(0, 255, w, dtype=np.uint8)[None, :]
    img = np.stack([np.broadcast_to(y, (h, w)),
                    np.broadcast_to(x, (h, w)),
                    np.broadcast_to((y // 2 + x // 2).astype(np.uint8), (h, w))],
                   axis=2)
    return np.ascontiguousarray(img)


def test_preprocess_resizes_by_factor():
    out = cc.preprocess_bgr(_gradient_bgr(), CFG)
    assert out.shape == (360, 480, 3)  # 480*0.75, 640*0.75


def test_preprocess_noop_when_disabled():
    cfg = {"performance": {"resize_factor": 1.0}, "clahe": {"enabled": False}}
    img = _gradient_bgr()
    out = cc.preprocess_bgr(img, cfg)
    assert out.shape == img.shape
    assert np.array_equal(out, img)


def test_preprocess_clahe_changes_pixels_but_not_shape():
    cfg = {"performance": {"resize_factor": 1.0},
           "clahe": {"enabled": True, "clip_limit": 2.5,
                     "base_tile_grid_size": [8, 8]}}
    img = _gradient_bgr()
    out = cc.preprocess_bgr(img, cfg)
    assert out.shape == img.shape
    assert not np.array_equal(out, img)


def test_is_grayscale_like():
    gray3 = np.full((10, 10, 3), 100, dtype=np.uint8)
    assert cc.is_grayscale_like(gray3) is True
    near_gray = gray3.copy()
    near_gray[:, :, 2] = 106  # spread 6 <= 8
    assert cc.is_grayscale_like(near_gray) is True
    color = gray3.copy()
    color[:, :, 0] = 200
    assert cc.is_grayscale_like(color) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.14 -m pytest dev/tests/test_preprocess.py -v`
Expected: FAIL with `AttributeError: ... 'preprocess_bgr'`

- [ ] **Step 3: Append implementation to `dev/calib_common.py`**

```python
def preprocess_bgr(frame, config):
    """Replicate the live server's preprocess_frame (frame_processor.py:219-230)."""
    import cv2

    rf = float((config.get("performance") or {}).get("resize_factor", 1.0))
    if rf != 1.0:
        frame = cv2.resize(frame, None, fx=rf, fy=rf)

    cl = config.get("clahe") or {}
    if cl.get("enabled", False):
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
```

(`cv2`/`numpy` are imported inside the functions so that pure-logic consumers of `calib_common` — e.g. the config editor tests — don't require OpenCV.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3.14 -m pytest dev/tests/test_preprocess.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add dev/calib_common.py dev/tests/test_preprocess.py
git commit -m "dev: server-faithful preprocessing + grayscale/IR detection helpers"
```

---

### Task 4: `prepare_dataset.py` — rebuild dataset/ from dataset_raw/

**Files:**
- Create: `dev/prepare_dataset.py`
- Test: `dev/tests/test_prepare_dataset.py`

**Interfaces:**
- Consumes: `calib_common.every_nth, RAW_DIR, DATASET_DIR, CLASS_DIRS, IMAGE_EXTS`
- Produces:
  - CLI: `py -3.14 dev/prepare_dataset.py [--raw-dir P] [--out-dir P] [--train-cap 5000] [--test-cap 300] [--dry-run]`
  - `discover_sources(raw_dir: Path) -> dict[str, list[Path]]` — class_dir → source image paths (test seam)
  - `plan_layout(sources: dict, train_cap: int, test_cap: int) -> dict[tuple[str, str], list[Path]]` — (split, class_dir) → chosen source paths (pure, deterministic)
  - On-disk result: `dataset/{train,test}/{6 class dirs}/*.jpg` + `dataset/MANIFEST.json`; pre-existing `dataset/test` archived to `dataset_raw/legacy_test/`

Source-folder name mapping (case-insensitive, matched against directory basenames anywhere under `raw_dir`):

| Source dir name | Target class | Split rule |
|---|---|---|
| `drowsy` | `is_drowsy` | subject-disjoint (filename `NNN_...` prefix; subject `005` → test, others → train; if `005` absent, last sorted subject → test) |
| `notdrowsy` | `not_drowsy` | same subject rule |
| `yawn` | `is_yawning` | upstream path split (`test` in path parts → test; `train`/`valid` → train) |
| `no_yawn` | `no_yawn` | upstream path split |
| `distracted` | `is_distracted` | upstream path split |
| `dangerousdriving` | `is_distracted` | only used if `distracted` alone yields < 150 test images; upstream path split |
| `safedriving` | `safe_driving` | upstream path split |

Files without a `NNN_` prefix in the drowsy sources are skipped and counted. Larger side downsampled to the smaller via `every_nth`, then capped (train: `--train-cap` per side, test: `--test-cap` per side). Fewer than 150 test images per side → warning, not failure. Missing source folders → per-dataset error message naming the exact `kaggle datasets download` command (from the spec) — but `prepare` continues for behaviors whose sources ARE present.

- [ ] **Step 1: Write the failing tests**

`dev/tests/test_prepare_dataset.py`:

```python
import json
from pathlib import Path

import prepare_dataset as pd


def _touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\xff\xd8fake")


def _make_raw(root: Path):
    # NTHU-like: subjects 001/002/005 in drowsy + notdrowsy
    for subj in ("001", "002", "005"):
        for i in range(10):
            _touch(root / "nthuddd2" / "drowsy" / f"{subj}_glasses_blink_{i:04d}_drowsy.jpg")
            _touch(root / "nthuddd2" / "notdrowsy" / f"{subj}_glasses_mix_{i:04d}_notdrowsy.jpg")
    _touch(root / "nthuddd2" / "drowsy" / "README.jpg")  # no subject prefix -> skipped
    # yawn dataset with upstream split
    for i in range(8):
        _touch(root / "yawn" / "train" / "yawn" / f"{i}.jpg")
        _touch(root / "yawn" / "train" / "no_yawn" / f"{i}.jpg")
    for i in range(4):
        _touch(root / "yawn" / "test" / "yawn" / f"t{i}.jpg")
        _touch(root / "yawn" / "test" / "no_yawn" / f"t{i}.jpg")
    # DMD-like with upstream split
    for i in range(8):
        _touch(root / "dmd" / "train" / "Distracted" / f"d{i}.jpg")
        _touch(root / "dmd" / "train" / "SafeDriving" / f"s{i}.jpg")
    for i in range(4):
        _touch(root / "dmd" / "test" / "Distracted" / f"dt{i}.jpg")
        _touch(root / "dmd" / "test" / "SafeDriving" / f"st{i}.jpg")


def test_discover_finds_all_six_sources(tmp_path):
    _make_raw(tmp_path)
    src = pd.discover_sources(tmp_path)
    # 30 subject images + README.jpg (discover doesn't filter; plan_layout does)
    assert len(src["is_drowsy"]) == 31 and len(src["not_drowsy"]) == 30
    assert len(src["is_yawning"]) == 12 and len(src["no_yawn"]) == 12
    assert len(src["is_distracted"]) == 12 and len(src["safe_driving"]) == 12


def test_plan_is_subject_disjoint_and_balanced(tmp_path):
    _make_raw(tmp_path)
    plan = pd.plan_layout(pd.discover_sources(tmp_path), train_cap=100, test_cap=100)
    train_subjects = {p.name[:3] for p in plan[("train", "is_drowsy")]}
    test_subjects = {p.name[:3] for p in plan[("test", "is_drowsy")]}
    assert test_subjects == {"005"}
    assert train_subjects == {"001", "002"}
    assert not (train_subjects & test_subjects)
    # balance: pos == neg count per behavior per split
    for split in ("train", "test"):
        assert len(plan[(split, "is_drowsy")]) == len(plan[(split, "not_drowsy")])
        assert len(plan[(split, "is_yawning")]) == len(plan[(split, "no_yawn")])
    # README.jpg (no NNN_ prefix) never planned
    all_names = {p.name for paths in plan.values() for p in paths}
    assert "README.jpg" not in all_names


def test_plan_respects_caps_and_upstream_split(tmp_path):
    _make_raw(tmp_path)
    plan = pd.plan_layout(pd.discover_sources(tmp_path), train_cap=5, test_cap=2)
    assert len(plan[("train", "is_yawning")]) == 5
    assert len(plan[("test", "is_yawning")]) == 2
    # upstream split respected: test images only from the source's test/ tree
    assert all("test" in p.parts for p in plan[("test", "is_distracted")])


def test_plan_deterministic(tmp_path):
    _make_raw(tmp_path)
    p1 = pd.plan_layout(pd.discover_sources(tmp_path), 5, 2)
    p2 = pd.plan_layout(pd.discover_sources(tmp_path), 5, 2)
    assert p1 == p2


def test_main_copies_archives_and_writes_manifest(tmp_path):
    _make_raw(tmp_path / "raw")
    out = tmp_path / "dataset"
    (out / "test" / "is_drowsy").mkdir(parents=True)
    (out / "test" / "is_drowsy" / "old.jpg").write_bytes(b"legacy")
    rc = pd.main(["--raw-dir", str(tmp_path / "raw"), "--out-dir", str(out),
                  "--train-cap", "5", "--test-cap", "2"])
    assert rc == 0
    # legacy test archived
    assert (tmp_path / "raw" / "legacy_test" / "is_drowsy" / "old.jpg").exists()
    manifest = json.loads((out / "MANIFEST.json").read_text())
    for split in ("train", "test"):
        for cls in ("is_drowsy", "not_drowsy", "is_yawning", "no_yawn",
                    "is_distracted", "safe_driving"):
            n = len(list((out / split / cls).glob("*.jpg")))
            assert n == manifest["counts"][split][cls] > 0


def test_main_missing_source_errors_but_continues(tmp_path, capsys):
    # only the yawn dataset present
    for i in range(4):
        _touch(tmp_path / "raw" / "yawn" / "train" / "yawn" / f"{i}.jpg")
        _touch(tmp_path / "raw" / "yawn" / "train" / "no_yawn" / f"{i}.jpg")
        _touch(tmp_path / "raw" / "yawn" / "test" / "yawn" / f"t{i}.jpg")
        _touch(tmp_path / "raw" / "yawn" / "test" / "no_yawn" / f"t{i}.jpg")
    rc = pd.main(["--raw-dir", str(tmp_path / "raw"),
                  "--out-dir", str(tmp_path / "dataset"),
                  "--train-cap", "5", "--test-cap", "2"])
    out = capsys.readouterr().out
    assert rc == 1  # something missing
    assert "kaggle datasets download -d banudeep/nthuddd2" in out
    assert (tmp_path / "dataset" / "train" / "is_yawning").exists()  # continued
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.14 -m pytest dev/tests/test_prepare_dataset.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'prepare_dataset'`

- [ ] **Step 3: Write `dev/prepare_dataset.py`**

```python
"""Rebuild dataset/{train,test} deterministically from dataset_raw/.

Usage: py -3.14 dev/prepare_dataset.py [--raw-dir P] [--out-dir P]
       [--train-cap 5000] [--test-cap 300] [--dry-run]
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calib_common as cc

# source dir basename (lowercased) -> target class dir
SOURCE_NAME_MAP = {
    "drowsy": "is_drowsy",
    "notdrowsy": "not_drowsy",
    "yawn": "is_yawning",
    "no_yawn": "no_yawn",
    "distracted": "is_distracted",
    "safedriving": "safe_driving",
}
DANGEROUS = "dangerousdriving"  # extra is_distracted source, used only if short

DOWNLOAD_HINTS = {
    "is_drowsy": "kaggle datasets download -d banudeep/nthuddd2 -p dataset_raw/nthuddd2 --unzip",
    "not_drowsy": "kaggle datasets download -d banudeep/nthuddd2 -p dataset_raw/nthuddd2 --unzip",
    "is_yawning": "kaggle datasets download -d serenaraju/yawn-eye-dataset-new -p dataset_raw/yawn --unzip",
    "no_yawn": "kaggle datasets download -d serenaraju/yawn-eye-dataset-new -p dataset_raw/yawn --unzip",
    "is_distracted": "kaggle datasets download -d zeyad1mashhour/driver-inattention-detection-dataset -p dataset_raw/dmd --unzip",
    "safe_driving": "kaggle datasets download -d zeyad1mashhour/driver-inattention-detection-dataset -p dataset_raw/dmd --unzip",
}

SUBJECT_RE = re.compile(r"^(\d{3})_")
TEST_SUBJECT_PREFERRED = "005"
MIN_TEST_WARN = 150


def _images_under(d: Path):
    return sorted(p for p in d.rglob("*")
                  if p.suffix.lower() in cc.IMAGE_EXTS and p.is_file())


def discover_sources(raw_dir: Path):
    """Map each target class to all images under matching source dirs."""
    raw_dir = Path(raw_dir)
    sources = {cls: [] for cls in cc.CLASS_DIRS}
    sources["_dangerous"] = []
    if not raw_dir.exists():
        return sources
    legacy = raw_dir / "legacy_test"
    for d in sorted(raw_dir.rglob("*")):
        if not d.is_dir() or legacy in d.parents or d == legacy:
            continue
        name = d.name.lower().replace(" ", "").replace("-", "_")
        if name in SOURCE_NAME_MAP:
            direct = sorted(p for p in d.iterdir()
                            if p.suffix.lower() in cc.IMAGE_EXTS and p.is_file())
            sources[SOURCE_NAME_MAP[name]].extend(direct)
        elif name == DANGEROUS:
            direct = sorted(p for p in d.iterdir()
                            if p.suffix.lower() in cc.IMAGE_EXTS and p.is_file())
            sources["_dangerous"].extend(direct)
    return sources


def _subject_split(paths):
    """NTHU rule: one whole subject is the test set (default 005)."""
    by_subject = {}
    skipped = 0
    for p in paths:
        m = SUBJECT_RE.match(p.name)
        if not m:
            skipped += 1
            continue
        by_subject.setdefault(m.group(1), []).append(p)
    if not by_subject:
        return [], [], skipped
    subjects = sorted(by_subject)
    test_subj = TEST_SUBJECT_PREFERRED if TEST_SUBJECT_PREFERRED in by_subject else subjects[-1]
    test = sorted(by_subject[test_subj])
    train = sorted(p for s in subjects if s != test_subj for p in by_subject[s])
    return train, test, skipped


def _path_split(paths):
    """Upstream split rule: 'test' dir component -> test, else train."""
    test = sorted(p for p in paths if "test" in [q.lower() for q in p.parts])
    train = sorted(p for p in paths if p not in set(test))
    return train, test


def plan_layout(sources, train_cap, test_cap):
    """Pure planning: (split, class_dir) -> list of source Paths. Deterministic."""
    plan = {}
    splits = {}
    for cls in ("is_drowsy", "not_drowsy"):
        train, test, _ = _subject_split(sources[cls])
        splits[cls] = (train, test)
    for cls in ("is_yawning", "no_yawn", "is_distracted", "safe_driving"):
        splits[cls] = _path_split(sources[cls])
    # top up distraction positives with DangerousDriving only if short on test
    if len(splits["is_distracted"][1]) < MIN_TEST_WARN and sources.get("_dangerous"):
        d_train, d_test = _path_split(sources["_dangerous"])
        splits["is_distracted"] = (
            sorted(splits["is_distracted"][0] + d_train),
            sorted(splits["is_distracted"][1] + d_test),
        )
    for behavior, spec in cc.BEHAVIORS.items():
        pos_cls, neg_cls = spec["pos"], spec["neg"]
        for split_name, idx, cap in (("train", 0, train_cap), ("test", 1, test_cap)):
            pos, neg = splits[pos_cls][idx], splits[neg_cls][idx]
            n = min(len(pos), len(neg), cap)
            plan[(split_name, pos_cls)] = cc.every_nth(pos, n)
            plan[(split_name, neg_cls)] = cc.every_nth(neg, n)
    return plan


def _archive_legacy(out_dir: Path, raw_dir: Path):
    old_test = out_dir / "test"
    if not old_test.exists():
        return
    dest = raw_dir / "legacy_test"
    if dest.exists():  # already archived on a previous run
        shutil.rmtree(old_test)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old_test), str(dest))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-dir", default=str(cc.RAW_DIR))
    ap.add_argument("--out-dir", default=str(cc.DATASET_DIR))
    ap.add_argument("--train-cap", type=int, default=5000)
    ap.add_argument("--test-cap", type=int, default=300)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    raw_dir, out_dir = Path(args.raw_dir), Path(args.out_dir)

    sources = discover_sources(raw_dir)
    missing = [cls for cls in cc.CLASS_DIRS if not sources[cls]]
    for cls in missing:
        print(f"MISSING source for {cls}. Download it with:\n  {DOWNLOAD_HINTS[cls]}")

    plan = plan_layout(sources, args.train_cap, args.test_cap)

    for (split, cls), paths in sorted(plan.items()):
        tag = " (LOW: <%d)" % MIN_TEST_WARN if split == "test" and 0 < len(paths) < MIN_TEST_WARN else ""
        print(f"{split}/{cls}: {len(paths)} images{tag}")
    if args.dry_run:
        return 1 if missing else 0

    _archive_legacy(out_dir, raw_dir)
    if (out_dir / "train").exists():
        shutil.rmtree(out_dir / "train")
    counts = {"train": {}, "test": {}}
    for (split, cls), paths in sorted(plan.items()):
        dest = out_dir / split / cls
        dest.mkdir(parents=True, exist_ok=True)
        for p in paths:
            target = dest / p.name
            if target.exists():  # name collision across source dirs
                target = dest / f"{p.parent.name}_{p.name}"
            shutil.copy2(p, target)
        counts[split][cls] = len(paths)

    manifest = {"train_cap": args.train_cap, "test_cap": args.test_cap,
                "raw_dir": str(raw_dir), "counts": counts}
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {out_dir / 'MANIFEST.json'}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3.14 -m pytest dev/tests/test_prepare_dataset.py -v`
Expected: 6 passed

Note: do NOT run `prepare_dataset.py` against the real `dataset/` during implementation — the real run happens in the operator runbook (Task 9) after the Kaggle downloads. The current `dataset/test` images must stay in place until Task 5 copies fixtures from them.

- [ ] **Step 5: Commit**

```bash
git add dev/prepare_dataset.py dev/tests/test_prepare_dataset.py
git commit -m "dev: deterministic dataset preparation with subject-disjoint drowsy split"
```

---

### Task 5: Test fixture + `annotate_dataset.py`

**Files:**
- Create: `dev/tests/fixtures/mini_dataset/` (36 real images copied from the current repo dataset — committed)
- Create: `dev/annotate_dataset.py`
- Test: `dev/tests/test_annotate.py`

**Interfaces:**
- Consumes: `calib_common` (paths, vocab, `preprocess_bgr`, `is_grayscale_like`, `CSV_FIELDS`); repo modules `config_loader.load_config`, `face_analysis.improved_detection.ImprovedFaceAnalyzer`
- Produces:
  - CLI: `py -3.14 dev/annotate_dataset.py [--dataset-dir P] [--out CSV] [--config P] [--workers N]` (`--workers 0` = inline single-process, used by tests)
  - `list_jobs(dataset_dir: Path, done: set[str]) -> list[tuple]` — job tuples `(relpath, abspath, split, class_dir)` for images not yet in the CSV (resume support)
  - `annotate_inline(jobs, config_path) -> iterator[dict]` — CSV row dicts
  - Output file: `dataset/annotations.csv` with `CSV_FIELDS` columns; metric fields empty when face/landmarks missing or file unreadable

- [ ] **Step 1: Build the committed mini fixture from images already in git**

The current `dataset/test` drowsy images only face-detect ~50% of the time (probe result), so the fixture must be built from images **verified to detect** through the real annotate path (preprocess + analyzer) — otherwise later smoke tests are flaky. The pairings are semantically plausible (drowsy frames have closed eyes + closed mouth + frontal pose): drowsy→`is_drowsy`+`no_yawn`+`safe_driving`, yawning→`is_yawning`+`not_drowsy`, distracted-IR→`is_distracted`.

Create `dev/tests/fixtures/build_fixture.py` (committed, so the fixture is reproducible):

```python
"""One-time fixture builder: copy DETECTING images into mini_dataset/.

Run from repo root: py -3.14 dev/tests/fixtures/build_fixture.py
Selects images that pass face+landmark detection via the same path
annotate_dataset uses; if a source class has too few detecting images,
detecting ones are duplicated under new names (fixture tests mechanics,
not semantics).
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "dev"))
sys.path.insert(0, str(REPO))

import cv2

import calib_common as cc
from config_loader import load_config
from face_analysis.improved_detection import ImprovedFaceAnalyzer

N_TRAIN, N_TEST = 4, 2


def detecting_images(src_dir, analyzer, cfg):
    """Sorted source images that detect; falls back to duplicating."""
    hits = []
    for p in sorted(Path(src_dir).glob("*.jpg")):
        img = cv2.imread(str(p))
        if img is None:
            continue
        r = analyzer.analyze_frame(cc.preprocess_bgr(img, cfg))
        if r.get("face_detected") and r.get("landmarks_detected"):
            hits.append(p)
    need = N_TRAIN + N_TEST
    out = list(hits)
    i = 0
    while out and len(out) < need:  # pad by duplicating detecting images
        out.append(out[i % len(hits)])
        i += 1
    if len(out) < need:
        raise SystemExit(f"no detecting images at all in {src_dir}")
    return out[:need]


def place(paths, class_dir):
    for split, chunk in (("train", paths[:N_TRAIN]), ("test", paths[N_TRAIN:])):
        dest = HERE / "mini_dataset" / split / class_dir
        dest.mkdir(parents=True, exist_ok=True)
        for k, p in enumerate(chunk):
            shutil.copy2(p, dest / f"{k}_{p.name}")


def main():
    cfg = load_config(str(cc.CONFIG_YAML))
    analyzer = ImprovedFaceAnalyzer(cfg)
    drowsy = detecting_images(REPO / "dataset/test/is_drowsy", analyzer, cfg)
    yawn = detecting_images(REPO / "dataset/test/is_yawning", analyzer, cfg)
    for cls in ("is_drowsy", "no_yawn", "safe_driving"):
        place(drowsy, cls)
    for cls in ("is_yawning", "not_drowsy"):
        place(yawn, cls)
    # distracted: IR imagery, low detect rate is EXPECTED — take first 6 as-is
    dist = sorted((REPO / "dataset/test/is_distracted").glob("*.jpg"))[:N_TRAIN + N_TEST]
    place(dist, "is_distracted")
    n = len(list((HERE / "mini_dataset").rglob("*.jpg")))
    print(f"fixture built: {n} images (expected 36)")


if __name__ == "__main__":
    main()
```

Run: `py -3.14 dev/tests/fixtures/build_fixture.py`
Expected: `fixture built: 36 images (expected 36)` (takes ~30 s — it runs dlib over the 24 source images)

- [ ] **Step 2: Write the failing tests**

`dev/tests/test_annotate.py`:

```python
import csv
from pathlib import Path

import pytest

import annotate_dataset as ad
import calib_common as cc

FIXTURE = Path(__file__).parent / "fixtures" / "mini_dataset"


def test_list_jobs_enumerates_and_resumes():
    jobs = ad.list_jobs(FIXTURE, done=set())
    assert len(jobs) == 36
    relpaths = [j[0] for j in jobs]
    assert relpaths == sorted(relpaths)
    assert all(j[2] in ("train", "test") and j[3] in cc.CLASS_DIRS for j in jobs)
    half = set(relpaths[:18])
    assert len(ad.list_jobs(FIXTURE, done=half)) == 18


def test_annotate_inline_produces_valid_rows(tmp_path):
    jobs = [j for j in ad.list_jobs(FIXTURE, done=set())
            if j[2] == "train" and j[3] == "is_drowsy"]  # 4 drowsy train images
    rows = list(ad.annotate_inline(jobs, cc.CONFIG_YAML))
    assert len(rows) == 4
    for row in rows:
        assert set(row) == set(cc.CSV_FIELDS)
        assert row["behavior"] == "drowsy" and row["label"] == 1
        # build_fixture.py selected these BECAUSE they detect via this exact path
        assert row["face_detected"] == 1 and row["landmarks_detected"] == 1
        assert 0.0 < float(row["ear"]) < 0.6
        assert 0.0 <= float(row["mar"]) < 2.0


def test_annotate_inline_handles_unreadable_file(tmp_path):
    bad = tmp_path / "train" / "is_drowsy" / "corrupt.jpg"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"not a jpeg")
    jobs = ad.list_jobs(tmp_path, done=set())
    rows = list(ad.annotate_inline(jobs, cc.CONFIG_YAML))
    assert len(rows) == 1
    assert rows[0]["face_detected"] == 0 and rows[0]["ear"] == ""


def test_main_writes_and_resumes_csv(tmp_path):
    out = tmp_path / "ann.csv"
    rc = ad.main(["--dataset-dir", str(FIXTURE), "--out", str(out), "--workers", "0"])
    assert rc == 0
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 36
    # second run adds nothing (resume) and exits cleanly
    rc = ad.main(["--dataset-dir", str(FIXTURE), "--out", str(out), "--workers", "0"])
    assert rc == 0
    with open(out, newline="", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 36
    # typed loader accepts the output; the 30 drowsy/yawn-derived fixture
    # images are detection-verified, only the 6 IR distracted ones may miss
    parsed = cc.load_annotations(out)
    assert len(cc.valid_rows(parsed)) >= 24
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `py -3.14 -m pytest dev/tests/test_annotate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'annotate_dataset'`

- [ ] **Step 4: Write `dev/annotate_dataset.py`**

```python
"""Annotate every dataset image with the pipeline's own EAR/MAR/yaw/pitch.

Usage: py -3.14 dev/annotate_dataset.py [--dataset-dir P] [--out CSV]
       [--config P] [--workers N]

--workers 0 runs inline (no pool). Resumable: relpaths already in the CSV
are skipped on rerun. Rows for unreadable/no-face images keep empty metric
fields (0.0 is the analyzer's error sentinel, so we never store it blindly).
"""
import argparse
import csv
import logging
import multiprocessing
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import calib_common as cc

_worker = {}


def _init_worker(config_path):
    logging.disable(logging.WARNING)  # analyzer logs INFO per frame — silence
    from config_loader import load_config
    from face_analysis.improved_detection import ImprovedFaceAnalyzer

    cfg = load_config(str(config_path))
    _worker["cfg"] = cfg
    _worker["analyzer"] = ImprovedFaceAnalyzer(cfg)


def _empty_row(relpath, split, class_dir):
    behavior, label = cc.CLASS_TO_BEHAVIOR[class_dir]
    row = {k: "" for k in cc.CSV_FIELDS}
    row.update(relpath=relpath, split=split, behavior=behavior, label=label,
               face_detected=0, landmarks_detected=0, grayscale_like="")
    return row


def _annotate_one(job):
    import cv2

    relpath, abspath, split, class_dir = job
    row = _empty_row(relpath, split, class_dir)
    img = cv2.imread(abspath)
    if img is None:
        return row
    row["height"], row["width"] = img.shape[:2]
    row["grayscale_like"] = int(cc.is_grayscale_like(img))
    img = cc.preprocess_bgr(img, _worker["cfg"])
    r = _worker["analyzer"].analyze_frame(img)
    row["face_detected"] = int(bool(r.get("face_detected")))
    row["landmarks_detected"] = int(bool(r.get("landmarks_detected")))
    if row["face_detected"] and row["landmarks_detected"]:
        m = r["metrics"]
        dbg = r.get("debug_info") or {}
        row.update(ear=f"{m['ear']:.4f}", mar=f"{m['mar']:.4f}",
                   yaw=f"{m['yaw']:.2f}", pitch=f"{m['pitch']:.2f}",
                   left_ear=f"{dbg.get('left_ear', 0.0):.4f}",
                   right_ear=f"{dbg.get('right_ear', 0.0):.4f}")
    return row


def list_jobs(dataset_dir, done):
    dataset_dir = Path(dataset_dir)
    jobs = []
    for split in ("train", "test"):
        for class_dir in cc.CLASS_DIRS:
            d = dataset_dir / split / class_dir
            if not d.is_dir():
                continue
            for p in sorted(d.iterdir()):
                if p.suffix.lower() not in cc.IMAGE_EXTS:
                    continue
                relpath = f"{split}/{class_dir}/{p.name}"
                if relpath not in done:
                    jobs.append((relpath, str(p), split, class_dir))
    return sorted(jobs)


def annotate_inline(jobs, config_path):
    _init_worker(config_path)
    for job in jobs:
        yield _annotate_one(job)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset-dir", default=str(cc.DATASET_DIR))
    ap.add_argument("--out", default=str(cc.ANNOTATIONS_CSV))
    ap.add_argument("--config", default=str(cc.CONFIG_YAML))
    ap.add_argument("--workers", type=int,
                    default=max(1, (os.cpu_count() or 2) - 2))
    args = ap.parse_args(argv)
    out = Path(args.out)

    done = set()
    if out.exists():
        with open(out, newline="", encoding="utf-8") as f:
            done = {r["relpath"] for r in csv.DictReader(f)}
    jobs = list_jobs(args.dataset_dir, done)
    print(f"{len(done)} already annotated, {len(jobs)} to do")
    if not jobs:
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    new_file = not out.exists()
    with open(out, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cc.CSV_FIELDS)
        if new_file:
            writer.writeheader()
        n = 0
        if args.workers == 0:
            results = annotate_inline(jobs, args.config)
            for row in results:
                writer.writerow(row)
                f.flush()
                n += 1
                if n % 200 == 0:
                    print(f"{n}/{len(jobs)}")
        else:
            with multiprocessing.Pool(args.workers, initializer=_init_worker,
                                      initargs=(args.config,)) as pool:
                for row in pool.imap_unordered(_annotate_one, jobs, chunksize=8):
                    writer.writerow(row)
                    f.flush()
                    n += 1
                    if n % 200 == 0:
                        print(f"{n}/{len(jobs)}")
    print(f"annotated {n} images -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `py -3.14 -m pytest dev/tests/test_annotate.py -v`
Expected: 4 passed (takes ~40-60 s — it runs dlib on 36+4+1 real images)

- [ ] **Step 6: Commit**

```bash
git add dev/tests/fixtures dev/annotate_dataset.py dev/tests/test_annotate.py
git commit -m "dev: dataset annotator (multiprocess, resumable) + committed mini fixture"
```

---

### Task 6: `spotcheck_labels.py` — HTML contact sheet for label verification

**Files:**
- Create: `dev/spotcheck_labels.py`
- Test: `dev/tests/test_spotcheck.py`

**Interfaces:**
- Consumes: `calib_common.every_nth, CLASS_DIRS, IMAGE_EXTS, DATASET_DIR`
- Produces:
  - CLI: `py -3.14 dev/spotcheck_labels.py [--dataset-dir P] [--out HTML] [--per-class 50]`
  - `build_html(dataset_dir: Path, per_class: int) -> str`
  - Output: self-contained `dataset/spotcheck.html` (base64 images, checkbox per image, an Export button that downloads `spotcheck_flags.csv` with header `relpath`). Calibrate/evaluate read that flags file if present.

- [ ] **Step 1: Write the failing tests**

`dev/tests/test_spotcheck.py`:

```python
from pathlib import Path

import spotcheck_labels as sc

FIXTURE = Path(__file__).parent / "fixtures" / "mini_dataset"


def test_build_html_contains_sections_images_and_export():
    html = sc.build_html(FIXTURE, per_class=2)
    for cls in ("is_drowsy", "not_drowsy", "is_yawning", "no_yawn",
                "is_distracted", "safe_driving"):
        assert f"<h2>{cls}" in html
    # 6 classes x (train 2 + test 2) = 24 images, embedded
    assert html.count("<img") == 24
    assert html.count("data:image/jpeg;base64,") == 24
    assert 'data-relpath="train/is_drowsy/' in html
    assert "function exportFlags()" in html
    assert "spotcheck_flags.csv" in html


def test_build_html_deterministic():
    assert sc.build_html(FIXTURE, per_class=2) == sc.build_html(FIXTURE, per_class=2)


def test_main_writes_file(tmp_path):
    out = tmp_path / "spotcheck.html"
    rc = sc.main(["--dataset-dir", str(FIXTURE), "--out", str(out),
                  "--per-class", "1"])
    assert rc == 0
    assert out.exists() and out.stat().st_size > 1000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.14 -m pytest dev/tests/test_spotcheck.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'spotcheck_labels'`

- [ ] **Step 3: Write `dev/spotcheck_labels.py`**

```python
"""Generate a self-contained HTML contact sheet for human label spot-checking.

Usage: py -3.14 dev/spotcheck_labels.py [--dataset-dir P] [--out HTML]
       [--per-class 50]

Open the HTML in a browser, tick every image whose folder label looks WRONG,
click "Export flags" — it downloads spotcheck_flags.csv. Put that file at
dataset/spotcheck_flags.csv; calibrate/evaluate exclude the flagged rows.
"""
import argparse
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calib_common as cc

_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>EyedTrack label spot-check</title>
<style>
 body {{ font-family: sans-serif; margin: 16px; }}
 .grid {{ display: flex; flex-wrap: wrap; gap: 8px; }}
 figure {{ margin: 0; width: 180px; }}
 img {{ width: 180px; display: block; }}
 figcaption {{ font-size: 11px; word-break: break-all; }}
 label.bad {{ color: #b00; font-weight: bold; }}
 #export {{ position: fixed; top: 8px; right: 8px; padding: 8px 14px; }}
</style></head><body>
<h1>Label spot-check — tick images whose label is WRONG</h1>
<button id="export" onclick="exportFlags()">Export flags</button>
{sections}
<script>
function exportFlags() {{
  var rows = ["relpath"];
  document.querySelectorAll("input[type=checkbox]:checked").forEach(function(c) {{
    rows.push(c.dataset.relpath);
  }});
  var blob = new Blob([rows.join("\\n") + "\\n"], {{type: "text/csv"}});
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "spotcheck_flags.csv";
  a.click();
}}
</script></body></html>
"""


def _figure(relpath, abspath):
    b64 = base64.b64encode(Path(abspath).read_bytes()).decode("ascii")
    return (f'<figure><img src="data:image/jpeg;base64,{b64}">'
            f'<figcaption>{relpath}</figcaption>'
            f'<label class="bad"><input type="checkbox" data-relpath="{relpath}">'
            f' wrong label</label></figure>')


def build_html(dataset_dir, per_class):
    dataset_dir = Path(dataset_dir)
    sections = []
    for class_dir in cc.CLASS_DIRS:
        figures = []
        for split in ("train", "test"):
            d = dataset_dir / split / class_dir
            if not d.is_dir():
                continue
            names = [p.name for p in d.iterdir()
                     if p.suffix.lower() in cc.IMAGE_EXTS]
            for name in cc.every_nth(names, per_class):
                relpath = f"{split}/{class_dir}/{name}"
                figures.append(_figure(relpath, d / name))
        sections.append(f"<h2>{class_dir} ({len(figures)} sampled)</h2>"
                        f'<div class="grid">{"".join(figures)}</div>')
    return _PAGE.format(sections="\n".join(sections))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset-dir", default=str(cc.DATASET_DIR))
    ap.add_argument("--out", default=str(cc.DATASET_DIR / "spotcheck.html"))
    ap.add_argument("--per-class", type=int, default=50)
    args = ap.parse_args(argv)
    html = build_html(args.dataset_dir, args.per_class)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} — open in a browser, tick wrong labels, Export flags,"
          f" save as {cc.DATASET_DIR / 'spotcheck_flags.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3.14 -m pytest dev/tests/test_spotcheck.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add dev/spotcheck_labels.py dev/tests/test_spotcheck.py
git commit -m "dev: HTML contact-sheet label spot-check with flags export"
```

---

### Task 7: Threshold sweeps + `calibrate_thresholds.py`

**Files:**
- Create: `dev/calibrate_thresholds.py`
- Test: `dev/tests/test_sweep.py`

**Interfaces:**
- Consumes: `calib_common` (annotations loading/filtering, `rows_for`, config editor, `CALIB_DIR`); `sklearn.metrics.roc_auc_score/roc_curve`; `matplotlib`
- Produces:
  - CLI: `py -3.14 dev/calibrate_thresholds.py [--annotations CSV] [--config P] [--out-dir P] [--flags CSV] [--dry-run]`
  - `sweep_scalar(pos: list[float], neg: list[float], direction: str) -> dict` — direction `"<"` or `">"`; returns `{"threshold", "f1", "precision", "recall", "auc"}` (floats); raises `ValueError` on an empty side
  - `sweep_pose(pos_yaw, pos_pitch, neg_yaw, neg_pitch) -> dict` — returns `{"yaw_threshold", "pitch_threshold", "f1", "precision", "recall"}`
  - `load_flags(path: Path) -> set[str]` — relpaths from `spotcheck_flags.csv` (empty set if absent)
  - Outputs: `test_results/calibration/thresholds.json`, `roc_<behavior>.png`, `hist_<behavior>.png`; edits `config.yaml` unless `--dry-run`

- [ ] **Step 1: Write the failing tests**

`dev/tests/test_sweep.py`:

```python
import numpy as np
import pytest

import calibrate_thresholds as ct


def test_sweep_scalar_less_than_separable():
    pos = np.linspace(0.10, 0.20, 60).tolist()   # drowsy EARs (low)
    neg = np.linspace(0.28, 0.40, 80).tolist()   # alert EARs (high)
    r = ct.sweep_scalar(pos, neg, "<")
    assert 0.20 < r["threshold"] < 0.28
    assert r["f1"] == 1.0 and r["precision"] == 1.0 and r["recall"] == 1.0
    assert r["auc"] == 1.0


def test_sweep_scalar_greater_than_with_overlap():
    pos = np.linspace(0.60, 1.40, 100).tolist()  # yawns (high MAR)
    neg = np.linspace(0.00, 0.75, 100).tolist()  # overlap in 0.60-0.75
    r = ct.sweep_scalar(pos, neg, ">")
    assert 0.55 < r["threshold"] < 0.80
    assert 0.8 < r["f1"] < 1.0
    assert 0.9 < r["auc"] <= 1.0


def test_sweep_scalar_raises_on_empty_side():
    with pytest.raises(ValueError):
        ct.sweep_scalar([], [0.1, 0.2], "<")
    with pytest.raises(ValueError):
        ct.sweep_scalar([0.1], [], "<")


def test_sweep_pose_finds_separating_box():
    pos_yaw = np.linspace(30, 60, 50).tolist()    # heads turned away
    pos_pitch = np.linspace(-5, 5, 50).tolist()
    neg_yaw = np.linspace(-8, 8, 50).tolist()     # heads forward
    neg_pitch = np.linspace(-6, 6, 50).tolist()
    r = ct.sweep_pose(pos_yaw, pos_pitch, neg_yaw, neg_pitch)
    assert 8 < r["yaw_threshold"] < 30
    assert r["pitch_threshold"] > 6      # must not fire on negatives' pitch
    assert r["f1"] == 1.0


def test_sweep_pose_uses_or_predicate():
    # positives distracted ONLY by pitch — yaw is centred for both classes
    pos_yaw = np.linspace(-5, 5, 40).tolist()
    pos_pitch = np.linspace(25, 40, 40).tolist()
    neg_yaw = np.linspace(-5, 5, 40).tolist()
    neg_pitch = np.linspace(-8, 8, 40).tolist()
    r = ct.sweep_pose(pos_yaw, pos_pitch, neg_yaw, neg_pitch)
    assert 8 < r["pitch_threshold"] < 25
    assert r["f1"] == 1.0


def test_load_flags(tmp_path):
    assert ct.load_flags(tmp_path / "absent.csv") == set()
    p = tmp_path / "flags.csv"
    p.write_text("relpath\ntrain/is_drowsy/a.jpg\ntest/no_yawn/b.jpg\n")
    assert ct.load_flags(p) == {"train/is_drowsy/a.jpg", "test/no_yawn/b.jpg"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.14 -m pytest dev/tests/test_sweep.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'calibrate_thresholds'`

- [ ] **Step 3: Write `dev/calibrate_thresholds.py`**

```python
"""Calibrate detection thresholds from dataset/annotations.csv.

Usage: py -3.14 dev/calibrate_thresholds.py [--annotations CSV] [--config P]
       [--out-dir P] [--flags CSV] [--dry-run]

Per behavior: sweep candidate thresholds on TRAIN rows (valid, not flagged),
pick max-F1, plot ROC + histograms, write thresholds.json, then apply the
values to config.yaml's detection: block by targeted line edit (--dry-run
skips the config write). Behaviors with no usable rows are skipped loudly.
"""
import argparse
import csv
import datetime
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calib_common as cc


def sweep_scalar(pos, neg, direction):
    """Max-F1 threshold for predicate (value < t) or (value > t)."""
    from sklearn.metrics import roc_auc_score

    pos = np.asarray(pos, dtype=float)
    neg = np.asarray(neg, dtype=float)
    if len(pos) == 0 or len(neg) == 0:
        raise ValueError(f"need both classes: pos={len(pos)} neg={len(neg)}")
    values = np.unique(np.concatenate([pos, neg]))
    if len(values) < 2:
        raise ValueError("metric is constant — cannot sweep")
    cands = (values[:-1] + values[1:]) / 2.0
    pos_sorted, neg_sorted = np.sort(pos), np.sort(neg)
    if direction == "<":
        tp = np.searchsorted(pos_sorted, cands, side="left")
        fp = np.searchsorted(neg_sorted, cands, side="left")
    elif direction == ">":
        tp = len(pos) - np.searchsorted(pos_sorted, cands, side="right")
        fp = len(neg) - np.searchsorted(neg_sorted, cands, side="right")
    else:
        raise ValueError(f"direction must be '<' or '>', got {direction!r}")
    precision = tp / np.maximum(tp + fp, 1)
    recall = tp / len(pos)
    f1 = np.where(tp > 0,
                  2 * precision * recall / np.maximum(precision + recall, 1e-12),
                  0.0)
    i = int(np.argmax(f1))
    y = np.concatenate([np.ones(len(pos)), np.zeros(len(neg))])
    scores = np.concatenate([pos, neg])
    auc = float(roc_auc_score(y, -scores if direction == "<" else scores))
    return {"threshold": float(cands[i]), "f1": float(f1[i]),
            "precision": float(precision[i]), "recall": float(recall[i]),
            "auc": auc}


def sweep_pose(pos_yaw, pos_pitch, neg_yaw, neg_pitch):
    """Max-F1 (yaw_t, pitch_t) grid search for |yaw|>yt OR |pitch|>pt."""
    py = np.abs(np.asarray(pos_yaw, dtype=float))
    pp = np.abs(np.asarray(pos_pitch, dtype=float))
    ny = np.abs(np.asarray(neg_yaw, dtype=float))
    npi = np.abs(np.asarray(neg_pitch, dtype=float))
    if len(py) == 0 or len(ny) == 0:
        raise ValueError(f"need both classes: pos={len(py)} neg={len(ny)}")
    yaw_grid = np.arange(5.0, 60.5, 0.5)
    pitch_grid = np.arange(5.0, 60.5, 0.5)
    best = None
    for yt in yaw_grid:
        pos_hit = (py > yt)[:, None] | (pp[:, None] > pitch_grid[None, :])
        neg_hit = (ny > yt)[:, None] | (npi[:, None] > pitch_grid[None, :])
        tp = pos_hit.sum(axis=0).astype(float)
        fp = neg_hit.sum(axis=0).astype(float)
        precision = tp / np.maximum(tp + fp, 1)
        recall = tp / len(py)
        f1 = np.where(tp > 0,
                      2 * precision * recall / np.maximum(precision + recall, 1e-12),
                      0.0)
        j = int(np.argmax(f1))
        if best is None or f1[j] > best["f1"]:
            best = {"yaw_threshold": float(yt),
                    "pitch_threshold": float(pitch_grid[j]),
                    "f1": float(f1[j]), "precision": float(precision[j]),
                    "recall": float(recall[j])}
    return best


def load_flags(path):
    path = Path(path)
    if not path.exists():
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {r["relpath"] for r in csv.DictReader(f)}


def _plots(out_dir, behavior, pos, neg, threshold, direction, pos_name, neg_name):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import roc_curve

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(neg, bins=50, alpha=0.6, label=neg_name)
    ax.hist(pos, bins=50, alpha=0.6, label=pos_name)
    ax.axvline(threshold, color="red", linestyle="--",
               label=f"threshold {threshold:.3f}")
    ax.set_title(f"{behavior}: metric distributions (train)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / f"hist_{behavior}.png", dpi=150)
    plt.close(fig)

    y = np.concatenate([np.ones(len(pos)), np.zeros(len(neg))])
    scores = np.concatenate([pos, neg])
    fpr, tpr, _ = roc_curve(y, -scores if direction == "<" else scores)
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot(fpr, tpr)
    ax.plot([0, 1], [0, 1], linestyle=":", color="gray")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title(f"{behavior}: ROC (train)")
    fig.tight_layout()
    fig.savefig(out_dir / f"roc_{behavior}.png", dpi=150)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--annotations", default=str(cc.ANNOTATIONS_CSV))
    ap.add_argument("--config", default=str(cc.CONFIG_YAML))
    ap.add_argument("--out-dir", default=str(cc.CALIB_DIR))
    ap.add_argument("--flags", default=str(cc.DATASET_DIR / "spotcheck_flags.csv"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    flags = load_flags(args.flags)
    rows = [r for r in cc.load_annotations(args.annotations)
            if r["relpath"] not in flags]
    usable = cc.valid_rows(rows)

    config_path = Path(args.config)
    config_text = config_path.read_text(encoding="utf-8")
    previous = cc.parse_detection_thresholds(config_text)

    results, counts, updates = {}, {}, {}
    for behavior in cc.BEHAVIORS:
        pos, neg = cc.rows_for(usable, "train", behavior)
        all_pos, all_neg = cc.rows_for(rows, "train", behavior)
        counts[behavior] = {
            "pos_valid": len(pos), "neg_valid": len(neg),
            "pos_excluded": len(all_pos) - len(pos),
            "neg_excluded": len(all_neg) - len(neg),
        }
        try:
            if behavior == "drowsy":
                r = sweep_scalar([x["ear"] for x in pos],
                                 [x["ear"] for x in neg], "<")
                updates["ear_threshold"] = round(r["threshold"], 3)
                _plots(out_dir, behavior, [x["ear"] for x in pos],
                       [x["ear"] for x in neg], r["threshold"], "<",
                       "is_drowsy", "not_drowsy")
            elif behavior == "yawning":
                r = sweep_scalar([x["mar"] for x in pos],
                                 [x["mar"] for x in neg], ">")
                updates["mar_threshold"] = round(r["threshold"], 3)
                _plots(out_dir, behavior, [x["mar"] for x in pos],
                       [x["mar"] for x in neg], r["threshold"], ">",
                       "is_yawning", "no_yawn")
            else:
                r = sweep_pose([x["yaw"] for x in pos], [x["pitch"] for x in pos],
                               [x["yaw"] for x in neg], [x["pitch"] for x in neg])
                updates["yaw_threshold"] = round(r["yaw_threshold"], 1)
                updates["pitch_threshold"] = round(r["pitch_threshold"], 1)
            results[behavior] = r
            print(f"{behavior}: {r}")
        except ValueError as e:
            print(f"SKIP {behavior}: {e}")

    note = datetime.date.today().isoformat()
    payload = {"date": note, "annotations": str(args.annotations),
               "flagged_excluded": len(flags), "previous": previous,
               "chosen": updates, "metrics": results, "counts": counts}
    (out_dir / "thresholds.json").write_text(json.dumps(payload, indent=2))
    print(f"wrote {out_dir / 'thresholds.json'}")

    if not updates:
        print("no thresholds calibrated — config untouched")
        return 1
    if args.dry_run:
        print(f"dry-run: config NOT written; would set {updates}")
        return 0
    config_path.write_text(
        cc.edit_detection_thresholds(config_text, updates, note),
        encoding="utf-8")
    print(f"updated {config_path}: {updates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3.14 -m pytest dev/tests/test_sweep.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add dev/calibrate_thresholds.py dev/tests/test_sweep.py
git commit -m "dev: max-F1 threshold calibration with ROC/histogram figures"
```

---

### Task 8: `evaluate_dataset.py` + end-to-end smoke test

**Files:**
- Create: `dev/evaluate_dataset.py`
- Test: `dev/tests/test_evaluate.py`
- Test: `dev/tests/test_e2e_smoke.py`

**Interfaces:**
- Consumes: `calib_common` (annotations, `rows_for`, `valid_rows`, `predict_row`, `parse_detection_thresholds`), `calibrate_thresholds.load_flags`, sklearn, matplotlib
- Produces:
  - CLI: `py -3.14 dev/evaluate_dataset.py [--annotations CSV] [--config P] [--out-dir P] [--flags CSV] [--dataset-dir P] [--tag NAME]`
  - `evaluate(rows: list[dict], th: dict) -> dict` — per behavior: `{"y_true": [...], "y_pred": [...], "rows": [...], "counts": {...}}` (pure; skips behaviors with no valid test rows)
  - `write_report(results: dict, th: dict, out_dir: Path, tag: str) -> Path` — writes `classification_report_{tag}.txt` (+ `confusion_{behavior}_{tag}.png`), returns report path
  - `sample_figures(results: dict, dataset_dir: Path, out_dir: Path, tag: str) -> int` — writes ≤2 `sample_{class_dir}_{tag}_{i}.png` per class (image + metric/PRED/TRUE overlay); returns count written; silently skips rows whose image file is absent
  - Report contains: date, thresholds used, per-behavior sklearn `classification_report`, per-class exclusion rates (undetected bucket), sample counts

- [ ] **Step 1: Write the failing tests**

`dev/tests/test_evaluate.py`:

```python
from pathlib import Path

import evaluate_dataset as ev


def _row(split, behavior, label, relpath, valid=True, **metrics):
    row = {"relpath": relpath, "split": split, "behavior": behavior,
           "label": label, "face_detected": valid, "landmarks_detected": valid,
           "ear": None, "mar": None, "yaw": None, "pitch": None}
    row.update(metrics)
    return row


TH = {"ear_threshold": 0.25, "mar_threshold": 0.7,
      "yaw_threshold": 25.0, "pitch_threshold": 15.0}


def test_evaluate_predicates_and_exclusions():
    rows = [
        _row("test", "drowsy", 1, "a", ear=0.20),          # TP (ear < 0.25)
        _row("test", "drowsy", 1, "b", ear=0.30),          # FN
        _row("test", "drowsy", 0, "c", ear=0.30),          # TN
        _row("test", "drowsy", 0, "d", ear=0.10),          # FP
        _row("test", "drowsy", 1, "e", valid=False),       # excluded
        _row("train", "drowsy", 1, "f", ear=0.10),         # wrong split -> ignored
        _row("test", "yawning", 1, "g", mar=0.90),         # TP (mar > 0.7)
        _row("test", "yawning", 0, "h", mar=0.30),         # TN
        _row("test", "distracted", 1, "i", yaw=-40.0, pitch=0.0),  # TP by |yaw|
        _row("test", "distracted", 0, "j", yaw=5.0, pitch=5.0),    # TN
    ]
    res = ev.evaluate(rows, TH)
    assert res["drowsy"]["y_true"] == [1, 1, 0, 0]
    assert res["drowsy"]["y_pred"] == [1, 0, 0, 1]
    assert res["drowsy"]["counts"]["excluded"] == 1
    assert res["drowsy"]["counts"]["total"] == 5
    assert res["yawning"]["y_pred"] == [1, 0]
    assert res["distracted"]["y_pred"] == [1, 0]


def test_evaluate_skips_behavior_without_rows():
    rows = [_row("test", "drowsy", 1, "a", ear=0.2),
            _row("test", "drowsy", 0, "b", ear=0.3)]
    res = ev.evaluate(rows, TH)
    assert "yawning" not in res and "drowsy" in res


def test_write_report(tmp_path):
    rows = [
        _row("test", "drowsy", 1, "a", ear=0.20),
        _row("test", "drowsy", 0, "b", ear=0.30),
        _row("test", "drowsy", 1, "c", valid=False),
    ]
    res = ev.evaluate(rows, TH)
    path = ev.write_report(res, TH, tmp_path, tag="baseline")
    text = path.read_text(encoding="utf-8")
    assert path.name == "classification_report_baseline.txt"
    assert "drowsy" in text and "precision" in text
    assert "excluded (no face/landmarks): 1/3" in text
    assert "ear_threshold: 0.25" in text
    assert (tmp_path / "confusion_drowsy_baseline.png").exists()


def test_sample_figures_writes_overlay_and_skips_missing_files(tmp_path):
    import cv2
    import numpy as np

    img_dir = tmp_path / "test" / "is_drowsy"
    img_dir.mkdir(parents=True)
    cv2.imwrite(str(img_dir / "a.jpg"), np.zeros((60, 80, 3), dtype=np.uint8))
    rows = [_row("test", "drowsy", 1, "test/is_drowsy/a.jpg",
                 ear=0.20, mar=0.05, yaw=1.0, pitch=2.0),
            _row("test", "drowsy", 0, "test/is_drowsy/missing.jpg",
                 ear=0.30, mar=0.05, yaw=1.0, pitch=2.0)]
    res = ev.evaluate(rows, TH)
    n = ev.sample_figures(res, tmp_path, tmp_path / "out", tag="t")
    assert n == 1  # a.jpg written, missing.jpg silently skipped
    assert (tmp_path / "out" / "sample_is_drowsy_t_0.png").exists()
```

`dev/tests/test_e2e_smoke.py`:

```python
"""End-to-end: annotate -> calibrate -> evaluate on the committed fixture.

Slow (~60 s): runs dlib on 36 real images. The fixture's drowsy/yawning
classes are semantically meaningful, so those two must calibrate; the
distracted fixture is IR imagery with a low detection rate and MAY be
skipped — that path is exactly what the skip-behavior logic is for.
"""
import csv
import json
import shutil
from pathlib import Path

import annotate_dataset as ad
import calibrate_thresholds as ct
import evaluate_dataset as ev
import calib_common as cc

FIXTURE = Path(__file__).parent / "fixtures" / "mini_dataset"


def test_full_chain(tmp_path):
    ann = tmp_path / "annotations.csv"
    cfg = tmp_path / "config.yaml"
    out = tmp_path / "calib"
    shutil.copy2(cc.CONFIG_YAML, cfg)

    assert ad.main(["--dataset-dir", str(FIXTURE), "--out", str(ann),
                    "--workers", "0"]) == 0
    with open(ann, newline="", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 36

    rc = ct.main(["--annotations", str(ann), "--config", str(cfg),
                  "--out-dir", str(out), "--flags", str(tmp_path / "no_flags.csv")])
    assert rc == 0
    payload = json.loads((out / "thresholds.json").read_text())
    assert "ear_threshold" in payload["chosen"]
    assert "mar_threshold" in payload["chosen"]
    # config was edited in place, comments elsewhere intact
    new_th = cc.parse_detection_thresholds(cfg.read_text(encoding="utf-8"))
    assert new_th["ear_threshold"] == payload["chosen"]["ear_threshold"]
    assert "calibrated" in cfg.read_text(encoding="utf-8")

    rc = ev.main(["--annotations", str(ann), "--config", str(cfg),
                  "--out-dir", str(tmp_path / "results"),
                  "--flags", str(tmp_path / "no_flags.csv"),
                  "--dataset-dir", str(FIXTURE),
                  "--tag", "calibrated"])
    assert rc == 0
    report = (tmp_path / "results" / "classification_report_calibrated.txt")
    text = report.read_text(encoding="utf-8")
    assert "drowsy" in text and "yawning" in text
    assert list((tmp_path / "results").glob("sample_*_calibrated_*.png"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3.14 -m pytest dev/tests/test_evaluate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evaluate_dataset'`

- [ ] **Step 3: Write `dev/evaluate_dataset.py`**

```python
"""Evaluate the rule-based detectors on the test split of annotations.csv.

Usage: py -3.14 dev/evaluate_dataset.py [--annotations CSV] [--config P]
       [--out-dir P] [--flags CSV] [--tag NAME]

Three INDEPENDENT binary detectors (pos vs domain-matched neg), instantaneous
predicates with the config's detection thresholds — matching how the live
system emits flags. Use --tag baseline before calibration and
--tag calibrated after, for the before/after comparison.
"""
import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import calib_common as cc
from calibrate_thresholds import load_flags


def evaluate(rows, th):
    """Pure evaluation: behavior -> y_true/y_pred over valid test rows."""
    results = {}
    for behavior in cc.BEHAVIORS:
        pos_all, neg_all = cc.rows_for(rows, "test", behavior)
        all_rows = pos_all + neg_all
        usable = cc.valid_rows(all_rows)
        if not usable:
            continue
        y_true = [r["label"] for r in usable]
        y_pred = [int(cc.predict_row(behavior, r, th)) for r in usable]
        results[behavior] = {
            "y_true": y_true, "y_pred": y_pred, "rows": usable,
            "counts": {"total": len(all_rows), "usable": len(usable),
                       "excluded": len(all_rows) - len(usable)},
        }
    return results


def sample_figures(results, dataset_dir, out_dir, tag):
    """2 sample-prediction images per class: metrics + PRED/TRUE overlay."""
    import cv2

    dataset_dir, out_dir = Path(dataset_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for behavior, res in results.items():
        by_class = {}
        for r, pred in zip(res["rows"], res["y_pred"]):
            cls = r["relpath"].split("/")[1]
            by_class.setdefault(cls, []).append((r, pred))
        for cls, pairs in by_class.items():
            pairs.sort(key=lambda x: x[0]["relpath"])
            chosen = [pairs[0]] if len(pairs) == 1 else [pairs[0], pairs[-1]]
            for i, (r, pred) in enumerate(chosen):
                img_path = dataset_dir / r["relpath"]
                if not img_path.exists():
                    continue
                img = cv2.imread(str(img_path))
                if img is None:
                    continue
                text = [f"EAR {r['ear']:.3f}  MAR {r['mar']:.3f}",
                        f"yaw {r['yaw']:.1f}  pitch {r['pitch']:.1f}",
                        f"TRUE {r['label']}  PRED {pred}"]
                for j, line in enumerate(text):
                    cv2.putText(img, line, (8, 24 + 22 * j),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                (0, 255, 0) if pred == r["label"] else (0, 0, 255),
                                2)
                cv2.imwrite(str(out_dir / f"sample_{cls}_{tag}_{i}.png"), img)
                written += 1
    return written


def _confusion_png(y_true, y_pred, behavior, out_dir, tag):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import confusion_matrix

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.imshow(cm, cmap="Blues")
    labels = [cc.BEHAVIORS[behavior]["neg"], cc.BEHAVIORS[behavior]["pos"]]
    ax.set_xticks([0, 1], labels)
    ax.set_yticks([0, 1], labels)
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color="black" if cm[i, j] < cm.max() / 2 else "white")
    ax.set_title(f"{behavior} ({tag})")
    fig.tight_layout()
    fig.savefig(out_dir / f"confusion_{behavior}_{tag}.png", dpi=150)
    plt.close(fig)


def write_report(results, th, out_dir, tag):
    from sklearn.metrics import classification_report

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"EyedTrack offline evaluation — {datetime.date.today().isoformat()}",
             f"tag: {tag}", "thresholds:"]
    for k in cc.DETECTION_KEYS:
        lines.append(f"  {k}: {th[k]}")
    for behavior, res in results.items():
        c = res["counts"]
        spec = cc.BEHAVIORS[behavior]
        lines += ["", "=" * 60, f"{behavior}  ({spec['pos']} vs {spec['neg']})",
                  f"excluded (no face/landmarks): {c['excluded']}/{c['total']}"]
        lines.append(classification_report(
            res["y_true"], res["y_pred"], labels=[0, 1],
            target_names=[spec["neg"], spec["pos"]], zero_division=0))
        _confusion_png(res["y_true"], res["y_pred"], behavior, out_dir, tag)
    path = out_dir / f"classification_report_{tag}.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--annotations", default=str(cc.ANNOTATIONS_CSV))
    ap.add_argument("--config", default=str(cc.CONFIG_YAML))
    ap.add_argument("--out-dir", default=str(cc.REPO_ROOT / "test_results"))
    ap.add_argument("--flags", default=str(cc.DATASET_DIR / "spotcheck_flags.csv"))
    ap.add_argument("--dataset-dir", default=str(cc.DATASET_DIR))
    ap.add_argument("--tag", default="calibrated")
    args = ap.parse_args(argv)

    th = cc.parse_detection_thresholds(
        Path(args.config).read_text(encoding="utf-8"))
    flags = load_flags(args.flags)
    rows = [r for r in cc.load_annotations(args.annotations)
            if r["relpath"] not in flags]
    results = evaluate(rows, th)
    if not results:
        print("no evaluable test rows found")
        return 1
    path = write_report(results, th, args.out_dir, args.tag)
    n = sample_figures(results, args.dataset_dir, args.out_dir, args.tag)
    print(path.read_text(encoding="utf-8"))
    print(f"wrote {path} + {n} sample figures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run unit tests, then the smoke test**

Run: `py -3.14 -m pytest dev/tests/test_evaluate.py -v`
Expected: 4 passed

Run: `py -3.14 -m pytest dev/tests/test_e2e_smoke.py -v`
Expected: 1 passed (~60 s — full annotate → calibrate → evaluate chain on real images)

- [ ] **Step 5: Run the whole suite**

Run: `py -3.14 -m pytest dev/tests -v`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add dev/evaluate_dataset.py dev/tests/test_evaluate.py dev/tests/test_e2e_smoke.py
git commit -m "dev: binary-per-behavior evaluation harness + end-to-end smoke test"
```

---

### Task 9: Operator runbook (`dev/README.md`)

**Files:**
- Create: `dev/README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: the exact command sequence a teammate follows to produce the thesis numbers.

- [ ] **Step 1: Write `dev/README.md`**

````markdown
# Threshold calibration toolchain

Spec: `docs/superpowers/specs/2026-07-16-threshold-calibration-design.md`.
All commands from the repo root. One-time: `py -3.14 -m pip install -r dev/requirements-dev.txt`.

## 1. Download source datasets (one-time, ~manual)

`pip install kaggle`, create an API token (kaggle.com → Settings → Create New
Token) and save it to `%USERPROFILE%\.kaggle\kaggle.json`. Then:

```bash
kaggle datasets download -d banudeep/nthuddd2 -p dataset_raw/nthuddd2 --unzip
kaggle datasets download -d serenaraju/yawn-eye-dataset-new -p dataset_raw/yawn --unzip
kaggle datasets download -d zeyad1mashhour/driver-inattention-detection-dataset -p dataset_raw/dmd --unzip
```

Thesis citations: NTHU-DDD, YawDD (IEEE DataPort), DMD (arXiv:2008.12085).

## 2. Rebuild dataset/ (deterministic, subject-disjoint drowsy split)

```bash
py -3.14 dev/prepare_dataset.py --dry-run   # preview counts
py -3.14 dev/prepare_dataset.py
```

The old dataset/train and dataset/test stop being tracked (they are now
regenerable): `git rm -r --cached dataset/train dataset/test` once, then
commit; history keeps the old images.

## 3. Annotate (~30-60 min for ~20k images)

```bash
py -3.14 dev/annotate_dataset.py
```

Resumable — rerun after an interruption and it continues.

## 4. Spot-check labels (~15-30 min, human)

```bash
py -3.14 dev/spotcheck_labels.py
```

Open `dataset/spotcheck.html`, tick wrong labels, Export flags, save the
download as `dataset/spotcheck_flags.csv`.

## 5. Baseline report (BEFORE calibration)

```bash
py -3.14 dev/evaluate_dataset.py --tag baseline
```

## 6. Calibrate

```bash
py -3.14 dev/calibrate_thresholds.py --dry-run   # inspect first
py -3.14 dev/calibrate_thresholds.py             # writes config.yaml
```

Figures + `thresholds.json` land in `test_results/calibration/`.

## 7. Calibrated report (AFTER) + commit

```bash
py -3.14 dev/evaluate_dataset.py --tag calibrated
git add config.yaml test_results
git commit -m "calibrate detection thresholds from annotated dataset"
```

Compare `test_results/classification_report_baseline.txt` vs
`classification_report_calibrated.txt` — that pair is the thesis
before/after table. Restore old thresholds anytime from
`test_results/calibration/thresholds.json` ("previous").
````

- [ ] **Step 2: Commit**

```bash
git add dev/README.md
git commit -m "dev: operator runbook for the calibration pipeline"
```

---

## Verification (after Task 9, and again after the real data run)

1. `py -3.14 -m pytest dev/tests -v` — full suite green.
2. `git diff HEAD~9 --stat` — changes confined to `dev/`, `.gitignore`, `docs/`.
3. After the operator runbook is executed with real downloads: `test_results/classification_report_baseline.txt` and `_calibrated.txt` exist; calibrated drowsy recall ≫ 0; `git diff config.yaml` shows exactly 4 changed lines.
