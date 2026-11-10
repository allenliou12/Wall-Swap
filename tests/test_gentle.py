"""INV-21: downloads WallSwap starts by itself are slowed, and very large Wallhaven images are skipped."""
import json

import pytest

import wallpaper_changer as wc


@pytest.mark.parametrize("received, elapsed, rate, wait", [
    (1_000_000, 0.0, 1_000_000, 1.0),   # a megabyte arrived at once: wait out the second
    (1_000_000, 0.4, 1_000_000, 0.6),
    (500_000, 2.0, 1_000_000, 0.0),     # already slower than the limit: no extra wait
    (5_000_000, 1.0, None, 0.0),        # no limit
    (5_000_000, 1.0, 0, 0.0),
])
def test_pace_delay(received, elapsed, rate, wait):
    assert wc.pace_delay(received, elapsed, rate) == pytest.approx(wait)


class FakeResponse:
    status_code, is_redirect, headers, url = 200, False, {}, "https://w.wallhaven.cc/x.jpg"

    def __init__(self, size, chunk):
        self.size, self.chunk = size, chunk

    def iter_content(self, _n):
        for start in range(0, self.size, self.chunk):
            yield b"x" * min(self.chunk, self.size - start)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def clock(monkeypatch):
    """A fake clock that only moves when the code sleeps; the 'server' answers instantly."""
    state = {"now": 100.0, "slept": 0.0}

    def sleep(seconds):
        state["now"] += seconds
        state["slept"] += seconds

    monkeypatch.setattr(wc.time, "monotonic", lambda: state["now"])
    monkeypatch.setattr(wc.time, "sleep", sleep)
    monkeypatch.setattr(wc.requests, "get", lambda *a, **kw: FakeResponse(3_000_000, 64 * 1024))
    return state


def test_a_gentle_download_takes_as_long_as_its_size_allows(clock):
    with wc.gentle_downloads():
        got = wc.safe_get("https://w.wallhaven.cc/x.jpg")
    assert len(got.content) == 3_000_000
    assert clock["slept"] == pytest.approx(3_000_000 / wc.GENTLE_BYTES_PER_SECOND)


def test_an_ordinary_download_is_not_slowed(clock):
    wc.safe_get("https://w.wallhaven.cc/x.jpg")
    assert clock["slept"] == 0.0


def test_the_limit_ends_with_the_block_even_after_an_error(clock):
    with pytest.raises(RuntimeError):
        with wc.gentle_downloads():
            raise RuntimeError("fetch blew up")
    wc.safe_get("https://w.wallhaven.cc/x.jpg")
    assert clock["slept"] == 0.0


def test_a_gentle_download_still_gives_up_at_the_deadline(clock, monkeypatch):
    monkeypatch.setattr(wc, "GENTLE_BYTES_PER_SECOND", 1000)  # 3 MB would take 50 minutes
    with wc.gentle_downloads():
        with pytest.raises(wc.DownloadError, match="took longer"):
            wc.safe_get("https://w.wallhaven.cc/x.jpg")
    assert clock["slept"] < wc.DOWNLOAD_DEADLINE + 70


# ── Who is gentle ──
@pytest.fixture
def app(monkeypatch):
    app = wc.WallSwapApp()
    app.rates = []
    monkeypatch.setattr(app, "_do_change_wallpaper",
                        lambda: app.rates.append(getattr(wc._pace, "rate", None)) or "set")
    monkeypatch.setitem(wc.settings.data, "interval_minutes", 30)
    return app


def test_the_timers_changes_are_gentle_and_a_clicked_next_is_not(app):
    app.elapsed = 30 * 60 - 5
    app.tick(5)                # the timer
    app._change_wallpaper()    # what Next Wallpaper runs
    assert app.rates == [wc.GENTLE_BYTES_PER_SECOND, None]
    assert getattr(wc._pace, "rate", None) is None  # nothing left switched on


def test_the_replacement_after_never_show_again_is_full_speed(app, monkeypatch):
    monkeypatch.setattr(app, "notify", lambda *a, **kw: None)
    monkeypatch.setattr(wc, "block_image", lambda key: None)
    app.current = wc.Wallpaper("x.jpg", "local", "x", key="k")
    app._block_current()
    assert app.rates == [None]


# ── Very large images ──
@pytest.mark.parametrize("size, too_big", [
    (wc.MAX_WALLHAVEN_FILE_BYTES + 1, True),
    (wc.MAX_WALLHAVEN_FILE_BYTES, False),
    (2_600_000, False),
    (None, False),        # not listed: not a reason to skip
    ("99999999999", False),
    (True, False),
])
def test_too_big(size, too_big):
    assert wc._too_big(size) is too_big


def test_a_huge_wallhaven_image_is_skipped_without_downloading_it(monkeypatch):
    def result(wp_id, size):
        return {"id": wp_id, "path": f"https://w.wallhaven.cc/full/{wp_id}.jpg", "dimension_x": 3840,
                "dimension_y": 2160, "favorites": 999, "file_size": size}

    downloaded = []

    def fake_get(url, *, params=None, **kw):
        if url.endswith("/search"):
            return wc.Fetched(200, json.dumps({"data": [result("huge", 40_000_000), result("fine", 3_000_000)],
                                               "meta": {"last_page": 1}}).encode())
        downloaded.append(url)
        return wc.Fetched(200, b"x" * 60_000)

    monkeypatch.setattr(wc, "safe_get", fake_get)
    monkeypatch.setattr(wc, "load_seen_ids", lambda: set())
    monkeypatch.setattr(wc, "load_blocked", lambda: set())
    monkeypatch.setattr(wc, "save_seen_id", lambda wp_id: None)
    for _ in range(5):
        assert wc.fetch_from_wallhaven(["x"], "random").key == "fine"
    assert all("fine" in url for url in downloaded)
