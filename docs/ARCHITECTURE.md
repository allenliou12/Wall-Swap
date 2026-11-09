# WallSwap — Architecture (one page)

> **Status:** reference-canon (as-built). Verified against `wallpaper_changer.py` on 2026-11-09. Update when a
> section, thread, file on disk or new module appears (`.claude/rules/wiki-lifecycle.md`).

## The parts

Everything is one file, `wallpaper_changer.py`, split by `# ─── … ───` banners:

| Section | Lines | Role tag | What it does |
|---|---|---|---|
| Configuration | `:54-289` | `app` / `sources` | paths, limits, default settings, search query lists |
| Setup | `:291-309` | `app` | creates the WallSwap folder, Pillow pixel cap, logging (runs on import) |
| Settings | `:312-400` | `app` | `Settings` (settings.json, re-entrant lock), `Wallpaper` record |
| History + cleanup | `:403-441` | `sources` | seen ids, keep-newest-50 cleanup |
| Windows API | `:444-535` | `windows` | desktop wallpaper, lock screen (WinRT), fullscreen check |
| Image validation | `:538-544` | `sources` | `fits_screen` |
| Safe downloads | `:547-597` | `sources` | `safe_get`: host allow-list, size and time caps, checked redirects |
| Sources | `:600-816` | `sources` | Wallhaven, Met, local folders |
| Core logic | `:819-887` | `app` | source weights, fallback order, save as JPEG |
| System tray app | `:890-1201` | `app` | `WallSwapApp`: menu, timer loop, favourites, settings actions |
| Entry point | `:1204-1214` | `windows` | single-instance mutex, start |

## Threads

- **Tray thread** (main): `pystray` event loop, menu callbacks.
- **Timer thread**: `timer_loop` — one change at start, then every `interval_minutes`, checking every 5 s.
- **Change threads**: "Next Wallpaper" starts one; `change_lock` drops a second concurrent change (INV-13).
- **Folder-picker thread**: tkinter dialog; `folder_dialog_open` blocks a second dialog.
- Shared state: `settings` (guarded by its `RLock`), `WallSwapApp.current`.

## Files on disk (`~/Pictures/WallSwap`)

`settings.json` · `wallswap.log` (rotating) · `seen_ids.txt` (downloaded ids) · `seen_local.txt` (local cycle) ·
`wallswap_<wallhaven|met>_<timestamp>.jpg` (newest 50) · `_temp_*.jpg` (in-flight) · `Favourites/` (never cleaned).

## One wallpaper change, end to end

1. Timer or menu → `_change_wallpaper` takes `change_lock` (or drops the request).
2. `_do_change_wallpaper`: skip if a fullscreen app is in front; `settings.reload()` picks up hand edits.
3. `get_new_wallpaper`: weighted pick from `source_weights`, then fall back to general Wallhaven, then local.
4. Online sources run through `download_wallpaper`: fetch → re-save as JPEG → delete the temp file → cleanup.
5. `set_wallpaper` (user32) and `set_lock_screen` (WinRT); update `current`, tooltip and menu.

## Dependencies

Runtime: `pystray`, `Pillow`, `requests`; `winrt-*` on Windows only (lock screen). Dev: `ruff`, `pytest`.
External services: `wallhaven.cc` API, Met collection API (`collectionapi.metmuseum.org`). No API keys.
