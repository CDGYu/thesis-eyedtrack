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
    """Max-F1 (yaw_t, pitch_t) grid search for |yaw|>yt OR |pitch|>pt.

    Many (yaw_t, pitch_t) pairs can tie for the best F1 (e.g. any threshold
    past the last negative sample keeps the same TP/FP counts). Picking the
    edge of that tied plateau would land the threshold exactly on a data
    point (zero margin — brittle on unseen data), so we pick the middle of
    the plateau instead, same intent as sweep_scalar's midpoint candidates.
    """
    py = np.abs(np.asarray(pos_yaw, dtype=float))
    pp = np.abs(np.asarray(pos_pitch, dtype=float))
    ny = np.abs(np.asarray(neg_yaw, dtype=float))
    npi = np.abs(np.asarray(neg_pitch, dtype=float))
    if len(py) == 0 or len(ny) == 0:
        raise ValueError(f"need both classes: pos={len(py)} neg={len(ny)}")
    yaw_grid = np.arange(5.0, 60.5, 0.5)
    pitch_grid = np.arange(5.0, 60.5, 0.5)
    f1 = np.empty((len(yaw_grid), len(pitch_grid)))
    precision = np.empty_like(f1)
    recall = np.empty_like(f1)
    for i, yt in enumerate(yaw_grid):
        pos_hit = (py > yt)[:, None] | (pp[:, None] > pitch_grid[None, :])
        neg_hit = (ny > yt)[:, None] | (npi[:, None] > pitch_grid[None, :])
        tp = pos_hit.sum(axis=0).astype(float)
        fp = neg_hit.sum(axis=0).astype(float)
        prec = tp / np.maximum(tp + fp, 1)
        rec = tp / len(py)
        precision[i] = prec
        recall[i] = rec
        f1[i] = np.where(tp > 0, 2 * prec * rec / np.maximum(prec + rec, 1e-12), 0.0)

    best_f1 = f1.max()
    tied_rows = np.unique(np.argwhere(f1 == best_f1)[:, 0])
    i = tied_rows[len(tied_rows) // 2]
    tied_cols = np.flatnonzero(f1[i] == best_f1)  # already ascending
    j = tied_cols[len(tied_cols) // 2]
    return {"yaw_threshold": float(yaw_grid[i]),
            "pitch_threshold": float(pitch_grid[j]),
            "f1": float(f1[i, j]), "precision": float(precision[i, j]),
            "recall": float(recall[i, j])}


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
