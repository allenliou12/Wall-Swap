"""INV-6: the smallest image used follows the biggest screen, capped at 2560x1440.

user32 is faked so the check runs on any OS.
"""
import types

import pytest

import wallpaper_changer as wc

ATTACHED = wc.DISPLAY_DEVICE_ATTACHED_TO_DESKTOP


def fake_displays(monkeypatch, displays):
    """displays: (name, state flags, (width, height) or None when Windows gives no mode)."""
    def enum_devices(_adapter, index, ref, _flags):
        if index >= len(displays):
            return 0
        device = ref._obj
        assert device.cb == wc.ctypes.sizeof(device)
        device.DeviceName, device.StateFlags = displays[index][0], displays[index][1]
        return 1

    def enum_settings(name, which, ref):
        assert which == wc.ENUM_CURRENT_SETTINGS
        mode = ref._obj
        assert mode.dmSize == wc.ctypes.sizeof(mode) == 220
        size = {d[0]: d[2] for d in displays}[name]
        if size is None:
            return 0
        mode.dmPelsWidth, mode.dmPelsHeight = size
        return 1

    user32 = types.SimpleNamespace(EnumDisplayDevicesW=enum_devices, EnumDisplaySettingsW=enum_settings)
    monkeypatch.setattr(wc.ctypes, "windll", types.SimpleNamespace(user32=user32), raising=False)


@pytest.mark.parametrize("displays, screen, minimum", [
    pytest.param([("D1", ATTACHED, (1920, 1080))], (1920, 1080), (1920, 1080), id="1080p"),
    pytest.param([("D1", ATTACHED, (2560, 1440))], (2560, 1440), (2560, 1440), id="1440p"),
    pytest.param([("D1", ATTACHED, (3840, 2160))], (3840, 2160), (2560, 1440), id="4k_capped"),
    pytest.param([("D1", ATTACHED, (3440, 1440))], (3440, 1440), (2560, 1440), id="ultrawide_capped"),
    pytest.param([("D1", ATTACHED, (1920, 1200))], (1920, 1200), (1920, 1200), id="16_10"),
    pytest.param([("D1", ATTACHED, (1080, 1920))], (1920, 1080), (1920, 1080), id="portrait"),
    pytest.param([("D1", ATTACHED, (1366, 768)), ("D2", ATTACHED, (1920, 1080))], (1920, 1080), (1920, 1080),
                 id="biggest_of_two"),
    pytest.param([("D1", 0, (3840, 2160)), ("D2", ATTACHED, (1920, 1080))], (1920, 1080), (1920, 1080),
                 id="unattached_ignored"),
    pytest.param([("D1", ATTACHED, None), ("D2", ATTACHED, (1920, 1080))], (1920, 1080), (1920, 1080),
                 id="no_mode_ignored"),
    pytest.param([], None, (2560, 1440), id="no_displays_falls_back"),
])
def test_minimum_follows_the_biggest_screen(monkeypatch, displays, screen, minimum):
    fake_displays(monkeypatch, displays)
    assert wc.largest_screen() == screen
    assert wc.min_size() == minimum


def test_a_failing_windows_call_falls_back_to_1440p(monkeypatch):
    def boom(*_args):
        raise OSError("no display driver")

    monkeypatch.setattr(wc.ctypes, "windll", types.SimpleNamespace(
        user32=types.SimpleNamespace(EnumDisplayDevicesW=boom)), raising=False)
    assert wc.largest_screen() is None
    assert wc.min_size() == (wc.MIN_WIDTH, wc.MIN_HEIGHT)


def test_1080p_images_fit_a_1080p_screen_but_not_a_1440p_one(monkeypatch):
    fake_displays(monkeypatch, [("D1", ATTACHED, (1920, 1080))])
    assert wc.fits_screen(1920, 1080)
    assert not wc.fits_screen(1600, 900)
    assert not wc.fits_screen(1080, 1920)  # portrait is still refused
    fake_displays(monkeypatch, [("D1", ATTACHED, (2560, 1440))])
    assert not wc.fits_screen(1920, 1080)
    assert wc.fits_screen(2560, 1440)


def test_wallhaven_is_asked_for_the_screen_size(monkeypatch):
    fake_displays(monkeypatch, [("D1", ATTACHED, (1920, 1080))])
    assert wc.wallhaven_filters()["atleast"] == "1920x1080"
    fake_displays(monkeypatch, [("D1", ATTACHED, (3840, 2160))])
    assert wc.wallhaven_filters()["atleast"] == "2560x1440"


# ── The min_resolution setting ──
@pytest.mark.parametrize("choice, minimum", [
    ("1080p", (1920, 1080)),
    ("1440p", (2560, 1440)),
    ("4k", (3840, 2160)),
    ("auto", (1920, 1200)),       # the faked screen
    ("8k please", (1920, 1200)),  # an unknown hand-typed value behaves as auto
])
def test_a_picked_size_wins_over_the_screen(monkeypatch, choice, minimum):
    fake_displays(monkeypatch, [("D1", ATTACHED, (1920, 1200))])
    monkeypatch.setitem(wc.settings.data, "min_resolution", choice)
    assert wc.min_size() == minimum
    assert wc.wallhaven_filters()["atleast"] == "%dx%d" % minimum


def test_picking_1080p_lets_a_16_10_screen_use_1080p_images(monkeypatch):
    fake_displays(monkeypatch, [("D1", ATTACHED, (1920, 1200))])
    assert not wc.fits_screen(1920, 1080)
    monkeypatch.setitem(wc.settings.data, "min_resolution", "1080p")
    assert wc.fits_screen(1920, 1080)


def test_every_size_has_a_label_and_the_default_is_auto():
    assert set(wc.RESOLUTION_LABELS) == {"auto", *wc.RESOLUTION_SIZES}
    assert wc.DEFAULT_SETTINGS["min_resolution"] == "auto"


def test_the_window_patch_carries_the_picked_size():
    before = wc.settings.snapshot()
    patch = wc.settings_patch(before, {**before, "min_resolution": "4k"})
    assert patch["set"] == [(("min_resolution",), "4k")]
    wc.apply_patch(before, patch)
    assert before["min_resolution"] == "4k"
