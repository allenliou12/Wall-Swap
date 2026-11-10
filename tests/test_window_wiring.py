"""The tray side of the Settings window: Save goes through Settings.update, and the window never imports the app."""
import ast
import json
from pathlib import Path

import pytest

import wallpaper_changer as wc

WINDOW_FILE = Path(wc.__file__).with_name("settings_window.py")


def _imports_app(source: str) -> bool:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "wallpaper_changer" for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "wallpaper_changer":
            return True
    return False


def test_settings_window_never_imports_wallpaper_changer():
    # The checker itself catches both forms (a checker that always says "no" would pass anything)
    assert _imports_app("import wallpaper_changer")
    assert _imports_app("def f():\n    from wallpaper_changer import settings")
    assert not _imports_app("import customtkinter as ctk")
    assert not _imports_app(WINDOW_FILE.read_text(encoding="utf-8"))


@pytest.fixture
def tmp_settings(tmp_path, monkeypatch):
    s = wc.Settings(tmp_path / "settings.json")
    monkeypatch.setattr(wc, "settings", s)
    return s


@pytest.fixture
def shortcut_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(wc, "set_start_with_windows", lambda enabled: calls.append(enabled))
    return calls


@pytest.fixture
def app():
    return wc.WallSwapApp()  # no icon: notify only logs, refresh_menu does nothing


def _on_disk(s):
    return json.loads(s.path.read_text(encoding="utf-8"))


def test_save_writes_only_the_changed_setting(app, tmp_settings, shortcut_calls):
    before = tmp_settings.snapshot()
    patch = wc.settings_patch(before, {**before, "interval_minutes": 15})
    # A tray change to a different setting made while the window was open
    tmp_settings.update(lambda d: d["sources"].update(museum=False))
    expected = {**_on_disk(tmp_settings), "interval_minutes": 15}

    assert app._save_from_window(patch, None) is None
    assert _on_disk(tmp_settings) == expected
    assert shortcut_calls == []


def test_save_changes_the_shortcut_only_when_asked(app, tmp_settings, shortcut_calls):
    assert app._save_from_window({"set": [], "add_folders": [], "remove_folders": []}, True) is None
    assert shortcut_calls == [True]


def test_empty_patch_leaves_the_file_alone(app, tmp_settings, shortcut_calls):
    tmp_settings.path.write_text('{"interval_minutes": 45}', encoding="utf-8")
    raw = tmp_settings.path.read_bytes()
    assert app._save_from_window({"set": [], "add_folders": [], "remove_folders": []}, None) is None
    assert tmp_settings.path.read_bytes() == raw


def test_broken_file_refuses_save_and_leaves_the_shortcut(app, tmp_settings, shortcut_calls):
    tmp_settings.path.write_text("{ not json", encoding="utf-8")
    patch = wc.settings_patch(tmp_settings.snapshot(), {**tmp_settings.snapshot(), "interval_minutes": 15})

    error = app._save_from_window(patch, True)
    assert error and error == app._problem_message()
    assert tmp_settings.problem == "broken"
    assert tmp_settings.path.read_text(encoding="utf-8") == "{ not json"
    assert shortcut_calls == []


def test_shortcut_failure_still_keeps_the_saved_settings(app, tmp_settings, monkeypatch):
    def fail(enabled):
        raise OSError("access denied")

    monkeypatch.setattr(wc, "set_start_with_windows", fail)
    patch = wc.settings_patch(tmp_settings.snapshot(), {**tmp_settings.snapshot(), "interval_minutes": 120})

    assert app._save_from_window(patch, True)  # an error message for the banner
    assert _on_disk(tmp_settings)["interval_minutes"] == 120


def test_open_settings_only_queues_the_window(app):
    app.open_settings()
    assert app.ui_calls.get_nowait() == app._show_settings
    assert app.ui_calls.empty()
    assert app.settings_window is None
