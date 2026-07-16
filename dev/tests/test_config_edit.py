import pytest

import calib_common as cc

SAMPLE = """\
camera:
  index: 0  # keep me

# a top-level comment
thresholds:
  drowsy_frames: 6     # ~0.2s at 30fps
  ear_threshold: 0.99  # decoy in wrong section — must NOT change

detection:
  use_improved_dlib: true
  # Eye aspect ratio threshold
  ear_threshold: 0.27  # raised from 0.25
  mar_threshold: 0.6   # CHANGED: Lowered from 0.7
  yaw_threshold: 35    # INCREASED
  pitch_threshold: 25  # INCREASED
"""


def test_parse_reads_only_detection_block():
    th = cc.parse_detection_thresholds(SAMPLE)
    assert th == {"ear_threshold": 0.27, "mar_threshold": 0.6,
                  "yaw_threshold": 35.0, "pitch_threshold": 25.0}


def test_edit_changes_only_target_lines():
    out = cc.edit_detection_thresholds(
        SAMPLE, {"ear_threshold": 0.238, "yaw_threshold": 27.5}, "2026-07-16")
    assert "ear_threshold: 0.238  # calibrated 2026-07-16 (was 0.27)" in out
    assert "yaw_threshold: 27.5  # calibrated 2026-07-16 (was 35)" in out
    # untouched keys keep their lines verbatim
    assert "mar_threshold: 0.6   # CHANGED: Lowered from 0.7" in out
    # decoy in thresholds: section untouched
    assert "ear_threshold: 0.99  # decoy in wrong section — must NOT change" in out
    # everything outside changed lines is byte-identical
    changed = {"ear_threshold", "yaw_threshold"}
    for old_line, new_line in zip(SAMPLE.splitlines(), out.splitlines()):
        key = old_line.strip().split(":")[0]
        if key not in changed or "decoy" in old_line:
            assert old_line == new_line
    # round-trip: parse of edited text sees new values
    th = cc.parse_detection_thresholds(out)
    assert th["ear_threshold"] == 0.238 and th["yaw_threshold"] == 27.5


def test_edit_raises_on_missing_key_or_section():
    with pytest.raises(ValueError):
        cc.edit_detection_thresholds(SAMPLE, {"nope_threshold": 1.0}, "d")
    with pytest.raises(ValueError):
        cc.edit_detection_thresholds("camera:\n  index: 0\n",
                                     {"ear_threshold": 0.2}, "d")


def test_real_config_yaml_round_trip():
    text = cc.CONFIG_YAML.read_text(encoding="utf-8")
    th = cc.parse_detection_thresholds(text)
    assert set(th) == set(cc.DETECTION_KEYS)
    out = cc.edit_detection_thresholds(text, dict(th), "test")
    assert cc.parse_detection_thresholds(out) == th
    # exactly 4 lines differ
    diffs = [1 for a, b in zip(text.splitlines(), out.splitlines()) if a != b]
    assert len(diffs) == 4
