"""Tests for compute_crop_box — pure math, no API calls needed."""
import pytest

from smart_crop import TARGET_RATIO, compute_crop_box


def _aspect(box):
    l, u, r, b = box
    return (r - l) / (b - u)


class TestWiderThan16x9:
    """Images wider than 16:9 — crop width is constrained, height is full."""

    def test_center_focal_point(self):
        box = compute_crop_box(2000, 1000, 50, 50)
        l, u, r, b = box
        assert u == 0 and b == 1000
        assert abs(_aspect(box) - TARGET_RATIO) < 0.01

    def test_result_stays_in_bounds(self):
        box = compute_crop_box(3840, 1080, 50, 50)
        l, u, r, b = box
        assert l >= 0 and r <= 3840

    def test_focal_at_left_edge(self):
        box = compute_crop_box(2000, 1000, 0, 50)
        l, u, r, b = box
        assert l == 0
        assert r <= 2000

    def test_focal_at_right_edge(self):
        box = compute_crop_box(2000, 1000, 100, 50)
        l, u, r, b = box
        assert r == 2000
        assert l >= 0


class TestTallerThan16x9:
    """Images taller than 16:9 (portrait, square) — crop height constrained, width is full."""

    def test_square_center_focal(self):
        box = compute_crop_box(1000, 1000, 50, 50)
        l, u, r, b = box
        assert l == 0 and r == 1000
        assert abs(_aspect(box) - TARGET_RATIO) < 0.01

    def test_portrait_center_focal(self):
        box = compute_crop_box(1080, 1920, 50, 50)
        l, u, r, b = box
        assert l == 0 and r == 1080
        assert abs(_aspect(box) - TARGET_RATIO) < 0.01

    def test_result_stays_in_bounds(self):
        box = compute_crop_box(1000, 2000, 50, 50)
        l, u, r, b = box
        assert u >= 0 and b <= 2000

    def test_focal_at_top_edge(self):
        box = compute_crop_box(1000, 2000, 50, 0)
        l, u, r, b = box
        assert u == 0
        assert b <= 2000

    def test_focal_at_bottom_edge(self):
        box = compute_crop_box(1000, 2000, 50, 100)
        l, u, r, b = box
        assert b == 2000
        assert u >= 0


class TestExact16x9:
    """An exactly 16:9 image should return itself."""

    def test_1080p(self):
        box = compute_crop_box(1920, 1080, 50, 50)
        assert box == (0, 0, 1920, 1080)

    def test_720p(self):
        box = compute_crop_box(1280, 720, 50, 50)
        assert box == (0, 0, 1280, 720)


class TestOutputAspectRatio:
    """The output box must always be 16:9 (within rounding)."""

    @pytest.mark.parametrize("w,h,fx,fy", [
        (4000, 3000, 25, 75),
        (800, 600, 10, 10),
        (3000, 4000, 90, 20),
        (1920, 1080, 50, 50),
        (100, 100, 0, 0),
        (100, 100, 100, 100),
    ])
    def test_aspect_ratio(self, w, h, fx, fy):
        box = compute_crop_box(w, h, fx, fy)
        l, u, r, b = box
        crop_w = r - l
        crop_h = b - u
        assert crop_w > 0 and crop_h > 0
        assert abs(crop_w / crop_h - TARGET_RATIO) < 0.02

    @pytest.mark.parametrize("w,h,fx,fy", [
        (4000, 3000, 25, 75),
        (800, 600, 10, 10),
        (3000, 4000, 90, 20),
    ])
    def test_box_within_image(self, w, h, fx, fy):
        l, u, r, b = compute_crop_box(w, h, fx, fy)
        assert l >= 0 and u >= 0
        assert r <= w and b <= h
