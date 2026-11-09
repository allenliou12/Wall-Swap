# WallSwap

Small Windows tray app that changes my wallpaper (and lock screen) every 30 minutes. I got tired of looking at the same background, so this pulls from a few places:

- [Wallhaven](https://wallhaven.cc) searches on topics you pick: scenery, space, cities, night skies, dark fantasy, games, anime and so on. SFW only, and low-rated stuff is skipped.
- Wallpapers for a favourite game, if you set one (mine is Path of Exile)
- Public-domain paintings from [the Met's open access API](https://metmuseum.github.io/)
- Your own folders of screenshots or wallpapers

Everything is 2560x1440 or bigger and landscape. It doesn't repeat images, and it won't change the wallpaper while a fullscreen game is running. No API keys needed.

## Installing it

Windows 10/11, no Python needed. Both downloads are on the [Releases page](https://github.com/allenliou12/Wall-Swap/releases/latest).

- **Installer (recommended):** run `WallSwap-Setup.exe`. It installs just for you (no admin prompt) into `AppData\Local\Programs\WallSwap`, and adds WallSwap to the Start menu. Two boxes, both ticked to start with, add a desktop shortcut and start WallSwap when you sign in (the same as the Start with Windows switch, which you can turn off later). Uninstall it from Settings → Apps like anything else. Installing a newer version over it upgrades in place.
- **Portable zip:** unzip `WallSwap-<version>.zip` somewhere that will stay put (for example `Documents\WallSwap`) and run `WallSwap.exe`. Keep the `_internal` folder next to it.

Neither is code-signed, so Windows SmartScreen may say "Windows protected your PC" the first time. Click **More info**, then **Run anyway**. If you'd rather not, run it from source as shown below.

Start with Windows is also the switch in the settings window. Its shortcut points at wherever `WallSwap.exe` is, so if you move the portable folder, turn the switch off and on again. If you already had Start with Windows on from an older copy (say, one run from source), the installed or portable exe takes that shortcut over the first time it runs. Uninstalling removes that shortcut too, but never touches `Pictures\WallSwap` (your settings, favourites and downloads); delete that folder yourself if you want them gone.

## Running it from source

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

To build the exe, the zip and the installer yourself (the installer needs [Inno Setup 6](https://jrsoftware.org/isinfo.php): `winget install --id JRSoftware.InnoSetup -e --scope user`):

```
uv sync
powershell -ExecutionPolicy Bypass -File build.ps1
```

That makes `dist\WallSwap\WallSwap.exe`, `dist\WallSwap-<version>.zip` and `dist\WallSwap-Setup.exe`. For just the exe, run `uv run pyinstaller --noconfirm WallSwap.spec`.

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

- the WallSwap version, at the top (also in the settings window and in Settings → Apps)
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

## Licence

MIT; see [LICENSE](LICENSE). The icon and libraries keep their own licences: see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and the downloads include `THIRD_PARTY_LICENSES.txt` with the full texts of everything they bundle (Python, Tcl/Tk, pystray, Pillow, requests and the rest).

## Credits

Images come from Wallhaven and the Met's Open Access collection (CC0) and belong to their artists.

The app icon is made from Microsoft's [Fluent Emoji](https://github.com/microsoft/fluentui-emoji) (MIT); see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
