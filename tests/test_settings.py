"""INV-10: settings.json falls back to defaults on bad values and is never overwritten when broken."""
import copy

import wallpaper_changer as wc


def test_merge_keeps_valid_user_values():
    loaded = {"interval_minutes": 15, "sources": {"museum": False}, "local_folders": ["D:\\Art"]}
    merged = wc._merge_settings(wc.DEFAULT_SETTINGS, loaded)
    assert merged["interval_minutes"] == 15
    assert merged["sources"]["museum"] is False
    assert merged["sources"]["wallhaven"] is True
    assert merged["local_folders"] == ["D:\\Art"]


def test_merge_falls_back_on_wrong_types_and_unknown_keys():
    loaded = {"interval_minutes": "soon", "chances": {"local": -1}, "sources": {"local": 1},
              "local_folders": [3], "surprise": True}
    merged = wc._merge_settings(wc.DEFAULT_SETTINGS, loaded)
    defaults = wc.DEFAULT_SETTINGS
    assert merged["interval_minutes"] == defaults["interval_minutes"]
    assert merged["chances"]["local"] == defaults["chances"]["local"]
    assert merged["sources"]["local"] is defaults["sources"]["local"]
    assert merged["local_folders"] == defaults["local_folders"]
    assert "surprise" not in merged


def test_broken_file_is_kept_and_not_overwritten(tmp_path):
    path = tmp_path / "settings.json"
    settings = wc.Settings(path)  # first run writes the defaults
    good = copy.deepcopy(settings.data)
    path.write_text("{ not json", encoding="utf-8")

    assert settings.reload() is False
    assert settings.data == good
    assert settings.update(lambda d: d.update(interval_minutes=60)) is False
    assert path.read_text(encoding="utf-8") == "{ not json"
