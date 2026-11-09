"""
WallSwap - Fresh Desktop Wallpapers on Autopilot
A lightweight system tray app that sets random 1440p+ wallpapers from
Wallhaven, The Met's public-domain paintings and your own folders as your
Windows desktop and lock screen background.

Usage (see README.md):
    uv sync
    uv run wallpaper_changer.py
"""

import asyncio
import copy
import ctypes
import ctypes.wintypes
import dataclasses
import filecmp
import io
import json
import logging
import os
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
from pathlib import Path
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
SCRIPT_DIR = Path(__file__).resolve().parent
ICON_PATH = SCRIPT_DIR / "wallswap.ico"
WALLPAPER_DIR = Path.home() / "Pictures" / "WallSwap"
LOG_FILE = WALLPAPER_DIR / "wallswap.log"
HISTORY_FILE = WALLPAPER_DIR / "seen_ids.txt"
SETTINGS_FILE = WALLPAPER_DIR / "settings.json"
FAVOURITES_DIR = WALLPAPER_DIR / "Favourites"
MIN_WIDTH = 2560
MIN_HEIGHT = 1440
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

# User settings live in SETTINGS_FILE (created from these defaults on first run) and can be
# changed from the tray menu or by editing the file.
#   chances: share of changes for each source; whatever's left goes to general Wallhaven
#   game_*:  a dedicated Wallhaven share for one favourite game
#   local_folders: your own image folders (top-level images only, not subfolders)
DEFAULT_SETTINGS = {
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
INTERVAL_CHOICES = [15, 30, 60, 120]  # minutes, offered in the tray menu
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

# Wallhaven search queries for variety
WALLHAVEN_QUERIES = [
    # Scenery (all verified 10+ results at 2560x1440)
    "landscape 4k",
    "sunset clouds",
    "aurora borealis",
    "cherry blossom japan",
    "milky way landscape",
    "desert dunes",
    "foggy mountains",
    "tropical beach",
    "mountains",
    "ocean",
    "forest",
    "snow",
    "rain",
    "storm",
    "clouds",
    "sky",
    "lake",
    "river",
    "island",
    "cave",
    "glacier",
    "canyon",
    # Urban / Street
    "cityscape night",
    "neon city rain",
    "futuristic city",
    "cyberpunk alley",
    "cyberpunk city",
    "neon lights",
    "skyscraper",
    "bridge night",
    # Space / Cosmos
    "nebula",
    "sci-fi concept art",
    "star wars",
    "mass effect",
    "space station",
    "eclipse",
    "space nebula",
    "galaxy",
    "milky way",
    # Digital Art / Fantasy / Dark
    "digital art fantasy",
    "concept art environment",
    "concept art dark",
    "dragon fire",
    "dark souls",
    "witcher geralt",
    "lord of the rings",
    "pixel art landscape",
    "cyberpunk girl",
    "dark fantasy",
    "dark castle",
    "gothic",
    "demon",
    "skull",
    "raven dark",
    "dark art",
    "void",
    "dark",
    "shadow",
    "dark landscape",
    "dark forest",
    "dark ocean",
    "dark mountain",
    "witch",
    "dark knight",
    "reaper",
    "dark angel",
    "dark warrior",
    "abyss",
    "ancient ruins",
    "dungeon",
    "castle",
    "ruins",
    "temple",
    "cathedral",
    "lighthouse",
    # Aesthetic / Abstract / Art
    "synthwave",
    "vaporwave",
    "glitch art",
    "fractal art",
    "dark abstract",
    "abstract dark",
    "smoke dark",
    "dark minimal",
    "monochrome",
    "noir",
    "oil painting",
    "watercolor",
    "digital painting",
    "surreal art",
    "surrealism",
    "minimalist",
    # Moon / Night
    "moon",
    "moonlight",
    "blood moon",
    "full moon",
    "crescent moon",
    "lunar",
    "night sky",
    "starry night",
    "dark sky",
    # Anime / Manga
    "anime scenery rain",
    "demon slayer",
    "jujutsu kaisen",
    "chainsaw man",
    "one piece",
    "evangelion",
    "evangelion unit",
    "solo leveling",
    "frieren",
    "spy x family",
    "studio ghibli",
    "akira",
    "bleach anime",
    "naruto",
    "dragon ball",
    # Games
    "elden ring",
    "zelda breath of the wild",
    "cyberpunk 2077 night city",
    "ghost of tsushima",
    "hollow knight",
    "final fantasy",
    "god of war",
    "horizon zero dawn",
    "red dead redemption 2",
    "sekiro",
    "hades game",
    "nier automata",
    "league of legends",
    "the last of us",
    "persona 5",
    "genshin impact",
    "resident evil",
    "skyrim",
    "fallout",
    "cyber",
    "hologram",
    # Movies / Series
    "blade runner",
    "dune",
    "arcane",
    "batman",
    "spider-verse",
]

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
        logging.StreamHandler(),
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


class Settings:
    """settings.json, shared by the tray menu and the wallpaper changer."""

    def __init__(self, path: Path):
        self.path = path
        # Re-entrant: update() holds it while calling reload() and save(), and the
        # wallpaper thread's reload() must wait for a tray change to finish saving
        self.lock = threading.RLock()
        self.data = copy.deepcopy(DEFAULT_SETTINGS)
        self.reload()

    def reload(self) -> bool:
        """Re-read the file. On a broken file, keep the current settings and return False."""
        with self.lock:
            if not self.path.exists():
                self.data = copy.deepcopy(DEFAULT_SETTINGS)
                self.save()
                return True
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                log.warning(f"Can't read {self.path.name}, keeping previous settings: {e}")
                return False
            self.data = _merge_settings(DEFAULT_SETTINGS, loaded)
            return True

    def save(self):
        """Write via a temp file so a crash mid-save can't leave a half-written file."""
        with self.lock:
            tmp = self.path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)

    def update(self, change) -> bool:
        """Reload, apply change(data), save. Won't overwrite a file the user broke by hand."""
        with self.lock:
            if not self.reload():
                return False
            change(self.data)
            self.save()
            return True

    @property
    def interval_seconds(self) -> int:
        return max(1, int(self.data["interval_minutes"])) * 60

    def enabled(self, source: str) -> bool:
        return self.data["sources"][source]

    def chance(self, source: str) -> float:
        return self.data["chances"][source]

    @property
    def local_folders(self) -> list[Path]:
        return [Path(f) for f in self.data["local_folders"]]

    @property
    def game_folders(self) -> list[Path]:
        return [Path(f) for f in self.data["game_folders"]]


settings = Settings(SETTINGS_FILE)


@dataclasses.dataclass
class Wallpaper:
    """A wallpaper ready to set, and where it came from."""
    path: str
    source: str             # a key of SOURCE_LABELS
    title: str
    url: str | None = None  # web page for the image, if any


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


# ─── Image Validation ─────────────────────────────────────────
def fits_screen(w: int, h: int, min_ratio: float = 1.0, max_ratio: float = float("inf"),
                check_size: bool = True) -> bool:
    """Is a w x h image a usable wallpaper: wider than tall (by min_ratio..max_ratio) and 1440p+?"""
    if h <= 0 or not (min_ratio < w / h <= max_ratio):
        return False
    return not check_size or (w >= MIN_WIDTH and h >= MIN_HEIGHT)


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
def fetch_from_wallhaven(queries: list[str] | None = None, sorting: str | None = None,
                         source: str = "wallhaven") -> Wallpaper | None:
    """Fetch a random 1440p+ wallpaper from Wallhaven."""
    if queries is None:
        queries = WALLHAVEN_QUERIES
    if not queries:  # e.g. game_queries emptied in settings.json: don't fall back to general
        return None
    query = random.choice(queries)
    sorting = sorting or random.choices(
        ["toplist", "hot", "random"], weights=[5, 3, 2], k=1)[0]

    params = {
        "q": query,
        "categories": "110",      # general + anime (no people: avoids celebrity photos)
        "purity": "100",          # SFW only
        "atleast": f"{MIN_WIDTH}x{MIN_HEIGHT}",
        "ratios": "landscape",
        "sorting": sorting,
        "order": "desc",
        "page": 1,
    }
    if sorting == "toplist":
        params["topRange"] = random.choice(["3M", "6M", "1y"])

    try:
        log.info(f"Trying Wallhaven: query='{query}', sorting={sorting}")
        resp = safe_get("https://wallhaven.cc/api/v1/search", params=params,
                        max_bytes=MAX_API_BYTES)
        if resp.status_code != 200:
            log.warning(f"Wallhaven returned {resp.status_code}")
            return None

        data = resp.json()
        wallpapers = data.get("data", [])
        if not wallpapers:
            log.info("Wallhaven returned no results")
            return None

        random.shuffle(wallpapers)
        seen = load_seen_ids()

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
                                 wp.get("url"))

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
        seen = load_seen_ids()
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
        return Wallpaper(str(tmp_path), "museum", title, obj.get("objectURL"))
    tmp_path.unlink(missing_ok=True)
    return None


def is_landscape_wallpaper(image_path: Path) -> bool:
    """Check a local image is 1440p+ and landscape."""
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


def pick_local_wallpaper(folders: list[Path] | None = None) -> Wallpaper | None:
    """Pick a random image from the folders (default: local folders), cycling before repeating."""
    if folders is None:
        folders = settings.local_folders
    candidates = [
        p for folder in folders if folder.is_dir()
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in LOCAL_EXTENSIONS
    ]
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
                return Wallpaper(str(path), "local", path.name)

    LOCAL_HISTORY_FILE.write_text("\n".join(seen), encoding="utf-8")
    return None


# ─── Core Logic ───────────────────────────────────────────────
def fetch_source(source: str) -> Wallpaper | None:
    """Get one wallpaper from the named source."""
    if source == "local":
        return pick_local_wallpaper()
    if source == "game":
        # Few game wallpapers exist on Wallhaven: "random" sorting reaches all of them
        # (toplist only returns a handful). Once they've all been shown, use the game folders.
        queries = settings.data["game_queries"]
        wallpaper = queries and download_wallpaper(
            lambda: fetch_from_wallhaven(queries, "random", source="game"), attempts=2)
        return wallpaper or pick_local_wallpaper(settings.game_folders)
    if source == "museum":
        return download_wallpaper(fetch_from_museum, attempts=3)
    return download_wallpaper(fetch_from_wallhaven)


def source_weights() -> dict[str, float]:
    """Share of changes per enabled source; general Wallhaven gets whatever's left."""
    chances = {s: settings.chance(s) for s in ("local", "game", "museum")}
    weights = {**chances, "wallhaven": max(0.0, 1 - sum(chances.values()))}
    return {s: w for s, w in weights.items() if w > 0 and settings.enabled(s)}


def get_new_wallpaper() -> Wallpaper | None:
    """Pick a source at random by weight, falling back to the others if it fails."""
    weights = source_weights()
    if not weights:
        log.warning("Every source is turned off (or has a chance of 0)")
        return None
    choice = random.choices(list(weights), weights=list(weights.values()), k=1)[0]

    # Fallbacks: general Wallhaven, then local folders (e.g. when offline)
    order = [choice, "wallhaven", "local"]
    tried = set()
    for source in order:
        if source in tried or not settings.enabled(source):
            continue
        tried.add(source)
        wallpaper = fetch_source(source)
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
        self.wallpapers_set = 0
        self.elapsed = 0
        self.change_lock = threading.Lock()  # one wallpaper change at a time
        self.folder_dialog_open = False

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

    def _change_wallpaper(self):
        """Fetch and set a new wallpaper, unless a change is already in progress."""
        if not self.change_lock.acquire(blocking=False):
            log.info("A wallpaper change is already in progress, ignoring this one")
            return
        try:
            self._do_change_wallpaper()
        finally:
            self.change_lock.release()

    def _do_change_wallpaper(self):
        if is_fullscreen_app_running():
            log.info("Fullscreen app detected, skipping wallpaper change")
            return

        settings.reload()  # pick up hand edits to settings.json
        log.info("Fetching new wallpaper...")
        wallpaper = get_new_wallpaper()
        if not wallpaper:
            log.warning("Could not fetch a new wallpaper this round")
            return
        try:
            set_wallpaper(wallpaper.path)
            set_lock_screen(wallpaper.path)
            self.current = wallpaper
            self.wallpapers_set += 1
            if self.icon:
                self.icon.title = f"WallSwap: {wallpaper.title}"[:127]
            self.refresh_menu()
        except Exception as e:
            log.error(f"Failed to set wallpaper: {e}")

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

    def _change_setting(self, change, done_message: str | None = None):
        if settings.update(change):
            self.refresh_menu()
            if done_message:
                self.notify(done_message)
        else:
            self.notify("settings.json has a mistake in it, so nothing was changed. "
                        "Fix it or delete it to go back to the defaults.")

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
        for folder in folders:
            tag = f"  ({settings.data['game_name']})" if folder in game else ""
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
        if self.folder_dialog_open:
            return
        self.folder_dialog_open = True  # set before the thread starts, so a double-click can't open two
        threading.Thread(target=self._pick_folder, daemon=True).start()

    def _pick_folder(self):
        """Ask for a folder with the standard Windows dialog, then add it."""
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            folder = filedialog.askdirectory(
                parent=root, title="Choose a folder of wallpapers",
                initialdir=str(Path.home() / "Pictures"))
            root.destroy()
        except Exception as e:
            log.error(f"Folder picker failed: {e}")
            folder = ""
        finally:
            self.folder_dialog_open = False

        if not folder:
            return
        folder = str(Path(folder))
        if folder in settings.data["local_folders"]:
            self.notify(f"Already using {folder}")
            return
        self._change_setting(
            lambda d: d["local_folders"].append(folder) if folder not in d["local_folders"] else None,
            f"Added {folder}")

    def open_settings(self, _=None):
        """Open settings.json in Notepad."""
        if not SETTINGS_FILE.exists():
            settings.save()
        subprocess.Popen(["notepad.exe", str(SETTINGS_FILE)])
        self.notify("Changes you make in the file apply from the next wallpaper change.")

    def open_folder(self, _=None):
        """Open the wallpaper save folder."""
        os.startfile(str(WALLPAPER_DIR))

    def quit_app(self, _=None):
        """Exit the application."""
        self.running = False
        if self.icon:
            self.icon.stop()

    def timer_loop(self):
        """Background timer that triggers wallpaper changes."""
        # Initial wallpaper on startup
        self._change_wallpaper()

        self.elapsed = 0
        while self.running:
            time.sleep(5)
            if not self.running:
                break
            if self.paused:
                continue

            self.elapsed += 5
            if self.elapsed >= settings.interval_seconds:
                self.elapsed = 0
                self._change_wallpaper()

    def build_menu(self) -> pystray.Menu:
        has_current = lambda item: self.current is not None  # noqa: E731
        return pystray.Menu(
            pystray.MenuItem("🔄 Next Wallpaper", self.next_wallpaper, default=True),
            pystray.MenuItem("⭐ Favourite", self.save_favourite, enabled=has_current),
            pystray.MenuItem("🔗 Details", self.open_source, enabled=has_current),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⏸ Pause", self.toggle_pause, checked=lambda item: self.paused),
            pystray.MenuItem("⏱ Interval", pystray.Menu(
                *[self.interval_item(m) for m in INTERVAL_CHOICES])),
            pystray.MenuItem("🌐 Sources", pystray.Menu(
                self.source_item("wallhaven", "Wallhaven (general)"),
                self.source_item("game", lambda item: f"Wallhaven: {settings.data['game_name']}"),
                self.source_item("museum", "The Met (paintings)"),
                self.source_item("local", "My folders"),
            )),
            pystray.MenuItem("📂 My Folders", pystray.Menu(self.local_folder_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙️ Settings", self.open_settings),
            pystray.MenuItem("📁 WallSwap Folder", self.open_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Quit", self.quit_app),
        )

    def run(self):
        """Start the system tray application."""
        log.info("=" * 50)
        log.info("WallSwap starting up!")
        log.info(f"Wallpaper folder: {WALLPAPER_DIR}")
        log.info(f"Interval: {settings.interval_seconds // 60} minutes")
        log.info(f"Min resolution: {MIN_WIDTH}x{MIN_HEIGHT}")
        log.info("=" * 50)

        self.icon = pystray.Icon(
            "WallSwap",
            self.create_tray_icon(),
            "WallSwap - Fresh Wallpapers",
            self.build_menu(),
        )

        # Start timer in background thread
        self.timer_thread = threading.Thread(
            target=self.timer_loop, daemon=True)
        self.timer_thread.start()

        # Run the tray icon (blocks until quit)
        self.icon.run()

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
