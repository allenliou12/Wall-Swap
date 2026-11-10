# WallSwap — Invariants and hazards

> Rules every change keeps, and traps that have bitten before. Each rule names the code that holds it today.
> Checked against `wallpaper_changer.py` on 2026-11-09 (after the settings window). Rewrite a rule in place when it
> changes.

## Invariants

IDs are stable: never renumber, retire with a note.

### Downloads and the network (security)

- **INV-1 · Only https, only the allowed sites.** Every network fetch goes through `safe_get`, which refuses any URL
  that is not https on `ALLOWED_HOSTS` or a subdomain, and re-checks every redirect hop (at most 3).
  Code: `wallpaper_changer.py:76`, `_check_url` `:810`, `safe_get` `:817`. A new source adds its host to
  `ALLOWED_HOSTS`, never a bare `requests.get`.
- **INV-2 · Bounded downloads.** One response may send at most `MAX_DOWNLOAD_BYTES` (images) or `MAX_API_BYTES`
  (JSON), and one request gives up after `DOWNLOAD_DEADLINE` seconds in total. Code: `:77-79`, `:830-839`.
- **INV-3 · Bounded image decoding.** Downloaded images over `MAX_IMAGE_PIXELS` raise instead of decoding (Pillow's
  bomb warning is an error). The user's own files are only measured, not decoded, so that limit is relaxed there.
  Code: `:80`, `:243-244`, `is_landscape_wallpaper` `:1007`.
- **INV-4 · Only real web pages are opened.** "Details" opens a link only if it starts with `https://`; anything else
  falls back to showing the file. The link comes from API data. Code: `open_source` `:1314`.

### Content

- **INV-5 · Safe for work.** Wallhaven searches ask for SFW only (`purity=100`) and general + anime categories, no
  people (`categories=110`). Code: `fetch_from_wallhaven` `:856-857`. Search text the user types only ever fills
  `q`, and excluded words are added to it only as `-word` for plain words (`wallhaven_q` checks each again, at
  most `MAX_EXCLUDE_WORDS`), so neither can change another filter. Tests: `tests/test_exclude.py`.
- **INV-6 · Wallpaper-shaped images only.** Everything shown is landscape and at least `min_size()`: the size the
  user picked (`min_resolution`: 1080p, 1440p or 4K), or for "auto" (and any unknown value) the biggest connected
  screen's real pixel size (long side × short side), each side capped at `MIN_WIDTH` × `MIN_HEIGHT`
  (2560 × 1440), and exactly that cap when Windows won't report a screen. It is read fresh on every check, and
  Wallhaven's `atleast` filter uses the same size. Met paintings also fall between `MUSEUM_MIN_RATIO` and
  `MUSEUM_MAX_RATIO`. Tests: `tests/test_screen_size.py`. Code: `largest_screen`, `min_size`, `fits_screen`
  `:783`, `:64-65`, `:160-161`.
- **INV-7 · Met paintings are public domain.** An object without `isPublicDomain` is never downloaded.
  Code: `_try_museum_object` `:970`.

### The user's files

- **INV-8 · The user's own folders are read-only.** Local and game folders are listed and measured, never written,
  moved or deleted. Code: `pick_local_wallpaper` `:1023`. The settings window and the folder dialog only
  choose folders and edit the lists.
- **INV-9 · Cleanup only touches WallSwap's own downloads.** Only `wallswap_*.jpg` directly inside the WallSwap
  folder are deleted, newest `MAX_WALLPAPERS` (50) kept. Favourites live in a subfolder the non-recursive glob never
  reaches. Code: `cleanup_old_wallpapers` `:526`, `:66`.
- **INV-10 · A broken settings file is never overwritten.** A file that fails to parse, or parses to something that
  is not a JSON object, keeps the previous settings in memory (the neutral defaults at startup), and no save writes
  over it. Saves go through a temp file, so a crash cannot leave half a file; a save that can't be written returns
  False and changes nothing. Unknown keys and wrong types fall back to defaults. A file from before the settings
  window (no `topics`) is upgraded in memory on read and written only by a save, which first copies the original to
  `settings.json.bak` (never overwritten; if the copy fails the save is refused). The settings window writes only
  the settings it changed, under the same lock as tray changes. Code: `_merge_settings` `:260`, `Settings.reload`
  `:370`, `save` `:400`, `update` `:449`, `persist_migration` `:469`.

### Behaviour

- **INV-11 · No repeats until a source runs out.** Downloaded ids are remembered (newest `MAX_SEEN_IDS` = 5000);
  local images cycle through every file before repeating. Code: `:500-523`, `pick_local_wallpaper` `:1023`.
- **INV-17 · A blocked image is never shown again.** Never Show Again appends the image's key (Wallhaven id,
  `met_<id>` or a local file's path) to `blocked.txt`, which is never trimmed; every source skips blocked keys. It
  deletes only WallSwap's own download of that image (`is_own_download`, the INV-9 pattern), never a file in the
  user's folders (INV-8). Code: `load_blocked`, `block_image`, `never_show_again`. Tests: `tests/test_blocked.py`.
- **INV-18 · The update check only reads and tells.** It fetches `UPDATE_API_URL` (GitHub's latest-release data for
  this repo) through `safe_get`, compares version numbers and shows a notification (once per version when
  automatic) and a tray line. It never downloads or installs anything, and the page it opens is the fixed `RELEASES_URL`,
  never a link from the reply. `check_for_updates: false` stops the automatic check. Code: `latest_release`,
  `newer_version`, `_check_for_updates`. Tests: `tests/test_update_check.py`.
- **INV-12 · A temporary failure never marks an image as seen.** Met 429/5xx and network errors skip the painting
  for now; only a definite yes/no is recorded. Code: `_museum_get` `:961`, `fetch_from_museum` `:933-954`.
- **INV-13 · One wallpaper change at a time.** A change requested while one is running is dropped. Code:
  `_change_wallpaper` `:1257`.
- **INV-14 · No change while a fullscreen app (a game) is in front.** The change is skipped and tried
  again every `RETRY_SECONDS` (a minute) until the app is no longer in front; a change that fails (offline) is
  retried the same way, slowing to `SLOW_RETRY_SECONDS` after `FAST_RETRIES` failures in a row. The normal interval
  restarts from the change that worked; nothing is retried while paused. Code: `retry_plan`, `WallSwapApp.tick`
  (`tests/test_retry.py`),
  `_do_change_wallpaper` `:1267`, `is_fullscreen_app_running` `:598`. "Fullscreen" = the foreground window covers
  the whole monitor it is on (any monitor), is not the desktop, and is not an ordinary maximized window (maximized
  *with* a full title bar). Tested with a faked user32 (`tests/test_fullscreen.py`); the real-window checks
  (`tests/test_fullscreen_windows.py`) open fullscreen windows and take the focus, so they run only with
  `uv run pytest --desktop`.
- **INV-15 · Turned-off, empty and 0% sources are never used,** including as a fallback. A source with nothing to
  use (no ticked topic with searches, no folders, no game searches or game folders) or with weight 0 gets no share;
  the percentages the settings window shows are the real shares. An empty search list never falls back to other
  searches. Code: `source_available` `:1075`, `source_weights` `:1104`, `get_new_wallpaper` `:1140`, `:848`.
- **INV-16 · Outside its own folder, WallSwap writes only `Startup\WallSwap.lnk`,** and only when the user flips
  Start with Windows or, in the packaged exe, to re-point one that already exists at this exe (never creating it);
  that exact file is the only one it deletes there. The shortcut is written by an absolute-path PowerShell (Windows
  folder from the OS), with paths passed only through environment variables. (The installer, a separate program,
  also writes it when its sign-in box is ticked.) Code: `startup_shortcut_path` `:734`, `write_shortcut` `:762`,
  `take_over_startup_shortcut` `:813`, `set_start_with_windows` `:834`.

## Hazards

Trigger → hidden failure → prevention → where it was verified.

- **HZ-1 · A function-level `import ctypes.wintypes` hides the module's `ctypes`.** Python then treats `ctypes` as a
  local name for the whole function, so the first `ctypes.windll` line raises `UnboundLocalError`; the blanket
  `except` turns that into "no fullscreen app", so INV-14 never holds. Prevention: import submodules at the top of the
  file or as `from ctypes import wintypes`; ruff rule F823 (`uv run ruff check .`) catches it. Verified 2026-11-09:
  `ruff check` F823 at `wallpaper_changer.py:479`, and a reproduction raised `UnboundLocalError`. Closed 2026-11-09:
  the import moved to the top of the file; `tests/test_fullscreen.py` fails if it comes back.
- **HZ-2 · Blanket `except Exception` around Windows calls turns bugs into silent "no".** `is_fullscreen_app_running`,
  `set_lock_screen` and the fetchers log and carry on, so a broken rule looks like "nothing happened". Prevention: a
  test for each rule that checks the rule's yes case, not only the no case.
- **HZ-3 · Importing the module touches the real home folder.** Import creates `~/Pictures/WallSwap`, writes
  `settings.json` when it is missing (an old-format file is only upgraded in memory) and opens `wallswap.log`
  (`:239`, `:248`, `:488`). Prevention: tests set `HOME`, `USERPROFILE` and
  `APPDATA` to temp dirs before import (`tests/conftest.py`).
