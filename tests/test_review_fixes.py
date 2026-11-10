"""Edge cases found in review: hand-edited blocked.txt, dead search results, nothing to fetch, a crashing fetcher."""
import json
import locale

import pytest

import wallpaper_changer as wc


@pytest.fixture(autouse=True)
def clean_block_file():
    wc.BLOCKED_FILE.unlink(missing_ok=True)
    yield
    wc.BLOCKED_FILE.unlink(missing_ok=True)


# ── blocked.txt as people really save it ──
@pytest.mark.parametrize("ending", ["", "\r"])
def test_a_last_line_without_a_line_break_is_not_merged_with_the_new_one(ending):
    wc.BLOCKED_FILE.write_bytes(b"mine" + ending.encode())
    wc.block_image("abc123")
    assert wc.load_blocked() == {"mine", "abc123"}


def test_a_byte_order_mark_does_not_hide_the_first_line():
    wc.BLOCKED_FILE.write_bytes(b"\xef\xbb\xbffirst\r\nsecond\r\n")
    assert wc.load_blocked() == {"first", "second"}


def test_a_file_saved_in_the_pcs_own_encoding_still_blocks():
    path = "C:\\Bilder\\Stra\u00dfe.jpg"
    try:
        raw = (path + "\nplain\n").encode(locale.getpreferredencoding(False))
        raw.decode("utf-8")
    except UnicodeEncodeError:
        pytest.skip("this PC's encoding can't write the test path")
    except UnicodeDecodeError:
        pass  # good: not valid UTF-8, which is the case being tested
    else:
        pytest.skip("this PC's encoding is UTF-8, so there is no second encoding to fall back to")
    wc.BLOCKED_FILE.write_bytes(raw)
    assert wc.load_blocked() == {path, "plain"}


# ── A search result that can never be downloaded ──
def _search(monkeypatch, pages, image_reply):
    asked, seen = [], set()

    def fake_get(url, *, params=None, **kw):
        if url.endswith("/search"):
            asked.append(params["page"])
            return wc.Fetched(200, json.dumps({"data": pages.get(params["page"], []),
                                               "meta": {"last_page": 9}}).encode())
        return image_reply(url)

    monkeypatch.setattr(wc, "safe_get", fake_get)
    monkeypatch.setattr(wc, "load_seen_ids", lambda: set(seen))
    monkeypatch.setattr(wc, "load_blocked", lambda: set())
    monkeypatch.setattr(wc, "save_seen_id", seen.add)
    return asked, seen


def _result(wp_id):
    return {"id": wp_id, "path": f"https://w.wallhaven.cc/full/{wp_id}.jpg", "dimension_x": 3840,
            "dimension_y": 2160, "favorites": 999}


@pytest.mark.parametrize("dead", [wc.Fetched(404, b""), wc.Fetched(200, b"tiny")])
def test_a_dead_result_is_marked_seen_and_does_not_pin_page_one(monkeypatch, dead):
    pages = {1: [_result("dead")], 2: [_result("good")]}
    asked, seen = _search(monkeypatch, pages,
                          lambda url: dead if "dead" in url else wc.Fetched(200, b"x" * 60_000))
    assert wc.fetch_from_wallhaven(["forest"], "toplist").key == "good"
    assert asked == [1, 2]
    assert "dead" in seen


def test_a_busy_server_is_not_a_definite_no(monkeypatch):
    pages = {1: [_result("later")], 2: [_result("good")]}
    asked, seen = _search(monkeypatch, pages, lambda url: wc.Fetched(503, b""))
    assert wc.fetch_from_wallhaven(["forest"], "toplist") is None
    assert asked == [1] and seen == set()  # INV-12: a temporary failure never marks an image as seen


# ── Changes that can't or shouldn't be retried quickly ──
@pytest.fixture
def app(monkeypatch):
    app = wc.WallSwapApp()
    monkeypatch.setattr(wc, "is_fullscreen_app_running", lambda: False)
    monkeypatch.setattr(wc.settings, "reload", lambda: True)
    return app


def test_nothing_to_fetch_waits_for_the_normal_interval(app, monkeypatch):
    data = wc.settings.snapshot()
    for source in data["sources"]:
        data["sources"][source] = False
    monkeypatch.setattr(wc.settings, "snapshot", lambda: data)
    monkeypatch.setattr(wc, "get_new_wallpaper", lambda: pytest.fail("fetched with every source off"))
    assert app._change_wallpaper() == "nothing"
    assert (app.retry_after, app.failures) == (None, 0)


def test_a_crashing_fetcher_is_a_failed_change_not_a_dead_timer(app, monkeypatch):
    def crash():
        raise RuntimeError("bug in a fetcher")

    monkeypatch.setattr(wc, "get_new_wallpaper", crash)
    assert app._change_wallpaper() == "failed"
    assert app.retry_after == wc.RETRY_SECONDS
    assert not app.change_lock.locked()


def test_blocking_waits_for_a_change_in_flight_and_blocks_what_is_really_current(app, monkeypatch):
    """The change lock is held while a change runs; Never Show Again must not act on the outgoing wallpaper."""
    notes = []
    monkeypatch.setattr(app, "notify", lambda message, title="WallSwap": notes.append(message))
    monkeypatch.setattr(wc, "set_wallpaper", lambda path: None)
    monkeypatch.setattr(wc, "set_lock_screen", lambda path: None)
    monkeypatch.setattr(wc, "get_new_wallpaper", lambda: None)
    old = wc.Wallpaper("old.jpg", "local", "old", key="old-key")
    new = wc.Wallpaper("new.jpg", "local", "new", key="new-key")
    app.current = old

    app.change_lock.acquire()  # a change is in flight...
    worker = wc.threading.Thread(target=app._block_current, daemon=True)
    worker.start()
    worker.join(0.2)
    assert worker.is_alive() and wc.load_blocked() == set()  # ...so nothing is blocked yet
    app.history.append(old)
    app.current = new          # ...and it finishes by showing the new wallpaper
    app.change_lock.release()
    worker.join(5)

    assert wc.load_blocked() == {"new-key"}
    assert [w.key for w in app.history] == ["old-key"]
