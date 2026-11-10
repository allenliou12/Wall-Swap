"""Which source the next wallpaper comes from: ticked topics, the four weights, and dropout."""
import copy
import json

import pytest

import wallpaper_changer as wc


def _data(**changes) -> dict:
    data = copy.deepcopy(wc.DEFAULT_SETTINGS)
    for topic in data["topics"].values():
        topic["enabled"] = False
    data.update(changes)
    return data


def _with_topic(data: dict, topic: str, searches: list[str], enabled: bool = True) -> dict:
    data["topics"][topic] = {"enabled": enabled, "searches": searches}
    return data


def test_query_pool_only_enabled_topics_dedup():
    data = _data()
    _with_topic(data, "nature", [" Forest ", "", "mountains"])
    _with_topic(data, "space", ["forest", "nebula", "  "])
    _with_topic(data, "cities", ["neon city rain"], enabled=False)

    assert wc.wallhaven_query_pool(data) == ["Forest", "mountains", "nebula"]


def test_query_pool_follows_topic_order_not_dict_order():
    data = _data()
    data["topics"] = dict(reversed(data["topics"].items()))  # file order: space before nature
    _with_topic(data, "space", ["nebula"])
    _with_topic(data, "nature", ["forest"])

    assert wc.wallhaven_query_pool(data) == ["forest", "nebula"]


def test_source_weights_four_weights_45_15_20_20(tmp_path):
    data = _with_topic(_data(game_queries=["path of exile"], local_folders=[str(tmp_path)]),
                       "nature", ["forest"])
    data["chances"] = {"wallhaven": 0.45, "museum": 0.15, "local": 0.2, "game": 0.2}

    weights = wc.source_weights(data)

    assert weights == {"wallhaven": 0.45, "museum": 0.15, "local": 0.2, "game": 0.2}
    assert wc.source_shares(weights) == {"wallhaven": 45, "museum": 15, "local": 20, "game": 20}


def test_new_user_mix_is_wallhaven_75_museum_25():
    data = copy.deepcopy(wc.DEFAULT_SETTINGS)
    assert wc.source_shares(wc.source_weights(data)) == {"wallhaven": 75, "museum": 25}


def test_game_drops_out_without_searches_and_folders(tmp_path):
    data = _data(game_queries=[], game_folders=[])
    assert not wc.source_available(data, "game")
    assert "game" not in wc.source_weights(data)
    assert wc.drop_reason(data, "game") == "Add a game or game folders"

    data["game_folders"] = [str(tmp_path)]
    assert wc.source_available(data, "game")
    assert "game" in wc.source_weights(data)
    assert wc.drop_reason(data, "game") is None


def test_local_drops_out_without_folders(tmp_path):
    data = _data(local_folders=[])
    assert "local" not in wc.source_weights(data)
    assert wc.drop_reason(data, "local") == "Add a folder to use this"

    data["local_folders"] = [str(tmp_path)]
    assert "local" in wc.source_weights(data)
    assert wc.drop_reason(data, "local") is None


def test_wallhaven_drops_out_with_empty_pool():
    data = _with_topic(_data(), "nature", ["  ", ""])
    assert wc.wallhaven_query_pool(data) == []
    assert "wallhaven" not in wc.source_weights(data)
    assert wc.drop_reason(data, "wallhaven") == "Tick a topic with searches"

    _with_topic(data, "space", ["nebula"])
    assert "wallhaven" in wc.source_weights(data)
    assert wc.drop_reason(data, "wallhaven") is None


def test_drop_reason_checks_off_then_empty_then_zero():
    data = _data(local_folders=[])
    data["sources"]["local"] = False
    data["chances"]["local"] = 0
    assert wc.drop_reason(data, "local") == "Off in the tray menu"

    data["sources"]["local"] = True
    assert wc.drop_reason(data, "local") == "Add a folder to use this"

    data["local_folders"] = ["C:/pics"]
    assert wc.drop_reason(data, "local") == "Set above 0%"

    data["chances"]["local"] = 0.1
    assert wc.drop_reason(data, "local") is None
    assert wc.drop_reason(data, "museum") is None


@pytest.mark.parametrize("change", [
    lambda d: d["sources"].update(local=False),
    lambda d: d["chances"].update(local=0),
    lambda d: d.update(local_folders=[]),
])
def test_zero_weight_or_off_source_never_used_as_fallback(monkeypatch, tmp_path, change):
    data = _with_topic(_data(local_folders=[str(tmp_path)]), "nature", ["forest"])
    data["chances"].update(wallhaven=0, museum=1, game=0)
    change(data)
    monkeypatch.setattr(wc.settings, "snapshot", lambda: copy.deepcopy(data))
    calls = []
    monkeypatch.setattr(wc, "fetch_source", lambda source, d: calls.append(source))

    assert wc.get_new_wallpaper() is None
    assert calls == ["museum"]  # wallhaven at 0% and local without a share are not fallbacks


def test_fallback_uses_sources_with_a_share(monkeypatch, tmp_path):
    data = _with_topic(_data(local_folders=[str(tmp_path)]), "nature", ["forest"])
    data["chances"].update(wallhaven=0.5, museum=0.5, local=0.5, game=0)
    monkeypatch.setattr(wc.settings, "snapshot", lambda: copy.deepcopy(data))
    monkeypatch.setattr(wc.random, "choices", lambda population, weights, k: ["museum"])
    calls = []
    monkeypatch.setattr(wc, "fetch_source", lambda source, d: calls.append(source))

    assert wc.get_new_wallpaper() is None
    assert calls == ["museum", "wallhaven", "local"]


def test_nothing_with_a_share_fetches_nothing(monkeypatch):
    data = _data()
    data["chances"]["museum"] = 0
    monkeypatch.setattr(wc.settings, "snapshot", lambda: copy.deepcopy(data))
    monkeypatch.setattr(wc, "fetch_source", lambda source, d: pytest.fail("fetched"))

    assert wc.get_new_wallpaper() is None


@pytest.mark.parametrize("weights", [
    {"a": 1, "b": 1, "c": 1},
    {"a": 0.45, "b": 0.15, "c": 0.2, "d": 0.2},
    {"a": 0.001, "b": 7, "c": 3.3},
    {"a": 2},
])
def test_source_shares_sum_to_100(weights):
    shares = wc.source_shares(weights)
    assert sum(shares.values()) == 100
    assert list(shares) == list(weights)


def test_source_shares_empty_when_total_is_zero():
    assert wc.source_shares({}) == {}
    assert wc.source_shares({"a": 0}) == {}


def test_empty_pool_makes_no_request(monkeypatch):
    monkeypatch.setattr(wc, "safe_get", lambda *a, **kw: pytest.fail("requested"))
    assert wc.fetch_from_wallhaven([]) is None


def _record_requests(monkeypatch, favourites: int) -> list[str]:
    search = {"data": [{"id": "abc", "path": "https://w.wallhaven.cc/full/ab/abc.jpg",
                        "dimension_x": 3840, "dimension_y": 2160, "favorites": favourites}]}
    requested = []

    def fake_get(url, *, params=None, **kw):
        requested.append(url)
        if url.endswith("/search"):
            return wc.Fetched(200, json.dumps(search).encode())
        return wc.Fetched(404, b"")

    monkeypatch.setattr(wc, "safe_get", fake_get)
    monkeypatch.setattr(wc, "load_seen_ids", lambda: set())
    monkeypatch.setattr(wc, "fits_screen", lambda w, h: True)
    return requested


def test_topic_searches_keep_min_favourites_game_searches_skip(monkeypatch):
    few = wc.WALLHAVEN_MIN_FAVORITES - 1
    requested = _record_requests(monkeypatch, few)
    wc.fetch_from_wallhaven(["my own tag"], "random")
    assert requested == ["https://wallhaven.cc/api/v1/search"]  # skipped: too few favourites

    requested = _record_requests(monkeypatch, few)
    wc.fetch_from_wallhaven(["path of exile"], "random", source="game")
    assert requested[-1] == "https://w.wallhaven.cc/full/ab/abc.jpg"  # game searches skip the rule

    requested = _record_requests(monkeypatch, wc.WALLHAVEN_MIN_FAVORITES)
    wc.fetch_from_wallhaven(["my own tag"], "random")
    assert requested[-1] == "https://w.wallhaven.cc/full/ab/abc.jpg"


def test_typed_tag_cannot_change_purity(monkeypatch):
    seen = []

    def fake_get(url, *, params=None, **kw):
        seen.append(params)
        return wc.Fetched(500, b"")

    monkeypatch.setattr(wc, "safe_get", fake_get)
    tag = "x&purity=111&categories=111"
    wc.fetch_from_wallhaven([tag], "random")

    assert seen[0]["q"] == tag
    assert seen[0]["purity"] == "100"
    assert seen[0]["categories"] == "110"
