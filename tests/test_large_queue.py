"""Regression coverage for behaviour that only bites at large queue sizes
(hundreds to thousands of photos).

Covers:
  - the preview cache must not grow without bound as photos are viewed
  - thumbnail-ready results must be applied in capped batches per poll tick,
    not all at once
"""
import pytest
from PIL import Image


def _make_image(path, color=(100, 150, 200)):
    Image.new("RGB", (40, 30), color=color).save(path)
    return str(path)


@pytest.fixture
def app_module():
    pytest.importorskip("tkinter")
    try:
        import tkinter as tk
        root = tk.Tk()
        root.destroy()
    except Exception as e:
        pytest.skip(f"no usable display for Tk: {e}")
    import app as app_mod
    return app_mod


def _build_app(app_module, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "SETTINGS_FILE", tmp_path / "settings.json")
    app = app_module.App()
    app.withdraw()
    return app


class TestPreviewCacheBound:
    def test_cache_is_capped(self, app_module, tmp_path, monkeypatch):
        app = _build_app(app_module, tmp_path, monkeypatch)
        try:
            paths = []
            for i in range(app._PREVIEW_CACHE_MAX + 10):
                p = tmp_path / f"photo_{i}.jpg"
                _make_image(p)
                paths.append(str(p))
                app._get_preview_image(str(p))
            assert len(app._preview_cache) <= app._PREVIEW_CACHE_MAX
            # the most recently viewed photo must still be cached
            assert paths[-1] in app._preview_cache
            # the earliest ones must have been evicted
            assert paths[0] not in app._preview_cache
        finally:
            app.destroy()

    def test_reaccessing_an_entry_keeps_it_alive(self, app_module, tmp_path, monkeypatch):
        app = _build_app(app_module, tmp_path, monkeypatch)
        try:
            first = tmp_path / "first.jpg"
            _make_image(first)
            app._get_preview_image(str(first))

            for i in range(app._PREVIEW_CACHE_MAX):
                p = tmp_path / f"filler_{i}.jpg"
                _make_image(p)
                app._get_preview_image(str(p))
                if i == app._PREVIEW_CACHE_MAX // 2:
                    # touch "first" again partway through so it isn't the
                    # least-recently-used entry once the cache fills up
                    app._get_preview_image(str(first))

            assert str(first) in app._preview_cache
        finally:
            app.destroy()

    def test_clear_queue_clears_the_cache(self, app_module, tmp_path, monkeypatch):
        app = _build_app(app_module, tmp_path, monkeypatch)
        try:
            p = tmp_path / "photo.jpg"
            _make_image(p)
            app._add_item(str(p))
            app._get_preview_image(str(p))
            assert app._preview_cache
            app._clear_crop_files()
            assert not app._preview_cache
        finally:
            app.destroy()


class TestRateGalleryIncrementalRender:
    """The rate gallery used to destroy and rebuild every card on every
    render. On a large rated library that meant rebuilding thousands of
    widgets each time a single new rating came in. It should now reuse
    cards whose content hasn't changed and only rebuild the ones that did."""

    def _rated_result(self, path, score=80):
        from rate_photos import RatingResult
        return RatingResult(path=path, status="rated", score=score,
                            headline="A headline", feedback="Some feedback",
                            tags=["tag1"])

    def test_unchanged_cards_are_not_rebuilt(self, app_module, tmp_path, monkeypatch):
        app = _build_app(app_module, tmp_path, monkeypatch)
        try:
            paths = []
            for i in range(30):
                p = tmp_path / f"photo_{i}.jpg"
                _make_image(p)
                paths.append(str(p))
                app.rate_paths.append(str(p))
                app.rate_results[str(p)] = self._rated_result(str(p), score=50 + i)

            app._render_rate_gallery()
            cards_before = {p: id(c) for p, c in app._rate_cards.items()}
            assert len(cards_before) == len(paths)

            app._render_rate_gallery()
            cards_after = {p: id(c) for p, c in app._rate_cards.items()}

            assert cards_before == cards_after
        finally:
            app.destroy()

    def test_only_the_changed_card_is_rebuilt(self, app_module, tmp_path, monkeypatch):
        app = _build_app(app_module, tmp_path, monkeypatch)
        try:
            paths = []
            for i in range(10):
                p = tmp_path / f"photo_{i}.jpg"
                _make_image(p)
                paths.append(str(p))
                app.rate_paths.append(str(p))
                app.rate_results[str(p)] = self._rated_result(str(p), score=50 + i)

            app._render_rate_gallery()
            cards_before = {p: id(c) for p, c in app._rate_cards.items()}

            changed_path = paths[3]
            app.rate_results[changed_path] = self._rated_result(changed_path, score=99)
            app._render_rate_gallery()
            cards_after = {p: id(c) for p, c in app._rate_cards.items()}

            for p in paths:
                if p == changed_path:
                    assert cards_after[p] != cards_before[p]
                else:
                    assert cards_after[p] == cards_before[p]
        finally:
            app.destroy()

    def test_clearing_rate_files_tears_down_cards(self, app_module, tmp_path, monkeypatch):
        app = _build_app(app_module, tmp_path, monkeypatch)
        try:
            p = tmp_path / "photo.jpg"
            _make_image(p)
            app.rate_paths.append(str(p))
            app.rate_results[str(p)] = self._rated_result(str(p))
            app._render_rate_gallery()
            assert app._rate_cards

            app._clear_rate_files()
            assert not app._rate_cards
            assert not app._rate_card_keys
        finally:
            app.destroy()


class TestRateThumbCacheBound:
    def test_cache_is_capped(self, app_module, tmp_path, monkeypatch):
        app = _build_app(app_module, tmp_path, monkeypatch)
        try:
            last = None
            for i in range(app._RATE_THUMB_CACHE_MAX + 20):
                p = tmp_path / f"photo_{i}.jpg"
                _make_image(p)
                app._get_rate_thumb(str(p))
                last = str(p)
            assert len(app._rate_thumb_cache) <= app._RATE_THUMB_CACHE_MAX
            assert last in app._rate_thumb_cache
        finally:
            app.destroy()


class TestThumbnailApplyBatching:
    def test_only_a_capped_batch_is_applied_per_tick(self, app_module, tmp_path, monkeypatch):
        app = _build_app(app_module, tmp_path, monkeypatch)
        try:
            from app import make_thumbnail

            # The real background thumb worker would race with our manually
            # queued thumb_ready entries below, so stop _add_item from
            # kicking off real thumbnail jobs for this test.
            monkeypatch.setattr(app, "_request_thumb", lambda path: None)

            total = app._THUMB_APPLY_PER_TICK + 15
            paths = []
            for i in range(total):
                p = tmp_path / f"photo_{i}.jpg"
                _make_image(p)
                paths.append(str(p))
                app._add_item(str(p))
                app.thumb_ready.put((str(p), make_thumbnail(str(p))))

            monkeypatch.setattr(app, "after", lambda ms, fn: None)
            app._poll_queues_once()

            applied = sum(1 for p in paths if app.item_by_path[p]["thumb_img"] is not None)
            assert applied == app._THUMB_APPLY_PER_TICK

            # a second tick must pick up where the first left off
            app._poll_queues_once()
            applied = sum(1 for p in paths if app.item_by_path[p]["thumb_img"] is not None)
            assert applied == total
        finally:
            app.destroy()
