"""Checking a newly added search against Wallhaven: the count request, the worker hand-off and the message text."""
import json

import pytest

import settings_window as sw
import wallpaper_changer as wc


# ── Message text ──
def test_no_answer_says_so():
    assert sw.search_check_message(None, is_game=False) == "Added. Couldn't check Wallhaven right now."
    assert sw.search_check_message(None, is_game=True) == "Added. Couldn't check Wallhaven right now."


@pytest.mark.parametrize("is_game", [False, True])
def test_zero_warns_but_keeps_the_tag(is_game):
    message = sw.search_check_message(0, is_game)
    assert message.startswith("Added, but Wallhaven has nothing big enough for your screen")
    assert "different spelling" in message


def test_topic_count_is_an_upper_bound():
    assert sw.search_check_message(340, is_game=False) == "Added. About 340 wallpapers on Wallhaven"
    assert sw.search_check_message(12345, is_game=False) == "Added. About 12,345 wallpapers on Wallhaven"


def test_game_count_is_exact():
    assert sw.search_check_message(340, is_game=True) == "Added. 340 wallpapers on Wallhaven"
    assert sw.search_check_message(1, is_game=True) == "Added. 1 wallpaper on Wallhaven"


# ── The request ──
def _stub(monkeypatch, response):
    calls = []

    def fake_get(url, **kw):
        calls.append((url, kw))
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(wc, "safe_get", fake_get)
    return calls


def _reply(total, status=200):
    return wc.Fetched(status, json.dumps({"data": [], "meta": {"total": total}}).encode())


def test_count_uses_the_same_filters_as_fetching(monkeypatch):
    calls = _stub(monkeypatch, _reply(340))
    assert wc.count_wallhaven("nebula") == 340
    (url, kw), = calls
    assert url == wc.WALLHAVEN_SEARCH_URL
    assert kw["max_bytes"] == wc.MAX_API_BYTES
    assert kw["params"] == {"q": "nebula", **wc.wallhaven_filters()}

    # And fetching sends exactly those filters too
    fetch_calls = _stub(monkeypatch, wc.Fetched(500, b""))
    wc.fetch_from_wallhaven(["nebula"], "random")
    sent = fetch_calls[0][1]["params"]
    assert {k: sent[k] for k in wc.wallhaven_filters()} == wc.wallhaven_filters()
    assert fetch_calls[0][0] == wc.WALLHAVEN_SEARCH_URL


@pytest.mark.parametrize("response", [
    _reply(5, status=429),
    wc.Fetched(200, b"not json"),
    wc.Fetched(200, b'{"data": []}'),
    _reply("lots"),
    _reply(-1),
    _reply(True),
    wc.DownloadError("too slow"),
])
def test_count_raises_on_anything_odd(monkeypatch, response):
    _stub(monkeypatch, response)
    with pytest.raises(Exception):
        wc.count_wallhaven("nebula")


# ── The hand-off to the Tk thread ──
@pytest.fixture
def app():
    return wc.WallSwapApp()


@pytest.mark.parametrize("response,expected", [(_reply(0), 0), (_reply(7), 7), (wc.DownloadError("offline"), None)])
def test_answer_comes_back_through_the_ui_queue(app, monkeypatch, response, expected):
    _stub(monkeypatch, response)
    answers = []
    app.count_search("nebula", answers.append)
    queued = app.ui_calls.get(timeout=5)  # the worker never calls done itself
    assert answers == []
    queued()
    assert answers == [expected]
