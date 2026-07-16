import json
from pathlib import Path

import prepare_dataset as pd


def _touch(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"\xff\xd8fake")


def _make_raw(root: Path):
    # NTHU-like: subjects 001/002/005 in drowsy + notdrowsy
    for subj in ("001", "002", "005"):
        for i in range(10):
            _touch(root / "nthuddd2" / "drowsy" / f"{subj}_glasses_blink_{i:04d}_drowsy.jpg")
            _touch(root / "nthuddd2" / "notdrowsy" / f"{subj}_glasses_mix_{i:04d}_notdrowsy.jpg")
    _touch(root / "nthuddd2" / "drowsy" / "README.jpg")  # no subject prefix -> skipped
    # yawn dataset with upstream split
    for i in range(8):
        _touch(root / "yawn" / "train" / "yawn" / f"{i}.jpg")
        _touch(root / "yawn" / "train" / "no_yawn" / f"{i}.jpg")
    for i in range(4):
        _touch(root / "yawn" / "test" / "yawn" / f"t{i}.jpg")
        _touch(root / "yawn" / "test" / "no_yawn" / f"t{i}.jpg")
    # DMD-like with upstream split
    for i in range(8):
        _touch(root / "dmd" / "train" / "Distracted" / f"d{i}.jpg")
        _touch(root / "dmd" / "train" / "SafeDriving" / f"s{i}.jpg")
    for i in range(4):
        _touch(root / "dmd" / "test" / "Distracted" / f"dt{i}.jpg")
        _touch(root / "dmd" / "test" / "SafeDriving" / f"st{i}.jpg")


def test_discover_finds_all_six_sources(tmp_path):
    _make_raw(tmp_path)
    src = pd.discover_sources(tmp_path)
    # 30 subject images + README.jpg (discover doesn't filter; plan_layout does)
    assert len(src["is_drowsy"]) == 31 and len(src["not_drowsy"]) == 30
    assert len(src["is_yawning"]) == 12 and len(src["no_yawn"]) == 12
    assert len(src["is_distracted"]) == 12 and len(src["safe_driving"]) == 12


def test_plan_is_subject_disjoint_and_balanced(tmp_path):
    _make_raw(tmp_path)
    plan = pd.plan_layout(pd.discover_sources(tmp_path), train_cap=100, test_cap=100)
    train_subjects = {p.name[:3] for p in plan[("train", "is_drowsy")]}
    test_subjects = {p.name[:3] for p in plan[("test", "is_drowsy")]}
    assert test_subjects == {"005"}
    assert train_subjects == {"001", "002"}
    assert not (train_subjects & test_subjects)
    # balance: pos == neg count per behavior per split
    for split in ("train", "test"):
        assert len(plan[(split, "is_drowsy")]) == len(plan[(split, "not_drowsy")])
        assert len(plan[(split, "is_yawning")]) == len(plan[(split, "no_yawn")])
    # README.jpg (no NNN_ prefix) never planned
    all_names = {p.name for paths in plan.values() for p in paths}
    assert "README.jpg" not in all_names


def test_plan_respects_caps_and_upstream_split(tmp_path):
    _make_raw(tmp_path)
    plan = pd.plan_layout(pd.discover_sources(tmp_path), train_cap=5, test_cap=2)
    assert len(plan[("train", "is_yawning")]) == 5
    assert len(plan[("test", "is_yawning")]) == 2
    # upstream split respected: test images only from the source's test/ tree
    assert all("test" in p.parts for p in plan[("test", "is_distracted")])


def test_plan_deterministic(tmp_path):
    _make_raw(tmp_path)
    p1 = pd.plan_layout(pd.discover_sources(tmp_path), 5, 2)
    p2 = pd.plan_layout(pd.discover_sources(tmp_path), 5, 2)
    assert p1 == p2


def test_main_copies_archives_and_writes_manifest(tmp_path):
    _make_raw(tmp_path / "raw")
    out = tmp_path / "dataset"
    (out / "test" / "is_drowsy").mkdir(parents=True)
    (out / "test" / "is_drowsy" / "old.jpg").write_bytes(b"legacy")
    rc = pd.main(["--raw-dir", str(tmp_path / "raw"), "--out-dir", str(out),
                  "--train-cap", "5", "--test-cap", "2"])
    assert rc == 0
    # legacy test archived
    assert (tmp_path / "raw" / "legacy_test" / "is_drowsy" / "old.jpg").exists()
    manifest = json.loads((out / "MANIFEST.json").read_text())
    for split in ("train", "test"):
        for cls in ("is_drowsy", "not_drowsy", "is_yawning", "no_yawn",
                    "is_distracted", "safe_driving"):
            n = len(list((out / split / cls).glob("*.jpg")))
            assert n == manifest["counts"][split][cls] > 0


def test_main_missing_source_errors_but_continues(tmp_path, capsys):
    # only the yawn dataset present
    for i in range(4):
        _touch(tmp_path / "raw" / "yawn" / "train" / "yawn" / f"{i}.jpg")
        _touch(tmp_path / "raw" / "yawn" / "train" / "no_yawn" / f"{i}.jpg")
        _touch(tmp_path / "raw" / "yawn" / "test" / "yawn" / f"t{i}.jpg")
        _touch(tmp_path / "raw" / "yawn" / "test" / "no_yawn" / f"t{i}.jpg")
    rc = pd.main(["--raw-dir", str(tmp_path / "raw"),
                  "--out-dir", str(tmp_path / "dataset"),
                  "--train-cap", "5", "--test-cap", "2"])
    out = capsys.readouterr().out
    assert rc == 1  # something missing
    assert "kaggle datasets download -d banudeep/nthuddd2" in out
    assert (tmp_path / "dataset" / "train" / "is_yawning").exists()  # continued
