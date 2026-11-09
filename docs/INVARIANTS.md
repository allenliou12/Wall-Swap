# WallSwap — Invariants and hazards

> **Status:** standard-canon, **declared conflict winner**. Every change keeps these rules; a plan that breaks one is
> rejected, not scored (`/feature` step 3). Each rule names the code that holds it today. Verified against
> `wallpaper_changer.py` on 2026-11-09. Rewrite in place when a rule changes (`.claude/rules/doc-lifecycle.md`).

## Invariants

IDs are stable: never renumber, retire with a note.

### Downloads and the network (security)

- **INV-1 · Only https, only the allowed sites.** Every network fetch goes through `safe_get`, which refuses any URL
  that is not https on `ALLOWED_HOSTS` or a subdomain, and re-checks every redirect hop (at most 3).
  Code: `wallpaper_changer.py:74`, `_check_url` `:566`, `safe_get` `:573`. A new source adds its host to
  `ALLOWED_HOSTS`, never a bare `requests.get`.
- **INV-2 · Bounded downloads.** One response may send at most `MAX_DOWNLOAD_BYTES` (images) or `MAX_API_BYTES`
  (JSON), and one request gives up after `DOWNLOAD_DEADLINE` seconds in total. Code: `:75-77`, `:585-596`.
- **INV-3 · Bounded image decoding.** Downloaded images over `MAX_IMAGE_PIXELS` raise instead of decoding (Pillow's
  bomb warning is an error). The user's own files are only measured, not decoded, so that limit is relaxed there.
  Code: `:78`, `:296-297`, `is_landscape_wallpaper` `:765`.
- **INV-4 · Only real web pages are opened.** "Details" opens a link only if it starts with `https://`; anything else
  falls back to showing the file. The link comes from API data. Code: `open_source` `:1011`.

### Content

- **INV-5 · Safe for work.** Wallhaven searches ask for SFW only (`purity=100`) and general + anime categories, no
  people (`categories=110`). Code: `fetch_from_wallhaven` `:613-615`.
- **INV-6 · Wallpaper-shaped images only.** Everything shown is landscape and at least `MIN_WIDTH` × `MIN_HEIGHT`
  (2560 × 1440); Met paintings also fall between `MUSEUM_MIN_RATIO` and `MUSEUM_MAX_RATIO`. Code: `fits_screen`
  `:539`, `:62-63`, `:109-110`.
- **INV-7 · Met paintings are public domain.** An object without `isPublicDomain` is never downloaded.
  Code: `_try_museum_object` `:735`.

### The user's files

- **INV-8 · The user's own folders are read-only.** Local and game folders are listed and measured, never written,
  moved or deleted. Code: `pick_local_wallpaper` `:781`.
- **INV-9 · Cleanup only touches WallSwap's own downloads.** Only `wallswap_*.jpg` directly inside the WallSwap
  folder are deleted, newest `MAX_WALLPAPERS` (50) kept. Favourites live in a subfolder the non-recursive glob never
  reaches. Code: `cleanup_old_wallpapers` `:429`, `:64`.
- **INV-10 · A broken settings file is never overwritten.** A file that fails to parse keeps the previous settings,
  and a tray change refuses to save over it. Saves go through a temp file, so a crash cannot leave half a file.
  Unknown keys and wrong types fall back to defaults. Code: `_merge_settings` `:313`, `Settings.reload` `:341`,
  `save` `:356`, `update` `:363`.

### Behaviour

- **INV-11 · No repeats until a source runs out.** Downloaded ids are remembered (newest `MAX_SEEN_IDS` = 5000);
  local images cycle through every file before repeating. Code: `:403-426`, `pick_local_wallpaper` `:781`.
- **INV-12 · A temporary failure never marks an image as seen.** Met 429/5xx and network errors skip the painting
  for now; only a definite yes/no is recorded. Code: `_museum_get` `:719`, `fetch_from_museum` `:691-712`.
- **INV-13 · One wallpaper change at a time.** A change requested while one is running is dropped. Code:
  `_change_wallpaper` `:954`.
- **INV-14 · No change while a fullscreen app (a game) is in front** — the change is skipped, not queued. Code:
  `_do_change_wallpaper` `:965`, `is_fullscreen_app_running` `:501`. "Fullscreen" = the foreground window covers
  the whole monitor it is on (any monitor), is not the desktop, and is not an ordinary maximized window (maximized
  *with* a full title bar). Mac-tested with a faked user32 (`tests/test_fullscreen.py`); real Windows behaviour is
  the verify-wallswap "Fullscreen skip" flow.
- **INV-15 · Turned-off sources are never used,** including as a fallback. An emptied `game_queries` does not fall
  back to general searches. Code: `source_weights` `:836`, `get_new_wallpaper` `:843`, `:606-607`.

## Hazards

Trigger → hidden failure → prevention → where it was verified.

- **HZ-1 · A function-level `import ctypes.wintypes` hides the module's `ctypes`.** Python then treats `ctypes` as a
  local name for the whole function, so the first `ctypes.windll` line raises `UnboundLocalError`; the blanket
  `except` turns that into "no fullscreen app", so INV-14 never holds. Prevention: import submodules at the top of the
  file or as `from ctypes import wintypes`; ruff rule F823 (in the gate) catches it. Verified 2026-11-09:
  `ruff check` F823 at `wallpaper_changer.py:479`, and a reproduction raised `UnboundLocalError`. Closed 2026-11-09:
  the import moved to the top of the file; `tests/test_fullscreen.py` fails if it comes back.
- **HZ-2 · Blanket `except Exception` around Windows calls turns bugs into silent "no".** `is_fullscreen_app_running`,
  `set_lock_screen` and the fetchers log and carry on, so a broken rule looks like "nothing happened". Prevention: a
  test for each rule that checks the rule's yes case, not only the no case.
- **HZ-3 · Importing the module touches the real home folder.** Import creates `~/Pictures/WallSwap`, writes
  `settings.json` and opens `wallswap.log` (`:292`, `:301-308`, `:391`). Prevention: tests set `HOME` to a temp dir
  before import (`tests/conftest.py`).
