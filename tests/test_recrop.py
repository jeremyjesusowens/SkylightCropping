"""Tests for recrop_image dry-run mode — image processing, no API calls."""
from pathlib import Path

from PIL import Image

from smart_crop import TARGET_RATIO, recrop_image


def _make_image(path: Path, width: int, height: int, color=(100, 150, 200)) -> Path:
    img = Image.new("RGB", (width, height), color=color)
    img.save(path)
    return path


class TestDryRun:
    def test_returns_dry_run_status(self, tmp_path):
        src = _make_image(tmp_path / "photo.jpg", 1920, 1080)
        out = str(tmp_path / "out.jpg")
        result = recrop_image(str(src), out, 50.0, 50.0, dry_run=True)
        assert result.status == "dry_run"

    def test_no_file_written_in_dry_run(self, tmp_path):
        src = _make_image(tmp_path / "photo.jpg", 1920, 1080)
        out = tmp_path / "out.jpg"
        recrop_image(str(src), str(out), 50.0, 50.0, dry_run=True)
        assert not out.exists()

    def test_result_has_correct_dimensions(self, tmp_path):
        src = _make_image(tmp_path / "photo.jpg", 2000, 1500)
        result = recrop_image(str(src), str(tmp_path / "out.jpg"), 50.0, 50.0, dry_run=True)
        assert result.width == 2000
        assert result.height == 1500

    def test_result_has_focal_point(self, tmp_path):
        src = _make_image(tmp_path / "photo.jpg", 1920, 1080)
        result = recrop_image(str(src), str(tmp_path / "out.jpg"), 30.0, 70.0, dry_run=True)
        assert result.focal == (30.0, 70.0)

    def test_result_has_box(self, tmp_path):
        src = _make_image(tmp_path / "photo.jpg", 1920, 1080)
        result = recrop_image(str(src), str(tmp_path / "out.jpg"), 50.0, 50.0, dry_run=True)
        assert result.box is not None
        l, u, r, b = result.box
        assert abs((r - l) / (b - u) - TARGET_RATIO) < 0.02

    def test_result_path_matches_input(self, tmp_path):
        src = _make_image(tmp_path / "photo.jpg", 1920, 1080)
        result = recrop_image(str(src), str(tmp_path / "out.jpg"), 50.0, 50.0, dry_run=True)
        assert result.path == str(src)

    def test_subject_preserved(self, tmp_path):
        src = _make_image(tmp_path / "photo.jpg", 1920, 1080)
        result = recrop_image(
            str(src), str(tmp_path / "out.jpg"), 50.0, 50.0,
            dry_run=True, subject="pelican",
        )
        assert result.subject == "pelican"


class TestActualCrop:
    def test_file_is_written(self, tmp_path):
        src = _make_image(tmp_path / "photo.jpg", 2000, 1500)
        out = tmp_path / "out.jpg"
        result = recrop_image(str(src), str(out), 50.0, 50.0)
        assert result.status == "cropped"
        assert out.exists()

    def test_output_is_16x9(self, tmp_path):
        src = _make_image(tmp_path / "photo.jpg", 2000, 1500)
        out = tmp_path / "out.jpg"
        recrop_image(str(src), str(out), 50.0, 50.0)
        with Image.open(out) as img:
            w, h = img.size
        assert abs(w / h - TARGET_RATIO) < 0.02

    def test_creates_output_directory(self, tmp_path):
        src = _make_image(tmp_path / "photo.jpg", 2000, 1500)
        out = tmp_path / "nested" / "dir" / "out.jpg"
        recrop_image(str(src), str(out), 50.0, 50.0)
        assert out.exists()

    def test_png_output(self, tmp_path):
        src = _make_image(tmp_path / "photo.png", 2000, 1500)
        out = tmp_path / "out.png"
        recrop_image(str(src), str(out), 50.0, 50.0)
        assert out.exists()
        with Image.open(out) as img:
            w, h = img.size
        assert abs(w / h - TARGET_RATIO) < 0.02
