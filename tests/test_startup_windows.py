"""A real shortcut round trip, written into tmp_path only (never the real Startup folder)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import wallpaper_changer as wc

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows shortcuts require Windows")

# Read back through Shell.Application (shell32, Unicode), independent of the writer; WScript.Shell is ANSI-only.
# The path travels in the environment, like the writer's.
READ_PS = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$folder = (New-Object -ComObject Shell.Application).Namespace((Split-Path -Parent $env:WS_LNK))
$link = $folder.ParseName((Split-Path -Leaf $env:WS_LNK)).GetLink
$iconPath = ''
$iconIndex = $link.GetIconLocation([ref]$iconPath)
@{target=$link.Path; arguments=$link.Arguments; working_dir=$link.WorkingDirectory;
  icon="$iconPath,$iconIndex"} | ConvertTo-Json -Compress
"""


def _read_back(lnk: Path) -> dict:
    powershell = str(wc.windows_directory() / "System32/WindowsPowerShell/v1.0/powershell.exe")
    out = subprocess.run([powershell, "-NoProfile", "-NonInteractive", "-Command", READ_PS],
                         env={**os.environ, "WS_LNK": str(lnk)}, capture_output=True, check=True, timeout=30)
    return json.loads(out.stdout.decode("utf-8-sig"))


@pytest.mark.parametrize("folder_name", ["app dir", "日本語 app"])  # a space, and characters outside the ANSI page
def test_real_shortcut_round_trip(tmp_path, folder_name):
    app = tmp_path / folder_name
    app.mkdir()
    script, icon = app / "wallpaper_changer.py", app / "wallswap.ico"
    script.write_text("")
    icon.write_bytes(b"")
    target = app / "pythonw.exe"  # inside the odd folder too, so the target path itself is tested
    target.write_bytes(b"")
    spec = wc.startup_shortcut_spec(target, script, icon, pythonw_exists=True)
    lnk = app / wc.STARTUP_SHORTCUT_NAME  # the shortcut path may hold them too (a non-Latin user name)

    wc.write_shortcut(lnk, spec)

    read = _read_back(lnk)
    assert Path(read["target"]) == Path(spec.target)
    assert read["arguments"] == spec.arguments
    assert Path(read["working_dir"]) == app
    assert read["icon"] == spec.icon


def test_real_frozen_shortcut_has_no_arguments(tmp_path):
    app = tmp_path / "WallSwap 日本語"
    app.mkdir()
    exe = app / "WallSwap.exe"
    exe.write_bytes(b"")
    spec = wc.startup_shortcut_spec(exe, app / "unused.py", app / "unused.ico", pythonw_exists=True, frozen=True)
    lnk = app / wc.STARTUP_SHORTCUT_NAME

    wc.write_shortcut(lnk, spec)  # an empty WS_ARGS must still produce a shortcut

    read = _read_back(lnk)
    assert Path(read["target"]) == exe
    assert read["arguments"] == ""
    assert Path(read["working_dir"]) == app
    assert read["icon"] == f"{exe},0"
