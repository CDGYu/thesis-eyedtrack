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


def test_build_html_escapes_special_chars_in_relpath(tmp_path):
    """Test that relpath with &, ', etc. are properly escaped in HTML attributes."""
    # Create a minimal dataset with an image filename containing & and '
    dataset_dir = tmp_path / "escape_test_dataset"
    train_dir = dataset_dir / "train" / "is_drowsy"
    train_dir.mkdir(parents=True)

    # Use a filename with & and ' (safe on Windows)
    test_filename = "test_&_apostrophe'_image.jpg"
    test_image = train_dir / test_filename

    # Copy bytes from an existing fixture image
    fixture_image = FIXTURE / "train" / "is_drowsy" / "0_001_glasses_slowBlinkWithNodding_1025_drowsy.jpg"
    test_image.write_bytes(fixture_image.read_bytes())

    # Build HTML
    html = sc.build_html(dataset_dir, per_class=1)

    # The relpath in the HTML should be: train/is_drowsy/test_&_apostrophe'_image.jpg
    relpath = f"train/is_drowsy/{test_filename}"

    # Assert that the unescaped relpath does NOT appear in data-relpath attribute
    assert f'data-relpath="{relpath}"' not in html, \
        "Unescaped special chars found in data-relpath attribute"

    # Assert that escaped versions ARE present
    # & should become &amp;
    # ' should become &#x27;
    escaped_relpath = relpath.replace("&", "&amp;").replace("'", "&#x27;")
    assert f'data-relpath="{escaped_relpath}"' in html, \
        f"Escaped relpath not found. Looking for: data-relpath=\"{escaped_relpath}\""

    # Also verify the figcaption contains escaped content in the attribute context
    # The figcaption text itself can have entities, but we're checking the attribute
    assert html.count("<figcaption>") >= 1
