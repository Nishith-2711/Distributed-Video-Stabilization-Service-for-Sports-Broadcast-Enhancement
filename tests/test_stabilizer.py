"""
Unit + smoke tests for api/stabilizer.py (TranslationStabilizer).

These tests avoid depending on real cricket footage — they generate
synthetic frames/video in-memory so they run fast and deterministically
in CI (GitHub Actions), with no external fixtures required.
"""
import os
import sys
import numpy as np
import cv2
import pytest

# Make `api` importable when tests run from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api.stabilizer import TranslationStabilizer


@pytest.fixture
def stabilizer():
    return TranslationStabilizer(smoothing_window=30, max_features=200)


class TestEstimateTranslation:
    def test_zero_displacement(self, stabilizer):
        pts = np.random.rand(20, 1, 2).astype(np.float32) * 100
        dx, dy = stabilizer.estimate_translation(pts, pts)
        assert dx == 0
        assert dy == 0

    def test_known_shift(self, stabilizer):
        src = np.random.rand(20, 1, 2).astype(np.float32) * 100
        shift = np.array([5.0, -3.0], dtype=np.float32)
        dst = src + shift
        dx, dy = stabilizer.estimate_translation(src, dst)
        assert dx == pytest.approx(5.0, abs=1e-3)
        assert dy == pytest.approx(-3.0, abs=1e-3)

    def test_none_input_returns_zero(self, stabilizer):
        dx, dy = stabilizer.estimate_translation(None, None)
        assert (dx, dy) == (0, 0)

    def test_robust_to_outliers(self, stabilizer):
        # median should ignore a handful of outlier matches (e.g. a moving
        # batsman in the foreground) and still recover the true camera shift
        src = np.random.rand(50, 1, 2).astype(np.float32) * 100
        dst = src + np.array([2.0, 2.0], dtype=np.float32)
        dst[:5] += 200  # outliers
        dx, dy = stabilizer.estimate_translation(src, dst)
        assert dx == pytest.approx(2.0, abs=0.5)
        assert dy == pytest.approx(2.0, abs=0.5)


class TestSmoothTrajectory:
    def test_preserves_shape(self, stabilizer):
        trajectory = np.cumsum(np.random.randn(100, 2), axis=0)
        smoothed = stabilizer.smooth_trajectory(trajectory)
        assert smoothed.shape == trajectory.shape

    def test_reduces_high_frequency_noise(self, stabilizer):
        t = np.linspace(0, 10, 200)
        clean = np.stack([t, t], axis=1)
        noisy = clean + np.random.randn(200, 2) * 5
        smoothed = stabilizer.smooth_trajectory(noisy)
        # smoothing should move the signal closer to the clean trend
        assert np.abs(smoothed - clean).mean() < np.abs(noisy - clean).mean()


class TestStabilizeIntegration:
    """Smoke test: run the full pipeline on a tiny synthetic clip."""

    @staticmethod
    def _make_synthetic_video(path, n_frames=15, size=(160, 120), shift_px=3):
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(path, fourcc, 15, size)
        rng = np.random.default_rng(42)
        base = rng.integers(0, 255, (size[1] + 40, size[0] + 40, 3), dtype=np.uint8)
        for i in range(n_frames):
            ox, oy = (i * shift_px) % 20, (i * shift_px) % 20
            frame = base[oy:oy + size[1], ox:ox + size[0]]
            writer.write(frame)
        writer.release()

    def test_stabilize_produces_valid_output(self, stabilizer, tmp_path):
        input_path = str(tmp_path / "input.mp4")
        output_path = str(tmp_path / "output.mp4")
        self._make_synthetic_video(input_path)

        result_path = stabilizer.stabilize(input_path, output_path)

        assert os.path.exists(result_path)
        cap = cv2.VideoCapture(result_path)
        assert cap.get(cv2.CAP_PROP_FRAME_WIDTH) == 160
        assert cap.get(cv2.CAP_PROP_FRAME_HEIGHT) == 120
        assert cap.get(cv2.CAP_PROP_FRAME_COUNT) >= 1
        cap.release()

    def test_missing_file_raises(self, stabilizer, tmp_path):
        with pytest.raises(FileNotFoundError):
            stabilizer.stabilize(str(tmp_path / "nope.mp4"), str(tmp_path / "out.mp4"))