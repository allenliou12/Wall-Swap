# WallSwap — Architecture (one page)

> How the code is built today. Checked against `wallpaper_changer.py` and `settings_window.py` on 2026-11-09.
> Update it when a section, thread, file on disk or new module appears.

## The parts

Two files. `wallpaper_changer.py` holds everything but the window, split by `# ─── … ───` banners:

| Section | Lines | Role tag | What it does |
|---|---|---|---|
| Configuration | `:56-237` | `app` / `sources` | paths, limits, default and legacy settings, topic labels and the old search lists |
| Setup | `:238-258` | `app` | creates the WallSwap folder, Pillow pixel cap, logging (runs on import) |
| Settings | `:259-499` | `app` | `_merge_settings`, migration, `clean_search`, `settings_patch`/`apply_patch`, `Settings` (settings.json, `.bak`, re-entrant lock), `Wallpaper` |
| History + cleanup | `:500-540` | `sources` | seen ids, keep-newest-50 cleanup |
| Windows API | `:541-634` | `windows` | desktop wallpaper, lock screen (WinRT), fullscreen check |
| Startup | `:635-781` | `windows` | Start with Windows: `Startup\WallSwap.lnk` via PowerShell + IShellLinkW |
| Image validation | `:782-790` | `sources` | `fits_screen` |
| Safe downloads | `:791-843` | `sources` | `safe_get`: host allow-list, size and time caps, checked redirects |
| Sources | `:844-1058` | `sources` | Wallhaven, Met, local folders |
| Core logic | `:1059-1184` | `app` | query pool from ticked topics, source availability, weights and shares, fallback order, save as JPEG |
| System tray app | `:1185-1639` | `app` | `WallSwapApp`: menu, timer loop, favourites, UI queue, folder dialog, settings window wiring |
| Entry point | `:1640-1650` | `windows` | single-instance mutex, start |

`settings_window.py` is the CustomTkinter settings window (`SettingsWindow`, `TagList`, `FolderList`). It never
imports `wallpaper_changer`: `WallSwapApp._show_settings` hands it a `WindowDeps` with a settings snapshot and
the functions it needs. Both `customtkinter` and `settings_window` are imported lazily in `run()`.

## Threads

- **Main thread (Tk)**: `run()` → `root.mainloop()` on a hidden CTk root, created before the tray icon. Every Tk call
  happens here: the settings window, the folder dialog (`ask_folder`) and Save.
- **Tray thread**: `pystray` via `icon.run_detached`; menu callbacks. Anything that needs Tk goes through
  `post_to_ui`, a queue `_drain_ui` empties every `UI_POLL_MS`. One Add Folder may be pending at a time.
- **Tray setup thread**: `_on_tray_ready` shows the icon, then starts the timer.
- **Timer thread**: `timer_loop`: one change at start, then every `interval_minutes`, checking every 5 s.
- **Change threads**: "Next Wallpaper" starts one; `change_lock` drops a second concurrent change (INV-13).
- **Quit**: `quit_app` stops the timer loop, queues `_close_ui` (closes the window, ends mainloop) and stops the icon.
- Shared state: `settings` (guarded by its `RLock`; readers take `snapshot()`), `WallSwapApp.current`.

## Files on disk

In `~/Pictures/WallSwap`: `settings.json` · `settings.json.bak` (the pre-settings-window file, kept once) ·
`wallswap.log` (rotating) · `seen_ids.txt` (downloaded ids) · `seen_local.txt` (local cycle) ·
`wallswap_<wallhaven|met>_<timestamp>.jpg` (newest 50) · `_temp_*.jpg` (in-flight) · `Favourites/` (never cleaned).

Outside it: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\WallSwap.lnk`, only when the user turns on
Start with Windows (INV-16).

## The packaged exe

`WallSwap.spec` builds a windowed onedir app with PyInstaller: `dist\WallSwap\WallSwap.exe` plus `_internal\`
(Python, the icon, customtkinter's themes, the `winrt` bindings). Frozen, `FROZEN` is true, `ICON_PATH` resolves
under `sys._MEIPASS`, logging skips the console handler (`sys.stderr` is `None`), and the Startup shortcut targets
the exe itself with no arguments.

`installer\WallSwap.iss` (Inno Setup) wraps that folder into `dist\WallSwap-Setup.exe`: per-user, no admin, into
`%LOCALAPPDATA%\Programs\WallSwap`, fixed `AppId` so a newer version upgrades in place. `AppMutex` matches the app's
single-instance mutex, so Setup and the uninstaller ask the user to quit a running WallSwap first. Two ticked-by-default tasks add a
desktop shortcut and `{userstartup}\WallSwap.lnk`, the same file and target as the app's frozen
`startup_shortcut_spec`; unticked, an existing one is left alone. The uninstaller deletes `Startup\WallSwap.lnk`
(whoever made it) and never touches `Pictures\WallSwap`. At startup the frozen app runs `take_over_startup_shortcut`
on a background thread: an existing `Startup\WallSwap.lnk` whose target isn't this exe (`should_repoint`) is
rewritten to it; it never creates the file. `build.ps1` builds the exe,
the portable zip and the installer.

## One wallpaper change, end to end

1. Timer or menu → `_change_wallpaper` takes `change_lock` (or drops the request).
2. `_do_change_wallpaper`: skip if a fullscreen app is in front; `settings.reload()` picks up hand edits.
3. `get_new_wallpaper`: one `snapshot()`; weighted pick from `source_weights` (off, empty and 0% sources dropped),
   then fall back to general Wallhaven, then local, but only to sources that have a share.
4. Online sources run through `download_wallpaper`: fetch → re-save as JPEG → delete the temp file → cleanup.
5. `set_wallpaper` (user32) and `set_lock_screen` (WinRT); update `current`, tooltip and menu.

## Dependencies

Runtime: `pystray`, `Pillow`, `requests`, `customtkinter` (pulls in `darkdetect`, `packaging`); `winrt-*` on Windows
only (lock screen). Dev: `ruff`, `pytest`, `pyinstaller`. External services: `wallhaven.cc` API, Met collection API
(`collectionapi.metmuseum.org`). No API keys.
