"""INV-19 (nothing is downloaded on a metered connection) and INV-20 (the fit is changed only when picked)."""
import types

import pytest
from PIL import Image

import wallpaper_changer as wc


# ── Is the connection metered? ──
@pytest.mark.parametrize("cost, metered", [
    (0x1, False),                 # unrestricted
    (0x0, False),                 # unknown
    (0x2, True),                  # fixed
    (0x4, True),                  # variable
    (0x1 | 0x10000, True),        # over the data limit
    (0x1 | 0x40000, True),        # roaming
    (0x1 | 0x20000, False),       # congested: slow, not costly
    (0x1 | 0x80000, False),       # approaching the limit: not over it yet
])
def test_cost_flags(monkeypatch, cost, metered):
    monkeypatch.setattr(wc, "connection_cost", lambda: cost)
    assert wc.is_metered() is metered


def test_when_windows_cannot_say_the_connection_counts_as_not_metered(monkeypatch):
    def fail():
        raise OSError("no network list manager")
    monkeypatch.setattr(wc, "connection_cost", fail)
    assert wc.is_metered() is False


def _data(**changes):
    data = wc.settings.snapshot()
    data.update(changes)
    return data


def test_downloads_are_allowed_unless_metered_and_not_switched_on(monkeypatch):
    monkeypatch.setattr(wc, "is_metered", lambda: True)
    assert wc.downloads_allowed(_data(metered_downloads=False)) is False
    assert wc.downloads_allowed(_data(metered_downloads=True)) is True
    monkeypatch.setattr(wc, "is_metered", lambda: False)
    assert wc.downloads_allowed(_data(metered_downloads=False)) is True


# ── What a metered change may use ──
def _image(path):
    Image.new("RGB", (2560, 1440)).save(path)
    return path


@pytest.fixture
def no_network(monkeypatch):
    monkeypatch.setattr(wc, "safe_get", lambda *a, **kw: pytest.fail("downloaded on a metered connection"))
    monkeypatch.setattr(wc, "largest_screen", lambda: (2560, 1440))
    wc.LOCAL_HISTORY_FILE.unlink(missing_ok=True)
    wc.BLOCKED_FILE.unlink(missing_ok=True)


def test_offline_weights_keep_only_sources_with_folders(tmp_path):
    data = _data(local_folders=[str(tmp_path)], game_queries=["poe"], game_folders=[])
    assert set(wc.source_weights(data)) >= {"wallhaven", "museum", "local", "game"}
    assert set(wc.offline_weights(data)) == {"local"}
    data["game_folders"] = [str(tmp_path)]
    assert set(wc.offline_weights(data)) == {"local", "game"}
    data["sources"]["local"] = False  # a source that is off stays off (INV-15)
    assert set(wc.offline_weights(data)) == {"game"}


def test_a_metered_fetch_uses_folders_and_never_the_network(monkeypatch, tmp_path, no_network):
    mine = _image(tmp_path / "mine.jpg")
    data = _data(local_folders=[str(tmp_path)], game_queries=["poe"], game_folders=[str(tmp_path)])
    monkeypatch.setattr(wc.settings, "snapshot", lambda: data)
    for _ in range(10):
        assert wc.get_new_wallpaper(online=False).path == str(mine)
    assert wc.fetch_source("wallhaven", data, online=False) is None
    assert wc.fetch_source("museum", data, online=False) is None
    assert wc.fetch_source("game", data, online=False).path == str(mine)  # its folder, not its searches


@pytest.fixture
def app(monkeypatch):
    app = wc.WallSwapApp()
    monkeypatch.setattr(wc, "is_fullscreen_app_running", lambda: False)
    monkeypatch.setattr(wc.settings, "reload", lambda: True)
    monkeypatch.setattr(wc, "set_wallpaper", lambda path: None)
    monkeypatch.setattr(wc, "set_lock_screen", lambda path: None)
    monkeypatch.setattr(wc, "apply_wallpaper_fit", lambda fit: None)
    return app


def test_metered_with_no_folders_leaves_the_wallpaper_and_does_not_retry(app, monkeypatch, no_network):
    monkeypatch.setattr(wc, "is_metered", lambda: True)
    data = _data(local_folders=[], game_folders=[])
    monkeypatch.setattr(wc.settings, "snapshot", lambda: data)
    assert app._change_wallpaper() == "nothing"
    assert app.retry_after is None


def test_metered_with_a_folder_changes_to_a_local_picture(app, monkeypatch, tmp_path, no_network):
    mine = _image(tmp_path / "mine.jpg")
    monkeypatch.setattr(wc, "is_metered", lambda: True)
    data = _data(local_folders=[str(tmp_path)])
    monkeypatch.setattr(wc.settings, "snapshot", lambda: data)
    assert app._change_wallpaper() == "set"
    assert app.current.path == str(mine)


def test_metered_but_allowed_fetches_as_usual(app, monkeypatch):
    monkeypatch.setattr(wc, "is_metered", lambda: True)
    data = _data(metered_downloads=True)
    monkeypatch.setattr(wc.settings, "snapshot", lambda: data)
    calls = []

    def fetch(*args, **kwargs):
        calls.append((args, kwargs))
        return wc.Wallpaper("x.jpg", "wallhaven", "x", key="x")

    monkeypatch.setattr(wc, "get_new_wallpaper", fetch)
    assert app._change_wallpaper() == "set"
    assert calls == [((), {})]  # the ordinary online fetch


def test_the_daily_update_check_waits_on_a_metered_connection(app, monkeypatch):
    started = []
    monkeypatch.setattr(wc.threading, "Thread",
                        lambda **kw: types.SimpleNamespace(start=lambda: started.append(1)))
    monkeypatch.setattr(wc.time, "monotonic", lambda: 100.0)
    monkeypatch.setitem(wc.settings.data, "check_for_updates", True)
    monkeypatch.setitem(wc.settings.data, "metered_downloads", False)
    monkeypatch.setattr(wc, "is_metered", lambda: True)
    app.auto_check_for_updates()
    assert started == [] and app.next_update_check == 100.0 + wc.UPDATE_RETRY_SECONDS

    monkeypatch.setattr(wc, "is_metered", lambda: False)
    app.next_update_check = 0.0
    app.auto_check_for_updates()
    assert started == [1]


# ── Wallpaper fit ──
class FakeRegistry:
    HKEY_CURRENT_USER, KEY_SET_VALUE, REG_SZ = "HKCU", "set", "sz"

    def __init__(self):
        self.written = {}
        self.opened = []

    def OpenKey(self, root, path, reserved, access):
        self.opened.append((root, path, access))
        return self

    def SetValueEx(self, key, name, reserved, kind, value):
        assert kind == self.REG_SZ
        self.written[name] = value

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.mark.parametrize("fit, style", [("fill", "10"), ("fit", "6"), ("span", "22")])
def test_a_picked_fit_writes_windows_own_style_values(monkeypatch, fit, style):
    registry = FakeRegistry()
    monkeypatch.setattr(wc, "winreg", registry)
    wc.apply_wallpaper_fit(fit)
    assert registry.opened == [("HKCU", "Control Panel\\Desktop", "set")]
    assert registry.written == {"WallpaperStyle": style, "TileWallpaper": "0"}


@pytest.mark.parametrize("fit", ["auto", "stretch", "", "Fill"])
def test_auto_and_unknown_values_never_touch_the_registry(monkeypatch, fit):
    registry = FakeRegistry()
    monkeypatch.setattr(wc, "winreg", registry)
    wc.apply_wallpaper_fit(fit)
    assert registry.opened == [] and registry.written == {}


def test_the_fit_is_applied_before_the_wallpaper_and_a_failure_does_not_stop_the_change(monkeypatch):
    app = wc.WallSwapApp()
    order = []

    def fit(value):
        order.append(("fit", value))
        raise OSError("registry locked")

    monkeypatch.setattr(wc, "apply_wallpaper_fit", fit)
    monkeypatch.setattr(wc, "set_wallpaper", lambda path: order.append(("wallpaper", path)))
    monkeypatch.setattr(wc, "set_lock_screen", lambda path: None)
    monkeypatch.setitem(wc.settings.data, "wallpaper_fit", "span")
    app._show(wc.Wallpaper("a.jpg", "local", "a"))
    assert order == [("fit", "span"), ("wallpaper", "a.jpg")]
    assert app.current.path == "a.jpg"


def test_new_settings_default_to_changing_nothing_and_travel_in_the_window_patch():
    assert wc.DEFAULT_SETTINGS["wallpaper_fit"] == "auto"
    assert wc.DEFAULT_SETTINGS["metered_downloads"] is False
    assert set(wc.FIT_LABELS) == {"auto", *wc.FIT_STYLES}
    before = wc.settings.snapshot()
    patch = wc.settings_patch(before, {**before, "wallpaper_fit": "fill", "metered_downloads": True})
    assert patch["set"] == [(("wallpaper_fit",), "fill"), (("metered_downloads",), True)]
