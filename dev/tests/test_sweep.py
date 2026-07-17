import numpy as np
import pytest

import calibrate_thresholds as ct


def test_sweep_scalar_less_than_separable():
    pos = np.linspace(0.10, 0.20, 60).tolist()   # drowsy EARs (low)
    neg = np.linspace(0.28, 0.40, 80).tolist()   # alert EARs (high)
    r = ct.sweep_scalar(pos, neg, "<")
    assert 0.20 < r["threshold"] < 0.28
    assert r["f1"] == 1.0 and r["precision"] == 1.0 and r["recall"] == 1.0
    assert r["auc"] == 1.0


def test_sweep_scalar_greater_than_with_overlap():
    pos = np.linspace(0.60, 1.40, 100).tolist()  # yawns (high MAR)
    neg = np.linspace(0.00, 0.75, 100).tolist()  # overlap in 0.60-0.75
    r = ct.sweep_scalar(pos, neg, ">")
    assert 0.55 < r["threshold"] < 0.80
    assert 0.8 < r["f1"] < 1.0
    assert 0.9 < r["auc"] <= 1.0


def test_sweep_scalar_raises_on_empty_side():
    with pytest.raises(ValueError):
        ct.sweep_scalar([], [0.1, 0.2], "<")
    with pytest.raises(ValueError):
        ct.sweep_scalar([0.1], [], "<")


def test_sweep_pose_finds_separating_box():
    pos_yaw = np.linspace(30, 60, 50).tolist()    # heads turned away
    pos_pitch = np.linspace(-5, 5, 50).tolist()
    neg_yaw = np.linspace(-8, 8, 50).tolist()     # heads forward
    neg_pitch = np.linspace(-6, 6, 50).tolist()
    r = ct.sweep_pose(pos_yaw, pos_pitch, neg_yaw, neg_pitch)
    assert 8 < r["yaw_threshold"] < 30
    assert r["pitch_threshold"] > 6      # must not fire on negatives' pitch
    assert r["f1"] == 1.0


def test_sweep_pose_uses_or_predicate():
    # positives distracted ONLY by pitch — yaw is centred for both classes
    pos_yaw = np.linspace(-5, 5, 40).tolist()
    pos_pitch = np.linspace(25, 40, 40).tolist()
    neg_yaw = np.linspace(-5, 5, 40).tolist()
    neg_pitch = np.linspace(-8, 8, 40).tolist()
    r = ct.sweep_pose(pos_yaw, pos_pitch, neg_yaw, neg_pitch)
    assert 8 < r["pitch_threshold"] < 25
    assert r["f1"] == 1.0


def test_sweep_pose_picks_middle_of_tied_plateau():
    """Pin sweep_pose's tie-break rule (its own docstring: pick the middle of
    a tied max-F1 plateau, not its edge). Construction: positives constant at
    yaw=40/pitch=40, negatives constant at yaw=10/pitch=10 — separable via
    EITHER axis, which (with the fixed grid arange(5.0, 60.5, 0.5), 111
    points, index k -> value 5.0 + 0.5*k) produces a broad tied F1=1.0
    region. Verified by direct execution that the tied region is:
      - tied rows (yaw_t where some pitch_t reaches best F1): contiguous
        indices 10..110 (101 rows) -> middle index 10 + 101//2 = 60
        -> yaw_grid[60] = 35.0
      - within that row, tied cols (pitch_t reaching best F1): also
        contiguous indices 10..110 (101 cols) -> middle index 60
        -> pitch_grid[60] = 35.0
    i.e. the rule's middle-of-plateau selection lands on the same index (60)
    on both axes for this construction.
    """
    pos_yaw = [40.0] * 6
    pos_pitch = [40.0] * 6
    neg_yaw = [10.0] * 6
    neg_pitch = [10.0] * 6
    r = ct.sweep_pose(pos_yaw, pos_pitch, neg_yaw, neg_pitch)
    assert r["yaw_threshold"] == 35.0
    assert r["pitch_threshold"] == 35.0
    assert r["f1"] == 1.0 and r["precision"] == 1.0 and r["recall"] == 1.0


def test_load_flags(tmp_path):
    assert ct.load_flags(tmp_path / "absent.csv") == set()
    p = tmp_path / "flags.csv"
    p.write_text("relpath\ntrain/is_drowsy/a.jpg\ntest/no_yawn/b.jpg\n")
    assert ct.load_flags(p) == {"train/is_drowsy/a.jpg", "test/no_yawn/b.jpg"}
