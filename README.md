# WallSwap

Small Windows tray app that changes my wallpaper (and lock screen) every 30 minutes. I got tired of looking at the same background, so this pulls from a few places:

- [Wallhaven](https://wallhaven.cc) searches: scenery, space, dark fantasy, games, anime. SFW only, and low-rated stuff is skipped.
- Path of Exile wallpapers from Wallhaven (you can change the game)
- Public-domain paintings from [the Met's open access API](https://metmuseum.github.io/)
- My own folders of screenshots

Everything is 2560x1440 or bigger and landscape. It doesn't repeat images, and it won't change the wallpaper while a fullscreen game is running. No API keys needed.

## Running it

Windows 10/11, Python 3.13+.

```
uv sync
uv run wallpaper_changer.py
```

Or with pip:

```
pip install pystray Pillow requests winrt-runtime winrt-windows-foundation winrt-windows-storage winrt-windows-system-userprofile
python wallpaper_changer.py
```

The `winrt` packages are only for the lock screen; without them it just does the desktop.

To start it with Windows, rename it to `wallpaper_changer.pyw` (no console window) and put a shortcut in `shell:startup`.

## Tray menu

Double-click the icon to skip to the next wallpaper. Right-click for:

- Next Wallpaper
- Favourite: copies the current one to `Pictures\WallSwap\Favourites`
- Details: opens the wallpaper's Wallhaven/Met page, or shows the file if it's a local one
- Pause
- Interval: 15 min, 30 min, 1 hour, 2 hours
- Sources: turn each source on/off
- My Folders: add or remove your own image folders
- Settings: opens `settings.json` in Notepad
- WallSwap Folder
- Quit

Hovering the icon shows what the current wallpaper is.

## Settings

Stored in `Pictures\WallSwap\settings.json`, created on first run. Hand edits apply on the next change. If you break the file it keeps the old settings; delete it to reset.

```json
{
  "interval_minutes": 30,
  "sources": {"wallhaven": true, "game": true, "museum": true, "local": true},
  "chances": {"local": 0.2, "game": 0.2, "museum": 0.15},
  "game_name": "Path of Exile",
  "game_queries": ["path of exile", "path of exile 2"],
  "local_folders": ["C:\\Users\\<you>\\Pictures\\Path of Exile 2"],
  "game_folders": ["C:\\Users\\<you>\\Pictures\\Path of Exile 2"]
}
```

- `chances` is how often each source gets picked. Whatever's left over (0.45 here) goes to general Wallhaven searches.
- `game_queries` are the Wallhaven searches for your game. There aren't many game wallpapers, so once they've all been shown, that share uses `game_folders` instead.
- `local_folders` only uses images directly in the folder, not subfolders.

The search terms, minimum resolution, and the 30-favourite cutoff for Wallhaven are constants at the top of `wallpaper_changer.py`.

## Files

Downloads go to `Pictures\WallSwap` and only the newest 50 are kept, so use Favourite for anything you want to hold on to. Your own folders are never touched. The log (`wallswap.log`) is in the same place if something isn't working.

If the lock screen doesn't change, check that it's set to "Picture" rather than Spotlight in Windows settings.

## Credits

Images come from Wallhaven and the Met's Open Access collection (CC0) and belong to their artists.

The app icon is made from Microsoft's [Fluent Emoji](https://github.com/microsoft/fluentui-emoji) (MIT); see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
