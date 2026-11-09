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
import ctypes
import io
import logging
import os
import random
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

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
CHANGE_INTERVAL = 30 * 60  # 30 minutes in seconds
MIN_WIDTH = 2560
MIN_HEIGHT = 1440
MAX_WALLPAPERS = 50         # keep only the most recent on disk
MAX_SEEN_IDS = 5000         # dedup history cap (oldest dropped first)
USER_AGENT = "WallSwap/1.0 (Windows Desktop Wallpaper Changer)"

# Local folders to mix in alongside Wallhaven (top-level images only, not subfolders)
LOCAL_FOLDERS = [
    Path.home() / "Pictures" / "Path of Exile 2",
]
# Source mix per change (whatever's left over goes to general Wallhaven searches):
#   PoE total ~40% = LOCAL_CHANCE + POE_WALLHAVEN_CHANCE
LOCAL_CHANCE = 0.2          # your local folders (PoE 2 screenshots)
POE_WALLHAVEN_CHANCE = 0.2  # Path of Exile searches on Wallhaven
POE_WALLHAVEN_QUERIES = ["path of exile", "path of exile 2"]
LOCAL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
LOCAL_HISTORY_FILE = WALLPAPER_DIR / "seen_local.txt"

# Public-domain paintings from The Metropolitan Museum of Art (no API key needed)
MUSEUM_CHANCE = 0.15        # chance each change uses a museum painting
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
    "3d render",
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


def load_seen_ids() -> set[str]:
    """Load previously downloaded wallpaper IDs from disk."""
    try:
        return set(HISTORY_FILE.read_text().splitlines())
    except FileNotFoundError:
        return set()


def save_seen_id(wp_id: str):
    """Append a wallpaper ID to the history file, dropping the oldest past the cap."""
    try:
        history = HISTORY_FILE.read_text().splitlines()  # oldest first
    except FileNotFoundError:
        history = []
    if wp_id in history:
        return
    history.append(wp_id)
    HISTORY_FILE.write_text("\n".join(history[-MAX_SEEN_IDS:]))


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

        import ctypes.wintypes
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)

        # Check if foreground window covers the full screen
        return (
            rect.left <= 0
            and rect.top <= 0
            and rect.right >= screen_w
            and rect.bottom >= screen_h
        )
    except Exception:
        return False


# ─── Image Validation ─────────────────────────────────────────
def is_valid_resolution(image_path: str) -> bool:
    """Check if image meets minimum 1440p resolution."""
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            return w >= MIN_WIDTH and h >= MIN_HEIGHT
    except Exception as e:
        log.warning(f"Can't read image {image_path}: {e}")
        return False


# ─── Sources ──────────────────────────────────────────────────
def fetch_from_wallhaven(queries: list[str] | None = None, sorting: str | None = None) -> str | None:
    """Fetch a random 1440p+ wallpaper from Wallhaven."""
    query = random.choice(queries or WALLHAVEN_QUERIES)
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
        resp = requests.get(
            "https://wallhaven.cc/api/v1/search",
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=15,
        )
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
            if wp_w < MIN_WIDTH or wp_h < MIN_HEIGHT:
                continue
            if wp_h > wp_w:  # skip vertical/portrait images
                continue
            if not wp_url:
                continue

            try:
                img_resp = requests.get(
                    wp_url,
                    headers={"User-Agent": USER_AGENT},
                    timeout=20,
                )
            except requests.RequestException as e:
                log.warning(f"Wallhaven download failed for {wp_id}: {e}")
                continue  # try the next result instead of giving up on this search
            if img_resp.status_code == 200 and len(img_resp.content) > 50_000:
                tmp_path = WALLPAPER_DIR / "_temp_wallhaven.jpg"
                tmp_path.write_bytes(img_resp.content)
                save_seen_id(wp_id)
                return str(tmp_path)

    except Exception as e:
        log.warning(f"Wallhaven fetch failed: {e}")
    return None


def fetch_from_museum() -> str | None:
    """Fetch a random public-domain painting from the Met that fits a wide screen."""
    query = random.choice(MUSEUM_QUERIES)
    try:
        log.info(f"Trying the Met: query='{query}'")
        object_ids = []
        for dept in MUSEUM_DEPARTMENTS:
            resp = requests.get(
                f"{MUSEUM_API}/v1.1/search",
                params={"q": query, "hasImages": "true", "limit": 100, **dept},
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
            if resp.status_code == 200:
                object_ids += resp.json().get("objectIDs") or []
            else:
                log.warning(f"The Met returned {resp.status_code}")
        random.shuffle(object_ids)
        seen = load_seen_ids()
        checked = 0

        for obj_id in object_ids:
            seen_key = f"met_{obj_id}"
            if seen_key in seen:
                continue
            if checked >= 15:  # don't hammer the API
                break
            checked += 1
            save_seen_id(seen_key)  # don't retry this one, whether or not it fits

            try:
                path = _try_museum_object(obj_id)
            except Exception as e:  # one bad painting shouldn't end the whole search
                log.warning(f"Met object {obj_id} failed: {e}")
                (WALLPAPER_DIR / "_temp_museum.jpg").unlink(missing_ok=True)
                continue
            if path:
                return path

    except Exception as e:
        log.warning(f"Met fetch failed: {e}")
    return None


def _try_museum_object(obj_id: int) -> str | None:
    """Download one Met object if it's a public-domain painting that fits a wide screen."""
    obj_resp = requests.get(
        f"{MUSEUM_API}/v1/objects/{obj_id}",
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    if obj_resp.status_code != 200:
        return None
    obj = obj_resp.json()
    image_url = obj.get("primaryImage")
    if not obj.get("isPublicDomain") or not image_url:
        return None

    # Check the shape on the small preview before downloading the full image
    small_url = obj.get("primaryImageSmall")
    if small_url:
        small = requests.get(
            small_url, headers={"User-Agent": USER_AGENT}, timeout=15)
        if small.status_code != 200:
            return None
        with Image.open(io.BytesIO(small.content)) as preview:
            pw, ph = preview.size
        if not MUSEUM_MIN_RATIO <= pw / ph <= MUSEUM_MAX_RATIO:
            return None

    img_resp = requests.get(
        image_url, headers={"User-Agent": USER_AGENT}, timeout=30)
    if img_resp.status_code != 200:
        return None

    tmp_path = WALLPAPER_DIR / "_temp_museum.jpg"
    tmp_path.write_bytes(img_resp.content)
    with Image.open(tmp_path) as img:
        w, h = img.size
    ratio = w / h
    if w >= MIN_WIDTH and h >= MIN_HEIGHT and MUSEUM_MIN_RATIO <= ratio <= MUSEUM_MAX_RATIO:
        artist = obj.get("artistDisplayName") or "Unknown artist"
        log.info(f"Met painting: '{obj.get('title')}' by {artist} ({w}x{h})")
        return str(tmp_path)
    tmp_path.unlink(missing_ok=True)
    return None


def is_landscape_wallpaper(image_path: Path) -> bool:
    """Check a local image is 1440p+ and landscape."""
    try:
        with Image.open(image_path) as img:
            w, h = img.size
            return w >= MIN_WIDTH and h >= MIN_HEIGHT and w > h
    except Exception as e:
        log.warning(f"Can't read image {image_path}: {e}")
        return False


def pick_local_wallpaper() -> str | None:
    """Pick a random image from LOCAL_FOLDERS, cycling through all before repeating."""
    candidates = [
        p for folder in LOCAL_FOLDERS if folder.is_dir()
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
            seen = set()
        random.shuffle(pool)
        for path in pool:
            seen.add(str(path))
            if is_landscape_wallpaper(path):
                LOCAL_HISTORY_FILE.write_text("\n".join(seen), encoding="utf-8")
                log.info(f"Picked local wallpaper: {path}")
                return str(path)

    LOCAL_HISTORY_FILE.write_text("\n".join(seen), encoding="utf-8")
    return None


# ─── Core Logic ───────────────────────────────────────────────
def get_new_wallpaper() -> str | None:
    """Pick a source at random (local / PoE / museum / Wallhaven), falling back if it fails."""
    roll = random.random()
    if roll < LOCAL_CHANCE:
        path = pick_local_wallpaper()
        if path:
            return path
    elif roll < LOCAL_CHANCE + POE_WALLHAVEN_CHANCE:
        # Only ~30 PoE wallpapers exist on Wallhaven: "random" sorting reaches all of them
        # (toplist only returns a few), and once all are seen, use the local PoE folder instead.
        path = download_wallpaper(
            lambda: fetch_from_wallhaven(POE_WALLHAVEN_QUERIES, "random"),
            "wallhaven", attempts=2)
        if path:
            return path
        path = pick_local_wallpaper()
        if path:
            return path
    elif roll < LOCAL_CHANCE + POE_WALLHAVEN_CHANCE + MUSEUM_CHANCE:
        path = download_wallpaper(fetch_from_museum, "met", attempts=3)
        if path:
            return path

    path = download_wallpaper(fetch_from_wallhaven, "wallhaven")
    if path:
        return path

    # Wallhaven down / offline: fall back to local images
    return pick_local_wallpaper()


def download_wallpaper(fetch, source: str, attempts: int = 5) -> str | None:
    """Run an online fetcher and save its result as a JPEG in WALLPAPER_DIR."""
    for attempt in range(attempts):
        try:
            tmp_path = fetch()
            if tmp_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                final_name = f"wallswap_{source}_{timestamp}.jpg"
                final_path = WALLPAPER_DIR / final_name

                with Image.open(tmp_path) as img:
                    img = img.convert("RGB")
                    img.save(str(final_path), "JPEG", quality=95)

                Path(tmp_path).unlink(missing_ok=True)
                log.info(f"Saved: {final_name}")
                cleanup_old_wallpapers()
                return str(final_path)
        except Exception as e:
            log.warning(f"{source} attempt {attempt + 1} failed: {e}")

    log.warning(f"All {source} attempts failed this round")
    return None


# ─── System Tray App ─────────────────────────────────────────
class WallSwapApp:
    def __init__(self):
        self.paused = False
        self.running = True
        self.icon = None
        self.timer_thread = None
        self.current_wallpaper = "None yet"
        self.wallpapers_set = 0
        self.elapsed = 0
        self.change_lock = threading.Lock()  # one wallpaper change at a time

    def create_tray_icon(self) -> Image.Image:
        """Load the app icon for the system tray."""
        size = 64
        try:
            img = Image.open(str(ICON_PATH))
            img = img.resize((size, size), Image.LANCZOS)
            if self.paused:
                # Tint orange when paused
                img = img.convert("RGBA")
                overlay = Image.new("RGBA", (size, size), (255, 165, 0, 100))
                img = Image.alpha_composite(img, overlay)
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

        log.info("Fetching new wallpaper...")
        path = get_new_wallpaper()
        if path:
            try:
                set_wallpaper(path)
                set_lock_screen(path)
                self.current_wallpaper = Path(path).name
                self.wallpapers_set += 1
            except Exception as e:
                log.error(f"Failed to set wallpaper: {e}")
        else:
            log.warning("Could not fetch a new wallpaper this round")

    def toggle_pause(self, _=None):
        """Pause/resume automatic wallpaper changing."""
        self.paused = not self.paused
        state = "PAUSED" if self.paused else "RESUMED"
        log.info(f"WallSwap {state}")
        # Update the icon
        if self.icon:
            self.icon.icon = self.create_tray_icon()

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
            if self.elapsed >= CHANGE_INTERVAL:
                self.elapsed = 0
                self._change_wallpaper()

    def run(self):
        """Start the system tray application."""
        log.info("=" * 50)
        log.info("WallSwap starting up!")
        log.info(f"Wallpaper folder: {WALLPAPER_DIR}")
        log.info(f"Interval: {CHANGE_INTERVAL // 60} minutes")
        log.info(f"Min resolution: {MIN_WIDTH}x{MIN_HEIGHT}")
        log.info("=" * 50)

        menu = pystray.Menu(
            pystray.MenuItem("🔄 Next Wallpaper",
                             self.next_wallpaper, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "⏸ Pause / Resume",
                self.toggle_pause,
            ),
            pystray.MenuItem("📁 Open Wallpaper Folder", self.open_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Quit WallSwap", self.quit_app),
        )

        self.icon = pystray.Icon(
            "WallSwap",
            self.create_tray_icon(),
            "WallSwap - Fresh Wallpapers",
            menu,
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
