"""The Tk-thread queue: every Tk call reaches the main thread through post_to_ui and _drain_ui."""
from pathlib import Path

import pytest

import wallpaper_changer as wc


class FakeRoot:
    """Records what _drain_ui and ask_folder ask of the Tk root; no real window."""

    def __init__(self):
        self.scheduled = []
        self.topmost = []
        self.quit_called = False

    def after(self, ms, fn):
        self.scheduled.append((ms, fn))

    def attributes(self, name, value):
        assert name == "-topmost"
        self.topmost.append(value)

    def quit(self):
        self.quit_called = True


class FakeIcon:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


@pytest.fixture
def app():
    app = wc.WallSwapApp()
    app.root = FakeRoot()
    return app


def _queued(app):
    calls = []
    while not app.ui_calls.empty():
        calls.append(app.ui_calls.get_nowait())
    return calls


def test_drain_runs_queued_calls_in_order_and_reschedules(app):
    ran = []
    app.post_to_ui(lambda: ran.append(1))
    app.post_to_ui(lambda: ran.append(2))
    app._drain_ui()
    assert ran == [1, 2]
    assert app.ui_calls.empty()
    assert app.root.scheduled == [(wc.UI_POLL_MS, app._drain_ui)]


def test_drain_survives_a_raising_call_and_still_reschedules(app):
    ran = []

    def broken():
        raise RuntimeError("a bug in a UI call")

    app.post_to_ui(broken)
    app.post_to_ui(lambda: ran.append("after"))
    app._drain_ui()
    assert ran == ["after"]
    assert app.root.scheduled == [(wc.UI_POLL_MS, app._drain_ui)]


def test_drain_keeps_polling_after_quit_so_close_ui_still_runs(app):
    # quit_app can set running=False while a drain is already past its last pop; the next drain must still come
    app.running = False
    app._drain_ui()
    assert app.root.scheduled == [(wc.UI_POLL_MS, app._drain_ui)]


def test_quit_stops_running_queues_close_ui_and_stops_icon(app):
    app.icon = FakeIcon()
    app.quit_app()
    assert app.running is False
    assert app.icon.stopped
    assert _queued(app) == [app._close_ui]


def test_close_ui_destroys_window_and_quits_root(app):
    class Window:
        destroyed = False

        def destroy(self):
            self.destroyed = True

    window = app.settings_window = Window()
    app._close_ui()
    assert window.destroyed
    assert app.root.quit_called


def test_add_local_folder_only_queues_and_never_opens_a_dialog(app, monkeypatch):
    def no_dialog(**_):
        raise AssertionError("the tray thread must never open a Tk dialog")

    monkeypatch.setattr(wc.filedialog, "askdirectory", no_dialog)
    app.add_local_folder()
    assert _queued(app) == [app._add_folder_from_tray]


def test_repeated_add_folder_clicks_open_one_dialog(app, monkeypatch):
    dialogs = []
    monkeypatch.setattr(wc.filedialog, "askdirectory", lambda **_: dialogs.append(1) or "")
    for _ in range(4):
        app.add_local_folder()  # clicks while the first one is still pending
    app._drain_ui()
    assert len(dialogs) == 1


def test_add_folder_can_be_used_again_after_the_dialog_closes(app, monkeypatch):
    dialogs = []
    monkeypatch.setattr(wc.filedialog, "askdirectory", lambda **_: dialogs.append(1) or "")
    app.add_local_folder()
    app._drain_ui()
    app.add_local_folder()
    app._drain_ui()
    assert len(dialogs) == 2


def test_add_folder_can_be_used_again_after_the_dialog_fails(app, monkeypatch):
    def broken(**_):
        raise RuntimeError("dialog crashed")

    monkeypatch.setattr(wc.filedialog, "askdirectory", broken)
    app.add_local_folder()
    app._drain_ui()
    assert _queued(app) == []
    app.add_local_folder()
    assert _queued(app) == [app._add_folder_from_tray]


def test_add_folder_queued_before_quit_opens_no_dialog_but_close_ui_runs(app, monkeypatch):
    dialogs = []
    monkeypatch.setattr(wc.filedialog, "askdirectory", lambda **_: dialogs.append(1) or "")
    app.icon = FakeIcon()
    app.add_local_folder()
    app.quit_app()
    app._drain_ui()
    assert dialogs == []
    assert app.root.quit_called
    assert app.root.scheduled == [(wc.UI_POLL_MS, app._drain_ui)]


def test_ask_folder_returns_the_chosen_folder_and_frees_the_guard(app, monkeypatch):
    chosen = str(Path.home() / "Pictures" / "Art")
    monkeypatch.setattr(wc.filedialog, "askdirectory", lambda **_: chosen.replace("\\", "/"))
    assert app.ask_folder() == chosen
    assert app.folder_dialog_open is False


def test_ask_folder_cancel_returns_none(app, monkeypatch):
    monkeypatch.setattr(wc.filedialog, "askdirectory", lambda **_: "")
    assert app.ask_folder() is None
    assert app.folder_dialog_open is False


def test_ask_folder_refuses_a_second_dialog_while_one_is_open(app, monkeypatch):
    opened = []
    monkeypatch.setattr(wc.filedialog, "askdirectory", lambda **_: opened.append(1) or "C:/x")
    app.folder_dialog_open = True
    assert app.ask_folder() is None
    assert opened == []
