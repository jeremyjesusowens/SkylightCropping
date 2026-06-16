import pytest


@pytest.fixture
def app_module():
    """The `app` module, skipping the test if no usable Tk display exists."""
    pytest.importorskip("tkinter")
    try:
        import tkinter as tk
        root = tk.Tk()
        root.destroy()
    except Exception as e:
        pytest.skip(f"no usable display for Tk: {e}")
    import app as app_mod
    return app_mod


@pytest.fixture
def make_app(app_module, tmp_path, monkeypatch):
    """Factory for a real App() instance with settings redirected to tmp_path."""
    created = []

    def _make():
        monkeypatch.setattr(app_module, "SETTINGS_FILE", tmp_path / "settings.json")
        app = app_module.App()
        app.withdraw()
        created.append(app)
        return app

    yield _make
    for app in created:
        app.destroy()
