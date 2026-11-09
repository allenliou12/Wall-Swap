"""The version the app shows is the one the build and installer use (pyproject.toml)."""
import tomllib
from pathlib import Path

import wallpaper_changer as wc

ROOT = Path(__file__).resolve().parent.parent


def test_app_version_matches_pyproject():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert wc.APP_VERSION == project["version"]


def test_installer_default_version_matches_pyproject():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert f'#define AppVersion "{project["version"]}"' in (ROOT / "installer" / "WallSwap.iss").read_text(encoding="utf-8")
