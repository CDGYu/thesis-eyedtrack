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
