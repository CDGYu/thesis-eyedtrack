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
