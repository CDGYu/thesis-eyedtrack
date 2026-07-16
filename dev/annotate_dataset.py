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
