"""INV-17: Never Show Again blocks an image for good, in every source, and deletes only WallSwap's own copy."""
import json

import pytest
from PIL import Image

import wallpaper_changer as wc


@pytest.fixture(autouse=True)
def clean_block_file():
    wc.BLOCKED_FILE.unlink(missing_ok=True)
    yield
    wc.BLOCKED_FILE.unlink(missing_ok=True)
    for path in wc.WALLPAPER_DIR.glob("wallswap_*.jpg"):
        path.unlink()


# ── The file ──
def test_blocking_appends_once_and_keeps_hand_edits():
    wc.BLOCKED_FILE.write_text("mine\n\n  spaced  \n", encoding="utf-8")
    wc.block_image("abc123")
    wc.block_image("abc123")
    assert wc.load_blocked() == {"mine", "spaced", "abc123"}
    assert wc.BLOCKED_FILE.read_text(encoding="utf-8").count("abc123") == 1


def test_no_file_blocks_nothing():
    assert wc.load_blocked() == set()


# ── Every source skips a blocked image ──
def test_wallhaven_skips_a_blocked_id(monkeypatch):
    search = {"data": [{"id": "abc", "path": "https://w.wallhaven.cc/full/ab/abc.jpg", "dimension_x": 3840,
                        "dimension_y": 2160, "favorites": 999}]}
    requested = []

    def fake_get(url, *, params=None, **kw):
        requested.append(url)
        return wc.Fetched(200, json.dumps(search).encode()) if url.endswith("/search") else wc.Fetched(404, b"")

    monkeypatch.setattr(wc, "safe_get", fake_get)
    monkeypatch.setattr(wc, "load_seen_ids", lambda: set())
    wc.fetch_from_wallhaven(["x"], "random")
    assert requested[-1].endswith("abc.jpg")  # not blocked: its download is tried

    wc.block_image("abc")
    requested.clear()
    wc.fetch_from_wallhaven(["x"], "random")
    assert all(url.endswith("/search") for url in requested)  # blocked: only searches, no download


def test_the_met_skips_a_blocked_painting(monkeypatch):
    monkeypatch.setattr(wc, "safe_get", lambda url, **kw: wc.Fetched(200, json.dumps({"objectIDs": [7]}).encode()))
    monkeypatch.setattr(wc, "load_seen_ids", lambda: set())
    tried = []
    monkeypatch.setattr(wc, "_try_museum_object", lambda obj_id: tried.append(obj_id))
    monkeypatch.setattr(wc, "save_seen_ids", lambda ids: None)
    wc.fetch_from_museum()
    assert set(tried) == {7}  # once per department searched

    wc.block_image("met_7")
    tried.clear()
    wc.fetch_from_museum()
    assert tried == []


def _image(path, size=(2560, 1440)):
    Image.new("RGB", size).save(path)
    return path


def test_a_blocked_local_file_is_never_picked_and_never_touched(tmp_path):
    wc.LOCAL_HISTORY_FILE.unlink(missing_ok=True)
    keep, blocked = _image(tmp_path / "keep.jpg"), _image(tmp_path / "blocked.jpg")
    wc.block_image(str(blocked))
    picks = {wc.pick_local_wallpaper([tmp_path]).path for _ in range(12)}
    assert picks == {str(keep)}
    assert blocked.exists()

    wc.block_image(str(keep))
    assert wc.pick_local_wallpaper([tmp_path]) is None  # everything blocked: nothing, not a repeat
    assert keep.exists() and blocked.exists()


def test_a_local_pick_carries_its_path_as_the_key(tmp_path):
    wc.LOCAL_HISTORY_FILE.unlink(missing_ok=True)
    path = _image(tmp_path / "one.png")
    assert wc.pick_local_wallpaper([tmp_path]).key == str(path)


# ── The tray action ──
class NowThread:
    """Runs the worker at once, so the test sees the whole action."""
    def __init__(self, target, args=(), daemon=None):
        self.target, self.args = target, args

    def start(self):
        self.target(*self.args)


@pytest.fixture
def app(monkeypatch):
    app = wc.WallSwapApp()
    app.notes = []
    monkeypatch.setattr(app, "notify", lambda message, title="WallSwap": app.notes.append(message))
    monkeypatch.setattr(wc.threading, "Thread", NowThread)
    monkeypatch.setattr(wc, "set_wallpaper", lambda path: None)
    monkeypatch.setattr(wc, "set_lock_screen", lambda path: None)
    monkeypatch.setattr(wc, "is_fullscreen_app_running", lambda: False)
    monkeypatch.setattr(wc.settings, "reload", lambda: True)
    return app


def test_blocking_a_download_switches_wallpaper_and_deletes_only_that_file(app, monkeypatch):
    download = wc.WALLPAPER_DIR / "wallswap_wallhaven_1.jpg"
    download.write_bytes(b"x")
    other = wc.WALLPAPER_DIR / "wallswap_wallhaven_2.jpg"
    other.write_bytes(b"y")
    app.current = wc.Wallpaper(str(download), "wallhaven", "Wallhaven abc", key="abc")
    app.history.append(wc.Wallpaper(str(download), "wallhaven", "Wallhaven abc", key="abc"))
    monkeypatch.setattr(wc, "get_new_wallpaper", lambda: wc.Wallpaper(str(other), "wallhaven", "next", key="def"))

    app.never_show_again()

    assert "abc" in wc.load_blocked()
    assert not download.exists() and other.exists()
    assert app.current.key == "def"
    assert list(app.history) == []  # the blocked one can't come back through Previous
    assert "won't be shown again" in app.notes[0]


def test_blocking_a_local_file_never_deletes_it(app, monkeypatch, tmp_path):
    mine = wc.WALLPAPER_DIR / "wallswap_mine.jpg"  # even a file that looks exactly like a download
    mine.write_bytes(b"x")
    app.current = wc.Wallpaper(str(mine), "local", mine.name, key=str(mine))
    monkeypatch.setattr(wc, "get_new_wallpaper", lambda: None)

    app.never_show_again()

    assert str(mine) in wc.load_blocked()
    assert mine.exists()
    assert app.current is None  # offline: nothing replaced it, and it is no longer "current"
    assert app.retry_after == wc.RETRY_SECONDS  # the replacement is retried like any failed change


def test_nothing_current_blocks_nothing(app):
    app.never_show_again()
    assert wc.load_blocked() == set()
    assert app.notes == ["There's no current wallpaper to block yet."]


def test_is_own_download_only_matches_wallswap_files_in_its_folder(tmp_path):
    assert wc.is_own_download(wc.WALLPAPER_DIR / "wallswap_met_1.jpg")
    assert not wc.is_own_download(wc.WALLPAPER_DIR / "Favourites" / "wallswap_met_1.jpg")
    assert not wc.is_own_download(wc.WALLPAPER_DIR / "holiday.jpg")
    assert not wc.is_own_download(tmp_path / "wallswap_met_1.jpg")
