# 🎨 WallSwap - Fresh Desktop Wallpapers on Autopilot

A lightweight Windows system tray app that sets a new **1440p+** desktop (and lock screen) wallpaper every 30 minutes, mixed from Wallhaven, public-domain paintings from The Metropolitan Museum of Art, and your own image folders.

---

## ✨ Features

- 🖼️ **1440p+ only**: never a blurry wallpaper (minimum 2560×1440, landscape)
- 🔄 **Auto-rotates every 30 minutes**, and updates the lock screen too
- 🌐 **Several sources, mixed at random:**
  - **[Wallhaven](https://wallhaven.cc)**: general searches (scenery, space, dark fantasy, games, anime…), SFW only, with the "people" category off to avoid celebrity photos
  - **Wallhaven game searches**: a dedicated share for one favourite game (Path of Exile by default)
  - **[The Met](https://metmuseum.github.io/)**: public-domain paintings (ruins, storms, castles, moonlight…) that fit a wide screen
  - **Your own folders**: cycles through every image before repeating
- 🔁 **No repeats**: remembers what it has already shown
- 🎮 **Game-aware**: skips changes while a fullscreen app is running
- 💾 **Saves downloads** to `Pictures/WallSwap/`, keeping the 50 most recent
- 🔑 **No API keys needed**
- ⏸️ **Pause/Resume** from the system tray

---

## 🚀 Quick Setup

Requires **Windows 10/11** and **Python 3.13+**.

### With [uv](https://docs.astral.sh/uv/) (recommended)
```
uv sync
uv run wallpaper_changer.py
```

### With pip
```
pip install pystray Pillow requests winrt-runtime winrt-windows-foundation winrt-windows-storage winrt-windows-system-userprofile
python wallpaper_changer.py
```
The `winrt-*` packages are only used to set the lock screen. Without them, WallSwap still changes the desktop wallpaper.

The WallSwap icon appears in your system tray (bottom-right of the taskbar). Only one copy can run at a time.

---

## 🖱️ System Tray Controls

Double-click the tray icon for the next wallpaper. Right-click it for the menu:

| Menu item | What it does |
|---|---|
| 🔄 **Next Wallpaper** | Next wallpaper now |
| ⭐ **Favourite** | Copies the current wallpaper to `Pictures/WallSwap/Favourites/`, which is never cleaned up |
| 🔗 **Details** | Shows what the current wallpaper is and opens its Wallhaven or Met page (or shows a local file in Explorer) |
| ⏸ **Pause** | Toggle auto-changing (icon turns orange) |
| ⏱ **Interval ▸** | Change every 15 min, 30 min, 1 hour or 2 hours |
| 🌐 **Sources ▸** | Turn each source on or off |
| 📂 **My Folders ▸** | Add one of your own image folders with a folder picker, or click one to remove it |
| ⚙️ **Settings** | Edit `settings.json` in Notepad |
| 📁 **WallSwap Folder** | Browse downloads, favourites and the log |
| ❌ **Quit** | Exit |

Hover over the tray icon to see the current wallpaper's title.

---

## 🎮 Auto-Start on Boot (Optional)

1. Press `Win + R`, type `shell:startup`, press Enter
2. Create a shortcut to `wallpaper_changer.pyw` in that folder

Copy or rename `wallpaper_changer.py` to `wallpaper_changer.pyw` (note the **w**) so it runs without a console window.

---

## ⚙️ Customization

Most things can be changed from the tray menu. Everything else is in `Pictures/WallSwap/settings.json`, created on first run. Open it with **⚙️ Settings** in the tray menu; edits apply from the next wallpaper change. If the file gets broken, WallSwap keeps its previous settings, and deleting the file restores the defaults.

```json
{
  "interval_minutes": 30,
  "sources": {"wallhaven": true, "game": true, "museum": true, "local": true},
  "chances": {"local": 0.2, "game": 0.2, "museum": 0.15},
  "game_name": "Path of Exile",
  "game_queries": ["path of exile", "path of exile 2"],
  "local_folders": ["C:\\Users\\<YourName>\\Pictures\\Path of Exile 2"],
  "game_folders": ["C:\\Users\\<YourName>\\Pictures\\Path of Exile 2"]
}
```

| Setting | Description |
|---|---|
| `interval_minutes` | Minutes between changes |
| `sources` | Turn each source on (`true`) or off (`false`) |
| `chances` | Share of changes for local folders, the favourite game and Met paintings. Whatever's left (0.45 by default) goes to general Wallhaven searches. Turning a source off shares its part among the others |
| `game_name` / `game_queries` | The favourite game shown in the Sources menu, and its Wallhaven searches. Change them to any game you like |
| `local_folders` | Your own image folders (top-level files only, not subfolders). Missing folders are skipped |
| `game_folders` | Folders of the favourite game's images (e.g. your screenshots). Once all of the game's Wallhaven wallpapers have been shown, its share uses these, so adding other folders can't dilute it. Marked with the game's name in **📂 My Folders** |

If a source fails (offline, nothing new found), WallSwap falls back to general Wallhaven and then to your local folders. General Wallhaven searches skip wallpapers with fewer than 30 favourites (`WALLHAVEN_MIN_FAVORITES`); the favourite game's searches don't, since few game wallpapers exist.

A few advanced settings stay at the top of `wallpaper_changer.py`: the general Wallhaven and Met search terms (`WALLHAVEN_QUERIES`, `MUSEUM_QUERIES`), the minimum size (`MIN_WIDTH` / `MIN_HEIGHT`, 2560×1440) and how many downloads to keep (`MAX_WALLPAPERS`, 50).

---

## 📁 Where are my wallpapers saved?

```
C:\Users\<YourName>\Pictures\WallSwap\
```

Downloads are named `wallswap_wallhaven_*.jpg` and `wallswap_met_*.jpg`. Images from your own folders are used in place and never copied or deleted. The folder also holds `settings.json`, `wallswap.log` and the history files that prevent repeats (`seen_ids.txt`, `seen_local.txt`).

> Downloaded wallpapers beyond the newest 50 are deleted automatically. Use **⭐ Favourite** in the tray menu to keep one: it's copied to the `Favourites` subfolder, which is never cleaned up.

---

## ❓ Troubleshooting

**Wallpaper didn't change**: check `wallswap.log` in the WallSwap folder. A fullscreen app (game, video) pauses changes; otherwise the log shows which source failed.

**Lock screen didn't change**: make sure the `winrt-*` packages are installed, and that your lock screen is set to "Picture" (not Spotlight) in Windows Settings → Personalization → Lock screen.

**Icon not showing in tray**: click the **^** arrow on the taskbar to find hidden tray icons, then drag it out to keep it visible.

---

## 🙏 Credits

Wallpapers come from [Wallhaven](https://wallhaven.cc) and the [Metropolitan Museum of Art Open Access](https://www.metmuseum.org/about-the-met/policies-and-documents/open-access) collection. Images belong to their respective artists. Met Open Access images are public domain (CC0).
