"""INV-14: no wallpaper change while a fullscreen app is in front (HZ-1 regression).

user32 is faked so the check runs on any OS; whether the real Windows calls behave is the Windows check's job.
"""
import types

import pytest

import wallpaper_changer as wc

SCREEN = (2560, 1440)
PRIMARY_MONITOR = (0, 0, *SCREEN)
SECONDARY_MONITOR = (2560, 0, 5120, 1440)


def fake_user32(class_name, rect, hwnd=1, zoomed=0, monitor=PRIMARY_MONITOR, monitor_info_ok=True,
                style=0x00C00000):
    def get_class_name(_hwnd, buf, _n):
        buf.value = class_name

    def get_window_rect(_hwnd, ref):
        r = ref._obj
        r.left, r.top, r.right, r.bottom = rect

    def get_window_long(_hwnd, index):
        assert index == -16
        return style

    def monitor_from_window(_hwnd, flags):
        assert flags == 2
        return 7

    def get_monitor_info(handle, ref):
        assert handle == 7
        info = ref._obj
        assert info.cbSize == wc.ctypes.sizeof(info)
        if not monitor_info_ok:
            return 0
        r = info.rcMonitor
        r.left, r.top, r.right, r.bottom = monitor
        return 1

    return types.SimpleNamespace(
        GetForegroundWindow=lambda: hwnd,
        GetClassNameW=get_class_name,
        GetWindowRect=get_window_rect,
        IsZoomed=lambda _hwnd: zoomed,
        GetWindowLongW=get_window_long,
        MonitorFromWindow=monitor_from_window,
        GetMonitorInfoW=get_monitor_info,
        GetSystemMetrics=lambda i: SCREEN[i],
    )


@pytest.mark.parametrize("class_name, rect, hwnd, zoomed, monitor, monitor_info_ok, expected", [
    # A game covers the primary monitor.
    pytest.param("UnrealWindow", PRIMARY_MONITOR, 1, 0, PRIMARY_MONITOR, True, True,
                 id="primary_monitor_game"),
    # A game covers the secondary monitor, away from the primary monitor's origin.
    pytest.param("UnrealWindow", SECONDARY_MONITOR, 1, 0, SECONDARY_MONITOR, True, True,
                 id="secondary_monitor_game"),
    # Maximized Explorer spills past the edges with an auto-hide taskbar; it is not a game.
    pytest.param("CabinetWClass", (-8, -8, 2568, 1448), 1, 1, PRIMARY_MONITOR, True, False,
                 id="maximized_explorer"),
    # An ordinary window does not cover its monitor.
    pytest.param("Notepad", (100, 100, 1200, 900), 1, 0, PRIMARY_MONITOR, True, False,
                 id="ordinary_window"),
    # The focused desktop covers the screen but must not block wallpaper changes.
    pytest.param("Progman", PRIMARY_MONITOR, 1, 0, PRIMARY_MONITOR, True, False,
                 id="desktop_progman"),
    # The alternate desktop class is excluded too.
    pytest.param("WorkerW", PRIMARY_MONITOR, 1, 0, PRIMARY_MONITOR, True, False,
                 id="desktop_workerw"),
    # No foreground window means there is no game in front.
    pytest.param("UnrealWindow", PRIMARY_MONITOR, 0, 0, PRIMARY_MONITOR, True, False,
                 id="no_foreground_window"),
    # Covering the primary monitor's area is not enough for a window on the secondary monitor.
    pytest.param("UnrealWindow", PRIMARY_MONITOR, 1, 0, SECONDARY_MONITOR, True, False,
                 id="wrong_monitor_area"),
    # A failed monitor lookup must allow wallpaper changes.
    pytest.param("UnrealWindow", PRIMARY_MONITOR, 1, 0, PRIMARY_MONITOR, False, False,
                 id="monitor_info_failure"),
])
def test_fullscreen_detection(monkeypatch, class_name, rect, hwnd, zoomed, monitor, monitor_info_ok, expected):
    monkeypatch.setattr(wc.ctypes, "windll",
                        types.SimpleNamespace(user32=fake_user32(
                            class_name, rect, hwnd, zoomed, monitor, monitor_info_ok)), raising=False)
    assert wc.is_fullscreen_app_running() is expected


@pytest.mark.parametrize("style", [
    0,           # A borderless window has no caption bits.
    0x00800000,  # A border alone is not a full caption.
    0x00400000,  # A dialog frame alone is not a full caption.
])
def test_maximized_borderless_fullscreen(monkeypatch, style) -> None:
    # Maximizing without a full caption can be how an app enters fullscreen.
    monkeypatch.setattr(wc.ctypes, "windll",
                        types.SimpleNamespace(user32=fake_user32(
                            "UnrealWindow", PRIMARY_MONITOR, zoomed=1, style=style)), raising=False)
    assert wc.is_fullscreen_app_running() is True


@pytest.mark.parametrize("window, monitor", [
    # Matching edges cover the whole monitor.
    (PRIMARY_MONITOR, PRIMARY_MONITOR),
    # Extending past every edge still covers the monitor.
    ((-8, -8, 2568, 1448), PRIMARY_MONITOR),
    # A monitor left of and above the primary monitor has negative coordinates.
    ((-2560, -1440, 0, 0), (-2560, -1440, 0, 0)),
])
def test_covers_monitor(window, monitor) -> None:
    assert wc._covers(wc.ctypes.wintypes.RECT(*window), wc.ctypes.wintypes.RECT(*monitor)) is True


@pytest.mark.parametrize("window", [
    (1, 0, 2560, 1440),     # The left edge is uncovered.
    (0, 1, 2560, 1440),     # The top edge is uncovered.
    (0, 0, 2559, 1440),     # The right edge is uncovered.
    (0, 0, 2560, 1439),     # The bottom edge is uncovered.
])
def test_does_not_cover_monitor(window) -> None:
    assert wc._covers(wc.ctypes.wintypes.RECT(*window), wc.ctypes.wintypes.RECT(*PRIMARY_MONITOR)) is False


@pytest.fixture
def app(monkeypatch):
    app = wc.WallSwapApp()
    monkeypatch.setattr(wc, "is_fullscreen_app_running", lambda: True)
    monkeypatch.setattr(wc.settings, "reload", lambda: True)
    monkeypatch.setattr(wc, "set_wallpaper", lambda path: None)
    monkeypatch.setattr(wc, "set_lock_screen", lambda path: None)
    monkeypatch.setattr(wc, "apply_wallpaper_fit", lambda fit: None)
    monkeypatch.setattr(wc, "is_metered", lambda: False)
    monkeypatch.setattr(wc, "get_new_wallpaper", lambda: wc.Wallpaper("x.jpg", "wallhaven", "x", key="x"))
    return app


def test_a_fullscreen_app_skips_the_change_and_retries(app, monkeypatch) -> None:
    monkeypatch.setitem(wc.settings.data, "pause_in_fullscreen", True)
    assert app._change_wallpaper() == "skipped"
    assert app.retry_after == wc.RETRY_SECONDS


def test_with_the_pause_off_a_fullscreen_app_does_not_stop_the_change(app, monkeypatch) -> None:
    monkeypatch.setitem(wc.settings.data, "pause_in_fullscreen", False)
    assert app._change_wallpaper() == "set"
    assert app.retry_after is None


def test_the_pause_is_on_by_default_and_travels_in_the_window_patch() -> None:
    assert wc.DEFAULT_SETTINGS["pause_in_fullscreen"] is True
    before = wc.settings.snapshot()
    patch = wc.settings_patch(before, {**before, "pause_in_fullscreen": not before["pause_in_fullscreen"]})
    assert patch["set"] == [(("pause_in_fullscreen",), not before["pause_in_fullscreen"])]
