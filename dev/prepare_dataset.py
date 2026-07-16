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
    """Direct (non-recursive) image children of d, sorted for determinism."""
    return sorted(p for p in d.iterdir()
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
            sources[SOURCE_NAME_MAP[name]].extend(_images_under(d))
        elif name == DANGEROUS:
            sources["_dangerous"].extend(_images_under(d))
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


def _unique_dest(dest: Path, p: Path) -> Path:
    """Collision-free destination for copying p into dest; never overwrites.

    Tries the plain basename first, then the immediate parent-dir-prefixed
    name, then keeps appending an incrementing numeric suffix until a name
    that doesn't already exist on disk is found. Deterministic given sorted
    input order.
    """
    target = dest / p.name
    if not target.exists():
        return target
    target = dest / f"{p.parent.name}_{p.name}"
    n = 2
    while target.exists():
        target = dest / f"{p.parent.name}_{p.stem}_{n}{p.suffix}"
        n += 1
    return target


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
            shutil.copy2(p, _unique_dest(dest, p))
        # count actual files on disk rather than assume len(paths) is exact
        counts[split][cls] = sum(1 for q in dest.iterdir() if q.is_file())

    manifest = {"train_cap": args.train_cap, "test_cap": args.test_cap,
                "raw_dir": str(raw_dir), "counts": counts}
    (out_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {out_dir / 'MANIFEST.json'}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
