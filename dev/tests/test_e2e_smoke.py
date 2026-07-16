"""End-to-end: annotate -> calibrate -> evaluate on the committed fixture.

Slow (~60 s): runs dlib on 36 real images. The fixture's drowsy/yawning
classes are semantically meaningful, so those two must calibrate; the
distracted fixture is IR imagery with a low detection rate and MAY be
skipped — that path is exactly what the skip-behavior logic is for.
"""
import csv
import json
import shutil
from pathlib import Path

import annotate_dataset as ad
import calibrate_thresholds as ct
import evaluate_dataset as ev
import calib_common as cc

FIXTURE = Path(__file__).parent / "fixtures" / "mini_dataset"


def test_full_chain(tmp_path):
    ann = tmp_path / "annotations.csv"
    cfg = tmp_path / "config.yaml"
    out = tmp_path / "calib"
    shutil.copy2(cc.CONFIG_YAML, cfg)

    assert ad.main(["--dataset-dir", str(FIXTURE), "--out", str(ann),
                    "--workers", "0"]) == 0
    with open(ann, newline="", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 36

    rc = ct.main(["--annotations", str(ann), "--config", str(cfg),
                  "--out-dir", str(out), "--flags", str(tmp_path / "no_flags.csv")])
    assert rc == 0
    payload = json.loads((out / "thresholds.json").read_text())
    assert "ear_threshold" in payload["chosen"]
    assert "mar_threshold" in payload["chosen"]
    # config was edited in place, comments elsewhere intact
    new_th = cc.parse_detection_thresholds(cfg.read_text(encoding="utf-8"))
    assert new_th["ear_threshold"] == payload["chosen"]["ear_threshold"]
    assert "calibrated" in cfg.read_text(encoding="utf-8")

    rc = ev.main(["--annotations", str(ann), "--config", str(cfg),
                  "--out-dir", str(tmp_path / "results"),
                  "--flags", str(tmp_path / "no_flags.csv"),
                  "--dataset-dir", str(FIXTURE),
                  "--tag", "calibrated"])
    assert rc == 0
    report = (tmp_path / "results" / "classification_report_calibrated.txt")
    text = report.read_text(encoding="utf-8")
    assert "drowsy" in text and "yawning" in text
    assert list((tmp_path / "results").glob("sample_*_calibrated_*.png"))
