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
