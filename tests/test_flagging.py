"""Tests for flagging bad detections and the crop/send buttons' busy state."""
import json

from PIL import Image

from app import record_flag
from smart_crop import CropResult


def _make_image(path, width=400, height=300, color=(100, 150, 200)):
    Image.new("RGB", (width, height), color=color).save(path)
    return str(path)


def _result(**overrides):
    defaults = dict(
        path="/photos/heron.jpg", status="cropped", width=1000, height=800,
        focal=(40.0, 55.0), box=(0, 0, 1000, 562), subject="great blue heron",
        confidence=72, focal_box=(10.0, 5.0, 70.0, 90.0), model="claude-opus-4-7",
    )
    defaults.update(overrides)
    return CropResult(**defaults)


class TestRecordFlag:
    def test_appends_one_json_line(self, tmp_path):
        flag_file = tmp_path / "flagged.jsonl"
        record_flag(_result(), "wrong subject", flag_file=flag_file)
        lines = flag_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["file"] == "heron.jpg"
        assert entry["subject"] == "great blue heron"
        assert entry["model"] == "claude-opus-4-7"
        assert entry["note"] == "wrong subject"
        assert entry["focal"] == [40.0, 55.0]

    def test_appends_multiple_flags_without_clobbering(self, tmp_path):
        flag_file = tmp_path / "flagged.jsonl"
        record_flag(_result(path="/photos/a.jpg"), "note a", flag_file=flag_file)
        record_flag(_result(path="/photos/b.jpg"), "note b", flag_file=flag_file)
        lines = flag_file.read_text(encoding="utf-8").splitlines()
        assert [json.loads(line)["file"] for line in lines] == ["a.jpg", "b.jpg"]

    def test_creates_parent_directory(self, tmp_path):
        flag_file = tmp_path / "nested" / "flagged.jsonl"
        record_flag(_result(), flag_file=flag_file)
        assert flag_file.exists()

    def test_blank_note_is_allowed(self, tmp_path):
        flag_file = tmp_path / "flagged.jsonl"
        record_flag(_result(), flag_file=flag_file)
        entry = json.loads(flag_file.read_text(encoding="utf-8").splitlines()[0])
        assert entry["note"] == ""


class TestFlagCurrentUI:
    def test_disabled_with_no_result(self, make_app):
        app = make_app()
        app._render_preview(None)
        assert app.flag_btn.cget("state") == "disabled"

    def test_enabled_once_a_result_with_a_box_exists(self, make_app, tmp_path):
        app = make_app()
        path = str(tmp_path / "photo.jpg")
        _make_image(path)
        app._add_item(path)
        item = app.item_by_path[path]
        item["result"] = _result(path=path)
        app._select_item(path)
        assert app.flag_btn.cget("state") == "normal"

    def test_writes_a_flag_record_and_logs_it(self, make_app, tmp_path, monkeypatch):
        app = make_app()
        flag_file = tmp_path / "flagged.jsonl"
        monkeypatch.setattr("app.FLAGGED_FILE", flag_file)
        monkeypatch.setattr("app.simpledialog.askstring", lambda *a, **k: "bad target")

        path = str(tmp_path / "photo.jpg")
        _make_image(path)
        app._add_item(path)
        item = app.item_by_path[path]
        item["result"] = _result(path=path)
        app.current_path = path

        app._flag_current()

        assert flag_file.exists()
        entry = json.loads(flag_file.read_text(encoding="utf-8").splitlines()[0])
        assert entry["note"] == "bad target"
        logged = app.log_queue.get_nowait()
        assert "Flagged" in logged and "bad target" in logged

    def test_cancelling_the_dialog_does_not_write_anything(self, make_app, tmp_path, monkeypatch):
        app = make_app()
        flag_file = tmp_path / "flagged.jsonl"
        monkeypatch.setattr("app.FLAGGED_FILE", flag_file)
        monkeypatch.setattr("app.simpledialog.askstring", lambda *a, **k: None)

        path = str(tmp_path / "photo.jpg")
        _make_image(path)
        app._add_item(path)
        item = app.item_by_path[path]
        item["result"] = _result(path=path)
        app.current_path = path

        app._flag_current()

        assert not flag_file.exists()

    def test_no_op_without_a_result(self, make_app, tmp_path, monkeypatch):
        app = make_app()
        called = []
        monkeypatch.setattr("app.simpledialog.askstring", lambda *a, **k: called.append(1))
        app.current_path = None
        app._flag_current()
        assert called == []


class TestBusyButtonAppearance:
    def test_crop_button_keeps_accent_text_color_while_disabled(self, make_app):
        app = make_app()
        assert app.crop_btn.cget("text_color_disabled") == app.crop_btn.cget("text_color")

    def test_set_busy_relabels_buttons(self, make_app):
        app = make_app()
        app._set_busy(True, "Cropping…")
        assert app.crop_btn.cget("text") == "Cropping…"
        assert app.send_btn.cget("text") == "Sending…"
        assert app.crop_btn.cget("state") == "disabled"

        app._set_busy(False)
        assert app.crop_btn.cget("text") == "Crop Photos"
        assert app.send_btn.cget("text") == "Send Photos"
        assert app.crop_btn.cget("state") == "normal"
