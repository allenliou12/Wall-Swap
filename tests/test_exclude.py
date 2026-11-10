"""Excluded words: kept out of every Wallhaven search as -word, and never able to add other search syntax."""
import json

import pytest

import wallpaper_changer as wc


@pytest.mark.parametrize("text, existing, stored", [
    ("car", [], "car"),
    ("  Car  ", [], "Car"),
    ("-car", [], "car"),          # a typed minus is the same word
    ("sci-fi", [], "sci-fi"),
    ("4k_wallpaper", [], "4k_wallpaper"),
])
def test_a_plain_word_is_accepted(text, existing, stored):
    assert wc.exclude_word_problem(text, existing) is None
    assert wc.clean_exclude_word(text, existing) == stored


@pytest.mark.parametrize("text, existing, why", [
    ("", [], "Empty"),
    ("  -  ", [], "Empty"),
    ("sports car", [], "One word at a time"),
    ("x" * (wc.MAX_EXCLUDE_LENGTH + 1), [], "Too long"),
    ("car&purity=111", [], "Letters, numbers, - and _ only"),
    ("id:123", [], "Letters, numbers, - and _ only"),
    ("CAR", ["car"], "Already there"),
    ("eleventh", [f"w{i}" for i in range(wc.MAX_EXCLUDE_WORDS)], f"{wc.MAX_EXCLUDE_WORDS} words at most"),
])
def test_anything_else_is_refused_with_a_reason(text, existing, why):
    assert wc.exclude_word_problem(text, existing) == why
    assert wc.clean_exclude_word(text, existing) is None


def test_q_gets_a_minus_word_for_each_excluded_word():
    assert wc.wallhaven_q("landscape", []) == "landscape"
    assert wc.wallhaven_q("landscape", ["car", "people"]) == "landscape -car -people"


def test_hand_edited_words_cannot_add_search_syntax_or_grow_without_limit():
    bad = ["car", "two words", "+must", "id:5", "x" * 99, "car", "ok-word"]
    assert wc.wallhaven_q("moon", bad) == "moon -car -ok-word"
    many = [f"w{i}" for i in range(wc.MAX_EXCLUDE_WORDS + 5)]
    assert wc.wallhaven_q("moon", many).count(" -") == wc.MAX_EXCLUDE_WORDS


def _capture(monkeypatch):
    seen = []

    def fake_get(url, *, params=None, **kw):
        seen.append(params)
        return wc.Fetched(200, json.dumps({"data": [], "meta": {"total": 3}}).encode())

    monkeypatch.setattr(wc, "safe_get", fake_get)
    return seen


def test_searches_and_the_count_send_the_excluded_words(monkeypatch):
    seen = _capture(monkeypatch)
    wc.fetch_from_wallhaven(["forest"], "random", exclude=["car"])
    assert wc.count_wallhaven("forest", ["car", "people"]) == 3
    assert [p["q"] for p in seen] == ["forest -car", "forest -car -people"]
    assert all(p["purity"] == "100" and p["categories"] == "110" for p in seen)


def test_topic_and_game_searches_both_use_the_settings_list(monkeypatch):
    seen = _capture(monkeypatch)
    data = wc.settings.snapshot()
    data.update(exclude_words=["car"], game_queries=["path of exile"], game_folders=[])
    data["topics"]["nature"] = {"enabled": True, "searches": ["forest"]}
    for topic in data["topics"]:
        data["topics"][topic]["enabled"] = topic == "nature"
    wc.fetch_source("wallhaven", data)
    wc.fetch_source("game", data)
    assert {p["q"] for p in seen} == {"forest -car", "path of exile -car"}


def test_the_window_patch_carries_the_words_and_old_files_get_an_empty_list():
    before = wc.settings.snapshot()
    assert before["exclude_words"] == []
    patch = wc.settings_patch(before, {**before, "exclude_words": ["car"]})
    assert patch["set"] == [(("exclude_words",), ["car"])]
    assert wc._merge_settings(wc.DEFAULT_SETTINGS, {"exclude_words": "car"})["exclude_words"] == []
