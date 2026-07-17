# Data-Calibrated Detection Thresholds — Design

**Date:** 2026-07-16
**Status:** Approved (brainstorming session with CDGYu)
**Scope:** Backend only — offline dataset annotation, threshold calibration, and evaluation harness. No server code changes except the four numeric values in `config.yaml → detection:`.

## Problem

EyedTrack detects drowsiness, yawning, and distraction with fixed thresholds (EAR, MAR, yaw/pitch) that have been hand-nudged back and forth (`config.yaml` comments: "raised from 0.25", "lowered from 0.7 to 0.6", "was 25, now 35"). The last recorded evaluation (`test_results/classification_report.txt`, 2026-06-17) shows 67% accuracy on a 24-image test set with **0% recall on `is_drowsy`**. Investigation findings that shape this design:

- The script that produced that report was never committed (likely `test_improved_detection.py`, existed only on the author's machine). Its reconstructed protocol forced a 3-way argmax over normalized per-class confidences — but the three behaviors are not mutually exclusive, and drowsy subjects tilt their heads, so "distracted" always outbid "drowsy". **The eval protocol itself guaranteed the 0% recall.**
- `dataset/train` has no negative (alert/neutral) class at all, no `is_distracted` training data, and a 15:1 drowsy:yawning imbalance (9,412 vs 617). Thresholds cannot be calibrated without examples on both sides.
- The drowsy images are consecutive video frames of 4 subjects (001/002/005/006, NTHU-DDD), and the current test images reuse **the same subjects** as train — frame-level splits leak.
- Empirical probe (dlib 20.0.1 via `py -3.14`): face-detection rates are ~95% on drowsy train, ~72% on yawning, ~62% on the IR distraction images; ~0.6 s/image.

## Goal

Improve the **offline test-set accuracy** of the existing rule-based dlib pipeline by (a) machine-annotating the dataset with the pipeline's own EAR/MAR/yaw/pitch values, (b) calibrating the four `detection:` thresholds from those annotations against proper negative classes, and (c) rebuilding a defensible evaluation harness. The thesis methodology (threshold-based detection on dlib landmarks) is unchanged.

**Non-goals:** training an ML classifier (kept as a possible future comparison); tuning temporal frame-count parameters (`*_frames_threshold`) — those need video-sequence evaluation; live/demo tuning.

## Data acquisition & layout

Three public datasets, one per behavior — each contains the matching negative class, keeping negatives domain-matched to their positives:

| Behavior | Dataset | Positive class | Negative class |
|---|---|---|---|
| Drowsy | Kaggle `banudeep/nthuddd2` (NTHU-DDD frames) | `drowsy` | `notdrowsy` |
| Yawning | Kaggle `serenaraju/yawn-eye-dataset-new` (YawDD-derived) | `yawn` | `no_yawn` |
| Distracted | Kaggle `zeyad1mashhour/driver-inattention-detection-dataset` (DMD via Roboflow, CC BY 4.0) | `Distracted` (adding `DangerousDriving` only if `Distracted` alone cannot fill the 150–300-per-side test target) | `SafeDriving` |

One-time manual step (user): `pip install kaggle`, API token at `%USERPROFILE%\.kaggle\kaggle.json`, then:

```
kaggle datasets download -d banudeep/nthuddd2 -p dataset_raw/nthuddd2 --unzip
kaggle datasets download -d serenaraju/yawn-eye-dataset-new -p dataset_raw/yawn --unzip
kaggle datasets download -d zeyad1mashhour/driver-inattention-detection-dataset -p dataset_raw/dmd --unzip
```

`dataset_raw/` is gitignored. Thesis citations: NTHU-DDD, YawDD (IEEE DataPort), DMD (arXiv:2008.12085) — the Kaggle copies are redistributions.

**`dev/prepare_dataset.py`** rebuilds `dataset/train` and `dataset/test` deterministically from `dataset_raw/`:

- Layout: `dataset/{train,test}/{is_drowsy,not_drowsy,is_yawning,no_yawn,is_distracted,safe_driving}/`.
- **Drowsy: subject-disjoint split** — subjects 001/002/006 → train, 005 → test (adjusted to whatever subjects exist in the download; the rule is: no subject appears in both splits).
- **Yawning / DMD:** upstream train/test splits used as-is. DMD labels are per-image bounding-box classes; the image's box class becomes its folder.
- Positives ≈ negatives per behavior (downsample the larger side deterministically: sort, take every Nth).
- Test split target: 150–300 images per class-side (vs today's 8).
- The current 24-image test set is archived to `dataset_raw/legacy_test/` and superseded. `dataset/` becomes fully regenerable.

## Components & data flow

```
dataset_raw/  --prepare_dataset.py-->  dataset/{train,test}/<6 class folders>
dataset/      --annotate_dataset.py--> dataset/annotations.csv        (the annotation layer)
annotations   --spotcheck_labels.py--> spotcheck.html + spotcheck_flags.csv   (human 15-30 min)
annotations + flags --calibrate_thresholds.py--> test_results/calibration/{thresholds.json, roc_*.png, hist_*.png}
                                                 + targeted edit of config.yaml detection: values
annotations + config --evaluate_dataset.py--> test_results/classification_report.txt, confusion_*.png, samples
```

### `dev/annotate_dataset.py` — the annotation step

For every image under `dataset/`: load BGR (`cv2.imread`) → apply the **same preprocessing the live server applies** (resize ×`performance.resize_factor` (0.75) + CLAHE on LAB-L, clip 2.5, tile 8×8 — per `frame_processor.py:219-228`) so calibrated thresholds match runtime conditions → `ImprovedFaceAnalyzer.analyze_frame()` → one CSV row:

```
relpath, split, behavior, label, face_detected, landmarks_detected,
ear, left_ear, right_ear, mar, yaw, pitch, width, height, grayscale_like
```

(`grayscale_like` = max per-pixel channel difference ≤ 8, i.e. effectively monochrome/IR capture stored as RGB — the probe found this predicts lower dlib detection rates, so it's worth tracking per row.)

- Uses `ImprovedFaceAnalyzer` directly (stateless per-image metrics). **Never** `OptimizedFrameProcessor` — its temporal counters persist across calls and its constructor instantiates `VideoRecorder` (creates directories).
- `load_config(<repo>/config.yaml)` with an explicit absolute path (CWD-dependent otherwise).
- Multiprocessing pool, one analyzer per worker (~25k images ≈ 35–45 min on 8 workers at the probed ~0.6 s/image).
- Logging suppressed to WARNING (analyzer logs per-frame at INFO).
- Resumable: on rerun, skips relpaths already in the CSV.

### `dev/spotcheck_labels.py` — human label verification

Deterministic sample of 50 images per class-side into one self-contained HTML contact sheet with checkboxes and an "export flags" button producing `spotcheck_flags.csv` (relpath per wrongly-labeled image). Flagged rows are excluded from calibration and evaluation.

### `dev/calibrate_thresholds.py`

Input: `annotations.csv` train rows where `face_detected AND landmarks_detected` and not flagged. Per behavior:

- **Drowsy:** sweep `t` over the observed EAR range; predicate `ear < t`; positives `is_drowsy`, negatives `not_drowsy`.
- **Yawning:** sweep `t`; predicate `mar > t`; positives `is_yawning`, negatives `no_yawn`.
- **Distracted:** joint grid search over `(yaw_t, pitch_t)`; predicate `|yaw| > yaw_t OR |pitch| > pitch_t` (the pipeline's actual rule, `improved_detection.py:393`); positives `is_distracted`, negatives `safe_driving`.
- Selection criterion: **max F1** on train. Report ROC AUC and the full precision/recall curve alongside.

Outputs:
- `test_results/calibration/thresholds.json` — chosen values, previous values, F1/AUC, dataset sizes, exclusion rates, calibration date.
- `test_results/calibration/roc_<behavior>.png`, `hist_<behavior>.png` (positive vs negative metric distributions with the chosen threshold marked) — thesis figures.
- `config.yaml` update by **targeted line edit** of the four keys (`ear_threshold`, `mar_threshold`, `yaw_threshold`, `pitch_threshold` under `detection:`) with a `# calibrated 2026-07-16` suffix comment — preserves all existing hand-written comments (a YAML round-trip would destroy them). A `--dry-run` flag prints values without writing.

### `dev/evaluate_dataset.py` — the new harness

Evaluates the **test split** as **three independent binary detectors** (positives vs their domain-matched negatives, instantaneous predicate with configured thresholds) — matching how the live system actually emits three independent flags, and fixing the argmax flaw. Produces:

- Per-behavior sklearn `classification_report` (precision/recall/F1) + combined summary in `test_results/classification_report.txt`. [Drift: the cross-behavior combined summary was not carried into the plan/implementation — the plan is the source of truth; each behavior's report stands alone.]
- Per-behavior confusion-matrix PNGs and 2 sample-prediction figures per class (annotated image + metric values), replacing the old artifacts.
- Per-class **exclusion rate** (no face / no landmarks) printed in every report.
- `--config-override` flag to evaluate with arbitrary threshold values. [Drift: `--config-override` was not carried into the plan/implementation; `thresholds.json["previous"]` already covers restoring prior values.]

**Before/after protocol:** run the harness twice — current hand-tuned thresholds vs calibrated ones — same data, same protocol. The old 67% figure is not comparable (lost script, unknown confidence formula) and is reported only as historical context.

## Error handling

- `analyze_frame` returns **0.0 as both a legitimate value and an error sentinel** (EAR/MAR) — rows are used only when `face_detected AND landmarks_detected` are true; `success=False` rows keep their relpath in the CSV with empty metric fields.
- Unreadable/corrupt images: logged, recorded as `face_detected=False`, never crash the batch.
- No-face images form an explicit "undetected" bucket with per-class rates in all reports (expected from probe: ~5% drowsy, ~28% yawning, ~38% IR-distracted). Stated as a limitation, not silently dropped.
- All sampling deterministic and RNG-free: sort filenames, take every Nth. `thresholds.json` archives prior values, so calibration is reversible; `git diff config.yaml` shows exactly four line changes.
- `prepare_dataset.py` fails loudly with a per-dataset message if an expected `dataset_raw/` folder is missing (tells the user which Kaggle command to run).

## Testing

- **pytest** (`dev/tests/`): threshold-sweep/F1 selection on synthetic score distributions (known optimum); config line-editor round-trip (values changed, comments byte-identical elsewhere); split determinism (same inputs → same file lists); subject-disjointness assertion for drowsy.
- **Smoke fixture:** ~20 committed images exercising annotate → calibrate → evaluate end-to-end in seconds.
- **Verification of the real thing:** the evaluation harness itself — before/after reports checked into `test_results/`.

## Success criteria

1. `annotations.csv` covers every image in `dataset/` with per-image metrics and validity flags.
2. Calibrated thresholds beat the current hand-tuned ones on the held-out test split (per-behavior F1, same harness, same data) — in particular drowsy recall ≫ 0.
3. Every number in the final report is reproducible from `dataset_raw/` by running the four scripts in order.
4. ROC curves, histograms, and before/after tables suitable for direct inclusion in the thesis.
