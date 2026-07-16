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
REPO = HERE.parents[2]
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
