"""Tests for collect_images — file system operations, no API calls."""
from pathlib import Path

from smart_crop import SUPPORTED_EXTS, collect_images


def _touch(path: Path, suffix: str) -> Path:
    f = path / f"photo{suffix}"
    f.write_bytes(b"placeholder")
    return f


class TestSingleFile:
    def test_supported_file_is_collected(self, tmp_path):
        f = _touch(tmp_path, ".jpg")
        result = collect_images([str(f)])
        assert result == [f]

    def test_png_collected(self, tmp_path):
        f = _touch(tmp_path, ".png")
        assert collect_images([str(f)]) == [f]

    def test_webp_collected(self, tmp_path):
        f = _touch(tmp_path, ".webp")
        assert collect_images([str(f)]) == [f]

    def test_unsupported_extension_skipped(self, tmp_path):
        f = _touch(tmp_path, ".pdf")
        warnings = []
        result = collect_images([str(f)], log=warnings.append)
        assert result == []
        assert any("unsupported" in w for w in warnings)

    def test_missing_path_skipped(self):
        warnings = []
        result = collect_images(["/no/such/file.jpg"], log=warnings.append)
        assert result == []
        assert any("not found" in w for w in warnings)


class TestDirectory:
    def test_finds_images_in_dir(self, tmp_path):
        _touch(tmp_path, ".jpg")
        _touch(tmp_path, ".png")
        result = collect_images([str(tmp_path)])
        assert len(result) == 2

    def test_ignores_non_images_in_dir(self, tmp_path):
        _touch(tmp_path, ".jpg")
        _touch(tmp_path, ".txt")
        result = collect_images([str(tmp_path)])
        assert len(result) == 1

    def test_uppercase_extension_found(self, tmp_path):
        f = tmp_path / "PHOTO.JPG"
        f.write_bytes(b"placeholder")
        result = collect_images([str(tmp_path)])
        assert f in result

    def test_empty_directory(self, tmp_path):
        result = collect_images([str(tmp_path)])
        assert result == []


class TestDeduplication:
    def test_same_file_listed_twice(self, tmp_path):
        f = _touch(tmp_path, ".jpg")
        result = collect_images([str(f), str(f)])
        assert len(result) == 1

    def test_file_and_parent_dir(self, tmp_path):
        f = _touch(tmp_path, ".jpg")
        result = collect_images([str(f), str(tmp_path)])
        assert len(result) == 1

    def test_results_are_sorted(self, tmp_path):
        for name in ("c.jpg", "a.jpg", "b.png"):
            (tmp_path / name).write_bytes(b"x")
        result = collect_images([str(tmp_path)])
        assert result == sorted(result)


class TestMultipleInputs:
    def test_mix_of_files_and_dirs(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        f1 = _touch(tmp_path, ".jpg")
        f2 = _touch(sub, ".png")
        result = collect_images([str(f1), str(sub)])
        assert set(result) == {f1, f2}

    def test_all_supported_extensions(self, tmp_path):
        for ext in SUPPORTED_EXTS:
            (tmp_path / f"photo{ext}").write_bytes(b"x")
        result = collect_images([str(tmp_path)])
        assert len(result) == len(SUPPORTED_EXTS)
