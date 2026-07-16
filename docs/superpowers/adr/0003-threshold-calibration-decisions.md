# ADR-0003: Data-Calibrated Detection Thresholds

**Date:** 2026-07-16 · **Status:** Accepted · **Branch:** `feat/threshold-calibration`
**Spec:** `docs/superpowers/specs/2026-07-16-threshold-calibration-design.md`
**Plan:** `docs/superpowers/plans/2026-07-16-threshold-calibration.md` (9 TDD tasks — the plan file is the single source of truth for task content)

## Context

Detection thresholds (EAR/MAR/yaw/pitch in `config.yaml → detection:`) were hand-guessed; the last evaluation showed 67% accuracy with **0% drowsy recall** on a 24-image test set. Investigation (4-agent workflow, 2026-07-16) established:

- The old eval script was never committed; its reconstructed protocol used a 3-way argmax over normalized confidences — behaviors aren't mutually exclusive, drowsy heads tilt down, so "distracted" always won. **The protocol, not just thresholds, caused the 0% recall.**
- `dataset/train` has no negative classes, no distraction training data, 15:1 class imbalance.
- Drowsy images = consecutive NTHU-DDD video frames of subjects 001/002/005/006; current test reuses train subjects → leakage.
- `ImprovedFaceAnalyzer.analyze_frame()` (face_analysis/improved_detection.py) is stateless per-image → clean annotator. Runtime thresholds come from `config.yaml → detection:` (the `thresholds:` section is dead for EAR/MAR/pose; it only feeds frame counts).
- dlib probe (py -3.14, dlib 20.0.1): detection rates ~95% drowsy train, ~72% yawning, ~62% IR distracted; ~0.6 s/image.

## Decisions

1. **Calibrate the rule-based detector; do NOT train an ML model.** Keeps thesis methodology (dlib landmarks + thresholds). Annotation = machine-generated CSV of the pipeline's own EAR/MAR/yaw/pitch per image. (Logistic-regression combiner kept as optional future comparison.)
2. **Domain-matched negatives from the three source datasets** (Kaggle): `banudeep/nthuddd2` (drowsy/notdrowsy), `serenaraju/yawn-eye-dataset-new` (yawn/no_yawn), `zeyad1mashhour/driver-inattention-detection-dataset` (DMD: Distracted/SafeDriving). Cite NTHU-DDD, YawDD, DMD (arXiv:2008.12085) in the thesis.
3. **Subject-disjoint drowsy split** (preferred test subject 005); upstream splits for yawn/DMD. Old 24-image test set archived to `dataset_raw/legacy_test/`; `dataset/` becomes fully regenerable via `dev/prepare_dataset.py`.
4. **Evaluate as three independent binary detectors** (pos vs domain-matched neg), not 3-way argmax — matches how the live system emits flags and fixes the protocol flaw. Before/after = same harness, old vs calibrated thresholds (`--tag baseline` / `--tag calibrated`).
5. **Max-F1 threshold selection** with ROC/AUC + histogram figures; distraction = joint (yaw, pitch) grid with the pipeline's OR-predicate.
6. **Comment-preserving config edit:** targeted line edits of the four keys inside `detection:` only (`parse/edit_detection_thresholds` in `dev/calib_common.py`); never YAML round-trip (would destroy hand comments).
7. **Annotation replicates server preprocessing** (resize ×0.75 + CLAHE LAB-L clip 2.5 tile 8×8). **CLAHE default when key absent is `enabled=True`** — matches `frame_processor.py:59`; a review fix (f1d686a) corrected the plan's original `False` default.
8. **Rows usable only when `face_detected AND landmarks_detected`** (0.0 is the analyzer's error sentinel); no-face images form an explicit reported exclusion bucket.
9. **Test fixture built only from images verified to detect** (`dev/tests/fixtures/build_fixture.py`) — current test drowsy images detect only ~50%, blind copying would make smoke tests flaky.
10. **All sampling deterministic and RNG-free** (sort + every-Nth). New code confined to `dev/`; only server change is the four numbers in `config.yaml`.
11. **No git worktrees for this work:** `shape_predictor_68_face_landmarks.dat` is gitignored (`*.dat`), so fresh worktrees lack it and all dlib tests break. Branch-in-place.

## Consequences

- Thesis gets defensible figures: ROC curves, histograms, before/after classification reports, subject-disjoint protocol, honest exclusion rates.
- Requires one-time manual Kaggle downloads (runbook = Task 9, `dev/README.md`).
- IR/distraction detection rate (~62%) is a stated limitation, not silently dropped.
