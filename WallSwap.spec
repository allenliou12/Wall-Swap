# PyInstaller build for the standalone WallSwap.exe. Build with:  uv run pyinstaller --noconfirm WallSwap.spec
# Output: dist\WallSwap\WallSwap.exe plus its _internal folder (zip the whole dist\WallSwap folder to share it).
#
# onedir, not onefile: a onefile exe unpacks itself to %TEMP% on every start, which is slower for a tray app that
# runs all day, leaves stray _MEI folders when Windows kills it at shutdown, and trips antivirus heuristics more often.
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import tomllib
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable,
                                                 VarFileInfo, VarStruct, VSVersionInfo)

# The version in pyproject.toml, so Properties > Details on WallSwap.exe shows the same number as the app
VERSION = tomllib.loads(Path(SPECPATH, "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
_numbers = tuple(int(n) for n in (VERSION.split(".") + ["0"] * 4)[:4])
version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=_numbers, prodvers=_numbers),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("ProductName", "WallSwap"),
            StringStruct("FileDescription", "WallSwap"),
            StringStruct("FileVersion", VERSION),
            StringStruct("ProductVersion", VERSION),
            StringStruct("OriginalFilename", "WallSwap.exe"),
            StringStruct("LegalCopyright", "Copyright (c) 2026 Liou Jun Yi. MIT licence."),
        ])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

datas = [
    ("wallswap.ico", "."),  # the tray icon and the settings window's icon (ICON_PATH, under sys._MEIPASS)
    ("THIRD_PARTY_NOTICES.md", "."),
]
datas += collect_data_files("customtkinter")  # its themes (JSON) and fonts are loaded from disk at runtime

hiddenimports = [
    "pystray._win32",  # pystray picks its backend at runtime, so the analysis can't see it
    "settings_window",  # imported inside WallSwapApp.run
]
hiddenimports += collect_submodules("winrt")  # the lock-screen bindings (winrt-runtime + the three windows.* pkgs)

a = Analysis(
    ["wallpaper_changer.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "ruff"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WallSwap",
    icon="wallswap.ico",
    version=version_info,
    console=False,  # windowed: no console window; sys.stdout/sys.stderr are None
    upx=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="WallSwap",
    upx=False,
)
