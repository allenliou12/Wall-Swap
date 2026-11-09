# Settings window

> **Status:** built 2026-11-09 on `feat/settings-window` (light process from Wave 2 on, allen's call). Plan approved 2026-11-09 (HIGH impact on `_merge_settings`, `Settings.reload`,
> `fetch_from_wallhaven` accepted). Lane: **full panel** (settings persistence, the user's folders, a file
> written outside WallSwap's folder). Branch: `feat/settings-window` (cut before the first slice).

## What this is (and is not)

This plan builds a CustomTkinter Settings window in the new file `settings_window.py` (R3). It opens on first run and from the tray item "Settings…". All settings logic stays in `wallpaper_changer.py` as pure functions.

**Spine.** The **minimal** design is the base. All three designs scored 7/10, and minimal won the tie because it has the fewest moving parts and the best scope discipline. On top of it:
- **From forward:** migration happens in memory on read, and is written only from `run()` after the single-instance mutex is held.
- **From seams:**
  - the pure decision helpers `source_available`, `source_shares`, `settings_patch` and `clean_search`;
  - `ShortcutSpec`;
  - an injected dependency bundle, so the window never imports `wallpaper_changer`.

**Fixes from all three critiques are applied:**
- The patch is computed per setting, not per top-level key, and folders are applied as add/remove changes.
- The `.bak` is enforced inside `save()`.
- A JSON file that is not an object counts as broken.
- The Tk root is created before pystray.
- The UI queue drain is protected, and `run()` ends in `try/finally`.
- PowerShell is called by its absolute path.
- `CREATE_NO_WINDOW` falls back to 0 off Windows.
- Tests redirect `APPDATA`.
- `fetch_source` reads all its data from one snapshot.
- Builders do not edit canon docs.

**Dropped as scope creep:**
- the frozen-exe branch of the shortcut code;
- the `schema_version` key and the refusal of files from newer versions;
- a game-folder picker in the window;
- source on/off switches in the window;
- live refresh of an open window.

**Lane:** full panel. The feature touches settings persistence and the user's folders, and writes a file outside WallSwap's folder.

**Is not:** the PyInstaller `.exe`, the MIT licence or a GitHub release (later, separate work); no new download host;
no change to how wallpapers are fetched, checked or set.

## Affected components + comparison base

- Comparison base: `ff92bfd` (main, "test: check fullscreen detection against real windows on Windows").
- Roles: **app** (settings, migration, source mix, tray, threads, the window) · **windows** (Startup shortcut, Tk and
  pystray threading on win32, DPI) · **sources** (query pool, `fetch_from_wallhaven` / `pick_local_wallpaper`
  signatures).
- GitNexus `impact` (upstream, CLI, 2026-11-09): **HIGH** `_merge_settings` (6 impacted), `Settings.reload` (10),
  `fetch_from_wallhaven` (4); LOW `fetch_source`, `source_weights`, `get_new_wallpaper`, `build_menu`, `run`;
  UNKNOWN (pystray callbacks have no call edges) `add_local_folder`, `_pick_folder`, `open_settings`, `quit_app`,
  `local_folder_items`. The HIGH rows go to allen as one acceptance at the plan checkpoint.
- This run is on allen's Windows 11 PC, so the Windows check can run here (D2 assumed a Mac).

## Settled-decisions ledger

- settings.json stays the storage; hand edits keep working · INV-10, brief.
- A broken file is never overwritten; Save on a broken file refuses and says so · INV-10.
- Every network fetch stays in `safe_get`; no host added · INV-1..INV-3.
- SFW and no-people categories are fixed; typed text only reaches `q` · INV-5.
- The user's folders are read-only · INV-8. Cleanup only touches `wallswap_*.jpg` · INV-9.
- Turned-off sources are never used, including as a fallback · INV-15.
- Imports at the top of the file; ruff F823 in the gate · HZ-1, D1.
- Tests redirect HOME/USERPROFILE before import · HZ-3, `tests/conftest.py`.
- Commit messages: `feat:` etc., no attribution lines · AGENTS.md, `.githooks/commit-msg`.
- First run (no settings.json) opens the window · brief.
- The game source drops out with no game searches and no game folders · brief.
- Tray Interval / Sources / My Folders submenus stay; "Settings…" opens the window · brief ("update labels").
- Startup shortcut name `WallSwap.lnk`; allen's existing one (pythonw + script, wd `.venv\Scripts`, icon
  `wallswap.ico,0`) shows as On · live Startup folder.
- allen's topics all on (migrated); new users get the starter set · R1.
- No `security-implementer` agent type exists on this PC; trust-boundary slices use a Claude `general-purpose` agent
  on the reasoning tier with the same brief · orchestrator, 2026-11-09.
- Approved designs or mock-ups for this feature: **none**.

## Decision log

- **R1 [PM] RATIFIED 2026-11-09: editable topics.** Topics are tickable groups whose searches are removable tags with
  an add box; own keywords are tags. New users get a ~25-search starter set (general topics ticked). allen keeps all
  141 current searches, grouped, all ticked. The pick stays uniform per search. *Why:* the current list is allen's
  taste, not a default; one model covers topics and keywords.
- **R2 [PM] RATIFIED 2026-11-09: four source sliders with %.** Wallhaven, Met, folders and game each have a weight;
  no "remainder" rule. allen's mix shows 45/15/20/20. *Why:* readable; it's what the brief asked for.
- **R3 [YOU] RATIFIED 2026-11-09: window in `settings_window.py`.** It never imports `wallpaper_changer`; it gets a
  `WindowDeps` bundle. *Why:* keeps the main file focused and tests UI-free; PyInstaller bundles both.
- **P1 [YOU] proposed: migrate in memory on read, write only after the mutex.** *Why:* the still-running old app and
  a second start must never rewrite the file; `.bak` keeps the first original.
- **P2 [YOU] proposed: topics as nine fixed ids in `DEFAULT_SETTINGS`.** *Why:* `_merge_settings` handles them
  unchanged.
- **P3 [YOU] proposed: window Save writes a per-setting patch.** *Why:* a tray change made while the window is open
  survives.
- **P4 [YOU] proposed: Startup shortcut via absolute-path PowerShell and WScript.Shell, paths in env vars.** *Why:*
  no new dependency, no string interpolation.
- **P5 [YOU] proposed: customtkinter imported lazily in `run()`.** *Why:* its import side effects (DPI awareness,
  darkdetect) stay out of module import and pytest.

- **F1 [PM] RATIFIED 2026-11-09:** the 141-search grouping and the 25-search starter set, as listed.
- **F2 [PM] RATIFIED 2026-11-09:** a source at 0% (or off, or empty) is never a fallback.
- **F3 [PM] RATIFIED 2026-11-09:** on first run the first wallpaper changes right away, window open.
- **P1-P5 [YOU] RATIFIED 2026-11-09** with the plan approval.

## Module structure

### Functions by file and section

**`wallpaper_changer.py`, Configuration section**

Changed:
- `DEFAULT_SETTINGS` becomes neutral and gains the new keys. The comment at `:80-84` is rewritten (no remainder rule).

Added:
- `LEGACY_DEFAULTS` (the frozen old literal)
- `TOPIC_LABELS`, `LEGACY_TOPIC_SEARCHES`
- `MIX_LABELS = {"wallhaven": "Wallhaven", "museum": "Met paintings", "local": "My folders", "game": "Favourite game"}`
- `SOURCE_ORDER = ("wallhaven", "museum", "local", "game")`
- `MAX_SEARCH_LENGTH = 100`, `MAX_GAME_NAME_LENGTH = 60`
- `UI_POLL_MS = 100`
- `STARTUP_SHORTCUT_NAME = "WallSwap.lnk"`
- `CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)`

Deleted:
- `WALLHAVEN_QUERIES`. S1 keeps a temporary derived flat list until S2 lands.

Imports at the top of the file: `queue`, `from tkinter import filedialog, messagebox`. Plain tkinter is safe to import with no display; `tests/test_fullscreen_windows.py` already imports it.

**Settings section**

- `_merge_settings`: unchanged.
- Pure: `is_legacy_settings(loaded: dict) -> bool`, `migrate_settings(old: dict) -> dict`.
- Pure: `clean_search(text: str, existing: list[str]) -> str | None`.
  - Strips the text and collapses runs of whitespace.
  - Returns None for empty text, text over `MAX_SEARCH_LENGTH`, or a case-insensitive duplicate.
  - Keeps the user's casing.
- Pure: `settings_patch(before: dict, after: dict) -> dict`, shaped `{"set": [(path: tuple, value)], "add_folders": [str], "remove_folders": [str]}`.
  - Paths are compared per setting: `("interval_minutes",)`, `("game_name",)`, `("game_queries",)`, `("chances", s)`, `("topics", t, "enabled")` and `("topics", t, "searches")`.
  - `add_folders` = `after.local − before.local`.
  - `remove_folders` = `(before.local ∪ before.game) − (after.local ∪ after.game)`.
- No I/O: `apply_patch(data: dict, patch: dict) -> None`.
  - Sets each path, skipping any path that no longer exists.
  - Appends added folders that are not already present.
  - Removes each removed folder from **both** `local_folders` and `game_folders`, mirroring the tray at `:1076-1079`.
- `Settings` changes as listed under Migration.

**Sources section**

- `fetch_from_wallhaven(queries: list[str], sorting: str | None = None, source: str = "wallhaven")`: `queries` is now required, and the `WALLHAVEN_QUERIES` fallback at `:604-605` is gone. An empty list still returns None before any request.
- `pick_local_wallpaper(folders: list[Path])`: `folders` is now required, and the live read of `settings` at `:783-784` is gone.

**Windows section, new Startup subsection**

- `@dataclass(frozen=True) class ShortcutSpec: target: str; arguments: str; working_dir: str; icon: str`
- Pure: `startup_shortcut_spec(executable: Path, script: Path, icon: Path, pythonw_exists: bool) -> ShortcutSpec`.
- `startup_shortcut_path() -> Path` reads `APPDATA` at call time, never at import.
- `startup_enabled() -> bool`
- `write_shortcut(path: Path, spec: ShortcutSpec) -> None`
- `set_start_with_windows(enabled: bool, write=write_shortcut) -> None`

**Core Logic section (pure functions take `data`)**

- `wallhaven_query_pool(data: dict) -> list[str]`: the searches of enabled topics in `TOPIC_LABELS` order, stripped, empty ones dropped, de-duplicated case-insensitively with the first kept.
- `source_available(data: dict, source: str) -> bool`:
  - wallhaven: the pool is non-empty.
  - game: `game_queries` or `game_folders` is non-empty.
  - local: `local_folders` is non-empty.
  - museum: always True.
- `drop_reason(data: dict, source: str) -> str | None`, for the window's labels:
  - "Off in the tray menu"
  - "Tick a topic with searches"
  - "Add game searches or folders"
  - "Add a folder to use this"
  - "Set above 0%"
- `source_weights(data: dict) -> dict[str, float]`: the signature changes.
- `source_shares(weights: dict[str, float]) -> dict[str, int]`: whole percentages that add to 100, by largest remainder; `{}` when the total is 0.
- `fetch_source(source: str, data: dict)`: every branch reads `data` (folders as `[Path(f) for f in …]`).
- `get_new_wallpaper()`: takes `data = settings.snapshot()` once.

**Tray (`WallSwapApp`)**

New fields: `root`, `ui_calls: queue.SimpleQueue`, `settings_window`.

New methods:
- `post_to_ui(fn) -> None`: callable from any thread.
- `_drain_ui() -> None`: Tk thread.
- `_on_tray_ready(icon) -> None`: pystray setup thread.
- `ask_folder(parent=None) -> str | None`: Tk thread; carries the `folder_dialog_open` guard for both the tray and the window.
- `_add_folder_from_tray() -> None`
- `_show_settings() -> None`: Tk thread.
- `_save_from_window(patch: dict, start_with_windows: bool | None) -> str | None`: returns an error message, or None.
- `_close_ui() -> None`
- `_problem_message() -> str`

Changed:
- `_change_setting` now returns a bool, and its message depends on `settings.problem`.
- `add_local_folder` becomes `post_to_ui(self._add_folder_from_tray)`.
- `_pick_folder` is deleted and folded into `ask_folder` plus `_add_folder_from_tray`.
- `open_settings` becomes `post_to_ui(self._show_settings)`.
- `quit_app` and `run` change (see the Threading model).
- Labels:
  - The game label is `f"Wallhaven: {name}" if name else "Favourite game"` (`:1165`).
  - The folder tag is `f"  ({name or 'game'})"` (`:1071`).
  - `"⚙️ Settings…"` (`:1171`).

**`settings_window.py` (new)**

- Imports `customtkinter as ctk`, `tkinter.messagebox` and the standard library. It **never** imports `wallpaper_changer`.
- `@dataclass class WindowDeps`:
  - `snapshot: dict`
  - `topic_labels: dict[str, str]`
  - `mix_labels: dict[str, str]`
  - `source_order: tuple`
  - `interval_choices: list[int]`
  - `shares: Callable[[dict], dict[str, int]]`
  - `drop_reason: Callable[[dict, str], str | None]`
  - `clean_search: Callable[[str, list[str]], str | None]`
  - `patch: Callable[[dict, dict], dict]`
  - `ask_folder: Callable[[Any], str | None]`
  - `save: Callable[[dict, bool | None], str | None]`
  - `startup_on: bool`
  - `icon_path: Path`
  - `on_closed: Callable[[], None]`
- `class TagList(ctk.CTkFrame)`: `__init__(master, searches: list[str], clean)`, `values() -> list[str]`.
- `class FolderList(ctk.CTkFrame)`: `__init__(master, local: list[str], game: list[str], game_tag: str, ask_folder)`, `values() -> tuple[list[str], list[str]]`.
- `class SettingsWindow(ctk.CTkToplevel)`: `__init__(master, deps)`, `form() -> dict`, `_refresh_shares()`, `_on_save()`, `_on_cancel()`.

**Packaging**

- `pyproject.toml`: `uv add customtkinter`.
- `THIRD_PARTY_NOTICES.md`: add customtkinter, darkdetect and packaging. The builder copies each licence from the installed metadata.

### Threading model

| Thread | Runs |
|---|---|
| Main (Tk) | `run()` and `mainloop`; every Tk call, the window and `ask_folder`; Save, including `settings.update`, `refresh_menu` and the shortcut write |
| pystray loop (non-daemon, from `run_detached`) | menu callbacks; `_change_setting` for interval, sources and folder removal, as today; any Tk work goes through `post_to_ui` only |
| pystray setup | `_on_tray_ready`: `icon.visible = True`, then starts the timer thread |
| Timer (daemon) | unchanged: `reload`, `get_new_wallpaper` on a `snapshot()`, `notify`, `icon.title`, `refresh_menu`; it never touches Tk |
| Workers (daemon) | Next Wallpaper, as today |

**`run()` order:**
1. Log the banner.
2. Lazy-import `customtkinter` and `settings_window`. The comment says why: importing customtkinter has process side effects (DPI awareness, darkdetect), so it is kept out of module import and pytest.
3. `if not settings.persist_migration(): log.warning(...)`.
4. `self.root = ctk.CTk(); self.root.withdraw()`. The root comes **before** the tray, so the process is DPI-aware before pystray creates its hwnds.
5. `self.icon = pystray.Icon(...)`, then `self.icon.run_detached(setup=self._on_tray_ready)`. The timer starts only once the icon is ready, so an early `notify` or `refresh_menu` cannot run on an icon that isn't ready.
6. `self.root.after(UI_POLL_MS, self._drain_ui)`.
7. If `settings.created`: `post_to_ui(self._show_settings)`.
8. `try: self.root.mainloop()`, then `finally: self.running = False; self.icon.stop(); root.destroy()`, with TclError ignored and commented. Then log "Goodbye".

**`_drain_ui`.** It pops every queued call and runs each inside `try/except Exception`, logging the failure with a comment as HZ-2 requires. It reschedules itself in `finally`, so one failing call cannot kill the queue.

**Quit.** `quit_app` runs on the tray thread:
1. `running = False`
2. `post_to_ui(self._close_ui)`
3. `icon.stop()`

`_close_ui` destroys the window (ignoring TclError) and calls `root.quit()`. If a modal folder dialog is open, Quit takes effect once it closes; this is documented.

**Snapshots.** The window takes `settings.snapshot()` under the lock when it opens. `get_new_wallpaper` takes its own snapshot. Nothing reads `settings.data` live while it might be mutated.

### Source weights (4 weights + dropout)

```python
def source_weights(data):
    c, on = data["chances"], data["sources"]
    return {s: c[s] for s in SOURCE_ORDER if c[s] > 0 and on[s] and source_available(data, s)}
```

- `random.choices` normalises the weights. There is no remainder rule.
- allen's file gives 0.45/0.15/0.20/0.20, so the shares are **45/15/20/20**. A new user gets Wallhaven 75% and the Met 25%.
- **Fallback (decided):** `order = [choice] + [s for s in ("wallhaven", "local") if s in weights]`, de-duplicated. A source only serves as a fallback if it has a share: turned on, available and above 0. This is stricter than INV-15, makes the slider percentages honest, and changes nothing for allen.
- **No settings (as today):** `get_new_wallpaper` logs "Every source is off, empty or at 0%" and returns None.

### Wallhaven query pool and min-favourites

- `fetch_source("wallhaven", data)` calls `download_wallpaper(lambda: fetch_from_wallhaven(wallhaven_query_pool(data)))`.
- An empty pool never reaches here, because Wallhaven has no weight. Even if it did, `fetch_from_wallhaven([])` returns None with no request, and there is no global fallback.
- The pick stays `random.choice(pool)`: uniform per search across ticked topics (R1).
- **Min-favourites:** unchanged and keyed on `source == "wallhaven"`. Every topic search, including tags the user added, keeps `WALLHAVEN_MIN_FAVORITES`. Game searches pass `source="game"` and skip it, as today. No new parameter is added.
- User text only ever fills `params["q"]`. `purity="100"` and `categories="110"` stay fixed (INV-5).

### Startup shortcut mechanism

No new dependency is needed.

- **Path:** `startup_shortcut_path()` = `Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs/Startup" / STARTUP_SHORTCUT_NAME`.
- **Spec (pure):** `startup_shortcut_spec(Path(sys.executable), SCRIPT_DIR / "wallpaper_changer.py", ICON_PATH, pythonw_exists=Path(sys.executable).with_name("pythonw.exe").exists())`:

  | Field | Value |
  |---|---|
  | target | `<exe dir>\pythonw.exe` if it exists, otherwise the executable |
  | arguments | `f'"{script}"'` |
  | working_dir | `str(SCRIPT_DIR)` |
  | icon | `f"{ICON_PATH},0"` |

  Under `uv run` or pythonw this is `.venv\Scripts\pythonw.exe`.
- **`write_shortcut(path, spec)`:**

  ```
  subprocess.run([str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"),
                  "-NoProfile", "-NonInteractive", "-Command", SHORTCUT_PS],
                 env={**os.environ, "WS_LNK": str(path), "WS_TARGET": spec.target, "WS_ARGS": spec.arguments,
                      "WS_WD": spec.working_dir, "WS_ICON": spec.icon},
                 creationflags=CREATE_NO_WINDOW, capture_output=True, check=True, timeout=15)
  ```

  - `SHORTCUT_PS` is a constant: `$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:WS_LNK); $s.TargetPath=$env:WS_TARGET; $s.Arguments=$env:WS_ARGS; $s.WorkingDirectory=$env:WS_WD; $s.IconLocation=$env:WS_ICON; $s.Save()`.
  - Paths travel only through environment variables, never by string interpolation.
  - PowerShell is called by absolute path, so a `powershell.exe` planted in `.venv\Scripts` or `SCRIPT_DIR` cannot run.
  - Afterwards: `if not path.exists(): raise OSError(...)`.
- **`set_start_with_windows(enabled)`:**
  - On: `write(path, spec)`.
  - Off: `path.unlink(missing_ok=True)`. That exact file is the only one ever removed.
  - It runs synchronously on the Tk thread (about 1 s, capped at 15 s by the timeout) while Save shows "Saving…". This avoids the create/delete ordering race that worker threads would have.
- **Frozen exe:** no branch is built (see Documented seams).
- **allen's existing shortcut** (target pythonw, working directory `.venv\Scripts`): the switch shows On. Save rewrites the shortcut only when the switch changes. Turning it off and on recreates it with the new spec; the working directory changes, which is harmless because every path in the code is absolute.

**Build revisions:** none yet.

## Files and state

### settings.json schema

| Key | Old (ff92bfd) | New type | New-user default | allen's migrated value |
|---|---|---|---|---|
| `interval_minutes` | int/float ≥0 | unchanged | `30` | his value |
| `sources` | `{wallhaven, game, museum, local}: bool` | unchanged | all `true` | his values |
| `chances` | `{local .2, game .2, museum .15}`; Wallhaven gets 1 − sum | `{wallhaven, museum, local, game}: float ≥0`, relative weights | `wallhaven .45, museum .15, local .2, game .2` | his three values, plus `wallhaven = round(max(0, 1 − sum), 4)` = **0.45** |
| `topics` | absent | `{id: {"enabled": bool, "searches": list[str]}}` with nine fixed ids | starter set below | all nine `enabled: true`, holding all 141 legacy searches |
| `game_name` | str `"Path of Exile"` | str | `""` | `"Path of Exile"` (written out) |
| `game_queries` | list[str] | unchanged | `[]` | `["path of exile", "path of exile 2"]` (written out) |
| `local_folders` | list[str] | unchanged | `[]` | his list, or `[~/Pictures/Path of Exile 2]` if the key is missing |
| `game_folders` | list[str], supplied only by the code default | unchanged | `[]` | `[~/Pictures/Path of Exile 2]`, **written out** |

**Topics.** Every id is listed in `DEFAULT_SETTINGS`, so the existing `_merge_settings` (`wallpaper_changer.py:313`) handles topics with **no change**:
- a missing topic takes its default;
- `searches` of the wrong type falls back to the default list;
- an emptied list `[]` is kept;
- an unknown topic id is dropped.

**Topic ids, labels and order.** `TOPIC_LABELS: dict[str, str]` holds them in the brief's order:

| Id | Label |
|---|---|
| `nature` | Nature & landscapes |
| `space` | Space |
| `dark_fantasy` | Dark fantasy & gothic |
| `cities` | Cities & cyberpunk |
| `abstract` | Abstract & minimal |
| `moon_night` | Moon & night |
| `anime` | Anime |
| `games` | Games |
| `movies` | Movies & series |

**New-user starter searches.** There are 25, and every one already exists in today's `WALLHAVEN_QUERIES`.

| Topic | Ticked | Searches |
|---|---|---|
| nature | yes | landscape 4k, mountains, forest, ocean, aurora borealis |
| space | yes | nebula, galaxy, milky way |
| cities | yes | cityscape night, neon city rain, futuristic city |
| abstract | yes | minimalist, synthwave, fractal art |
| moon_night | yes | moon, night sky, starry night |
| dark_fantasy | no | dark fantasy, gothic |
| anime | no | anime scenery rain, studio ghibli |
| games | no | elden ring, hollow knight |
| movies | no | blade runner, dune |

That is 17 ticked searches and 8 unticked.

**New-user weights.** The stored weights match allen's. Dropout does the neutralising: with no folders and no game, the effective mix is Wallhaven 75% and the Met 25%.

**allen's grouping (`LEGACY_TOPIC_SEARCHES`, replacing `WALLHAVEN_QUERIES`).** Each old comment block maps to one topic, with these moves (line numbers from ff92bfd):

| Topic | Count | Contents |
|---|---|---|
| nature | 23 | Scenery `:140-161` + `lighthouse` |
| space | 7 | Space `:172-180` − `star wars` − `mass effect` |
| dark_fantasy | 30 | Fantasy `:182-217` − `lighthouse`, `cyberpunk girl`, `dark souls`, `witcher geralt`, `lord of the rings`, `pixel art landscape` |
| cities | 11 | Urban `:163-170` + `cyberpunk girl`, `cyber`, `hologram` |
| abstract | 17 | Aesthetic `:219-234` + `pixel art landscape` |
| moon_night | 9 | `:236-244` |
| anime | 15 | `:246-260` |
| games | 22 | `:262-280` + `mass effect`, `dark souls`, `witcher geralt` |
| movies | 7 | `:284-288` + `star wars`, `lord of the rings` |

The total is 23+7+30+11+17+9+15+22+7 = **141**, each search exactly once. Every topic is ticked and the pick stays uniform per search, so the grouping is display only and allen's mix is unchanged.

### Migration

**Detection.** `Settings.reload` decides as follows:
- The file must parse, and the parsed value must be a `dict`. A file that is valid JSON but not an object is now treated as **broken**: `reload` returns False and the file is never saved over.
- `is_legacy_settings(loaded) -> bool` returns `"topics" not in loaded`. There is no version key: a version key has the same blind spot (a hand-written file without it), and the S5 README example will include `topics`.

**In memory, on every read (pure).** `migrate_settings(old: dict) -> dict`:
1. `d = _merge_settings(LEGACY_DEFAULTS, old)`. `LEGACY_DEFAULTS` is a frozen copy of today's `DEFAULT_SETTINGS` literal, so this gives exactly what the old app reads, including the `game_folders` code default.
2. `wallhaven = round(max(0.0, 1 - (local + game + museum)), 4)`. A sum of 1 or more gives 0.
3. `d["chances"]["wallhaven"] = wallhaven`, and `d["topics"] = {t: {"enabled": True, "searches": list(s)} for t, s in LEGACY_TOPIC_SEARCHES.items()}`.
4. Return `_merge_settings(DEFAULT_SETTINGS, d)`.

`reload` stores `self.legacy = True` and `self._legacy_raw = <the bytes it read>`, so a legacy file behaves like the new format before it is ever written.

**What is written, and when.** Only `save()` writes, and the backup check lives inside it:
1. If `self.legacy` is set and `settings.json.bak` does not exist yet, write `_legacy_raw` to `settings.json.bak.tmp`, then rename it to `settings.json.bak`. An existing `.bak` is never overwritten, so it always holds the first original. Because the bytes are the ones `reload` read, nothing can change between the read and the copy.
2. If the backup fails with `OSError`, the save is refused:
   - `self.problem = "backup"` and `save()` returns False;
   - `settings.json` is untouched and the migrated data stays in memory;
   - `log.warning`, with a comment as HZ-2 requires.
3. Otherwise the existing temp-file write plus `os.replace` runs, then `self.legacy = False`.

**Who triggers the write.**
- `Settings.persist_migration() -> bool` is `with lock: return self.save() if self.legacy else True`.
- It is called **only in `WallSwapApp.run()`**, which is reached only after the mutex check in `__main__` (`:1205-1211`).
- Importing the module never migrates the file on disk. Importing still creates a missing file, as HZ-3 already says.
- The first tray change runs `update()`, which ends in `save()`, so that change also migrates safely with the `.bak`.

**Idempotence.** After the write the file has `topics`, so `self.legacy` stays False and nothing is written again.

**Broken file.** Parsing fails before migration, so there is no `.bak` and no write (INV-10). At startup a broken file now gives the *neutral* defaults in memory. Nothing is written; this is accepted and goes into the INV-10 text.

**The old app that is still running.**
- Starting the new code while the old app runs: import migrates in memory only, the mutex exits, and **nothing is written**. This fixes the seams critic's problem 1.
- After the switch, the old app cannot run alongside the new one. If an old checkout ever saves over the new file, it strips `topics` and `chances.wallhaven`. The next `reload` re-migrates in memory from his kept values, which recovers his mix; only topic edits made in between are lost, and the `.bak` is left alone.
- Handover step: quit both old pythonw processes, run `uv sync`, then start the new app.

**`Settings` changes.**

| Name | Kind | Meaning |
|---|---|---|
| `created: bool` | new attribute | set when `reload` found no file |
| `legacy: bool` | new attribute | in-memory data came from a legacy file not yet written |
| `_legacy_raw: bytes \| None` | new attribute | the legacy file's bytes, for the `.bak` |
| `problem: str \| None` | new attribute | `"broken"` or `"backup"` |
| `save() -> bool` | changed | was `None`; now refuses on a failed backup |
| `update()` | changed | returns `self.save()` |
| `snapshot() -> dict` | new | deepcopy taken under `self.lock` |
| `persist_migration() -> bool` | new | see above |
| `chance()` | deleted | its only caller was `source_weights` (`:838`) |

### Other files and shared state

- `settings.json.bak` (and a short-lived `.bak.tmp`) in `Pictures\WallSwap`.
- `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\WallSwap.lnk`, only when the switch is flipped.
- Seen-history files are untouched.
- Shared state: `settings` (RLock; the window and the changer use `snapshot()`), `WallSwapApp.ui_calls`
  (SimpleQueue, any thread to Tk), `current`, `paused`, `running`.

## Interface surface

### Window layout

The window is a `CTkToplevel` titled "WallSwap Settings", about 640×720, with the `wallswap.ico` icon and one `CTkScrollableFrame`. Only one window exists at a time: `_show_settings` calls `lift()` and `focus_force()` when the window `winfo_exists()`. Sections, in the brief's order:

1. **Topics.** Nine rows, each with a `CTkCheckBox` (the label), the search count and an expand arrow.
   - The `TagList` is built only on the first expand. That keeps opening fast with 141 searches.
   - Each tag is a "search ×" chip; clicking it removes the tag.
   - An entry with Add (or Enter) adds a tag. A `clean_search` rejection shows inline ("Already there", "Too long", "Empty").
2. **Favourite game.** A name `CTkEntry`, stripped and at most 60 characters, plus a `TagList` for `game_queries`. Hint: "Leave empty if you don't want one."
3. **My folders.** A `FolderList` showing `local_folders ∪ game_folders`, with game folders tagged like the tray.
   - "Add folder…" runs `deps.ask_folder(self)`, normalises with `str(Path(f))`, ignores duplicates and adds to `local_folders`.
   - Remove takes the folder out of both lists.
   - Folder contents are never touched.
4. **Source mix.** Four `CTkSlider`s (0-100, step 1) in `SOURCE_ORDER`, labelled from `MIX_LABELS`.
   - Each shows "NN% of changes" from `deps.shares({**snapshot, **form})`, recomputed on every slider move, topic tick, tag edit or folder edit.
   - A source that drops out shows "0% · <drop_reason>".
   - If every source drops out, a warning line appears. Save is not blocked.
   - A slider keeps the stored value until it is moved: `form()` returns the snapshot value for an untouched slider, so a hand-set 1.5 is not rewritten. A moved slider stores `round(v / 100, 2)`.
5. **Change every.** `CTkSegmentedButton` with 15 / 30 / 60 / 120 min. A hand-set value that is not one of these shows nothing selected, and `form()` returns the stored value unchanged.
6. **Start with Windows.** A `CTkSwitch`, initially `deps.startup_on` (`WallSwap.lnk` exists).
7. **Footer.** An error banner, plus Cancel and Save.

**Cancel or the close button.** If `deps.patch(snapshot, form())` is non-empty or the switch changed, ask "Discard your changes?". Otherwise just close. Quitting from the tray discards without asking.

**Save, on the Tk thread:**
1. `patch = deps.patch(snapshot, form())`. `startup` is the switch value if it changed, otherwise None. Disable the buttons and show "Saving…".
2. `err = deps.save(patch, startup)`, which is `_save_from_window`:
   1. If the patch is non-empty: `settings.update(lambda d: apply_patch(d, patch))`. On False, return `_problem_message()` without touching the shortcut:
      - broken: "settings.json has a mistake in it, so nothing was saved…"
      - backup: "Couldn't make the settings.json.bak backup, so nothing was saved…"
   2. `refresh_menu()`.
   3. If `startup` is not None: `set_start_with_windows(startup)`. On `(OSError, subprocess.SubprocessError)`, return "Settings saved, but Start with Windows couldn't be changed: …"
   4. `notify("Settings saved. They apply from the next wallpaper change.")`, then return None.
3. If `err` is set, show it in the banner, re-enable the buttons and keep the window open. Otherwise destroy the window and call `deps.on_closed()`.

**What applies when.**
- Only the settings the user changed are written. A tray change to a different setting (for example turning off a source, or adding a folder) made while the window was open survives.
- Topics, weights and folders apply from the next wallpaper change. Save never triggers a change itself.
- Interval: the timer compares against the new value on its next 5-second tick. `elapsed` is not reset, so lowering the interval below `elapsed` changes the wallpaper on that tick.

### Tray

- "⚙️ Settings…" opens (or raises) the window; first run opens it by itself.
- Game label: "Wallhaven: <name>", or "Favourite game" when the name is empty; folder tag "(<name or game>)".
- Notifications: "Settings saved. They apply from the next wallpaper change."; problem-specific messages for a broken
  file or a failed backup.

## Invariant impact

| Invariant | How it stays held |
|---|---|
| INV-1, 2, 3 | Every fetch still goes through `safe_get`; no host is added. The shortcut write is local only. |
| INV-4, 6, 7, 11, 12 | Untouched. |
| INV-5 | Typed tags go only into `q`; `purity` and `categories` stay hard-coded. Tested. |
| INV-8 | The window and dialog only choose folders and edit the lists. Nothing inside a folder is written. |
| INV-9 | `settings.json.bak`, `.bak.tmp` and `.lnk` do not match `wallswap_*.jpg`. |
| INV-10 | **Strengthened.** A file that is valid JSON but not an object counts as broken. Migration runs only after a successful parse. The `.bak` is enforced inside `save()` (exclusive, never overwritten; a failed backup blocks the save). Window Save goes through `update()`. A broken file at startup now means the neutral defaults in memory. The text and line refs are updated. |
| INV-13 | Save never starts a change. Lowering the interval can make the next timer tick fire, which is still a single change. |
| INV-14 | The CTk root makes the process DPI-aware. This needs a Windows re-check (S3) and a DPI-aware variant of the Windows test. |
| INV-15 | **Strengthened.** Sources that are off, empty or at 0 are excluded from both the weights and the fallback, and `WALLHAVEN_QUERIES` is gone, so an empty pool cannot fall back. The anchor moves to `source_available`, `source_weights` and `get_new_wallpaper`. |
| HZ-3 (text) | Import still writes only a missing file. A legacy file is migrated in memory, and written only from `run()` after the mutex. |
| **New INV-16** (reconcile) | WallSwap writes outside its own folder only `Startup\WallSwap.lnk`, and only when the user flips Start with Windows. That exact file is the only one it ever deletes. |

## Hazards that apply

- **HZ-1:** new imports (`queue`, `tkinter.filedialog/messagebox`) go at the top; `customtkinter` is the one lazy
  import, in `run()`, with a comment; ruff F823 stays in the gate.
- **HZ-2:** `_drain_ui`, `write_shortcut` and the backup path log what they absorb; tests cover each rule's yes case.
- **HZ-3:** import still writes only a missing file; a legacy file is not written at import; conftest also redirects
  `APPDATA`.
- **Running old app (new hazard):** the old process saves through the old merge and drops new keys. The migration
  write happens only after the mutex, and re-migration recovers allen's mix.

### Feature hazards

1. **Double module load.** If `settings_window.py` imported `wallpaper_changer` while the app runs as `__main__`, there would be a second `Settings` with its own RLock guarding the same file, plus a second import-time read. Log handlers are *not* duplicated, because `basicConfig` does nothing the second time. Prevention: `WindowDeps`, plus an AST test.
2. **Tk off the main thread.** Prevention: only `post_to_ui`, `ask_folder` and the window ever touch Tk, and `_pick_folder`'s private `Tk()` is gone.
3. **A dead UI queue.** Prevented by try/except plus a reschedule in `finally` in `_drain_ui`, and `run()` ending in `try/finally: icon.stop()`. Remaining edge: Tk dies before the icon is ready, so `stop()` does nothing and the process stays alive. Documented.
4. **DPI awareness changes the fullscreen math (INV-14).** Windows check, plus a DPI-aware variant of the test.
5. **A hand-written file without `topics` is treated as legacy** and gets the Path of Exile values. Rare; the README example includes `topics`.
6. **Tests touching allen's real shortcut.** conftest sets `APPDATA` to a temp folder and asserts it.
7. **`CREATE_NO_WINDOW` on the Mac.** Solved with `getattr(..., 0)`.
8. **A modal dialog blocks the drain.** Quit and Settings… wait for the dialog to close. Documented.
9. **pythonw has `stdout` and `stderr` set to None.** CustomTkinter and darkdetect may print. Windows check.
10. **The window comes up behind other windows** because of Windows' foreground lock. `lift`, `focus_force` and a short `-topmost` pulse; Windows check.
11. **A window Save and a tray change on the *same* setting.** The window wins for that setting only.

## Threat + scale notes

**Threat**

| Input | Where it can go | Guard |
|---|---|---|
| Typed tags | only Wallhaven's `q` | fixed `purity` and `categories`; INV-5 test |
| Folder paths | settings lists only; read-only use | INV-8 |
| Shortcut paths | PowerShell, as environment variables | no interpolation; absolute `powershell.exe` |
| Shortcut removal | the exact `WallSwap.lnk` only | INV-16 |
| `.bak` | created exclusively | never overwritten |
| settings.json | trusted local input | merge type-checks everything |

The window shows user strings as plain Tk text, so there is no markup risk.

**Scale.** 141 searches become about 141 CTk chip widgets. Building them lazily on expand keeps opening under about 0.5 s. `clean_search` caps tag length at 100. Each wallpaper change rebuilds the pool from a few hundred strings, which is negligible.

## Testing & scope

### Tests

**Mac / pytest**

`tests/test_settings.py`:
- `test_merge_keeps_valid_user_values` stays as it is.
- `test_merge_falls_back_on_wrong_types_and_unknown_keys` stays: the `[3]` → `[]` check is still meaningful. Add assertions that `topics` with the wrong type falls back and that an unknown topic id is dropped.
- `test_broken_file_is_kept_and_not_overwritten` stays.
- `test_non_object_json_is_treated_as_broken`
- `test_migrate_fills_old_effective_values`: no `game_folders` key gives Path of Exile, `wallhaven` 0.45, nine topics on.
- `test_migrate_wallhaven_gets_old_remainder`: custom values, and a sum of 1 or more gives 0.
- `test_legacy_topic_searches_are_old_list_exactly_once`: 141, with the same set as the ff92bfd list (a literal kept in the test).
- `test_import_time_load_does_not_write_legacy_file`: bytes unchanged, no `.bak`.
- `test_persist_migration_writes_bak_once_and_is_idempotent`
- `test_existing_bak_is_never_overwritten`
- `test_backup_failure_refuses_save_and_keeps_original` (stub `os.rename` or `open` to raise; check `problem == "backup"`)
- `test_first_update_on_legacy_file_backs_up_first`
- `test_new_user_defaults_are_neutral` (17 ticked, 25 total, no game or folders, `created` True)
- `test_clean_search_rejects_empty_duplicate_too_long`
- `test_settings_patch_per_setting_and_folder_changes`
- `test_tray_and_window_changes_both_survive` (`update` toggles museum, then `apply_patch` changes Wallhaven; also a folder added by the tray plus one removed by the window)

`tests/test_sources.py` (new):
- `test_query_pool_only_enabled_topics_dedup`
- `test_source_weights_four_weights_45_15_20_20`
- `test_game_drops_out_without_searches_and_folders` (yes case: folders only keeps it)
- `test_local_drops_out_without_folders`
- `test_wallhaven_drops_out_with_empty_pool`
- `test_zero_weight_or_off_source_never_used_as_fallback` (monkeypatch `fetch_source` and record the calls)
- `test_source_shares_sum_to_100`
- `test_empty_pool_makes_no_request` (`safe_get` stub raises if called)
- `test_topic_searches_keep_min_favourites_game_searches_skip`
- `test_typed_tag_cannot_change_purity`

`tests/test_startup.py` (new):
- `test_shortcut_spec_uses_pythonw`
- `test_shortcut_spec_falls_back_to_executable`
- `test_turning_on_passes_paths_only_in_env` (stub `subprocess.run`; the script equals the constant)
- `test_turning_off_removes_only_wallswap_lnk`
- `test_settings_window_never_imports_wallpaper_changer` (`ast` parse of the file; no import)

`tests/conftest.py`: set `APPDATA` to a temp folder and assert `startup_shortcut_path()` starts with it.

**Windows only (pytest, skipped off win32)**
- `tests/test_startup_windows.py::test_real_shortcut_round_trip`: write a `.lnk` in `tmp_path` through the real PowerShell call, read it back with WScript.Shell, and check target, arguments, working directory and icon.
- `tests/test_fullscreen_windows.py`: add a DPI-aware parametrisation that calls `SetProcessDpiAwareness(2)` (or `SetProcessDpiAwarenessContext`) in a subprocess fixture.

**Windows check (verify-wallswap)**: see the step list below.

### Windows-check steps

1. Quit both old pythonw processes, then `uv sync`. Start the new app while one old process is still running: it exits, `settings.json` is unchanged and there is no `.bak`.
2. Quit the old app and start the new one. `settings.json.bak` now matches the original bytes, `settings.json` has `topics`, `chances.wallhaven` = 0.45 and `game_folders`. The tray Sources and My Folders submenus still show Path of Exile.
3. Tray "Settings…" opens the window in front. A second click brings it to the front, with no second copy. The Topics section shows nine ticked topics with the expected counts. The Source mix shows 45/15/20/20.
4. Untick Dark fantasy, move the Met slider, add a tag and Save. You get the notification, `settings.json` has only those changes, and the next wallpaper's logged query comes from a ticked topic.
5. With the window open, turn off a source from the tray, change a different setting in the window and Save. Both changes are kept.
6. Edit something, then click Cancel or the close button: the "Discard?" prompt appears and nothing is written.
7. Break `settings.json` by hand, then Save in the window. The banner appears and the file is unchanged.
8. Tray "Add Folder…" opens the dialog in front (with and without the window open). The window's Add folder… works too, and only one dialog can be open at a time.
9. Set the interval to 15 and confirm the change in the log within the tick. A hand-set 45 shows nothing selected and is kept after Save.
10. Turn Start with Windows off and Save: `Startup\WallSwap.lnk` is gone. Turn it on and Save: the shortcut exists with target `.venv\Scripts\pythonw.exe`, argument the script, icon `wallswap.ico`. Sign out and back in: the app starts, with no console.
11. First run: point `USERPROFILE` and `HOME` at a temporary profile and start the app. The window opens by itself, with neutral defaults and the mix at 75/25.
12. Quit from the tray, including while the folder dialog is open (Quit takes effect after the dialog closes). No pythonw process is left behind.
13. Re-run the "Fullscreen skip" flow at 125% and 150% scaling, and on mixed-DPI monitors if available. Run `tests/test_fullscreen_windows.py`, including the DPI-aware variant. The tray icon and menu render sharply.
14. Check the window in the light and dark Windows themes, at 125% and 150% scaling, under pythonw.

No test sets the real wallpaper or lock screen, and none touches allen's real Startup folder or settings.json.

## Slice plan

| # | Slice | Payoff | Builder |
|---|---|---|---|
| S1 | Schema and migration: the new `DEFAULT_SETTINGS`, `LEGACY_DEFAULTS`, `TOPIC_LABELS`, `LEGACY_TOPIC_SEARCHES` (temporary flat `WALLHAVEN_QUERIES` derived from it), `is_legacy_settings`, `migrate_settings`, the `Settings` changes (`.bak` in `save`, `problem`, `snapshot`, `persist_migration`, `created`, non-object counts as broken), `clean_search`, `settings_patch`, `apply_patch`, the problem-specific `_change_setting` message plus bool return, the empty-`game_name` label fixes at `:1071` and `:1165`; `test_settings.py` additions | allen's file is upgraded with a `.bak` on first save and his mix is unchanged; new users get neutral defaults | **Claude** (settings persistence) |
| S2 | Sources: `wallhaven_query_pool`, `source_available`, `drop_reason`, `source_weights(data)`, `source_shares`, `fetch_source(source, data)`, `get_new_wallpaper` snapshot plus fallback filter, required `queries` and `folders`; delete `WALLHAVEN_QUERIES` and `Settings.chance`; `test_sources.py` | Ticked topics and the four weights drive the real mix; empty sources drop out | **Codex** |
| S3 | Threading: `uv add customtkinter`, THIRD_PARTY_NOTICES, lazy import in `run()`, CTk root before tray, `run_detached(setup=_on_tray_ready)`, `post_to_ui`, `_drain_ui`, `ask_folder`, `_add_folder_from_tray`, `quit_app`, `_close_ui`, `run()` try/finally, `persist_migration()` call; DPI-aware fullscreen test | Add Folder and Quit work on the shared root; the migration write happens after the mutex; INV-14 re-proven under DPI awareness | **Claude** (user folders) |
| S4 | Startup: `CREATE_NO_WINDOW`, `STARTUP_SHORTCUT_NAME`, `ShortcutSpec`, `startup_shortcut_spec`, `startup_shortcut_path`, `startup_enabled`, `write_shortcut`, `set_start_with_windows`; conftest `APPDATA`; `test_startup.py`, `test_startup_windows.py` | A proven shortcut writer and remover | **Claude** (writes outside WallSwap's folder, runs PowerShell) |
| S5 | Window: `settings_window.py`, `WindowDeps`, `_show_settings`, `_save_from_window`, `_problem_message`, `open_settings` wiring, first-run open, "Settings…" label, the AST test | The settings window, which is the feature as the user sees it | **Claude** (folder lists and Save write settings) |

Canon docs are written by the orchestrator at reconcile, not by builders:
- README: Notepad line `:43`, remainder rule `:57-67`, the `shell:startup` advice `:30`, plain first-person tone, example with `topics`;
- INVARIANTS: INV-10 and INV-15 text and anchors, INV-16, the HZ-3 text;
- ARCHITECTURE `:41` and the threads section;
- `/maintain-verify` for `.claude/skills/verify-wallswap/SKILL.md:30` ("rename settings.json" now opens the first-run window).

**Run order:**
- **Wave 1: S1, S3 and S4 in parallel.**
  - S1 owns the Configuration and Settings sections plus three tray lines (`:1041`, `:1071`, `:1165`).
  - S3 owns `run`, `quit_app`, `add_local_folder`, `_pick_folder`, `__init__` fields and `pyproject`.
  - S4 owns a new Startup subsection, one Configuration constant pair, and conftest.
  - The line sets do not overlap; the orchestrator merges.
- **Wave 2: S2.** Needs S1's `topics` and `chances.wallhaven` schema. Shares the Configuration section (it deletes the temporary `WALLHAVEN_QUERIES`). Held back because the pool and dropout read keys that only S1 adds.
- **Wave 3: S5.** Needs S1 (`settings_patch`, `apply_patch`, `clean_search`, `snapshot`, `problem`), S2 (`source_shares`, `drop_reason`), S3 (root, `post_to_ui`, `ask_folder`) and S4 (`set_start_with_windows`, `startup_enabled`). Shares the `WallSwapApp` tray section with S3. Held back because it is wired against all four.

Builder note: "Claude" means a `general-purpose` agent on the reasoning tier (there's no `security-implementer` type
here); S2 is Codex via `.claude/scripts/codex-lane.sh`.

## Documented seams (flagged, not built)

- **Frozen or PyInstaller exe:** a `getattr(sys, "frozen", False)` branch in `startup_shortcut_spec`; `sys._MEIPASS` for `ICON_PATH`; customtkinter theme data files.
- **`schema_version`** and refusing to save over a file from a newer version, to protect people who downgrade.
- **User-created topics:** a merge branch for dynamic keys.
- **A game-folder picker** in the window (today: tray removal or a hand edit).
- **Source on/off switches** in the window (the tray Sources submenu stays).
- **Live refresh** of an open window when the tray changes settings.
- **Startup folder through `SHGetKnownFolderPath(FOLDERID_Startup)`**, for redirected profiles.
- **Shortcut repair:** offer a fix when the existing `.lnk` points elsewhere.
- **A cap on searches per topic.**
- **Watching the tray thread** so a dead icon also stops Tk.

## Open decisions owed

None. F1-F3 ratified 2026-11-09 (see Decision log).

## Implementation checkpoints

### Panel verdicts (step 3)

| Lens | Score | Verdict | Grafted |
|---|---|---|---|
| minimal | 7 | accept-with-fixes (**spine**) | fixed-key topics with no change to `_merge_settings`; `LEGACY_DEFAULTS` plus pure `migrate_settings`; `.bak` holds the oldest original; PowerShell via environment variables; `WALLHAVEN_QUERIES` removed; drop-out reasons; SimpleQueue drain; starter list and grouping (plus seams' move of `pixel art landscape` to abstract) |
| seams | 7 | accept-with-fixes | `source_available`, `source_shares` (largest remainder), `settings_patch` (made per setting), `clean_search`, `ShortcutSpec` (frozen branch dropped), dependency bundle, AST import test, lazily built TagList, `run()` try/finally, "Discard changes?" |
| forward | 7 | accept-with-fixes | migration in memory on read, written after the mutex; non-object JSON counts as broken; conftest `APPDATA`; THIRD_PARTY_NOTICES; typed-tag purity test; never rewrite allen's shortcut unless the switch changed; INV-16 |

### Wave 1 build (S1, S3, S4) — 2026-11-09

- Builders: Claude `general-purpose` (opus) in agent worktrees; all three gates green (S1 39 passed; S3 35 passed,
  2 skipped, 1 xpassed; S4 29 passed). Builder spot-mutants: S1 `.bak` overwrite → 2 tests RED; S3 narrowed
  `_drain_ui` except → RED; S4 off-branch deletes every `.lnk` → RED. All restored.
- Cleanup pass (fresh builder each): S1 one change (`local_folder_items` game tag built once); S3, S4 none.
- Snapshots (no-branch commits): S1 pre `9ab517e` / post-cleanup `b8901b4`; S3 `e9b0b5c`; S4 `d166217`.
- Dry landing of all three with `git apply --3way` on `ff92bfd`: clean; gate 56 passed, 1 skipped, 1 xpassed.
- Builder deviations accepted: S1 `update()` rolls back memory when a save is refused; S1 `.bak` rename
  FileExistsError keeps the existing `.bak` and continues; S1 `settings_patch` takes paths from `before`; S3
  `_drain_ui` always reschedules (quit race); S3 `ask_folder` catches `TclError` only; S4 separate no-file test;
  S4 `working_dir = script.parent` (equal to `SCRIPT_DIR` in use).

### Wave 1 review — `/adversarial-review` + Codex attackers

| Slice | Review | Attacker (rerun by orchestrator) | Folded |
|---|---|---|---|
| S1 | 1 low confirmed (problem read outside lock) | 6 reproduced | persist_migration re-reads first (broken file, stale bytes); failed main write returns False (`problem "write"`); `.bak` that is not a file refuses |
| S3 | 1 medium (Add Folder repeat clicks queue dialogs) + lows | 4 reproduced (spam 4 dialogs; others low / accepted) | one pending Add Folder; no queued call but `_close_ui` after Quit |
| S4 | 1 medium (Mac absolute-path test) + 3 low + 1 plausible | 4 reproduced | PureWindowsPath test; Windows dir from the OS, not `SystemRoot`; Unicode-safe shortcut write + read-back check |

**Residuals (low / PLAUSIBLE, not folded):** S1 migration rounds a tiny remainder to 0; `clean_search` misses
NFC-equivalent duplicates; `_change_setting` reads `problem` after the lock (S5 reads it under the lock). S3 DPI
wrapper passes on any pass; timer starts only if `icon.visible` succeeds; top-level tkinter import needs a Tk-enabled
test Python; CTk appearance poll every 30 ms; Quit before the tray is ready leaves pystray threads; Quit waits for
an open folder dialog (accepted in plan); private-method tests. S4 hard-linked `WallSwap.lnk`; `%VAR%` in a literal
path expands; unset `APPDATA` raises KeyError; PowerShell stderr not logged; `creationflags` not asserted.
Tooling: `codex-lane.sh` needs `pgrep`, absent in Git Bash on Windows (status unusable; exit files used).

### Process change and the rest of the build

- allen switched to a light process after Wave 1's review (2026-11-09, from a side session): no more per-slice
  cleanup, review or Codex attackers; S2 and S5 built directly on the branch one after the other; one review over
  the whole feature.
- Wave 1 landed post-fold (`762cd59`, `43f5ff9`, `9e1476e`) on `feat/settings-window`; one import-line conflict
  resolved by hand; gate 63 passed, 7 skipped.
- S2 (Claude, not Codex, under the light process): 84 passed, 7 skipped; spot-mutant (unfiltered fallback order) →
  3 RED. Added `EMPTY_SOURCE_REASONS`.
- S5 (Claude): 93 passed, 7 skipped; spot-mutant (refused save still writes the shortcut) → RED. Deviations:
  `WindowDeps.game_name_max`, `on_change` callbacks on `TagList`/`FolderList`, folder already in either list is
  ignored, `bring_to_front()`. Deleted the unused `Settings.local_folders`/`game_folders`.
- Whole-feature `/adversarial-review` (diff vs `ff92bfd`): 1 medium confirmed and folded by the orchestrator (a
  failed Start with Windows change showed the whole PowerShell script instead of PowerShell's error; now a short
  reason + stderr in the log; regression test, mutant RED). Also folded: tray `_change_setting` reads `problem`
  under the lock (flagged twice).
- Whole-feature residuals (low/PLAUSIBLE, not folded): partial save keeps the window's old snapshot; `_on_save`
  has no try/finally and Tk callback errors aren't logged under pythonw; a shortcut that fails the read-back stays
  in Startup; an infinite weight in a hand-edited file crashes shares/the timer; `form()` normalises a hand-edited
  game name (spurious "Discard?"); removing a game folder and re-adding it keeps it in `game_folders`; unset
  `APPDATA` / redirected Startup folder; no test drives `SettingsWindow.form()`.

### Proof (orchestrator-run)

| Check | Result |
|---|---|
| Gate after the fold | see the commit; code + docs |
| Full-app smoke (temp profile, real tray, stubs for wallpaper/lock screen) | icon visible, timer alive, first-run window open with the neutral starter set (screenshot), Settings… raises the same window, Quit exits in 6.2 s with no tray thread left |
| Migration of a copy of allen's real settings.json | legacy detected, file untouched on load; Path of Exile + searches, 45/15/20/20, all 141 old searches in the pool, interval 30, all sources on; `.bak` = original bytes; real file untouched |
| Real window (S5 smoke) | 141-search file opens in ~0.6 s; recorded patch exactly the three edits; screenshots in `.scratch/` |
| Windows check by allen | not yet: restart WallSwap on the new code (quit both old pythonw first) and run the verify-wallswap flows "Settings window", "Start with Windows", "Upgrade from the old settings file" |

## Next action

Progress: done | slice 5/5 · next: allen's Windows check · rest: none
Committed on `feat/settings-window`, not pushed. Later, separate: strip the work workflow from the repo before the
public release.
