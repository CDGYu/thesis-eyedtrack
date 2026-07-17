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


def test_main_archives_stale_annotations_and_flags_csv(tmp_path, capsys):
    """A rerun of prepare_dataset rewrites dataset/train + dataset/test with
    new pixels under the same relpaths; a pre-existing annotations.csv (or
    spotcheck_flags.csv) would then have stale metrics silently attached to
    new images on the next annotate resume. main() must archive both instead
    of leaving them in place, overwriting any previous stale copy."""
    _make_raw(tmp_path / "raw")
    out = tmp_path / "dataset"
    out.mkdir(parents=True)
    ann = out / "annotations.csv"
    ann.write_text("relpath,split\ntrain/is_drowsy/x.jpg,train\n", encoding="utf-8")
    flags = out / "spotcheck_flags.csv"
    flags.write_text("relpath\ntrain/is_drowsy/x.jpg\n", encoding="utf-8")
    # a previous stale copy must be overwritten, not left behind or blocking
    old_stale = out / "annotations.stale.csv"
    old_stale.write_text("stale-from-earlier-rerun", encoding="utf-8")

    rc = pd.main(["--raw-dir", str(tmp_path / "raw"), "--out-dir", str(out),
                  "--train-cap", "5", "--test-cap", "2"])
    assert rc == 0
    out_text = capsys.readouterr().out

    assert not ann.exists()
    assert not flags.exists()
    stale_ann = out / "annotations.stale.csv"
    stale_flags = out / "spotcheck_flags.stale.csv"
    assert stale_ann.exists() and stale_ann.read_text(encoding="utf-8") == \
        "relpath,split\ntrain/is_drowsy/x.jpg,train\n"
    assert stale_flags.exists() and stale_flags.read_text(encoding="utf-8") == \
        "relpath\ntrain/is_drowsy/x.jpg\n"
    assert "annotations.csv" in out_text and "invalidat" in out_text.lower()
    assert "spotcheck_flags.csv" in out_text


def test_main_no_stale_warning_when_no_annotations_csv(tmp_path, capsys):
    _make_raw(tmp_path / "raw")
    out = tmp_path / "dataset"
    rc = pd.main(["--raw-dir", str(tmp_path / "raw"), "--out-dir", str(out),
                  "--train-cap", "5", "--test-cap", "2"])
    assert rc == 0
    out_text = capsys.readouterr().out
    assert "invalidat" not in out_text.lower()
    assert not (out / "annotations.stale.csv").exists()


def test_main_reports_skipped_files_without_subject_prefix(tmp_path, capsys):
    """_make_raw plants exactly one no-prefix file (README.jpg, drowsy source
    only); main() must surface that count instead of discarding it."""
    _make_raw(tmp_path / "raw")
    out = tmp_path / "dataset"
    rc = pd.main(["--raw-dir", str(tmp_path / "raw"), "--out-dir", str(out),
                  "--train-cap", "5", "--test-cap", "2"])
    assert rc == 0
    out_text = capsys.readouterr().out
    assert "skipped 1 files without subject prefix" in out_text


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


def test_copy_collision_never_overwrites_and_manifest_matches_disk(tmp_path):
    """Finding 1 regression: 3+ sources sharing a basename AND an immediate
    parent dir name must all survive under distinct names, with correct
    contents, and MANIFEST.json counts must equal what's actually on disk.
    """
    raw = tmp_path / "raw"
    contents = (b"AAA-source-0", b"BBB-source-1", b"CCC-source-2", b"DDD-source-3")
    for i, content in enumerate(contents):
        d = raw / f"set{i}" / "distracted"  # same immediate parent name each time
        d.mkdir(parents=True)
        (d / "0.jpg").write_bytes(content)
        s = raw / f"set{i}" / "safedriving"
        s.mkdir(parents=True)
        (s / "0.jpg").write_bytes(content)

    out = tmp_path / "dataset"
    pd.main(["--raw-dir", str(raw), "--out-dir", str(out),
             "--train-cap", "10", "--test-cap", "10"])

    dist_dir = out / "train" / "is_distracted"
    files = sorted(dist_dir.iterdir())
    assert len(files) == len(contents)  # nothing silently overwritten
    names = {f.name for f in files}
    assert len(names) == len(contents)  # all distinct names
    on_disk_contents = {f.read_bytes() for f in files}
    assert on_disk_contents == set(contents)  # correct contents preserved

    manifest = json.loads((out / "MANIFEST.json").read_text())
    actual_on_disk = len(list(dist_dir.glob("*")))
    assert manifest["counts"]["train"]["is_distracted"] == actual_on_disk == len(contents)


def test_discover_finds_dangerousdriving_source(tmp_path):
    """Finding 3a: the DangerousDriving discovery branch (elif name == DANGEROUS)."""
    raw = tmp_path / "raw"
    for i in range(5):
        _touch(raw / "DangerousDriving" / f"dd{i}.jpg")  # mixed case, normalizes to DANGEROUS
    src = pd.discover_sources(raw)
    assert len(src["_dangerous"]) == 5
    assert {p.name for p in src["_dangerous"]} == {f"dd{i}.jpg" for i in range(5)}


def _make_dmd_raw(root: Path, n_train, n_test):
    for i in range(n_train):
        _touch(root / "dmd" / "train" / "Distracted" / f"d{i}.jpg")
        _touch(root / "dmd" / "train" / "SafeDriving" / f"s{i}.jpg")
    for i in range(n_test):
        _touch(root / "dmd" / "test" / "Distracted" / f"dt{i}.jpg")
        _touch(root / "dmd" / "test" / "SafeDriving" / f"st{i}.jpg")


def _make_dangerous_raw(root: Path, n):
    # the matched dir (literally named "dangerousdriving") must itself contain
    # the images directly (discover_sources scans it non-recursively), and it
    # must sit under a "test" ancestor for _path_split to route it to test.
    for i in range(n):
        _touch(root / "extra" / "test" / "dangerousdriving" / f"dd{i}.jpg")


def test_dangerousdriving_tops_up_when_below_min_test_warn(tmp_path, monkeypatch):
    """Finding 3b: top-up fires when pre-top-up test count < MIN_TEST_WARN."""
    monkeypatch.setattr(pd, "MIN_TEST_WARN", 3)
    raw = tmp_path / "raw"
    _make_dmd_raw(raw, n_train=2, n_test=2)  # is_distracted test count = 2 < 3
    _make_dangerous_raw(raw, n=4)

    plan = pd.plan_layout(pd.discover_sources(raw), train_cap=10, test_cap=10)
    test_names = {p.name for p in plan[("test", "is_distracted")]}
    assert any(name.startswith("dd") for name in test_names)  # topped up


def test_dangerousdriving_does_not_top_up_at_or_above_min_test_warn(tmp_path, monkeypatch):
    """Finding 3b: top-up does NOT fire once pre-top-up test count >= MIN_TEST_WARN."""
    monkeypatch.setattr(pd, "MIN_TEST_WARN", 2)
    raw = tmp_path / "raw"
    _make_dmd_raw(raw, n_train=2, n_test=2)  # is_distracted test count = 2, at threshold
    _make_dangerous_raw(raw, n=4)

    plan = pd.plan_layout(pd.discover_sources(raw), train_cap=10, test_cap=10)
    test_names = {p.name for p in plan[("test", "is_distracted")]}
    assert not any(name.startswith("dd") for name in test_names)  # not topped up
