"""Import wallpaper_changer safely on any OS.

Importing it creates ~/Pictures/WallSwap, writes settings.json and opens the log (HZ-3), so HOME points at a temp dir
before the import. pystray is stubbed: the tray is never started in tests, and on macOS it would pull in AppKit.
"""
import os
import sys
import tempfile
import types
from pathlib import Path

_home = tempfile.mkdtemp(prefix="wallswap-test-home-")
os.environ["HOME"] = _home
os.environ["USERPROFILE"] = _home  # Path.home() on Windows

sys.modules.setdefault("pystray", types.SimpleNamespace(MenuItem=object, Menu=object, Icon=object))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wallpaper_changer  # noqa: E402,F401  (import after HOME is redirected)

assert str(wallpaper_changer.WALLPAPER_DIR).startswith(_home), "tests must never touch the real home folder"
