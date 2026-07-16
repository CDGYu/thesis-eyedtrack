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
