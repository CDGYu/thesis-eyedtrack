import numpy as np

import calib_common as cc

CFG = {"performance": {"resize_factor": 0.75},
       "clahe": {"enabled": True, "clip_limit": 2.5,
                 "base_tile_grid_size": [8, 8]}}


def _gradient_bgr(h=480, w=640):
    """Deterministic synthetic color image (no RNG)."""
    y = np.linspace(0, 255, h, dtype=np.uint8)[:, None]
    x = np.linspace(0, 255, w, dtype=np.uint8)[None, :]
    img = np.stack([np.broadcast_to(y, (h, w)),
                    np.broadcast_to(x, (h, w)),
                    np.broadcast_to((y // 2 + x // 2).astype(np.uint8), (h, w))],
                   axis=2)
    return np.ascontiguousarray(img)


def test_preprocess_resizes_by_factor():
    out = cc.preprocess_bgr(_gradient_bgr(), CFG)
    assert out.shape == (360, 480, 3)  # 480*0.75, 640*0.75


def test_preprocess_noop_when_disabled():
    cfg = {"performance": {"resize_factor": 1.0}, "clahe": {"enabled": False}}
    img = _gradient_bgr()
    out = cc.preprocess_bgr(img, cfg)
    assert out.shape == img.shape
    assert np.array_equal(out, img)


def test_preprocess_clahe_changes_pixels_but_not_shape():
    cfg = {"performance": {"resize_factor": 1.0},
           "clahe": {"enabled": True, "clip_limit": 2.5,
                     "base_tile_grid_size": [8, 8]}}
    img = _gradient_bgr()
    out = cc.preprocess_bgr(img, cfg)
    assert out.shape == img.shape
    assert not np.array_equal(out, img)


def test_is_grayscale_like():
    gray3 = np.full((10, 10, 3), 100, dtype=np.uint8)
    assert cc.is_grayscale_like(gray3) is True
    near_gray = gray3.copy()
    near_gray[:, :, 2] = 106  # spread 6 <= 8
    assert cc.is_grayscale_like(near_gray) is True
    color = gray3.copy()
    color[:, :, 0] = 200
    assert cc.is_grayscale_like(color) is False


def test_preprocess_empty_config_defaults_clahe_on():
    """Empty config must still apply CLAHE (server default: enabled=True)."""
    img = _gradient_bgr()
    out = cc.preprocess_bgr(img, {})
    assert out.shape == img.shape  # no performance section -> resize_factor 1.0 -> no resize
    assert not np.array_equal(out, img)  # CLAHE applied by default


def test_is_grayscale_like_2d_array():
    frame = np.full((10, 10), 100, dtype=np.uint8)
    assert cc.is_grayscale_like(frame) is True
