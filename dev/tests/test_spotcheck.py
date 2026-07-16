from pathlib import Path

import spotcheck_labels as sc

FIXTURE = Path(__file__).parent / "fixtures" / "mini_dataset"


def test_build_html_contains_sections_images_and_export():
    html = sc.build_html(FIXTURE, per_class=2)
    for cls in ("is_drowsy", "not_drowsy", "is_yawning", "no_yawn",
                "is_distracted", "safe_driving"):
        assert f"<h2>{cls}" in html
    # 6 classes x (train 2 + test 2) = 24 images, embedded
    assert html.count("<img") == 24
    assert html.count("data:image/jpeg;base64,") == 24
    assert 'data-relpath="train/is_drowsy/' in html
    assert "function exportFlags()" in html
    assert "spotcheck_flags.csv" in html


def test_build_html_deterministic():
    assert sc.build_html(FIXTURE, per_class=2) == sc.build_html(FIXTURE, per_class=2)


def test_main_writes_file(tmp_path):
    out = tmp_path / "spotcheck.html"
    rc = sc.main(["--dataset-dir", str(FIXTURE), "--out", str(out),
                  "--per-class", "1"])
    assert rc == 0
    assert out.exists() and out.stat().st_size > 1000
