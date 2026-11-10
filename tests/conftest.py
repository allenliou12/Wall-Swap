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
_appdata = tempfile.mkdtemp(prefix="wallswap-test-appdata-")
os.environ["APPDATA"] = _appdata  # the Startup shortcut lives under APPDATA (INV-16)

sys.modules.setdefault("pystray", types.SimpleNamespace(MenuItem=object, Menu=object, Icon=object))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
import wallpaper_changer  # noqa: E402,F401  (import after HOME is redirected)


def pytest_addoption(parser):
    parser.addoption("--desktop", action="store_true",
                     help="also run the tests that open real fullscreen windows and take the keyboard focus")


def pytest_configure(config):
    if config.getoption("--desktop"):
        os.environ["WALLSWAP_DESKTOP_TESTS"] = "1"  # the DPI-aware child run inherits it


@pytest.fixture(autouse=True)
def _fixed_screen(request, monkeypatch):
    """Size checks never depend on the monitor the tests happen to run on; test_screen_size fakes its own."""
    if request.module.__name__ != "test_screen_size":
        monkeypatch.setattr(wallpaper_changer, "largest_screen", lambda: (2560, 1440))


@pytest.fixture(autouse=True)
def _no_real_windows_state(request, monkeypatch):
    """Tests never depend on the PC's real connection and never write the real registry; test_metered_fit
    fakes both itself."""
    if request.module.__name__ != "test_metered_fit":
        monkeypatch.setattr(wallpaper_changer, "is_metered", lambda: False)
        monkeypatch.setattr(wallpaper_changer, "apply_wallpaper_fit", lambda fit: None)

assert str(wallpaper_changer.WALLPAPER_DIR).startswith(_home), "tests must never touch the real home folder"
assert str(wallpaper_changer.startup_shortcut_path()).startswith(_appdata), "tests must never touch the real Startup folder"
