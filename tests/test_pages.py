"""Wallhaven pages: page 1 until everything usable on it has been shown, then page 2, then 3, never further."""
import json

import pytest

import wallpaper_changer as wc


def _result(wp_id, favourites=999):
    return {"id": wp_id, "path": f"https://w.wallhaven.cc/full/{wp_id}.jpg", "dimension_x": 3840,
            "dimension_y": 2160, "favorites": favourites}


@pytest.fixture
def wallhaven(monkeypatch):
    """pages: {page number: results}. Records the pages asked for and the images downloaded."""
    state = {"pages": {}, "last_page": 9, "asked": [], "downloaded": [], "download_ok": True, "seen": set()}

    def fake_get(url, *, params=None, **kw):
        if url.endswith("/search"):
            state["asked"].append(params["page"])
            body = {"data": state["pages"].get(params["page"], []), "meta": {"last_page": state["last_page"]}}
            return wc.Fetched(200, json.dumps(body).encode())
        state["downloaded"].append(url)
        return wc.Fetched(200, b"x" * 60_000) if state["download_ok"] else wc.Fetched(503, b"")

    monkeypatch.setattr(wc, "safe_get", fake_get)
    monkeypatch.setattr(wc, "load_seen_ids", lambda: set(state["seen"]))
    monkeypatch.setattr(wc, "load_blocked", lambda: set())
    monkeypatch.setattr(wc, "save_seen_id", lambda wp_id: state["seen"].add(wp_id))
    return state


def test_page_one_is_enough_while_it_has_something_unshown(wallhaven):
    wallhaven["pages"] = {1: [_result("a")], 2: [_result("b")]}
    assert wc.fetch_from_wallhaven(["forest"], "toplist").key == "a"
    assert wallhaven["asked"] == [1]


def test_a_used_up_page_moves_on_to_the_next(wallhaven):
    wallhaven["pages"] = {1: [_result("a"), _result("low", favourites=1)], 2: [_result("b")], 3: [_result("c")]}
    wallhaven["seen"] = {"a"}
    assert wc.fetch_from_wallhaven(["forest"], "hot").key == "b"
    assert wallhaven["asked"] == [1, 2]

    wallhaven["asked"].clear()
    assert wc.fetch_from_wallhaven(["forest"], "hot").key == "c"
    assert wallhaven["asked"] == [1, 2, 3]


def test_it_never_goes_past_page_three(wallhaven):
    wallhaven["pages"] = {page: [_result(f"p{page}")] for page in range(1, 6)}
    wallhaven["seen"] = {"p1", "p2", "p3"}
    assert wc.fetch_from_wallhaven(["forest"], "toplist") is None
    assert wallhaven["asked"] == [1, 2, 3]
    assert wallhaven["downloaded"] == []


def test_it_stops_at_the_last_page_wallhaven_has(wallhaven):
    wallhaven["pages"] = {1: [_result("a")]}
    wallhaven["seen"] = {"a"}
    wallhaven["last_page"] = 1
    assert wc.fetch_from_wallhaven(["forest"], "toplist") is None
    assert wallhaven["asked"] == [1]


def test_failed_downloads_do_not_count_as_used_up(wallhaven):
    wallhaven["pages"] = {1: [_result("a")], 2: [_result("b")]}
    wallhaven["download_ok"] = False
    assert wc.fetch_from_wallhaven(["forest"], "toplist") is None
    assert wallhaven["asked"] == [1]  # page 1 still has an unshown wallpaper: stay on it for next time


@pytest.mark.parametrize("sorting, source", [("random", "wallhaven"), ("random", "game"), ("toplist", "game")])
def test_random_and_game_searches_only_ever_ask_for_page_one(wallhaven, sorting, source):
    wallhaven["pages"] = {1: [_result("a")], 2: [_result("b")]}
    wallhaven["seen"] = {"a"}
    assert wc.fetch_from_wallhaven(["forest"], sorting, source=source) is None
    assert wallhaven["asked"] == [1]
