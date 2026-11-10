"""
WallSwap - Fresh Desktop Wallpapers on Autopilot
A lightweight system tray app that sets random screen-sized wallpapers from
Wallhaven, The Met's public-domain paintings and your own folders as your
Windows desktop and lock screen background.

Usage (see README.md):
    uv sync
    uv run wallpaper_changer.py
"""

import asyncio
import collections
import copy
import ctypes
import ctypes.wintypes
import dataclasses
import filecmp
import io
import json
import logging
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import warnings
import webbrowser
from datetime import datetime
from pathlib import Path, PureWindowsPath
from tkinter import TclError, filedialog  # plain tkinter opens no window on import, so tests stay headless
from urllib.parse import urljoin, urlsplit

try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("=" * 60)
    print("  Missing dependencies! Run:")
    print("  pip install pystray Pillow requests")
    print("=" * 60)
    sys.exit(1)

try:
    import requests
except ImportError:
    print("=" * 60)
    print("  Missing dependency! Run:")
    print("  pip install requests")
    print("=" * 60)
    sys.exit(1)

# ─── Configuration ────────────────────────────────────────────
APP_VERSION = "1.0.2"  # keep equal to pyproject.toml's version (a test checks); shown in the tray, window and log
# A PyInstaller build sets sys.frozen; its bundled files (the icon) unpack to sys._MEIPASS, not next to this file
FROZEN = getattr(sys, "frozen", False)
SCRIPT_DIR = Path(__file__).resolve().parent
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", SCRIPT_DIR)) if FROZEN else SCRIPT_DIR
ICON_PATH = BUNDLE_DIR / "wallswap.ico"
WALLPAPER_DIR = Path.home() / "Pictures" / "WallSwap"
LOG_FILE = WALLPAPER_DIR / "wallswap.log"
HISTORY_FILE = WALLPAPER_DIR / "seen_ids.txt"
BLOCKED_FILE = WALLPAPER_DIR / "blocked.txt"  # Never Show Again: one image per line, never trimmed
SETTINGS_FILE = WALLPAPER_DIR / "settings.json"
FAVOURITES_DIR = WALLPAPER_DIR / "Favourites"
# The most "Match my screen" ever asks an image to be. A smaller screen asks only for its own size (see
# min_size), so a 1080p screen can use 1080p images; a bigger one still accepts 1440p unless 4K is picked.
MIN_WIDTH = 2560
MIN_HEIGHT = 1440
# The min_resolution setting: the smallest image used. "auto" follows the screen; the rest are fixed sizes.
RESOLUTION_SIZES = {"1080p": (1920, 1080), "1440p": (2560, 1440), "4k": (3840, 2160)}
RESOLUTION_LABELS = {"auto": "Match my screen", "1080p": "1080p", "1440p": "1440p", "4k": "4K"}  # display order
MAX_WALLPAPERS = 50         # keep only the most recent on disk
MAX_SEEN_IDS = 5000         # dedup history cap (oldest dropped first)
USER_AGENT = "WallSwap/1.0 (Windows Desktop Wallpaper Changer)"
# General Wallhaven searches skip wallpapers with fewer favourites than this (random-sorted
# results are often low-rated). Not applied to the favourite-game searches: few game
# wallpapers exist and most have only a handful of favourites.
WALLHAVEN_MIN_FAVORITES = 30

# Download safety limits: only fetch over https from these sites (and their subdomains),
# cap how much a single response may send, and give up on downloads that drag on
ALLOWED_HOSTS = ("wallhaven.cc", "metmuseum.org")
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024   # images
MAX_API_BYTES = 5 * 1024 * 1024         # JSON responses
DOWNLOAD_DEADLINE = 120                 # seconds per request, in total
MAX_IMAGE_PIXELS = 64_000_000           # ~8000x8000; a 4K wallpaper is ~8 million pixels

# Start with Windows: the one file WallSwap writes outside its own folder (INV-16)
STARTUP_SHORTCUT_NAME = "WallSwap.lnk"
# Hide the PowerShell console that writes the shortcut; the flag exists only on Windows, 0 elsewhere
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
MAX_WINDOWS_PATH = 260  # MAX_PATH: the Windows folder always fits; a longer answer is treated as no answer

# User settings live in SETTINGS_FILE (created from these defaults on first run) and can be
# changed from the tray menu, the Settings window or by editing the file.
#   chances: relative weight of each source (they need not add up to 1); a source that is
#            turned off, at 0 or has nothing to use gets no share
#   topics:  Wallhaven search groups; every search of a ticked topic is equally likely
#   game_*:  a dedicated Wallhaven share for one favourite game. game_folders hold the game's
#            images, used for its share once all of its Wallhaven wallpapers have been shown
#            (so other folders can't dilute it)
#   local_folders: your own image folders (top-level images only, not subfolders)
#   min_resolution: a key of RESOLUTION_LABELS; anything else counts as "auto"
DEFAULT_SETTINGS = {
    "interval_minutes": 30,
    "min_resolution": "auto",
    "sources": {"wallhaven": True, "game": True, "museum": True, "local": True},
    "chances": {"wallhaven": 0.45, "museum": 0.15, "local": 0.2, "game": 0.2},
    "topics": {
        "nature": {"enabled": True,
                   "searches": ["landscape 4k", "mountains", "forest", "ocean", "aurora borealis"]},
        "space": {"enabled": True, "searches": ["nebula", "galaxy", "milky way"]},
        "dark_fantasy": {"enabled": False, "searches": ["dark fantasy", "gothic"]},
        "cities": {"enabled": True, "searches": ["cityscape night", "neon city rain", "futuristic city"]},
        "abstract": {"enabled": True, "searches": ["minimalist", "synthwave", "fractal art"]},
        "moon_night": {"enabled": True, "searches": ["moon", "night sky", "starry night"]},
        "anime": {"enabled": False, "searches": ["anime scenery rain", "studio ghibli"]},
        "games": {"enabled": False, "searches": ["elden ring", "hollow knight"]},
        "movies": {"enabled": False, "searches": ["blade runner", "dune"]},
    },
    "exclude_words": [],
    "game_name": "",
    "game_queries": [],
    "local_folders": [],
    "game_folders": [],
}
# DEFAULT_SETTINGS as it was before topics (ff92bfd), kept exactly: migrate_settings reads an old
# settings.json through it, so the upgraded file holds the values the old app really used
LEGACY_DEFAULTS = {
    "interval_minutes": 30,
    "sources": {"wallhaven": True, "game": True, "museum": True, "local": True},
    "chances": {"local": 0.2, "game": 0.2, "museum": 0.15},
    "game_name": "Path of Exile",
    "game_queries": ["path of exile", "path of exile 2"],
    "local_folders": [str(Path.home() / "Pictures" / "Path of Exile 2")],
    # Folders of the favourite game's images, used for the game's share once all of its
    # Wallhaven wallpapers have been shown (so other folders can't dilute it)
    "game_folders": [str(Path.home() / "Pictures" / "Path of Exile 2")],
}
TOPIC_LABELS = {  # topic id -> label, in display order; the ids are fixed settings.json keys
    "nature": "Nature & landscapes",
    "space": "Space",
    "dark_fantasy": "Dark fantasy & gothic",
    "cities": "Cities & cyberpunk",
    "abstract": "Abstract & minimal",
    "moon_night": "Moon & night",
    "anime": "Anime",
    "games": "Games",
    "movies": "Movies & series",
}
# Typed searches only ever fill Wallhaven's q; the cap keeps a pasted paragraph out of it
MAX_SEARCH_LENGTH = 100
# Excluded words go into every Wallhaven q as -word. Few and short, so q stays small; one plain word each,
# because that is the only form Wallhaven documents (-tagname).
MAX_EXCLUDE_WORDS = 10
MAX_EXCLUDE_LENGTH = 30
EXCLUDE_WORD = re.compile(r"\w[\w-]*")
# Long enough for any real game title, short enough to fit the tray menu label
MAX_GAME_NAME_LENGTH = 60
INTERVAL_CHOICES = [15, 30, 60, 120]  # minutes, offered in the tray menu
# A change that was skipped (a game in front) or failed (offline) is tried again soon instead of a whole
# interval later. Failed downloads slow down after a few tries so a PC left offline doesn't fill the log.
RETRY_SECONDS = 60
SLOW_RETRY_SECONDS = 300
FAST_RETRIES = 5
HISTORY_LENGTH = 20  # how many earlier wallpapers Previous can step back through (this run only)
UI_POLL_MS = 100  # how often the Tk thread runs calls queued from the tray; fast enough to feel instant, cheap when idle
SOURCE_LABELS = {
    "wallhaven": "Wallhaven",
    "game": "Wallhaven (favourite game)",
    "museum": "The Met",
    "local": "Local folder",
}

LOCAL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
LOCAL_HISTORY_FILE = WALLPAPER_DIR / "seen_local.txt"

# Public-domain paintings from The Metropolitan Museum of Art (no API key needed)
MUSEUM_API = "https://collectionapi.metmuseum.org/public/collection"
MUSEUM_MIN_RATIO = 1.3      # skip paintings too tall/narrow to fill a 16:9 screen
MUSEUM_MAX_RATIO = 2.5      # ...or too wide (would crop most of the painting)
MUSEUM_DEPARTMENTS = [      # search filters: European Paintings, and paintings in the American Wing
    {"departmentId": 11},
    {"departmentId": 1, "medium": "Paintings"},
]
MUSEUM_QUERIES = [
    "ruins",
    "castle",
    "gothic",
    "cathedral",
    "abbey",
    "storm",
    "shipwreck",
    "moonlight",
    "night",
    "volcano",
    "mountain landscape",
    "waterfall",
    "fog",
    "battle",
    "hell",
    "apocalypse",
    "Saint Michael",
    "romantic landscape",
    "Hudson River School",
]

# The searches of the old single Wallhaven list, grouped by topic (each exactly once). An
# upgraded settings.json gets all of them, all ticked, so the old mix is unchanged.
LEGACY_TOPIC_SEARCHES = {
    "nature": [
        "landscape 4k", "sunset clouds", "aurora borealis", "cherry blossom japan", "milky way landscape",
        "desert dunes", "foggy mountains", "tropical beach", "mountains", "ocean", "forest", "snow", "rain",
        "storm", "clouds", "sky", "lake", "river", "island", "cave", "glacier", "canyon", "lighthouse",
    ],
    "space": [
        "nebula", "sci-fi concept art", "space station", "eclipse", "space nebula", "galaxy", "milky way",
    ],
    "dark_fantasy": [
        "digital art fantasy", "concept art environment", "concept art dark", "dragon fire", "dark fantasy",
        "dark castle", "gothic", "demon", "skull", "raven dark", "dark art", "void", "dark", "shadow",
        "dark landscape", "dark forest", "dark ocean", "dark mountain", "witch", "dark knight", "reaper",
        "dark angel", "dark warrior", "abyss", "ancient ruins", "dungeon", "castle", "ruins", "temple",
        "cathedral",
    ],
    "cities": [
        "cityscape night", "neon city rain", "futuristic city", "cyberpunk alley", "cyberpunk city",
        "neon lights", "skyscraper", "bridge night", "cyberpunk girl", "cyber", "hologram",
    ],
    "abstract": [
        "synthwave", "vaporwave", "glitch art", "fractal art", "dark abstract", "abstract dark", "smoke dark",
        "dark minimal", "monochrome", "noir", "oil painting", "watercolor", "digital painting", "surreal art",
        "surrealism", "minimalist", "pixel art landscape",
    ],
    "moon_night": [
        "moon", "moonlight", "blood moon", "full moon", "crescent moon", "lunar", "night sky", "starry night",
        "dark sky",
    ],
    "anime": [
        "anime scenery rain", "demon slayer", "jujutsu kaisen", "chainsaw man", "one piece", "evangelion",
        "evangelion unit", "solo leveling", "frieren", "spy x family", "studio ghibli", "akira", "bleach anime",
        "naruto", "dragon ball",
    ],
    "games": [
        "elden ring", "zelda breath of the wild", "cyberpunk 2077 night city", "ghost of tsushima",
        "hollow knight", "final fantasy", "god of war", "horizon zero dawn", "red dead redemption 2", "sekiro",
        "hades game", "nier automata", "league of legends", "the last of us", "persona 5", "genshin impact",
        "resident evil", "skyrim", "fallout", "mass effect", "dark souls", "witcher geralt",
    ],
    "movies": [
        "blade runner", "dune", "arcane", "batman", "spider-verse", "star wars", "lord of the rings",
    ],
}
# The four sources in the order the Settings window lists them, and their names there
SOURCE_ORDER = ("wallhaven", "museum", "local", "game")
MIX_LABELS = {"wallhaven": "Wallhaven", "museum": "Met paintings", "local": "My folders", "game": "Favourite game"}

# ─── Setup ────────────────────────────────────────────────────
WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)

# Refuse huge images outright instead of only warning: decoding a giant scan could use
# gigabytes of memory. Image.open then raises, and the image is skipped.
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
warnings.simplefilter("error", Image.DecompressionBombWarning)

from logging.handlers import RotatingFileHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=2, encoding="utf-8"),
        # The windowed .exe has no console: sys.stderr is None there, so log only to the file
        *([logging.StreamHandler()] if sys.stderr is not None else []),
    ],
)
log = logging.getLogger("WallSwap")


# ─── Settings ─────────────────────────────────────────────────
def _merge_settings(defaults, loaded):
    """Overlay user values on the defaults, ignoring unknown keys and wrong types."""
    if isinstance(defaults, dict):
        if not isinstance(loaded, dict):
            return copy.deepcopy(defaults)
        return {k: _merge_settings(v, loaded.get(k, v)) for k, v in defaults.items()}
    if isinstance(defaults, bool):
        return loaded if isinstance(loaded, bool) else defaults
    if isinstance(defaults, (int, float)):
        ok = isinstance(loaded, (int, float)) and not isinstance(loaded, bool) and loaded >= 0
        return loaded if ok else defaults
    if isinstance(defaults, list):
        ok = isinstance(loaded, list) and all(isinstance(x, str) for x in loaded)
        return list(loaded) if ok else list(defaults)
    return loaded if isinstance(loaded, type(defaults)) else defaults


def is_legacy_settings(loaded: dict) -> bool:
    """A settings.json written before topics existed (it needs migrate_settings)."""
    return "topics" not in loaded


def migrate_settings(old: dict) -> dict:
    """The new-format settings that give exactly the mix the old app used for this file."""
    d = _merge_settings(LEGACY_DEFAULTS, old)  # what the old app read, defaults included
    chances = d["chances"]
    # The old app gave general Wallhaven whatever the other chances left over
    chances["wallhaven"] = round(max(0.0, 1 - (chances["local"] + chances["game"] + chances["museum"])), 4)
    d["topics"] = {t: {"enabled": True, "searches": list(s)} for t, s in LEGACY_TOPIC_SEARCHES.items()}
    return _merge_settings(DEFAULT_SETTINGS, d)


def clean_search(text: str, existing: list[str]) -> str | None:
    """The search as it should be stored, or None if it's empty, too long or already there."""
    cleaned = " ".join(text.split())
    if not cleaned or len(cleaned) > MAX_SEARCH_LENGTH:
        return None
    if cleaned.casefold() in {" ".join(e.split()).casefold() for e in existing}:
        return None
    return cleaned


def exclude_word_problem(text: str, existing: list[str]) -> str | None:
    """Why text can't be added to the excluded words, or None when it can."""
    word = text.strip().lstrip("-+").strip()
    if not word:
        return "Empty"
    if len(word.split()) > 1:
        return "One word at a time"
    if len(word) > MAX_EXCLUDE_LENGTH:
        return "Too long"
    if not EXCLUDE_WORD.fullmatch(word):
        return "Letters, numbers, - and _ only"
    if word.casefold() in {e.casefold() for e in existing}:
        return "Already there"
    if len(existing) >= MAX_EXCLUDE_WORDS:
        return f"{MAX_EXCLUDE_WORDS} words at most"
    return None


def clean_exclude_word(text: str, existing: list[str]) -> str | None:
    """The excluded word as it should be stored, or None if it can't be added (exclude_word_problem says why)."""
    if exclude_word_problem(text, existing):
        return None
    return text.strip().lstrip("-+").strip()


def wallhaven_q(query: str, exclude: list[str]) -> str:
    """Wallhaven's q for a search: the search itself, then -word for each excluded word.

    Words are checked again here, because settings.json can be edited by hand: anything that isn't a plain
    word is left out, so an excluded "word" can never add its own search syntax.
    """
    words = [w for w in dict.fromkeys(exclude) if EXCLUDE_WORD.fullmatch(w) and len(w) <= MAX_EXCLUDE_LENGTH]
    return query + "".join(f" -{w}" for w in words[:MAX_EXCLUDE_WORDS])


def _setting_at(data: dict, path: tuple):
    """The value at path inside data, or KeyError/TypeError if it isn't there."""
    for key in path:
        data = data[key]
    return data


def settings_patch(before: dict, after: dict) -> dict:
    """What a form changed, setting by setting, so applying it keeps other changes made meanwhile.

    Folders are listed as adds and removes, not whole lists, for the same reason.
    """
    paths = [("interval_minutes",), ("min_resolution",), ("exclude_words",), ("game_name",), ("game_queries",)]
    paths += [("chances", s) for s in before["chances"]]
    paths += [("topics", t, f) for t in before["topics"] for f in ("enabled", "searches")]
    changes = []
    for path in paths:
        try:
            value = _setting_at(after, path)
        except (KeyError, TypeError):
            continue  # the form doesn't hold this setting
        if value != _setting_at(before, path):
            changes.append((path, copy.deepcopy(value)))

    local = after.get("local_folders", before["local_folders"])
    game = after.get("game_folders", before["game_folders"])
    kept = set(local) | set(game)
    return {
        "set": changes,
        "add_folders": [f for f in local if f not in before["local_folders"]],
        "remove_folders": [f for f in dict.fromkeys(before["local_folders"] + before["game_folders"])
                           if f not in kept],
    }


def apply_patch(data: dict, patch: dict) -> None:
    """Apply a settings_patch to settings data in place (no I/O)."""
    for path, value in patch["set"]:
        try:
            parent = _setting_at(data, path[:-1])
        except (KeyError, TypeError):
            continue  # the setting no longer exists
        if isinstance(parent, dict) and path[-1] in parent:
            parent[path[-1]] = copy.deepcopy(value)
    for folder in patch["add_folders"]:
        if folder not in data["local_folders"]:
            data["local_folders"].append(folder)
    for folder in patch["remove_folders"]:
        # A removed folder leaves both lists, as removing it from the tray does
        for key in ("local_folders", "game_folders"):
            data[key][:] = [f for f in data[key] if f != folder]


class Settings:
    """settings.json, shared by the tray menu and the wallpaper changer."""

    def __init__(self, path: Path):
        self.path = path
        # Re-entrant: update() holds it while calling reload() and save(), and the
        # wallpaper thread's reload() must wait for a tray change to finish saving
        self.lock = threading.RLock()
        self.data = copy.deepcopy(DEFAULT_SETTINGS)
        self.created = False      # reload found no file and wrote the defaults (first run)
        self.legacy = False       # data was migrated from an old-format file not yet written back
        self._legacy_raw = None   # that file's bytes, for settings.json.bak
        self.problem = None       # why the last read or save failed: "broken" or "backup"
        self.reload()

    def reload(self) -> bool:
        """Re-read the file. On a broken file, keep the current settings and return False.

        An old-format file is migrated in memory only; save() writes it (after backing it up).
        """
        with self.lock:
            if not self.path.exists():
                self.data = copy.deepcopy(DEFAULT_SETTINGS)
                self.legacy, self._legacy_raw, self.problem = False, None, None
                self.created = True
                self.save()
                return True
            try:
                raw = self.path.read_bytes()
                loaded = json.loads(raw.decode("utf-8"))
                if not isinstance(loaded, dict):
                    raise ValueError(f"expected a JSON object, got {type(loaded).__name__}")
            except (OSError, ValueError) as e:
                log.warning(f"Can't read {self.path.name}, keeping previous settings: {e}")
                self.problem = "broken"
                return False
            if is_legacy_settings(loaded):
                self.data = migrate_settings(loaded)
                self.legacy, self._legacy_raw = True, raw
            else:
                self.data = _merge_settings(DEFAULT_SETTINGS, loaded)
                self.legacy, self._legacy_raw = False, None
            self.problem = None
            return True

    def save(self) -> bool:
        """Write via a temp file so a crash mid-save can't leave a half-written file.

        Before the first write over an old-format file, its original bytes go to settings.json.bak
        (never overwritten, so it always holds the first original). If that backup or the write
        fails, settings.json is left as it was, `problem` says why and this returns False.
        """
        with self.lock:
            if self.legacy:
                bak = self.path.with_name(self.path.name + ".bak")
                bak_tmp = self.path.with_name(self.path.name + ".bak.tmp")
                error = None
                if not bak.exists():
                    try:
                        bak_tmp.write_bytes(self._legacy_raw)
                        os.rename(bak_tmp, bak)  # on Windows this refuses to replace an existing .bak
                    except FileExistsError:
                        pass  # a .bak appeared meanwhile: keep that one (checked below)
                    except OSError as e:
                        error = e
                    try:
                        bak_tmp.unlink(missing_ok=True)
                    except OSError:
                        pass  # only a leftover temp file; harmless, and the next save retries
                if error is None and not bak.is_file():
                    error = f"{bak.name} exists but is not a file"  # e.g. a folder: no copy is kept
                if error is not None:
                    # HZ-2: absorbed so the tray keeps running, but logged, and the save is
                    # refused so the original is never lost without a copy
                    log.warning(f"Can't back up {self.path.name} to {bak.name}, not saving: {error}")
                    self.problem = "backup"
                    return False
            tmp = self.path.with_suffix(".json.tmp")
            try:
                tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
                os.replace(tmp, self.path)
            except OSError as e:
                # HZ-2: absorbed so the tray keeps running (e.g. a read-only settings.json), but
                # logged, and the caller is told the save didn't happen
                log.warning(f"Can't write {self.path.name}, nothing saved: {e}")
                self.problem = "write"
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass  # only a leftover temp file; the warning above already says why
                return False
            self.legacy, self._legacy_raw, self.problem = False, None, None
            return True

    def update(self, change) -> bool:
        """Reload, apply change(data), save. Won't overwrite a file the user broke by hand.

        On a refused save the change is dropped from memory too, so memory matches the file.
        """
        with self.lock:
            if not self.reload():
                return False
            unchanged = copy.deepcopy(self.data)
            change(self.data)
            if not self.save():
                self.data = unchanged
                return False
            return True

    def snapshot(self) -> dict:
        """A copy of the settings that later changes can't touch."""
        with self.lock:
            return copy.deepcopy(self.data)

    def persist_migration(self) -> bool:
        """Write an old-format file in the new format (with its .bak). Call only once the app owns
        the single-instance mutex, so a second start or the old app never rewrites the file.

        Re-reads first: a file broken since it was loaded is never touched, a hand edit made
        meanwhile is kept, and the .bak holds exactly the bytes being replaced."""
        with self.lock:
            if not self.reload():
                return False
            return self.save() if self.legacy else True

    @property
    def interval_seconds(self) -> int:
        return max(1, int(self.data["interval_minutes"])) * 60

    def enabled(self, source: str) -> bool:
        return self.data["sources"][source]


settings = Settings(SETTINGS_FILE)


@dataclasses.dataclass
class Wallpaper:
    """A wallpaper ready to set, and where it came from."""
    path: str
    source: str             # a key of SOURCE_LABELS
    title: str
    url: str | None = None  # web page for the image, if any
    key: str | None = None  # what Never Show Again blocks: a Wallhaven id, "met_<id>" or a local file's path


def load_seen_ids() -> set[str]:
    """Load previously downloaded wallpaper IDs from disk."""
    try:
        return set(HISTORY_FILE.read_text().splitlines())
    except FileNotFoundError:
        return set()


def save_seen_ids(ids):
    """Append wallpaper IDs to the history file in one write, dropping the oldest past the cap."""
    try:
        history = HISTORY_FILE.read_text().splitlines()  # oldest first
    except FileNotFoundError:
        history = []
    known = set(history)
    new = [i for i in dict.fromkeys(ids) if i not in known]
    if not new:
        return
    history += new
    HISTORY_FILE.write_text("\n".join(history[-MAX_SEEN_IDS:]))


def load_blocked() -> set[str]:
    """The images Never Show Again has blocked. The user may edit the file; blank lines and spaces are ignored."""
    try:
        lines = BLOCKED_FILE.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return set()
    except (OSError, UnicodeDecodeError) as e:
        log.warning(f"Can't read {BLOCKED_FILE.name}, nothing is blocked this time: {e}")
        return set()
    return {line.strip() for line in lines if line.strip()}


def block_image(key: str) -> None:
    """Add one image to blocked.txt (appended, so the user's own edits stay). Raises OSError if it can't."""
    if key in load_blocked():
        return
    with open(BLOCKED_FILE, "a", encoding="utf-8") as f:
        f.write(key + "\n")


def is_own_download(path: Path) -> bool:
    """A file WallSwap downloaded itself: wallswap_*.jpg directly in its folder (INV-9)."""
    return path.parent == WALLPAPER_DIR and path.name.startswith("wallswap_") and path.suffix == ".jpg"


def save_seen_id(wp_id: str):
    save_seen_ids([wp_id])


def cleanup_old_wallpapers():
    """Delete old wallpaper files, keeping only the most recent ones."""
    wallpapers = sorted(
        WALLPAPER_DIR.glob("wallswap_*.jpg"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    for old_file in wallpapers[MAX_WALLPAPERS:]:
        try:
            old_file.unlink()
            log.info(f"Cleaned up: {old_file.name}")
        except Exception as e:
            log.warning(f"Failed to clean up {old_file.name}: {e}")


# ─── Windows API ──────────────────────────────────────────────
MONITOR_DEFAULTTONEAREST = 2  # Use the nearest monitor if the window does not intersect one
GWL_STYLE = -16  # Read the window style rather than another window attribute
WS_CAPTION = 0x00C00000  # A full caption combines the border and dialog-frame bits


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", ctypes.wintypes.RECT),
        ("rcWork", ctypes.wintypes.RECT),
        ("dwFlags", ctypes.wintypes.DWORD),
    ]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.wintypes.DWORD),
        ("DeviceName", ctypes.c_wchar * 32),
        ("DeviceString", ctypes.c_wchar * 128),
        ("StateFlags", ctypes.wintypes.DWORD),
        ("DeviceID", ctypes.c_wchar * 128),
        ("DeviceKey", ctypes.c_wchar * 128),
    ]


class DEVMODEW(ctypes.Structure):
    """The display form of DEVMODEW (220 bytes); only the pixel size is read."""
    _fields_ = [
        ("dmDeviceName", ctypes.c_wchar * 32),
        ("dmSpecVersion", ctypes.wintypes.WORD),
        ("dmDriverVersion", ctypes.wintypes.WORD),
        ("dmSize", ctypes.wintypes.WORD),
        ("dmDriverExtra", ctypes.wintypes.WORD),
        ("dmFields", ctypes.wintypes.DWORD),
        ("dmPositionX", ctypes.wintypes.LONG),
        ("dmPositionY", ctypes.wintypes.LONG),
        ("dmDisplayOrientation", ctypes.wintypes.DWORD),
        ("dmDisplayFixedOutput", ctypes.wintypes.DWORD),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", ctypes.c_wchar * 32),
        ("dmLogPixels", ctypes.wintypes.WORD),
        ("dmBitsPerPel", ctypes.wintypes.DWORD),
        ("dmPelsWidth", ctypes.wintypes.DWORD),
        ("dmPelsHeight", ctypes.wintypes.DWORD),
        ("dmDisplayFlags", ctypes.wintypes.DWORD),
        ("dmDisplayFrequency", ctypes.wintypes.DWORD),
        ("dmICMMethod", ctypes.wintypes.DWORD),
        ("dmICMIntent", ctypes.wintypes.DWORD),
        ("dmMediaType", ctypes.wintypes.DWORD),
        ("dmDitherType", ctypes.wintypes.DWORD),
        ("dmReserved1", ctypes.wintypes.DWORD),
        ("dmReserved2", ctypes.wintypes.DWORD),
        ("dmPanningWidth", ctypes.wintypes.DWORD),
        ("dmPanningHeight", ctypes.wintypes.DWORD),
    ]


DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x1  # the display is part of the desktop (not a disconnected output)
ENUM_CURRENT_SETTINGS = -1  # ask for the mode the display is in now
MAX_DISPLAYS = 64  # far more outputs than any PC has; only stops a misbehaving driver from looping forever


def largest_screen() -> tuple[int, int] | None:
    """The biggest connected screen as (long side, short side) in real pixels, or None if Windows won't say.

    Display modes are real pixels whatever the scaling (125%, 150%...) and whether or not the process is
    DPI-aware; GetSystemMetrics would give scaled numbers before the Tk root exists.
    """
    try:
        user32 = ctypes.windll.user32
        best = None
        for index in range(MAX_DISPLAYS):
            device = DISPLAY_DEVICEW()
            device.cb = ctypes.sizeof(device)
            if not user32.EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
                break
            if not device.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP:
                continue
            mode = DEVMODEW()
            mode.dmSize = ctypes.sizeof(mode)
            if not user32.EnumDisplaySettingsW(device.DeviceName, ENUM_CURRENT_SETTINGS, ctypes.byref(mode)):
                continue
            # A screen turned to portrait still needs a picture as big as its long side
            size = (max(mode.dmPelsWidth, mode.dmPelsHeight), min(mode.dmPelsWidth, mode.dmPelsHeight))
            if size[1] > 0 and (best is None or size[0] * size[1] > best[0] * best[1]):
                best = size
        return best
    except Exception as e:
        # HZ-2: absorbed so a change still happens (with the 1440p minimum), but never silently
        log.warning(f"Couldn't read the screen size, asking for {MIN_WIDTH}x{MIN_HEIGHT}: {e}")
        return None


def min_size() -> tuple[int, int]:
    """The smallest image WallSwap uses: the size picked in settings, or for "Match my screen" the biggest
    screen's size, but never more than MIN_WIDTH x MIN_HEIGHT.

    Read fresh each time, so a new choice or a monitor plugged in or out applies from the next change.
    """
    picked = RESOLUTION_SIZES.get(settings.data["min_resolution"])
    if picked:
        return picked
    screen = largest_screen()
    if screen is None:
        return MIN_WIDTH, MIN_HEIGHT
    return min(screen[0], MIN_WIDTH), min(screen[1], MIN_HEIGHT)


def set_wallpaper(image_path: str):
    """Set the desktop wallpaper using Windows API."""
    SPI_SETDESKWALLPAPER = 0x0014
    SPIF_UPDATEINIFILE = 0x01
    SPIF_SENDCHANGE = 0x02
    abs_path = str(Path(image_path).resolve())
    result = ctypes.windll.user32.SystemParametersInfoW(
        SPI_SETDESKWALLPAPER, 0, abs_path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    )
    if not result:
        raise OSError(f"Failed to set wallpaper: {abs_path}")
    log.info(f"Wallpaper set: {abs_path}")


def set_lock_screen(image_path: str):
    """Set the Windows lock screen image using WinRT API."""
    try:
        from winrt.windows.system.userprofile import LockScreen
        from winrt.windows.storage import StorageFile

        abs_path = str(Path(image_path).resolve())

        async def _set():
            file = await StorageFile.get_file_from_path_async(abs_path)
            await LockScreen.set_image_file_async(file)

        asyncio.run(_set())
        log.info(f"Lock screen set: {abs_path}")
    except Exception as e:
        log.warning(f"Failed to set lock screen: {e}")


def _covers(window: ctypes.wintypes.RECT, monitor: ctypes.wintypes.RECT) -> bool:
    """Check if a window covers all four edges of a monitor."""
    return (
        window.left <= monitor.left
        and window.top <= monitor.top
        and window.right >= monitor.right
        and window.bottom >= monitor.bottom
    )


def is_fullscreen_app_running() -> bool:
    """Detect if a fullscreen application (like a game) is running."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False

        # The desktop itself covers the whole screen when focused; that's not a game
        class_name = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_name, 256)
        if class_name.value in ("Progman", "WorkerW"):
            return False

        # Maximized windows with a full caption are ordinary apps; borderless ones can be games
        if (
            user32.IsZoomed(hwnd)
            and (user32.GetWindowLongW(hwnd, GWL_STYLE) & WS_CAPTION) == WS_CAPTION
        ):
            return False

        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(info)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False

        # Check if foreground window covers its full monitor
        return _covers(rect, info.rcMonitor)
    except Exception:
        # If a Windows check fails, allow the wallpaper change as usual
        return False


# ─── Startup ──
# Writes the .lnk through the Unicode IShellLinkW interface (WScript.Shell turns characters outside the
# ANSI code page into "?"), then prints the target read back from the saved file as UTF-8.
# Paths reach PowerShell only through the WS_* environment variables, never pasted into the script text.
SHORTCUT_TYPE_PS = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;

[ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("000214F9-0000-0000-C000-000000000046")]
interface IShellLinkW {
    void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder file, int size, IntPtr data, uint flags);
    void GetIDList(out IntPtr idList);
    void SetIDList(IntPtr idList);
    void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder name, int size);
    void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string name);
    void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder dir, int size);
    void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string dir);
    void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder args, int size);
    void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string args);
    void GetHotkey(out short hotkey);
    void SetHotkey(short hotkey);
    void GetShowCmd(out int showCmd);
    void SetShowCmd(int showCmd);
    void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int size, out int index);
    void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string path, int index);
    void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, uint reserved);
    void Resolve(IntPtr hwnd, uint flags);
    void SetPath([MarshalAs(UnmanagedType.LPWStr)] string file);
}

[ComImport, Guid("00021401-0000-0000-C000-000000000046")]
class ShellLink {}

public static class WallSwapShortcut {
    public static void Save(string lnk, string target, string args, string dir, string icon) {
        IShellLinkW link = (IShellLinkW)new ShellLink();
        link.SetPath(target);
        link.SetArguments(args);
        link.SetWorkingDirectory(dir);
        int comma = icon.LastIndexOf(',');
        link.SetIconLocation(icon.Substring(0, comma), int.Parse(icon.Substring(comma + 1)));
        ((IPersistFile)link).Save(lnk, true);
    }

    public static string Target(string lnk) {
        IShellLinkW link = (IShellLinkW)new ShellLink();
        ((IPersistFile)link).Load(lnk, 0);
        StringBuilder target = new StringBuilder(32768);
        link.GetPath(target, target.Capacity, IntPtr.Zero, 4);  // 4 = SLGP_RAWPATH: as stored, not resolved
        return target.ToString();
    }
}
'@
"""
SHORTCUT_PS = SHORTCUT_TYPE_PS + r"""
[WallSwapShortcut]::Save($env:WS_LNK, $env:WS_TARGET, $env:WS_ARGS, $env:WS_WD, $env:WS_ICON)
[WallSwapShortcut]::Target($env:WS_LNK)
"""
# Reads a shortcut's stored target the same Unicode-safe way, without changing the file
SHORTCUT_READ_PS = SHORTCUT_TYPE_PS + r"""
[WallSwapShortcut]::Target($env:WS_LNK)
"""


@dataclasses.dataclass(frozen=True)
class ShortcutSpec:
    target: str
    arguments: str
    working_dir: str
    icon: str


def startup_shortcut_spec(executable: Path, script: Path, icon: Path, pythonw_exists: bool,
                          frozen: bool = False) -> ShortcutSpec:
    """Describe the shortcut that starts WallSwap; pythonw when present so no console window opens.

    Frozen (the WallSwap.exe build), the exe is the whole app: no script argument, it starts in its own folder,
    and its embedded icon is the shortcut's icon.
    """
    if frozen:
        return ShortcutSpec(target=str(executable), arguments="", working_dir=str(executable.parent),
                            icon=f"{executable},0")
    return ShortcutSpec(
        target=str(executable.with_name("pythonw.exe") if pythonw_exists else executable),
        arguments=f'"{script}"',
        working_dir=str(script.parent),
        icon=f"{icon},0",
    )


def startup_shortcut_path() -> Path:
    """Where the Start with Windows shortcut lives; APPDATA is read now, not at import."""
    return Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup" / STARTUP_SHORTCUT_NAME


def startup_enabled() -> bool:
    return startup_shortcut_path().exists()


def windows_directory() -> PureWindowsPath:
    """The Windows folder as the OS reports it; %SystemRoot% is not trusted, any parent process can set it."""
    buf = ctypes.create_unicode_buffer(MAX_WINDOWS_PATH)
    try:
        length = ctypes.windll.kernel32.GetSystemWindowsDirectoryW(buf, MAX_WINDOWS_PATH)
    except AttributeError:  # ctypes.windll exists only on Windows; elsewhere use the default folder
        length = 0
    found = PureWindowsPath(buf.value)
    if 0 < length < MAX_WINDOWS_PATH and found.is_absolute():
        return found
    return PureWindowsPath(r"C:\Windows")


def _last_line(output: bytes | None) -> str:
    """The last non-empty line of a process's output, short enough for a message."""
    lines = [ln.strip() for ln in (output or b"").decode(errors="replace").splitlines() if ln.strip()]
    return lines[-1][:200] if lines else ""


def write_shortcut(path: Path, spec: ShortcutSpec):
    """Write a .lnk through the Unicode IShellLinkW interface; raises OSError on failure so the caller can tell the user (HZ-2)."""
    # Absolute path from the OS, so a powershell.exe planted next to the script, in .venv or under a
    # relative %SystemRoot% can never run
    powershell = windows_directory() / "System32/WindowsPowerShell/v1.0/powershell.exe"
    try:
        done = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-Command", SHORTCUT_PS],
            env={**os.environ, "WS_LNK": str(path), "WS_TARGET": spec.target, "WS_ARGS": spec.arguments,
                 "WS_WD": spec.working_dir, "WS_ICON": spec.icon},
            creationflags=CREATE_NO_WINDOW, capture_output=True, check=True, timeout=15,
        )
    except subprocess.TimeoutExpired:
        raise OSError("PowerShell took longer than 15 seconds") from None
    except subprocess.CalledProcessError as e:
        # str(e) would repeat the whole script; PowerShell's own error is in stderr
        reason = _last_line(e.stderr) or f"exit code {e.returncode}"
        log.warning(f"Startup shortcut PowerShell failed: {(e.stderr or b'').decode(errors='replace')}")
        raise OSError(f"PowerShell said: {reason}") from None
    if not path.exists():
        raise OSError(f"Startup shortcut was not created: {path}")
    # A shortcut whose target came out mangled would silently never start WallSwap
    saved_target = (done.stdout or b"").decode("utf-8-sig", errors="replace").strip()
    if saved_target != spec.target:
        raise OSError(f"Startup shortcut points to {saved_target!r}, not {spec.target!r}: {path}")


def read_shortcut_target(path: Path) -> str:
    """The target stored in a .lnk, read through IShellLinkW; raises OSError on failure."""
    powershell = windows_directory() / "System32/WindowsPowerShell/v1.0/powershell.exe"
    try:
        done = subprocess.run(
            [str(powershell), "-NoProfile", "-NonInteractive", "-Command", SHORTCUT_READ_PS],
            env={**os.environ, "WS_LNK": str(path)},
            creationflags=CREATE_NO_WINDOW, capture_output=True, check=True, timeout=15,
        )
    except subprocess.TimeoutExpired:
        raise OSError("PowerShell took longer than 15 seconds") from None
    except subprocess.CalledProcessError as e:
        raise OSError(f"PowerShell said: {_last_line(e.stderr) or f'exit code {e.returncode}'}") from None
    return (done.stdout or b"").decode("utf-8-sig", errors="replace").strip()


def should_repoint(existing_target: str, exe_path: Path | str) -> bool:
    """Should the Startup shortcut be re-pointed at this exe? Yes unless it already targets it (Windows paths
    compare case-insensitively); an empty or unreadable target also gets re-pointed."""
    if not existing_target.strip():
        return True
    return str(PureWindowsPath(existing_target)).casefold() != str(PureWindowsPath(exe_path)).casefold()


# The settings window's switch and the exe's take-over both change Startup\WallSwap.lnk from different threads
STARTUP_SHORTCUT_LOCK = threading.Lock()


def take_over_startup_shortcut(frozen: bool = FROZEN, read=read_shortcut_target, write=write_shortcut) -> bool:
    """Installed exe only: if the user already has Startup\\WallSwap.lnk (say, from a copy run from source),
    point it at this WallSwap.exe. Never creates it and touches no other file (INV-16). Returns True if rewritten."""
    if not frozen:
        return False  # running from source never re-points the shortcut
    path = startup_shortcut_path()
    if not path.exists():
        return False  # the user hasn't turned Start with Windows on
    exe = Path(sys.executable)
    try:
        existing = read(path)
    except OSError as e:
        log.warning(f"Couldn't read the Start with Windows shortcut, rewriting it: {e}")
        existing = ""
    if not should_repoint(existing, exe):
        return False
    # The read takes seconds; the user may have turned Start with Windows off meanwhile. Check again under the
    # same lock the switch uses, so the take-over never brings back a shortcut that was just removed (INV-16)
    with STARTUP_SHORTCUT_LOCK:
        if not path.exists():
            return False
        write(path, startup_shortcut_spec(exe, SCRIPT_DIR / "wallpaper_changer.py", ICON_PATH, False, frozen=True))
    log.info(f"Start with Windows shortcut now starts {exe} (was {existing or 'unreadable'})")
    return True


def set_start_with_windows(enabled: bool, write=write_shortcut) -> None:
    """Create or remove Startup\\WallSwap.lnk; that exact file is the only one ever deleted (INV-16)."""
    path = startup_shortcut_path()
    exe = Path(sys.executable)
    with STARTUP_SHORTCUT_LOCK:
        if not enabled:
            path.unlink(missing_ok=True)
            return
        write(path, startup_shortcut_spec(exe, SCRIPT_DIR / "wallpaper_changer.py", ICON_PATH,
                                          exe.with_name("pythonw.exe").exists(), frozen=FROZEN))


# ─── Image Validation ─────────────────────────────────────────
def fits_screen(w: int, h: int, min_ratio: float = 1.0, max_ratio: float = float("inf"),
                check_size: bool = True) -> bool:
    """Is a w x h image a usable wallpaper: wider than tall (by min_ratio..max_ratio) and at least min_size()?"""
    if h <= 0 or not (min_ratio < w / h <= max_ratio):
        return False
    if not check_size:
        return True
    min_w, min_h = min_size()
    return w >= min_w and h >= min_h


# ─── Safe downloads ───────────────────────────────────────────
class DownloadError(requests.RequestException):
    """A download refused by the safety limits (wrong site, too big, too slow)."""


@dataclasses.dataclass
class Fetched:
    """A fully read, size-checked HTTP response."""
    status_code: int
    content: bytes

    def json(self):
        return json.loads(self.content)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _check_url(url: str):
    host = (urlsplit(url).hostname or "").lower()
    allowed = any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)
    if urlsplit(url).scheme != "https" or not allowed:
        raise DownloadError(f"Refusing to fetch {url!r}: not an https Wallhaven/Met address")


def safe_get(url: str, *, params: dict | None = None, timeout: int = 15,
             max_bytes: int = MAX_DOWNLOAD_BYTES) -> Fetched:
    """GET that only talks to ALLOWED_HOSTS over https (redirects included), stops past
    max_bytes, and gives up after DOWNLOAD_DEADLINE seconds in total."""
    deadline = time.monotonic() + DOWNLOAD_DEADLINE
    for _ in range(4):  # the request plus at most 3 redirects, each one checked
        _check_url(url)
        with requests.get(url, params=params, headers={"User-Agent": USER_AGENT},
                          timeout=timeout, stream=True, allow_redirects=False) as resp:
            if resp.is_redirect:
                url, params = urljoin(resp.url, resp.headers["Location"]), None
                continue
            length = resp.headers.get("Content-Length", "")
            if length.isdigit() and int(length) > max_bytes:
                raise DownloadError(f"{url} is too large ({int(length) // 1_000_000} MB)")
            chunks, total = [], 0
            for chunk in resp.iter_content(64 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise DownloadError(f"{url} is too large (over {max_bytes // 1_000_000} MB)")
                if time.monotonic() > deadline:
                    raise DownloadError(f"{url} took longer than {DOWNLOAD_DEADLINE}s")
                chunks.append(chunk)
            return Fetched(resp.status_code, b"".join(chunks))
    raise DownloadError(f"Too many redirects for {url}")


# ─── Sources ──────────────────────────────────────────────────
WALLHAVEN_SEARCH_URL = "https://wallhaven.cc/api/v1/search"


def wallhaven_filters() -> dict:
    """The filters every Wallhaven search uses; the add-a-search check counts with the same ones."""
    min_w, min_h = min_size()
    return {
        "categories": "110",      # general + anime (no people: avoids celebrity photos)
        "purity": "100",          # SFW only
        "atleast": f"{min_w}x{min_h}",
        "ratios": "landscape",
    }


def count_wallhaven(query: str, exclude: list[str] = ()) -> int:
    """How many wallpapers Wallhaven has for a search with WallSwap's filters and excluded words (before the
    favourites cutoff). Raises on any network, HTTP or format problem."""
    resp = safe_get(WALLHAVEN_SEARCH_URL, params={"q": wallhaven_q(query, exclude), **wallhaven_filters()},
                    max_bytes=MAX_API_BYTES)
    resp.raise_for_status()
    total = resp.json()["meta"]["total"]
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise ValueError(f"Wallhaven sent an odd total: {total!r}")
    return total


def fetch_from_wallhaven(queries: list[str], sorting: str | None = None,
                         source: str = "wallhaven", exclude: list[str] = ()) -> Wallpaper | None:
    """Fetch a random screen-sized wallpaper from Wallhaven for one of the searches, leaving out results
    tagged with an excluded word."""
    if not queries:  # nothing ticked, or game_queries emptied: there is no general fallback
        return None
    query = random.choice(queries)
    sorting = sorting or random.choices(
        ["toplist", "hot", "random"], weights=[5, 3, 2], k=1)[0]

    params = {
        "q": wallhaven_q(query, exclude),
        **wallhaven_filters(),
        "sorting": sorting,
        "order": "desc",
        "page": 1,
    }
    if sorting == "toplist":
        params["topRange"] = random.choice(["3M", "6M", "1y"])

    try:
        log.info(f"Trying Wallhaven: query='{query}', sorting={sorting}")
        resp = safe_get(WALLHAVEN_SEARCH_URL, params=params, max_bytes=MAX_API_BYTES)
        if resp.status_code != 200:
            log.warning(f"Wallhaven returned {resp.status_code}")
            return None

        data = resp.json()
        wallpapers = data.get("data", [])
        if not wallpapers:
            log.info("Wallhaven returned no results")
            return None

        random.shuffle(wallpapers)
        seen = load_seen_ids() | load_blocked()

        for wp in wallpapers:
            wp_id = wp.get("id", "")
            wp_url = wp.get("path", "")
            wp_w = wp.get("dimension_x", 0)
            wp_h = wp.get("dimension_y", 0)

            if wp_id in seen:
                continue
            if source == "wallhaven" and wp.get("favorites", 0) < WALLHAVEN_MIN_FAVORITES:
                continue
            if not fits_screen(wp_w, wp_h):  # too small, or portrait/square
                continue
            if not wp_url:
                continue

            try:
                img_resp = safe_get(wp_url, timeout=20)
            except requests.RequestException as e:
                log.warning(f"Wallhaven download failed for {wp_id}: {e}")
                continue  # try the next result instead of giving up on this search
            if img_resp.status_code == 200 and len(img_resp.content) > 50_000:
                tmp_path = WALLPAPER_DIR / "_temp_wallhaven.jpg"
                tmp_path.write_bytes(img_resp.content)
                save_seen_id(wp_id)
                return Wallpaper(str(tmp_path), source, f"Wallhaven {wp_id} (search: {query})",
                                 wp.get("url"), key=wp_id)

    except Exception as e:
        log.warning(f"Wallhaven fetch failed: {e}")
    return None


def fetch_from_museum() -> Wallpaper | None:
    """Fetch a random public-domain painting from the Met that fits a wide screen."""
    query = random.choice(MUSEUM_QUERIES)
    try:
        log.info(f"Trying the Met: query='{query}'")
        object_ids = []
        for dept in MUSEUM_DEPARTMENTS:
            resp = safe_get(f"{MUSEUM_API}/v1.1/search",
                            params={"q": query, "hasImages": "true", "limit": 100, **dept},
                            max_bytes=MAX_API_BYTES)
            if resp.status_code == 200:
                object_ids += resp.json().get("objectIDs") or []
            else:
                log.warning(f"The Met returned {resp.status_code}")
        random.shuffle(object_ids)
        seen = load_seen_ids() | load_blocked()
        checked = 0
        decided = []  # objects that got a definite yes/no, never to be checked again

        try:
            for obj_id in object_ids:
                seen_key = f"met_{obj_id}"
                if seen_key in seen:
                    continue
                if checked >= 15:  # don't hammer the API
                    break
                checked += 1

                try:
                    wallpaper = _try_museum_object(obj_id)
                except Exception as e:  # network hiccup etc.: skip it now, retry another day
                    log.warning(f"Met object {obj_id} failed: {e}")
                    (WALLPAPER_DIR / "_temp_museum.jpg").unlink(missing_ok=True)
                    continue
                decided.append(seen_key)
                if wallpaper:
                    return wallpaper
        finally:
            save_seen_ids(decided)

    except Exception as e:
        log.warning(f"Met fetch failed: {e}")
    return None


def _museum_get(url: str, timeout: int, max_bytes: int = MAX_DOWNLOAD_BYTES) -> Fetched | None:
    """GET from the Met: None for 404 (gone for good), an exception for other failures."""
    resp = safe_get(url, timeout=timeout, max_bytes=max_bytes)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()  # 429/5xx are temporary: don't mark the painting as seen
    return resp


def _try_museum_object(obj_id: int) -> Wallpaper | None:
    """Download one Met object if it's a public-domain painting that fits a wide screen."""
    obj_resp = _museum_get(f"{MUSEUM_API}/v1/objects/{obj_id}", timeout=15, max_bytes=MAX_API_BYTES)
    if not obj_resp:
        return None
    obj = obj_resp.json()
    image_url = obj.get("primaryImage")
    if not obj.get("isPublicDomain") or not image_url:
        return None

    # Check the shape on the small preview before downloading the full image
    small_url = obj.get("primaryImageSmall")
    if small_url:
        small = _museum_get(small_url, timeout=15)
        if not small:
            return None
        with Image.open(io.BytesIO(small.content)) as preview:
            if not fits_screen(*preview.size, MUSEUM_MIN_RATIO, MUSEUM_MAX_RATIO, check_size=False):
                return None

    img_resp = _museum_get(image_url, timeout=30)
    if not img_resp:
        return None

    tmp_path = WALLPAPER_DIR / "_temp_museum.jpg"
    tmp_path.write_bytes(img_resp.content)
    with Image.open(tmp_path) as img:
        w, h = img.size
    if fits_screen(w, h, MUSEUM_MIN_RATIO, MUSEUM_MAX_RATIO):
        artist = obj.get("artistDisplayName") or "Unknown artist"
        title = f"{obj.get('title') or 'Untitled'} by {artist}"
        log.info(f"Met painting: {title} ({w}x{h})")
        return Wallpaper(str(tmp_path), "museum", title, obj.get("objectURL"), key=f"met_{obj_id}")
    tmp_path.unlink(missing_ok=True)
    return None


def is_landscape_wallpaper(image_path: Path) -> bool:
    """Check a local image is big enough for the screen and landscape."""
    try:
        # Your own files are only measured here, not decoded (Windows draws them), so the
        # pixel limit for downloads doesn't apply. Opening still refuses truly absurd ones
        # (over twice the limit).
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            img = Image.open(image_path)
        with img:
            return fits_screen(*img.size)
    except Exception as e:
        log.warning(f"Can't read image {image_path}: {e}")
        return False


def pick_local_wallpaper(folders: list[Path]) -> Wallpaper | None:
    """Pick a random image from the folders, cycling before repeating."""
    candidates = [
        p for folder in folders if folder.is_dir()
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in LOCAL_EXTENSIONS
    ]
    blocked = load_blocked()
    candidates = [p for p in candidates if str(p) not in blocked]
    if not candidates:
        return None

    try:
        seen = set(LOCAL_HISTORY_FILE.read_text(encoding="utf-8").splitlines())
    except FileNotFoundError:
        seen = set()

    unseen = [p for p in candidates if str(p) not in seen]
    # Try the unseen ones first; if none of them work (e.g. only portrait or too-small
    # files are left), start a new cycle over everything instead of giving up.
    pools = [unseen, candidates] if unseen else [candidates]

    for pool in pools:
        if pool is candidates:
            # New cycle for these folders only; other folders keep their progress
            seen -= {str(p) for p in candidates}
        random.shuffle(pool)
        for path in pool:
            seen.add(str(path))
            if is_landscape_wallpaper(path):
                LOCAL_HISTORY_FILE.write_text("\n".join(seen), encoding="utf-8")
                log.info(f"Picked local wallpaper: {path}")
                return Wallpaper(str(path), "local", path.name, key=str(path))

    LOCAL_HISTORY_FILE.write_text("\n".join(seen), encoding="utf-8")
    return None


# ─── Core Logic ───────────────────────────────────────────────
def wallhaven_query_pool(data: dict) -> list[str]:
    """The searches of the ticked topics, in topic order, without blanks or repeats (any case)."""
    pool, seen = [], set()
    for topic in TOPIC_LABELS:
        entry = data["topics"].get(topic)
        if not entry or not entry["enabled"]:
            continue
        for search in entry["searches"]:
            search = search.strip()
            if search and search.casefold() not in seen:
                seen.add(search.casefold())
                pool.append(search)
    return pool


def source_available(data: dict, source: str) -> bool:
    """Whether the source has anything to pick from."""
    if source == "wallhaven":
        return bool(wallhaven_query_pool(data))
    if source == "game":
        return bool(data["game_queries"] or data["game_folders"])
    if source == "local":
        return bool(data["local_folders"])
    return True  # museum


EMPTY_SOURCE_REASONS = {
    "wallhaven": "Tick a topic with searches",
    "game": "Add game searches or folders",
    "local": "Add a folder to use this",
}


def drop_reason(data: dict, source: str) -> str | None:
    """Why the source gets no share of changes, or None when it has one."""
    if not data["sources"][source]:
        return "Off in the tray menu"
    if not source_available(data, source):
        return EMPTY_SOURCE_REASONS[source]
    if data["chances"][source] <= 0:
        return "Set above 0%"
    return None


def source_weights(data: dict) -> dict[str, float]:
    """Relative weight of each source that is on, has something to use and is above 0."""
    chances, on = data["chances"], data["sources"]
    return {s: chances[s] for s in SOURCE_ORDER
            if chances[s] > 0 and on[s] and source_available(data, s)}


def source_shares(weights: dict[str, float]) -> dict[str, int]:
    """Whole percentages per source that add up to 100 (largest remainder); {} when all are 0."""
    total = sum(weights.values())
    if total <= 0:
        return {}
    exact = {s: w * 100 / total for s, w in weights.items()}
    shares = {s: int(x) for s, x in exact.items()}
    by_remainder = sorted(exact, key=lambda s: exact[s] - shares[s], reverse=True)
    for s in by_remainder[:100 - sum(shares.values())]:
        shares[s] += 1
    return shares


def fetch_source(source: str, data: dict) -> Wallpaper | None:
    """Get one wallpaper from the named source, using the settings in data."""
    if source == "local":
        return pick_local_wallpaper([Path(f) for f in data["local_folders"]])
    if source == "game":
        # Few game wallpapers exist on Wallhaven: "random" sorting reaches all of them
        # (toplist only returns a handful). Once they've all been shown, use the game folders.
        queries = data["game_queries"]
        wallpaper = queries and download_wallpaper(
            lambda: fetch_from_wallhaven(queries, "random", source="game", exclude=data["exclude_words"]),
            attempts=2)
        return wallpaper or pick_local_wallpaper([Path(f) for f in data["game_folders"]])
    if source == "museum":
        return download_wallpaper(fetch_from_museum, attempts=3)
    return download_wallpaper(
        lambda: fetch_from_wallhaven(wallhaven_query_pool(data), exclude=data["exclude_words"]))


def get_new_wallpaper() -> Wallpaper | None:
    """Pick a source at random by weight, falling back to the others if it fails."""
    data = settings.snapshot()
    weights = source_weights(data)
    if not weights:
        log.warning("Every source is off, empty or at 0%")
        return None
    choice = random.choices(list(weights), weights=list(weights.values()), k=1)[0]

    # Fallbacks (e.g. when offline): general Wallhaven, then local folders, but only a source
    # that has a share, so one that is off, empty or at 0% is never used
    order = [choice] + [s for s in ("wallhaven", "local") if s in weights]
    for source in dict.fromkeys(order):
        wallpaper = fetch_source(source, data)
        if wallpaper:
            return wallpaper
    return None


def download_wallpaper(fetch, attempts: int = 5) -> Wallpaper | None:
    """Run an online fetcher and save its result as a JPEG in WALLPAPER_DIR."""
    for attempt in range(attempts):
        try:
            wallpaper = fetch()
            if wallpaper:
                prefix = "met" if wallpaper.source == "museum" else "wallhaven"
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                final_name = f"wallswap_{prefix}_{timestamp}.jpg"
                final_path = WALLPAPER_DIR / final_name

                with Image.open(wallpaper.path) as img:
                    img = img.convert("RGB")
                    img.save(str(final_path), "JPEG", quality=95)

                Path(wallpaper.path).unlink(missing_ok=True)
                log.info(f"Saved: {final_name}")
                cleanup_old_wallpapers()
                return dataclasses.replace(wallpaper, path=str(final_path))
        except Exception as e:
            log.warning(f"Download attempt {attempt + 1} failed: {e}")

    log.warning("All download attempts failed this round")
    return None


# ─── System Tray App ─────────────────────────────────────────
def retry_plan(outcome: str, failures: int) -> tuple[int | None, int]:
    """After a change attempt: (seconds until it is tried again, or None for the normal interval; failed tries
    in a row). outcome is "set", "skipped" (fullscreen app in front), "failed" or "busy" (another change is
    already running, which will make its own plan)."""
    if outcome == "skipped":
        return RETRY_SECONDS, failures  # checking for a fullscreen window costs nothing, so never slow down
    if outcome == "failed":
        failures += 1
        return (RETRY_SECONDS if failures <= FAST_RETRIES else SLOW_RETRY_SECONDS), failures
    return None, 0


def _safe_filename(text: str) -> str:
    """Turn a title into something Windows accepts as a file name."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", text).strip(" .")
    return name[:120] or "wallpaper"


class WallSwapApp:
    def __init__(self):
        self.paused = False
        self.running = True
        self.icon = None
        self.timer_thread = None
        self.current: Wallpaper | None = None
        # Wallpapers shown before the current one, oldest first; Previous takes from the end
        self.history: collections.deque[Wallpaper] = collections.deque(maxlen=HISTORY_LENGTH)
        self.wallpapers_set = 0
        self.elapsed = 0
        self.retry_after: int | None = None  # seconds until a skipped or failed change is tried again
        self.failures = 0                    # failed changes in a row
        self.change_lock = threading.Lock()  # one wallpaper change at a time
        self.folder_dialog_open = False
        self.root = None  # the hidden Tk root; every Tk call happens on its (the main) thread
        self.ui_calls = queue.SimpleQueue()  # calls from other threads waiting for the Tk thread
        self.settings_window = None
        self.settings_ui = None  # the settings_window module, imported in run()
        # Held from a tray Add Folder click until its dialog closes, so clicks while it is queued or open (the
        # drain is blocked behind a modal dialog) can't pile up dialogs. A lock, because the tray thread takes it
        # and the Tk thread releases it.
        self.tray_folder_pending = threading.Lock()

    def create_tray_icon(self) -> Image.Image:
        """Load the app icon for the system tray."""
        size = 64
        try:
            img = Image.open(str(ICON_PATH)).convert("RGBA")
            img = img.resize((size, size), Image.LANCZOS)
            if self.paused:
                # Tint orange when paused, only where the icon is drawn (not its transparent corners)
                tint = Image.new("RGBA", (size, size), (255, 150, 0, 255))
                tinted = Image.blend(img, tint, 0.45)
                tinted.putalpha(img.getchannel("A"))
                img = tinted
            return img
        except Exception:
            # Fallback if icon file is missing
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            color = (255, 165, 0) if self.paused else (88, 166, 255)
            draw.rounded_rectangle([4, 4, 60, 60], radius=12, fill=color)
            try:
                font = ImageFont.truetype("arial.ttf", 32)
            except OSError:
                font = ImageFont.load_default()
            draw.text((14, 10), "W", fill="white", font=font)
            return img

    def notify(self, message: str, title: str = "WallSwap"):
        """Show a Windows notification from the tray icon."""
        log.info(f"{title}: {message}")
        try:
            if self.icon:
                self.icon.notify(message[:250], title[:60])
        except Exception as e:
            log.warning(f"Notification failed: {e}")

    def refresh_menu(self):
        if self.icon:
            self.icon.update_menu()

    # ── Wallpaper changes ──
    def next_wallpaper(self, _=None):
        """Manually trigger next wallpaper and reset timer."""
        self.elapsed = 0
        threading.Thread(target=self._change_wallpaper, daemon=True).start()

    def _change_wallpaper(self) -> str:
        """Fetch and set a new wallpaper, unless a change is already in progress. Returns what happened
        ("set", "skipped", "failed" or "busy") and plans the retry for a change that didn't happen."""
        if not self.change_lock.acquire(blocking=False):
            log.info("A wallpaper change is already in progress, ignoring this one")
            return "busy"
        try:
            outcome = self._do_change_wallpaper()
            self.retry_after, self.failures = retry_plan(outcome, self.failures)
            self.elapsed = 0  # the wait for the retry, or the next interval, starts now
            if self.retry_after:
                log.info(f"Trying again in {self.retry_after} seconds")
            return outcome
        finally:
            self.change_lock.release()

    def _do_change_wallpaper(self) -> str:
        if is_fullscreen_app_running():
            log.info("Fullscreen app detected, skipping wallpaper change")
            return "skipped"

        settings.reload()  # pick up hand edits to settings.json
        log.info("Fetching new wallpaper...")
        wallpaper = get_new_wallpaper()
        if not wallpaper:
            log.warning("Could not fetch a new wallpaper this round")
            return "failed"
        previous = self.current
        try:
            self._show(wallpaper)
        except Exception as e:
            log.error(f"Failed to set wallpaper: {e}")
            return "failed"
        if previous:
            self.history.append(previous)
        self.refresh_menu()
        return "set"

    def _show(self, wallpaper: Wallpaper):
        """Put a wallpaper on the desktop and lock screen and make it the current one. Raises if Windows refuses."""
        set_wallpaper(wallpaper.path)
        set_lock_screen(wallpaper.path)
        self.current = wallpaper
        self.wallpapers_set += 1
        if self.icon:
            self.icon.title = f"WallSwap: {wallpaper.title}"[:127]

    def previous_wallpaper(self, _=None):
        """Go back to the wallpaper shown before this one (tray thread: the work happens on its own thread)."""
        threading.Thread(target=self._previous_wallpaper, daemon=True).start()

    def _previous_wallpaper(self):
        if not self.change_lock.acquire(blocking=False):
            return  # a change is running; the menu is as good as new once it finishes
        try:
            while self.history:
                wallpaper = self.history.pop()
                if not Path(wallpaper.path).exists():
                    continue  # cleaned up, or the user moved their own file: try the one before
                try:
                    self._show(wallpaper)
                except Exception as e:
                    log.error(f"Failed to set the previous wallpaper: {e}")
                    continue
                # Going back is a change like any other: the interval starts again and no retry is pending
                self.elapsed, self.retry_after, self.failures = 0, None, 0
                log.info(f"Back to the previous wallpaper: {wallpaper.title}")
                return
            self.notify("There's no earlier wallpaper to go back to.")
        finally:
            self.change_lock.release()
            self.refresh_menu()

    # ── Current wallpaper ──
    def save_favourite(self, _=None):
        """Copy the current wallpaper into the Favourites folder (never cleaned up)."""
        wallpaper = self.current
        if not wallpaper or not Path(wallpaper.path).exists():
            self.notify("There's no current wallpaper to save yet.")
            return
        FAVOURITES_DIR.mkdir(parents=True, exist_ok=True)
        base, suffix = _safe_filename(wallpaper.title), Path(wallpaper.path).suffix
        dest = FAVOURITES_DIR / f"{base}{suffix}"
        n = 2
        while dest.exists():
            # Same file saved before (copy2 keeps size and timestamp)? Otherwise it's a
            # different picture that happens to share the title: number it
            if filecmp.cmp(wallpaper.path, dest):
                self.notify(f"Already in Favourites: {dest.name}")
                return
            dest = FAVOURITES_DIR / f"{base} ({n}){suffix}"
            n += 1
        try:
            shutil.copy2(wallpaper.path, dest)
            self.notify(f"Saved {dest.name}", "Added to Favourites")
        except OSError as e:
            self.notify(f"Couldn't save it: {e}")

    def never_show_again(self, _=None):
        """Block the current wallpaper for good, switch to a new one, then delete the blocked download."""
        wallpaper = self.current
        if not wallpaper or not wallpaper.key:
            self.notify("There's no current wallpaper to block yet.")
            return
        try:
            block_image(wallpaper.key)
        except OSError as e:
            self.notify(f"Couldn't block it: {e}")
            return
        # Not the current wallpaper any more, so the change below doesn't put it in the Previous history
        self.current = None
        self.history = collections.deque((w for w in self.history if w.key != wallpaper.key),
                                         maxlen=HISTORY_LENGTH)
        if self.icon:
            self.icon.title = f"WallSwap {APP_VERSION}"
        self.refresh_menu()
        self.notify(f"{wallpaper.title} won't be shown again. To undo, remove its line from {BLOCKED_FILE.name}.",
                    "Blocked")
        self.elapsed = 0
        threading.Thread(target=self._replace_blocked, args=(wallpaper,), daemon=True).start()

    def _replace_blocked(self, wallpaper: Wallpaper):
        self._change_wallpaper()
        # Only WallSwap's own download is deleted; a file from the user's folders is blocked, never touched (INV-8)
        path = Path(wallpaper.path)
        if wallpaper.source != "local" and is_own_download(path):
            try:
                path.unlink(missing_ok=True)
            except OSError as e:
                log.warning(f"Couldn't delete the blocked wallpaper {path.name}: {e}")

    def open_source(self, _=None):
        """Show what the current wallpaper is, and open its web page (or its file)."""
        wallpaper = self.current
        if not wallpaper:
            self.notify("No wallpaper has been set yet.")
            return
        self.notify(wallpaper.title, SOURCE_LABELS.get(wallpaper.source, "Wallpaper"))
        # The link comes from API data; only ever open a real web page (on Windows,
        # webbrowser.open would launch anything else like a double-clicked file)
        if wallpaper.url and wallpaper.url.startswith("https://"):
            webbrowser.open(wallpaper.url)
        elif Path(wallpaper.path).exists():
            subprocess.Popen(["explorer", "/select,", wallpaper.path])

    # ── Settings ──
    def toggle_pause(self, _=None):
        """Pause/resume automatic wallpaper changing."""
        self.paused = not self.paused
        state = "PAUSED" if self.paused else "RESUMED"
        log.info(f"WallSwap {state}")
        # Update the icon
        if self.icon:
            self.icon.icon = self.create_tray_icon()

    def _change_setting(self, change, done_message: str | None = None) -> bool:
        # problem is read under the same lock as update(), so a timer reload can't reset it in between
        with settings.lock:
            if not settings.update(change):
                self.notify(self._problem_message())
                return False
        self.refresh_menu()
        if done_message:
            self.notify(done_message)
        return True

    def interval_item(self, minutes: int) -> pystray.MenuItem:
        label = f"{minutes} min" if minutes < 60 else f"{minutes // 60} hour" + ("s" if minutes > 60 else "")

        def choose(icon, item):
            self._change_setting(lambda d: d.update(interval_minutes=minutes))
            log.info(f"Interval set to {minutes} minutes")

        return pystray.MenuItem(
            label, choose, radio=True,
            checked=lambda item: settings.data["interval_minutes"] == minutes)

    def source_item(self, source: str, label) -> pystray.MenuItem:
        def toggle(icon, item):
            self._change_setting(
                lambda d: d["sources"].update({source: not d["sources"][source]}))

        return pystray.MenuItem(label, toggle, checked=lambda item: settings.enabled(source))

    def local_folder_items(self):
        """Submenu listing local folders (click one to remove it) plus 'Add Folder…'."""
        yield pystray.MenuItem("➕ Add Folder…", self.add_local_folder)
        yield pystray.Menu.SEPARATOR
        local, game = settings.data["local_folders"], settings.data["game_folders"]
        folders = local + [f for f in game if f not in local]
        if not folders:
            yield pystray.MenuItem("(no folders yet)", None, enabled=False)
        game_tag = f"  ({settings.data['game_name'] or 'game'})"
        for folder in folders:
            tag = game_tag if folder in game else ""
            yield pystray.MenuItem(f"✖ Remove  {folder}{tag}", self._remove_folder_action(folder))

    def _remove_folder_action(self, folder: str):
        def remove(icon, item):
            def change(d):
                for key in ("local_folders", "game_folders"):
                    if folder in d[key]:
                        d[key].remove(folder)
            self._change_setting(change, f"Removed {folder}")
        return remove

    def add_local_folder(self, _=None):
        if not self.tray_folder_pending.acquire(blocking=False):
            return  # one is already queued or open
        self.post_to_ui(self._add_folder_from_tray)

    def ask_folder(self, parent=None) -> str | None:
        """Tk thread: ask for a folder with the standard Windows dialog. None if cancelled or one is already open."""
        # A modal dialog keeps Tk's event loop running, so the queue can drain a second Add Folder meanwhile
        if self.folder_dialog_open:
            return None
        self.folder_dialog_open = True
        owner = parent or self.root
        try:
            # Windows' foreground lock can open the dialog behind other windows; a topmost owner brings it to the front
            owner.attributes("-topmost", True)
            folder = filedialog.askdirectory(
                parent=owner, title="Choose a folder of wallpapers",
                initialdir=str(Path.home() / "Pictures"))
        except TclError as e:
            log.error(f"Folder picker failed: {e}")
            folder = ""
        finally:
            self.folder_dialog_open = False
            try:
                owner.attributes("-topmost", False)
            except TclError:
                pass  # the owner window was closed while the dialog was open; nothing left to lower
        return str(Path(folder)) if folder else None

    def _add_folder_from_tray(self):
        """Tk thread: ask for a folder, then add it to My Folders."""
        try:
            folder = self.ask_folder()
        finally:
            self.tray_folder_pending.release()  # the dialog is closed (chosen, cancelled or failed)
        if not folder:
            return
        if folder in settings.data["local_folders"]:
            self.notify(f"Already using {folder}")
            return
        self._change_setting(
            lambda d: d["local_folders"].append(folder) if folder not in d["local_folders"] else None,
            f"Added {folder}")

    def open_settings(self, _=None):
        """Open the Settings window (or bring it to the front) on the Tk thread."""
        self.post_to_ui(self._show_settings)

    def _show_settings(self):
        """Tk thread: open the Settings window on a snapshot of the settings, or raise the one already open."""
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.bring_to_front()
            return

        def closed():
            self.settings_window = None

        deps = self.settings_ui.WindowDeps(
            snapshot=settings.snapshot(),
            topic_labels=TOPIC_LABELS,
            mix_labels=MIX_LABELS,
            source_order=SOURCE_ORDER,
            interval_choices=INTERVAL_CHOICES,
            resolution_labels=RESOLUTION_LABELS,
            shares=lambda d: source_shares(source_weights(d)),
            drop_reason=drop_reason,
            clean_search=clean_search,
            clean_exclude=clean_exclude_word,
            exclude_problem=exclude_word_problem,
            patch=settings_patch,
            ask_folder=self.ask_folder,
            save=self._save_from_window,
            count_search=self.count_search,
            startup_on=startup_enabled(),
            icon_path=ICON_PATH,
            on_closed=closed,
            game_name_max=MAX_GAME_NAME_LENGTH,
            version=APP_VERSION,
        )
        self.settings_window = self.settings_ui.SettingsWindow(self.root, deps)

    def count_search(self, query: str, done):
        """Count Wallhaven's wallpapers for a search on a worker thread, then call done(count) on the Tk thread
        (count is None if the check failed)."""
        def work():
            try:
                count = count_wallhaven(query, settings.snapshot()["exclude_words"])
            except Exception as e:  # offline, timeout, HTTP error or an odd reply: the window just says so
                log.warning(f"Couldn't count Wallhaven results for {query!r}: {e}")
                count = None
            self.post_to_ui(lambda: done(count))

        threading.Thread(target=work, daemon=True).start()

    def _save_from_window(self, patch: dict, start_with_windows: bool | None) -> str | None:
        """Tk thread: write what the window changed, then the Start with Windows choice. An error message, or None."""
        if any(patch.values()):
            # problem is read under the same lock as update(), so a timer reload can't reset it in between
            with settings.lock:
                if not settings.update(lambda d: apply_patch(d, patch)):
                    return self._problem_message()  # nothing saved, so the shortcut is left alone too
        self.refresh_menu()
        if start_with_windows is not None:
            try:
                set_start_with_windows(start_with_windows)
            except (OSError, subprocess.SubprocessError) as e:
                # HZ-2: absorbed so the window stays usable, but logged and shown in its banner
                log.warning(f"Couldn't change Start with Windows: {e}")
                return f"Settings saved, but Start with Windows couldn't be changed: {e}"
        self.notify("Settings saved. They apply from the next wallpaper change.")
        return None

    def _problem_message(self) -> str:
        """Why the last settings save was refused, for the window's banner."""
        with settings.lock:
            problem = settings.problem
        if problem == "backup":
            return ("Couldn't make the settings.json.bak backup, so nothing was saved. "
                    "Check the WallSwap folder can be written to, then try again.")
        if problem == "write":
            return "Couldn't save settings.json (is it read-only?), so nothing was saved."
        return "settings.json has a mistake in it, so nothing was saved. Fix it or delete it to go back to the defaults."

    def open_folder(self, _=None):
        """Open the wallpaper save folder."""
        os.startfile(str(WALLPAPER_DIR))

    def quit_app(self, _=None):
        """Exit the application (tray thread): close the Tk side through the queue, then the tray."""
        self.running = False
        self.post_to_ui(self._close_ui)
        if self.icon:
            self.icon.stop()

    # ── Tk thread ──
    def post_to_ui(self, fn):
        """Run fn on the Tk (main) thread soon. Safe from any thread."""
        self.ui_calls.put(fn)

    def _drain_ui(self):
        """Tk thread: run every queued call, then check again in UI_POLL_MS."""
        try:
            while True:
                try:
                    fn = self.ui_calls.get_nowait()
                except queue.Empty:
                    break
                if not self.running and fn != self._close_ui:
                    continue  # quitting: nothing else may run now (a folder dialog must not open after Quit)
                try:
                    fn()
                except Exception:
                    # HZ-2: a bug or Tk error in one call must not kill the queue (Quit and Add Folder go through
                    # it); it is logged, and the user sees only that one action do nothing
                    log.exception("A queued UI call failed")
        finally:
            # Always reschedule, even after Quit: quit_app can set running=False after this drain's last pop but
            # before it queues _close_ui, and that call must still run. root.quit() ends mainloop regardless.
            self.root.after(UI_POLL_MS, self._drain_ui)

    def _close_ui(self):
        """Tk thread: close the settings window, if open, and end mainloop."""
        if self.settings_window is not None:
            try:
                self.settings_window.destroy()
            except TclError:
                pass  # the user closed it at the same moment; nothing left to destroy
            self.settings_window = None
        self.root.quit()

    def _take_over_startup_shortcut(self):
        """Background thread: re-point an old Start with Windows shortcut at this exe (frozen only)."""
        try:
            take_over_startup_shortcut()
        except Exception:
            # HZ-2: logged with the traceback, not hidden; a bad shortcut must never stop the app from starting
            log.exception("Couldn't update the Start with Windows shortcut")

    def _on_tray_ready(self, icon):
        """pystray setup thread: show the icon, then start the timer (so it never notifies an icon that isn't up)."""
        icon.visible = True
        self.timer_thread = threading.Thread(target=self.timer_loop, daemon=True)
        self.timer_thread.start()

    def timer_loop(self):
        """Background timer that triggers wallpaper changes."""
        # Initial wallpaper on startup
        self._change_wallpaper()

        while self.running:
            time.sleep(5)
            if not self.running:
                break
            self.tick(5)

    def tick(self, seconds: int):
        """Timer thread: count the time passed and change the wallpaper when the interval, or the shorter
        wait after a skipped or failed change, is up. Nothing counts and nothing is retried while paused."""
        if self.paused:
            return
        self.elapsed += seconds
        if self.elapsed >= (self.retry_after or settings.interval_seconds):
            self.elapsed = 0
            self._change_wallpaper()

    def build_menu(self) -> pystray.Menu:
        has_current = lambda item: self.current is not None  # noqa: E731
        return pystray.Menu(
            pystray.MenuItem(f"WallSwap {APP_VERSION}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🔄 Next Wallpaper", self.next_wallpaper, default=True),
            pystray.MenuItem("⏮ Previous Wallpaper", self.previous_wallpaper,
                             enabled=lambda item: bool(self.history)),
            pystray.MenuItem("⭐ Favourite", self.save_favourite, enabled=has_current),
            pystray.MenuItem("🚫 Never Show Again", self.never_show_again, enabled=has_current),
            pystray.MenuItem("🔗 Details", self.open_source, enabled=has_current),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⏸ Pause", self.toggle_pause, checked=lambda item: self.paused),
            pystray.MenuItem("⏱ Interval", pystray.Menu(
                *[self.interval_item(m) for m in INTERVAL_CHOICES])),
            pystray.MenuItem("🌐 Sources", pystray.Menu(
                self.source_item("wallhaven", "Wallhaven (general)"),
                self.source_item("game", lambda item: (
                    f"Wallhaven: {name}" if (name := settings.data["game_name"]) else "Favourite game")),
                self.source_item("museum", "The Met (paintings)"),
                self.source_item("local", "My folders"),
            )),
            pystray.MenuItem("📂 My Folders", pystray.Menu(self.local_folder_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙️ Settings…", self.open_settings),
            pystray.MenuItem("📁 WallSwap Folder", self.open_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Quit", self.quit_app),
        )

    def run(self):
        """Start the system tray application."""
        log.info("=" * 50)
        log.info(f"WallSwap {APP_VERSION} starting up!")
        log.info(f"Wallpaper folder: {WALLPAPER_DIR}")
        log.info(f"Interval: {settings.interval_seconds // 60} minutes")
        log.info("Min resolution: %dx%d" % min_size())
        log.info("=" * 50)

        # Imported here, not at the top: customtkinter starts darkdetect and its root makes the whole process
        # DPI-aware, side effects that must stay out of a plain import (and so out of pytest). settings_window
        # imports customtkinter, so it comes in here too.
        import customtkinter as ctk
        import settings_window
        self.settings_ui = settings_window

        # Only now, after the single-instance mutex, may an upgraded settings.json be written
        if not settings.persist_migration():
            log.warning("Couldn't save the upgraded settings.json; using the upgraded settings in memory for now")

        # Off the main thread: reading the shortcut starts PowerShell, which would hold up the tray for a second
        threading.Thread(target=self._take_over_startup_shortcut, daemon=True).start()

        # The Tk root comes before the tray, so the process is DPI-aware before pystray creates its windows
        self.root = ctk.CTk()
        self.root.withdraw()

        self.icon = pystray.Icon(
            "WallSwap",
            self.create_tray_icon(),
            f"WallSwap {APP_VERSION}",
            self.build_menu(),
        )
        # The tray runs its own thread; _on_tray_ready shows it and starts the timer once it is up
        self.icon.run_detached(setup=self._on_tray_ready)

        self.root.after(UI_POLL_MS, self._drain_ui)
        if settings.created:
            self.post_to_ui(self._show_settings)  # first run; the first wallpaper change still happens right away

        try:
            self.root.mainloop()  # blocks until _close_ui calls root.quit()
        finally:
            self.running = False
            self.icon.stop()
            try:
                self.root.destroy()
            except TclError:
                pass  # Tk already tore the root down (it failed or was destroyed); nothing left to close

        log.info("WallSwap stopped. Goodbye!")


# ─── Entry Point ──────────────────────────────────────────────
if __name__ == "__main__":
    # Prevent multiple instances using a Windows named mutex
    mutex = ctypes.windll.kernel32.CreateMutexW(
        None, False, "WallSwap_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        log.info("WallSwap is already running, exiting.")
        sys.exit(0)

    app = WallSwapApp()
    app.run()
