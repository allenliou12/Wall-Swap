"""INV-10: settings.json falls back to defaults on bad values and is never overwritten when broken.

Also the legacy migration: a pre-topics file is upgraded in memory, and written only by save(), which first keeps the
original as settings.json.bak (never overwritten; a failed backup blocks the save).
"""
import copy
import json

import wallpaper_changer as wc

# WALLHAVEN_QUERIES as it was at ff92bfd, kept literally so the grouping can be checked against it
OLD_WALLHAVEN_QUERIES = [
    "landscape 4k", "sunset clouds", "aurora borealis", "cherry blossom japan", "milky way landscape",
    "desert dunes", "foggy mountains", "tropical beach", "mountains", "ocean", "forest", "snow", "rain", "storm",
    "clouds", "sky", "lake", "river", "island", "cave", "glacier", "canyon",
    "cityscape night", "neon city rain", "futuristic city", "cyberpunk alley", "cyberpunk city", "neon lights",
    "skyscraper", "bridge night",
    "nebula", "sci-fi concept art", "star wars", "mass effect", "space station", "eclipse", "space nebula",
    "galaxy", "milky way",
    "digital art fantasy", "concept art environment", "concept art dark", "dragon fire", "dark souls",
    "witcher geralt", "lord of the rings", "pixel art landscape", "cyberpunk girl", "dark fantasy", "dark castle",
    "gothic", "demon", "skull", "raven dark", "dark art", "void", "dark", "shadow", "dark landscape",
    "dark forest", "dark ocean", "dark mountain", "witch", "dark knight", "reaper", "dark angel", "dark warrior",
    "abyss", "ancient ruins", "dungeon", "castle", "ruins", "temple", "cathedral", "lighthouse",
    "synthwave", "vaporwave", "glitch art", "fractal art", "dark abstract", "abstract dark", "smoke dark",
    "dark minimal", "monochrome", "noir", "oil painting", "watercolor", "digital painting", "surreal art",
    "surrealism", "minimalist",
    "moon", "moonlight", "blood moon", "full moon", "crescent moon", "lunar", "night sky", "starry night",
    "dark sky",
    "anime scenery rain", "demon slayer", "jujutsu kaisen", "chainsaw man", "one piece", "evangelion",
    "evangelion unit", "solo leveling", "frieren", "spy x family", "studio ghibli", "akira", "bleach anime",
    "naruto", "dragon ball",
    "elden ring", "zelda breath of the wild", "cyberpunk 2077 night city", "ghost of tsushima", "hollow knight",
    "final fantasy", "god of war", "horizon zero dawn", "red dead redemption 2", "sekiro", "hades game",
    "nier automata", "league of legends", "the last of us", "persona 5", "genshin impact", "resident evil",
    "skyrim", "fallout", "cyber", "hologram",
    "blade runner", "dune", "arcane", "batman", "spider-verse",
]

# A settings.json as the old app (ff92bfd) wrote it: no topics, no chances.wallhaven, no game_folders key
LEGACY_FILE = {
    "interval_minutes": 60,
    "sources": {"wallhaven": True, "game": True, "museum": False, "local": True},
    "chances": {"local": 0.2, "game": 0.2, "museum": 0.15},
    "game_name": "Path of Exile",
    "game_queries": ["path of exile", "path of exile 2"],
    "local_folders": ["D:\\Art"],
}


def write_legacy(path, data=LEGACY_FILE) -> bytes:
    raw = json.dumps(data, indent=4).encode("utf-8")
    path.write_bytes(raw)
    return raw


def bak_of(path):
    return path.with_name(path.name + ".bak")


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

    # topics of the wrong type fall back whole; a bad searches list falls back per topic; [] is kept;
    # an unknown topic id is dropped
    assert wc._merge_settings(defaults, {"topics": ["nature"]})["topics"] == defaults["topics"]
    topics = wc._merge_settings(defaults, {"topics": {
        "nature": {"enabled": False, "searches": "forest"},
        "space": {"searches": []},
        "my_topic": {"enabled": True, "searches": ["x"]},
    }})["topics"]
    assert topics["nature"] == {"enabled": False, "searches": defaults["topics"]["nature"]["searches"]}
    assert topics["space"]["searches"] == []
    assert "my_topic" not in topics
    assert list(topics) == list(wc.TOPIC_LABELS)


def test_broken_file_is_kept_and_not_overwritten(tmp_path):
    path = tmp_path / "settings.json"
    settings = wc.Settings(path)  # first run writes the defaults
    good = copy.deepcopy(settings.data)
    path.write_text("{ not json", encoding="utf-8")

    assert settings.reload() is False
    assert settings.problem == "broken"
    assert settings.data == good
    assert settings.update(lambda d: d.update(interval_minutes=60)) is False
    assert path.read_text(encoding="utf-8") == "{ not json"


def test_non_object_json_is_treated_as_broken(tmp_path):
    path = tmp_path / "settings.json"
    settings = wc.Settings(path)
    good = copy.deepcopy(settings.data)

    for text in ("[1, 2]", "null", '"hello"', "3"):
        path.write_text(text, encoding="utf-8")
        assert settings.reload() is False
        assert settings.problem == "broken"
        assert settings.data == good
        assert settings.update(lambda d: d.update(interval_minutes=60)) is False
        assert path.read_text(encoding="utf-8") == text

    # no case: a good object reads fine and clears the problem
    path.write_text(json.dumps({"interval_minutes": 15}), encoding="utf-8")
    assert settings.reload() is True
    assert settings.problem is None
    assert settings.data["interval_minutes"] == 15


def test_migrate_fills_old_effective_values():
    old = {k: v for k, v in LEGACY_FILE.items() if k != "local_folders"}
    assert wc.is_legacy_settings(old) is True
    migrated = wc.migrate_settings(old)

    poe = str(wc.Path.home() / "Pictures" / "Path of Exile 2")
    assert migrated["game_folders"] == [poe]
    assert migrated["local_folders"] == [poe]
    assert migrated["game_name"] == "Path of Exile"
    assert migrated["game_queries"] == ["path of exile", "path of exile 2"]
    assert migrated["interval_minutes"] == 60
    assert migrated["sources"]["museum"] is False
    assert migrated["chances"] == {"wallhaven": 0.45, "museum": 0.15, "local": 0.2, "game": 0.2}
    assert list(migrated["topics"]) == list(wc.TOPIC_LABELS)
    assert all(t["enabled"] for t in migrated["topics"].values())
    assert sum(len(t["searches"]) for t in migrated["topics"].values()) == 141
    assert wc.is_legacy_settings(migrated) is False


def test_migrate_wallhaven_gets_old_remainder():
    custom = wc.migrate_settings({"chances": {"local": 0.1, "game": 0.05, "museum": 0.3}})
    assert custom["chances"] == {"wallhaven": 0.55, "museum": 0.3, "local": 0.1, "game": 0.05}

    for full in ({"local": 0.5, "game": 0.3, "museum": 0.2}, {"local": 1, "game": 1, "museum": 1}):
        assert wc.migrate_settings({"chances": full})["chances"]["wallhaven"] == 0

    # an old file with only some chances uses the old defaults for the rest
    partial = wc.migrate_settings({"chances": {"museum": 0.35}})
    assert partial["chances"] == {"wallhaven": 0.25, "museum": 0.35, "local": 0.2, "game": 0.2}


def test_legacy_topic_searches_are_old_list_exactly_once():
    assert len(OLD_WALLHAVEN_QUERIES) == 141 == len(set(OLD_WALLHAVEN_QUERIES))
    grouped = [q for qs in wc.LEGACY_TOPIC_SEARCHES.values() for q in qs]
    assert len(grouped) == 141
    assert sorted(grouped) == sorted(OLD_WALLHAVEN_QUERIES)
    assert list(wc.LEGACY_TOPIC_SEARCHES) == list(wc.TOPIC_LABELS)
    counts = {t: len(qs) for t, qs in wc.LEGACY_TOPIC_SEARCHES.items()}
    assert counts == {"nature": 23, "space": 7, "dark_fantasy": 30, "cities": 11, "abstract": 17,
                      "moon_night": 9, "anime": 15, "games": 22, "movies": 7}


def test_import_time_load_does_not_write_legacy_file(tmp_path):
    path = tmp_path / "settings.json"
    raw = write_legacy(path)

    settings = wc.Settings(path)

    assert path.read_bytes() == raw
    assert not bak_of(path).exists()
    assert settings.legacy is True and settings.created is False
    assert settings.data["chances"]["wallhaven"] == 0.45
    # reading it again (the timer's reload) still writes nothing
    assert settings.reload() is True
    assert path.read_bytes() == raw


def test_persist_migration_writes_bak_once_and_is_idempotent(tmp_path):
    path = tmp_path / "settings.json"
    raw = write_legacy(path)
    settings = wc.Settings(path)

    assert settings.persist_migration() is True
    assert bak_of(path).read_bytes() == raw
    written = json.loads(path.read_text(encoding="utf-8"))
    assert "topics" in written and written["chances"]["wallhaven"] == 0.45
    assert written["game_folders"] == settings.data["game_folders"]
    assert settings.legacy is False
    assert not path.with_name("settings.json.bak.tmp").exists()

    after_first = path.read_bytes()
    assert settings.persist_migration() is True
    assert wc.Settings(path).persist_migration() is True
    assert path.read_bytes() == after_first
    assert bak_of(path).read_bytes() == raw


def test_existing_bak_is_never_overwritten(tmp_path):
    path = tmp_path / "settings.json"
    bak_of(path).write_bytes(b"the first original")
    write_legacy(path)

    settings = wc.Settings(path)
    assert settings.persist_migration() is True
    assert bak_of(path).read_bytes() == b"the first original"
    assert "topics" in json.loads(path.read_text(encoding="utf-8"))


def test_backup_failure_refuses_save_and_keeps_original(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    raw = write_legacy(path)
    settings = wc.Settings(path)
    migrated = copy.deepcopy(settings.data)

    def no_rename(src, dst):
        raise PermissionError("disk says no")
    monkeypatch.setattr(wc.os, "rename", no_rename)

    assert settings.persist_migration() is False
    assert settings.problem == "backup"
    assert settings.update(lambda d: d.update(interval_minutes=15)) is False
    assert settings.problem == "backup"
    assert path.read_bytes() == raw
    assert not bak_of(path).exists()
    assert settings.legacy is True
    assert settings.data == migrated  # migrated data stays in memory, without the refused change

    # yes case: once the backup can be made, the same change goes through
    monkeypatch.undo()
    assert settings.update(lambda d: d.update(interval_minutes=15)) is True
    assert settings.problem is None
    assert bak_of(path).read_bytes() == raw


def test_first_update_on_legacy_file_backs_up_first(tmp_path):
    path = tmp_path / "settings.json"
    raw = write_legacy(path)
    settings = wc.Settings(path)

    assert settings.update(lambda d: d["sources"].update(museum=True)) is True
    assert bak_of(path).read_bytes() == raw
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["sources"]["museum"] is True
    assert written["chances"]["wallhaven"] == 0.45
    assert len(written["topics"]) == 9


def test_new_user_defaults_are_neutral(tmp_path):
    path = tmp_path / "settings.json"
    settings = wc.Settings(path)

    assert settings.created is True and settings.legacy is False
    assert json.loads(path.read_text(encoding="utf-8")) == settings.data == wc.DEFAULT_SETTINGS
    assert not bak_of(path).exists()
    d = settings.data
    assert d["game_name"] == "" and d["game_queries"] == []
    assert d["local_folders"] == [] and d["game_folders"] == []
    assert all(d["sources"].values())
    assert d["chances"] == {"wallhaven": 0.45, "museum": 0.15, "local": 0.2, "game": 0.2}
    ticked = [q for t in d["topics"].values() if t["enabled"] for q in t["searches"]]
    every = [q for t in d["topics"].values() for q in t["searches"]]
    assert len(ticked) == 17 and len(every) == 25
    assert set(every) <= set(OLD_WALLHAVEN_QUERIES)
    assert wc.is_legacy_settings(d) is False

    # no case: an existing file is not "created"
    assert wc.Settings(path).created is False


def test_clean_search_rejects_empty_duplicate_too_long():
    existing = ["Dark Fantasy", "moon"]
    assert wc.clean_search("  neon   city\train ", existing) == "neon city rain"
    assert wc.clean_search("Blade Runner", existing) == "Blade Runner"  # casing kept
    assert wc.clean_search("", existing) is None
    assert wc.clean_search("   \t ", existing) is None
    assert wc.clean_search("dark  fantasy", existing) is None
    assert wc.clean_search("MOON", existing) is None
    assert wc.clean_search("x" * wc.MAX_SEARCH_LENGTH, existing) == "x" * wc.MAX_SEARCH_LENGTH
    assert wc.clean_search("x" * (wc.MAX_SEARCH_LENGTH + 1), existing) is None


def test_settings_patch_per_setting_and_folder_changes():
    before = copy.deepcopy(wc.DEFAULT_SETTINGS)
    before["local_folders"] = ["C:\\A", "C:\\B"]
    before["game_folders"] = ["C:\\G"]
    assert wc.settings_patch(before, copy.deepcopy(before)) == {"set": [], "add_folders": [], "remove_folders": []}

    after = copy.deepcopy(before)
    after["chances"]["museum"] = 0.3
    after["topics"]["anime"]["enabled"] = True
    after["topics"]["space"]["searches"].append("eclipse")
    after["game_name"] = "Hades"
    after["local_folders"] = ["C:\\B", "C:\\New"]
    after["game_folders"] = []
    patch = wc.settings_patch(before, after)

    assert sorted(patch["set"], key=str) == sorted([
        (("chances", "museum"), 0.3),
        (("topics", "anime", "enabled"), True),
        (("topics", "space", "searches"), after["topics"]["space"]["searches"]),
        (("game_name",), "Hades"),
    ], key=str)
    assert patch["add_folders"] == ["C:\\New"]
    assert sorted(patch["remove_folders"]) == ["C:\\A", "C:\\G"]

    # apply_patch: removal hits both lists, adds are not doubled, a path that is gone is skipped
    data = copy.deepcopy(before)
    data["local_folders"].append("C:\\G")
    data["local_folders"].append("C:\\New")
    del data["topics"]["anime"]
    wc.apply_patch(data, patch)
    assert data["chances"]["museum"] == 0.3
    assert data["game_name"] == "Hades"
    assert data["topics"]["space"]["searches"][-1] == "eclipse"
    assert "anime" not in data["topics"]
    assert data["local_folders"] == ["C:\\B", "C:\\New"]
    assert data["game_folders"] == []


def test_tray_and_window_changes_both_survive(tmp_path):
    settings = wc.Settings(tmp_path / "settings.json")
    settings.update(lambda d: d["local_folders"].extend(["C:\\Old", "C:\\Keep"]))
    snapshot = settings.snapshot()  # the window opens

    # tray, while the window is open: museum off and a folder added
    settings.update(lambda d: d["sources"].update(museum=False))
    settings.update(lambda d: d["local_folders"].append("C:\\FromTray"))

    # window Save: Wallhaven weight changed and a folder removed
    form = copy.deepcopy(snapshot)
    form["chances"]["wallhaven"] = 0.7
    form["local_folders"].remove("C:\\Old")
    patch = wc.settings_patch(snapshot, form)
    assert settings.update(lambda d: wc.apply_patch(d, patch)) is True

    saved = json.loads(settings.path.read_text(encoding="utf-8"))
    assert saved["sources"]["museum"] is False
    assert saved["chances"]["wallhaven"] == 0.7
    assert saved["local_folders"] == ["C:\\Keep", "C:\\FromTray"]
    # snapshot is a copy: changing it never touched the live settings
    snapshot["interval_minutes"] = 999
    assert settings.data["interval_minutes"] != 999


def test_persist_migration_rereads_and_keeps_a_later_edit(tmp_path):
    path = tmp_path / "settings.json"
    write_legacy(path, {**LEGACY_FILE, "game_name": "First", "interval_minutes": 30})
    settings = wc.Settings(path)

    edited = write_legacy(path, {**LEGACY_FILE, "game_name": "Second", "interval_minutes": 120})
    assert settings.persist_migration() is True
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["game_name"] == "Second" and written["interval_minutes"] == 120
    assert bak_of(path).read_bytes() == edited  # the .bak holds the bytes that were replaced


def test_persist_migration_never_touches_a_file_broken_meanwhile(tmp_path):
    path = tmp_path / "settings.json"
    write_legacy(path)
    settings = wc.Settings(path)

    path.write_text("null", encoding="utf-8")
    assert settings.persist_migration() is False
    assert settings.problem == "broken"
    assert path.read_text(encoding="utf-8") == "null"
    assert not bak_of(path).exists()


def test_failed_write_refuses_save_and_keeps_memory(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    settings = wc.Settings(path)
    original = path.read_bytes()
    before = copy.deepcopy(settings.data)

    def no_replace(src, dst):
        raise PermissionError("read-only")
    monkeypatch.setattr(wc.os, "replace", no_replace)

    assert settings.update(lambda d: d.update(interval_minutes=120)) is False
    assert settings.problem == "write"
    assert settings.data == before
    assert path.read_bytes() == original
    assert not path.with_suffix(".json.tmp").exists()

    # yes case: once writing works again the change is saved
    monkeypatch.undo()
    assert settings.update(lambda d: d.update(interval_minutes=120)) is True
    assert settings.problem is None


def test_bak_that_is_not_a_file_refuses_save(tmp_path):
    path = tmp_path / "settings.json"
    raw = write_legacy(path)
    bak_of(path).mkdir()
    settings = wc.Settings(path)

    assert settings.persist_migration() is False
    assert settings.problem == "backup"
    assert path.read_bytes() == raw
    assert bak_of(path).is_dir()
