# WallSwap

Small Windows tray app that changes my wallpaper (and lock screen) every 30 minutes. I got tired of looking at the same background, so this pulls from a few places:

- [Wallhaven](https://wallhaven.cc) searches on topics you pick: scenery, space, cities, night skies, dark fantasy, games, anime and so on. SFW only, and low-rated stuff is skipped.
- Wallpapers for a favourite game, if you set one (mine is Path of Exile)
- Public-domain paintings from [the Met's open access API](https://metmuseum.github.io/)
- Your own folders of screenshots or wallpapers

Everything is 2560x1440 or bigger and landscape. It doesn't repeat images, and it won't change the wallpaper while a fullscreen game is running. No API keys needed.

## Running it

Windows 10/11, Python 3.13+.

```
uv sync
uv run wallpaper_changer.py
```

Or with pip:

```
pip install pystray Pillow requests customtkinter winrt-runtime winrt-windows-foundation winrt-windows-storage winrt-windows-system-userprofile
python wallpaper_changer.py
```

The `winrt` packages are only for the lock screen; without them it just does the desktop.

The first time it runs, the settings window opens so you can pick what you want. The first wallpaper changes straight away with the starter mix while you look around.

## Settings window

Right-click the tray icon and pick Settings… to open it again.

- **Topics:** tick the ones you want. Click a topic's arrow to see its searches; click a search to remove it, or type your own and press Add. Only ticked topics are searched, and every search in them is equally likely.
- **Favourite game:** a name and some Wallhaven searches for it. Leave it empty if you don't want one. There aren't many game wallpapers, so once they've all been shown, that share uses the game's folders instead.
- **My folders:** add or remove your own image folders. Only images directly in a folder are used, not subfolders, and WallSwap never changes anything in them.
- **Source mix:** one slider each for Wallhaven, Met paintings, your folders and your favourite game. The percentage next to each is its real share of changes. A source with nothing to use (no folders, no game searches, no ticked topics) or turned off drops out and says why.
- **Change every:** 15 min, 30 min, 1 hour or 2 hours.
- **Start with Windows:** puts a WallSwap shortcut in your Startup folder (or takes it out).

Save applies from the next wallpaper change. Cancel throws away what you changed.

## Tray menu

Double-click the icon to skip to the next wallpaper. Right-click for:

- Next Wallpaper
- Favourite: copies the current one to `Pictures\WallSwap\Favourites`
- Details: opens the wallpaper's Wallhaven/Met page, or shows the file if it's a local one
- Pause
- Interval, Sources, My Folders: quick versions of the same settings
- Settings…: opens the settings window
- WallSwap Folder
- Quit

Hovering the icon shows what the current wallpaper is.

## settings.json

The window saves to `Pictures\WallSwap\settings.json`. You can still edit it by hand; changes apply on the next wallpaper change. If you break the file it keeps the old settings and won't save over it; delete it to start again from the defaults.

```json
{
  "interval_minutes": 30,
  "sources": {"wallhaven": true, "game": true, "museum": true, "local": true},
  "chances": {"wallhaven": 0.45, "museum": 0.15, "local": 0.2, "game": 0.2},
  "topics": {
    "nature": {"enabled": true, "searches": ["landscape 4k", "mountains", "forest", "ocean", "aurora borealis"]},
    "...": "eight more topics: space, dark_fantasy, cities, abstract, moon_night, anime, games, movies"
  },
  "game_name": "Path of Exile",
  "game_queries": ["path of exile", "path of exile 2"],
  "local_folders": ["C:\\Users\\<you>\\Pictures\\Path of Exile 2"],
  "game_folders": ["C:\\Users\\<you>\\Pictures\\Path of Exile 2"]
}
```

- `chances` are weights, not percentages; they're compared with each other.
- The nine topic names are fixed; their searches are yours to change.

If you're upgrading from the version before the settings window, your old file is copied to `settings.json.bak` the first time the new version saves, and your old searches, game and folders carry over.

## Files

Downloads go to `Pictures\WallSwap` and only the newest 50 are kept, so use Favourite for anything you want to hold on to. Your own folders are never touched. The log (`wallswap.log`) is in the same place if something isn't working.

If the lock screen doesn't change, check that it's set to "Picture" rather than Spotlight in Windows settings.

## Credits

Images come from Wallhaven and the Met's Open Access collection (CC0) and belong to their artists.

The app icon is made from Microsoft's [Fluent Emoji](https://github.com/microsoft/fluentui-emoji) (MIT); see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
