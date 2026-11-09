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

| Action | What it does |
|---|---|
| **Double-click** tray icon | Next wallpaper now |
| **Right-click → Next Wallpaper** | Next wallpaper now |
| **Right-click → Pause / Resume** | Toggle auto-changing (icon turns orange) |
| **Right-click → Open Wallpaper Folder** | Browse saved wallpapers and the log |
| **Right-click → Quit WallSwap** | Exit |

---

## 🎮 Auto-Start on Boot (Optional)

1. Press `Win + R`, type `shell:startup`, press Enter
2. Create a shortcut to `wallpaper_changer.pyw` in that folder

Copy or rename `wallpaper_changer.py` to `wallpaper_changer.pyw` (note the **w**) so it runs without a console window.

---

## ⚙️ Customization

All settings are at the top of `wallpaper_changer.py`.

### Source mix
Each wallpaper change rolls once to pick a source; whatever is left over goes to general Wallhaven searches. If a source fails (offline, nothing new found), WallSwap falls back to Wallhaven and then to your local folders.

| Setting | Default | Description |
|---|---|---|
| `LOCAL_CHANCE` | `0.2` | Chance of an image from `LOCAL_FOLDERS` |
| `POE_WALLHAVEN_CHANCE` | `0.2` | Chance of a Wallhaven search from `POE_WALLHAVEN_QUERIES` |
| `MUSEUM_CHANCE` | `0.15` | Chance of a Met painting |
| *(rest)* | `0.45` | General Wallhaven search from `WALLHAVEN_QUERIES` |

### Other settings

| Setting | Default | Description |
|---|---|---|
| `LOCAL_FOLDERS` | `Pictures/Path of Exile 2` | Your own image folders (top-level files only, not subfolders). Missing folders are skipped |
| `POE_WALLHAVEN_QUERIES` | `path of exile`, `path of exile 2` | Searches for the favourite-game share. Change them to any game you like |
| `WALLHAVEN_QUERIES` | ~150 terms | General Wallhaven search terms |
| `MUSEUM_QUERIES` | ~20 terms | Search terms for Met paintings |
| `CHANGE_INTERVAL` | `30 * 60` | Seconds between changes |
| `MIN_WIDTH` / `MIN_HEIGHT` | `2560` / `1440` | Minimum wallpaper size |
| `MAX_WALLPAPERS` | `50` | Downloaded wallpapers kept on disk |

---

## 📁 Where are my wallpapers saved?

```
C:\Users\<YourName>\Pictures\WallSwap\
```

Downloads are named `wallswap_wallhaven_*.jpg` and `wallswap_met_*.jpg`. Images from your own folders are used in place and never copied or deleted. The folder also holds `wallswap.log` and the history files that prevent repeats (`seen_ids.txt`, `seen_local.txt`).

> Downloaded wallpapers beyond the newest 50 are deleted automatically. Copy any favourites somewhere else to keep them.

---

## ❓ Troubleshooting

**Wallpaper didn't change**: check `wallswap.log` in the WallSwap folder. A fullscreen app (game, video) pauses changes; otherwise the log shows which source failed.

**Lock screen didn't change**: make sure the `winrt-*` packages are installed, and that your lock screen is set to "Picture" (not Spotlight) in Windows Settings → Personalization → Lock screen.

**Icon not showing in tray**: click the **^** arrow on the taskbar to find hidden tray icons, then drag it out to keep it visible.

---

## 🙏 Credits

Wallpapers come from [Wallhaven](https://wallhaven.cc) and the [Metropolitan Museum of Art Open Access](https://www.metmuseum.org/about-the-met/policies-and-documents/open-access) collection. Images belong to their respective artists. Met Open Access images are public domain (CC0).
