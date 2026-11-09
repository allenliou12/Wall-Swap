---
name: verify-wallswap
description: Prove WallSwap behaviour on a real Windows PC — the tray menu, wallpaper and lock-screen changes, the fullscreen skip, favourites, settings and cleanup — by writing exact steps for allen to run and reading back what he saw. Use when a change touches anything a person would notice, to reproduce a Windows-only bug, or before calling a slice done. The Mac cannot run the app.
---

# Verify WallSwap

WallSwap only runs on Windows; this machine is a Mac (D2). Mac tests prove the logic with Windows calls stubbed. This
skill proves the real app: you write the exact steps, allen runs them on a Windows PC, you read back the result. Until
he reports, the change is "Mac-proven, Windows unverified" — never "done".

## Prepare

1. Pick the flows below that the change touches, plus the **Startup** flow. Add the change's own steps from the
   Record's Testing & scope.
2. Write them into the Record (or the `/fix` proof file) as a numbered checklist: the exact action, then what must be
   true afterwards — a file in `Pictures\WallSwap`, a line in `wallswap.log`, what the tray shows. Plain words, one
   action per line, no code.
3. Send allen the checklist with the branch to test and the run command.

## Launch (Windows)

```
git fetch && git switch <branch>
uv sync
uv run wallpaper_changer.py
```

Close any running WallSwap first (tray → Quit): a second copy exits on start (single-instance mutex).
For a clean run, rename `Pictures\WallSwap\settings.json` first and restore it after; with no settings file the
settings window opens by itself (first run).

## Flows

Each flow: what it is, how to reach it, the end state that proves it.

- **Startup.** Run the app. Proof: the tray icon appears, a wallpaper is set within a short wait, the tooltip names
  it, and `wallswap.log` shows "WallSwap starting up!" then "Wallpaper set:".
- **Next wallpaper.** Double-click the icon, or right-click → Next Wallpaper. Proof: the desktop changes, the lock
  screen (Win+L) shows the same image if it is set to "Picture", the tooltip updates.
- **Fullscreen check, automated (INV-14).** Run first; it needs no game: `uv run pytest tests/test_fullscreen_windows.py
  -v` on an unlocked desktop, without touching the mouse or keyboard while it runs. It opens real test windows
  (fullscreen, borderless, maximized, ordinary, second monitor) and checks WallSwap's answer for each. PASSED = rule
  holds; SKIPPED = Windows refused the setup (the reason names what), not a verdict; FAILED = the rule is wrong for
  that window. `test_maximized_then_fullscreen` reports XPASS (handled) or XFAIL (the parked "maximized-then-fullscreen"
  residual is real).
- **Fullscreen skip (INV-14).** Set the interval to 15 min, start a fullscreen game or a fullscreen video, and stay
  in it past the next timer tick. Use the timer, not Next Wallpaper: opening the tray menu takes focus off the game,
  so a manual click never shows the skip. Proof: `wallswap.log` shows "Fullscreen app detected, skipping wallpaper
  change" and the wallpaper did not change. Repeat with: a borderless-windowed game; a game on a second monitor (if
  you have one); a game maximized as a window and then switched to fullscreen. Also check the opposite: with an
  ordinary window maximized (Explorer), the auto-hide taskbar on, the timer still changes the wallpaper.
- **Pause.** Right-click → Pause. Proof: the icon turns orange, no change at the next interval; Pause again resumes.
- **Interval.** Right-click → Interval → 15 min. Proof: the radio mark moves, `settings.json` shows
  `"interval_minutes": 15`.
- **Sources.** Turn every source but one off. Proof: the next few wallpapers all come from that source (tooltip /
  Details), and `settings.json` shows the toggles.
- **Settings window.** Right-click → Settings…; click it again. Proof: one window comes to the front (no second
  copy). Untick a topic, add a search, move a slider (the % labels change), Save: a "Settings saved" notification,
  `settings.json` shows only those changes, and the next wallpaper's logged query comes from a ticked topic. Edit
  something and press Cancel: "Discard your changes?" and nothing is written.
- **Start with Windows.** In the window, turn it off and Save: `Startup\WallSwap.lnk` is gone. Turn it on and Save:
  the shortcut exists, points at `.venv\Scripts\pythonw.exe` with the script as its argument and the WallSwap icon.
  Sign out and in: WallSwap starts with no console window.
- **Upgrade from the old settings file.** Quit the old WallSwap first. Start the new one. Proof: `settings.json.bak`
  is the old file, `settings.json` now has `topics`, and the window shows the same game, folders and a 45/15/20/20 mix.
- **My Folders.** Add a folder of 1440p+ landscape images; remove it again. Proof: it appears in the submenu and
  `local_folders`; with only Local on, its images are used; the folder's files are untouched (INV-8).
- **Favourite.** Right-click → Favourite. Proof: a copy appears in `Pictures\WallSwap\Favourites`; doing it twice
  says "Already in Favourites".
- **Details.** Right-click → Details. Proof: a Wallhaven or Met page opens in the browser, or Explorer selects the
  local file.
- **Broken settings (INV-10).** Put a syntax error in `settings.json`, then change the interval from the tray. Proof:
  a notification says the file has a mistake, the file is left as you broke it, the app keeps running.
- **Cleanup (INV-9).** With more than 50 `wallswap_*.jpg` files present, trigger a change. Proof: only the newest 50
  remain; `Favourites` and your own folders are untouched.

## Evidence

Ask allen for: which steps passed, a screenshot of anything that failed, and the tail of
`Pictures\WallSwap\wallswap.log` covering the run. Paste his results into the Record's Proof table (or the proof
file), marked "Windows check, run by allen".

## Keeping this true

A flow here wrong about the app is fixed in the same session. App behaviour that is actually broken is a bug: report
it for `/fix` and leave the flow saying what should happen. `/maintain-verify` audits every flow in one pass.
