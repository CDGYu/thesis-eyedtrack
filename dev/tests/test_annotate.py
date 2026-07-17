import csv
from pathlib import Path

import pytest

import annotate_dataset as ad
import calib_common as cc

FIXTURE = Path(__file__).parent / "fixtures" / "mini_dataset"


def test_list_jobs_enumerates_and_resumes():
    jobs = ad.list_jobs(FIXTURE, done=set())
    assert len(jobs) == 36
    relpaths = [j[0] for j in jobs]
    assert relpaths == sorted(relpaths)
    assert all(j[2] in ("train", "test") and j[3] in cc.CLASS_DIRS for j in jobs)
    half = set(relpaths[:18])
    assert len(ad.list_jobs(FIXTURE, done=half)) == 18


def test_annotate_inline_produces_valid_rows(tmp_path):
    jobs = [j for j in ad.list_jobs(FIXTURE, done=set())
            if j[2] == "train" and j[3] == "is_drowsy"]  # 4 drowsy train images
    rows = list(ad.annotate_inline(jobs, cc.CONFIG_YAML))
    assert len(rows) == 4
    for row in rows:
        assert set(row) == set(cc.CSV_FIELDS)
        assert row["behavior"] == "drowsy" and row["label"] == 1
        # build_fixture.py selected these BECAUSE they detect via this exact path
        assert row["face_detected"] == 1 and row["landmarks_detected"] == 1
        assert 0.0 < float(row["ear"]) < 0.6
        assert 0.0 <= float(row["mar"]) < 2.0


def test_annotate_inline_handles_unreadable_file(tmp_path):
    bad = tmp_path / "train" / "is_drowsy" / "corrupt.jpg"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"not a jpeg")
    jobs = ad.list_jobs(tmp_path, done=set())
    rows = list(ad.annotate_inline(jobs, cc.CONFIG_YAML))
    assert len(rows) == 1
    assert rows[0]["face_detected"] == 0 and rows[0]["ear"] == ""


def test_main_writes_and_resumes_csv(tmp_path):
    out = tmp_path / "ann.csv"
    rc = ad.main(["--dataset-dir", str(FIXTURE), "--out", str(out), "--workers", "0"])
    assert rc == 0
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 36
    # second run adds nothing (resume) and exits cleanly
    rc = ad.main(["--dataset-dir", str(FIXTURE), "--out", str(out), "--workers", "0"])
    assert rc == 0
    with open(out, newline="", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 36
    # typed loader accepts the output; the 30 drowsy/yawn-derived fixture
    # images are detection-verified, only the 6 IR distracted ones may miss
    parsed = cc.load_annotations(out)
    assert len(cc.valid_rows(parsed)) >= 24


def test_main_treats_zero_byte_existing_file_as_new(tmp_path):
    """A pre-existing but empty annotations.csv (e.g. left by a crashed run
    or `touch`) must still get a header written, not headerless data rows
    that would corrupt the next read (first data row misread as header)."""
    out = tmp_path / "ann.csv"
    out.touch()
    assert out.exists() and out.stat().st_size == 0
    rc = ad.main(["--dataset-dir", str(FIXTURE), "--out", str(out), "--workers", "0"])
    assert rc == 0
    with open(out, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == cc.CSV_FIELDS
        rows = list(reader)
    assert len(rows) == 36
    parsed = cc.load_annotations(out)
    assert len(cc.valid_rows(parsed)) >= 24


def test_main_pool_workers_writes_valid_csv(tmp_path):
    """--workers 2 exercises the real multiprocessing.Pool path (spawn on
    Windows): workers re-import annotate_dataset and build their own
    dlib/analyzer objects via _init_worker. Slow (model load x2) but must
    stay real — no mocking the pool."""
    out = tmp_path / "ann_pool.csv"
    rc = ad.main(["--dataset-dir", str(FIXTURE), "--out", str(out),
                  "--workers", "2"])
    assert rc == 0
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 36
    assert {r["relpath"] for r in rows} == {j[0] for j in ad.list_jobs(FIXTURE, done=set())}
    # same detection-verified guarantee as the inline full-fixture run
    parsed = cc.load_annotations(out)
    assert len(cc.valid_rows(parsed)) >= 24
