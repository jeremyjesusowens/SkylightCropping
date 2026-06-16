"""Tests for queue-row thumbnail generation and rendering.

Covers the regression where thumbnails silently stopped appearing: a single
bad/corrupt image could raise inside the Tk polling loop and permanently stop
*all* future UI updates (thumbnails, progress, results) since the recursive
`after()` reschedule was never reached.
"""
import pytest
from PIL import Image

from app import THUMB_SIZE, make_thumbnail


def _make_image(path, width=400, height=300, color=(100, 150, 200), exif=None):
    img = Image.new("RGB", (width, height), color=color)
    img.save(path, exif=exif) if exif else img.save(path)
    return str(path)


class TestMakeThumbnail:
    def test_returns_requested_size(self, tmp_path):
        path = _make_image(tmp_path / "photo.jpg")
        thumb = make_thumbnail(path)
        assert thumb.size == THUMB_SIZE

    def test_returns_rgb_with_real_pixel_data(self, tmp_path):
        path = _make_image(tmp_path / "photo.jpg", color=(200, 30, 30))
        thumb = make_thumbnail(path)
        assert thumb.mode == "RGB"
        # not a blank/black placeholder — it should carry the source color
        assert thumb.getpixel((thumb.width // 2, thumb.height // 2)) != (0, 0, 0)

    def test_custom_size(self, tmp_path):
        path = _make_image(tmp_path / "photo.jpg")
        thumb = make_thumbnail(path, size=(100, 50))
        assert thumb.size == (100, 50)

    def test_survives_exif_orientation(self, tmp_path):
        piexif = pytest.importorskip("piexif")
        exif_bytes = piexif.dump({"0th": {piexif.ImageIFD.Orientation: 6}})
        path = _make_image(tmp_path / "rotated.jpg", width=600, height=400, exif=exif_bytes)
        thumb = make_thumbnail(path)
        assert thumb.size == THUMB_SIZE

    def test_detached_from_file_handle(self, tmp_path):
        """The returned image must be fully loaded — usable after the file closes."""
        path = _make_image(tmp_path / "photo.jpg")
        thumb = make_thumbnail(path)
        # If pixel data weren't fully decoded/copied, this would error or
        # return garbage once the source file's handle is gone.
        thumb.load()
        assert thumb.getpixel((0, 0)) is not None

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(Exception):
            make_thumbnail(str(tmp_path / "does_not_exist.jpg"))


class TestPollQueuesResilience:
    """Regression coverage for the poll loop that stopped rescheduling itself."""

    def test_bad_thumbnail_does_not_break_polling(self, make_app, tmp_path, monkeypatch):
        app = make_app()
        path = str(tmp_path / "photo.jpg")
        _make_image(path)
        app._add_item(path)

        # Simulate a thumbnail payload that fails to convert to a CTkImage
        # (e.g. a corrupt/unsupported image), the way a real-world bad
        # file would surface in the queue.
        app.thumb_ready.put((path, object()))

        calls = []
        monkeypatch.setattr(app, "after", lambda ms, fn: calls.append(fn))

        app._poll_queues()  # must not raise despite the bad payload

        assert calls and calls[0] == app._poll_queues

    def test_good_thumbnail_still_renders_after_a_bad_one(self, make_app, tmp_path, monkeypatch):
        app = make_app()
        bad_path = str(tmp_path / "bad.jpg")
        good_path = str(tmp_path / "good.jpg")
        _make_image(good_path)
        app._add_item(bad_path)
        app._add_item(good_path)

        app.thumb_ready.put((bad_path, object()))
        app.thumb_ready.put((good_path, make_thumbnail(good_path)))

        monkeypatch.setattr(app, "after", lambda ms, fn: None)
        app._poll_queues()

        good_item = app.item_by_path[good_path]
        assert good_item["thumb_img"] is not None

    def test_poll_queues_reschedules_even_if_inner_step_raises(self, make_app, monkeypatch):
        app = make_app()
        monkeypatch.setattr(app, "_poll_queues_once", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        calls = []
        monkeypatch.setattr(app, "after", lambda ms, fn: calls.append(fn))

        with pytest.raises(RuntimeError):
            app._poll_queues()

        # Despite the exception, the recursive reschedule must still happen —
        # this is what previously let thumbnails (and everything else) stop
        # updating forever after a single failure.
        assert calls and calls[0] == app._poll_queues
