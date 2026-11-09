"""Start with Windows: WallSwap writes and removes only Startup\\WallSwap.lnk (INV-16)."""
import os
import subprocess
import sys
import types
from pathlib import Path, PureWindowsPath

import pytest

import wallpaper_changer as wc


def _spec(tmp_path: Path, pythonw_exists: bool) -> wc.ShortcutSpec:
    exe = tmp_path / "Scripts" / "python.exe"
    return wc.startup_shortcut_spec(exe, tmp_path / "app" / "wallpaper_changer.py", tmp_path / "app" / "wallswap.ico",
                                    pythonw_exists)


def test_shortcut_spec_uses_pythonw(tmp_path):
    spec = _spec(tmp_path, pythonw_exists=True)
    assert spec.target == str(tmp_path / "Scripts" / "pythonw.exe")
    assert spec.arguments == f'"{tmp_path / "app" / "wallpaper_changer.py"}"'
    assert spec.working_dir == str(tmp_path / "app")
    assert spec.icon == f"{tmp_path / 'app' / 'wallswap.ico'},0"


def test_shortcut_spec_falls_back_to_executable(tmp_path):
    spec = _spec(tmp_path, pythonw_exists=False)
    assert spec.target == str(tmp_path / "Scripts" / "python.exe")


@pytest.fixture
def appdata(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    startup = tmp_path / "AppData" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    startup.mkdir(parents=True)
    return startup


def test_turning_on_passes_paths_only_in_env(appdata, monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        Path(kwargs["env"]["WS_LNK"]).write_bytes(b"lnk")
        return subprocess.CompletedProcess(argv, 0, stdout=kwargs["env"]["WS_TARGET"].encode("utf-8"))

    monkeypatch.setattr(wc.subprocess, "run", fake_run)
    wc.set_start_with_windows(True)

    lnk = appdata / wc.STARTUP_SHORTCUT_NAME
    assert lnk.exists() and wc.startup_enabled()
    (argv, kwargs), = calls
    assert PureWindowsPath(argv[0]).is_absolute() and PureWindowsPath(argv[0]).name.lower() == "powershell.exe"
    assert argv[-1] == wc.SHORTCUT_PS
    env = kwargs["env"]
    script = str(wc.SCRIPT_DIR / "wallpaper_changer.py")
    assert env["WS_LNK"] == str(lnk)
    assert env["WS_ARGS"] == f'"{script}"'
    assert env["WS_WD"] == str(wc.SCRIPT_DIR)
    assert env["WS_ICON"] == f"{wc.ICON_PATH},0"
    assert Path(env["WS_TARGET"]).parent == Path(sys.executable).parent
    for path in (str(lnk), script, str(wc.SCRIPT_DIR), str(wc.ICON_PATH), env["WS_TARGET"]):
        assert all(path not in arg for arg in argv)
    assert kwargs["check"] is True and kwargs["timeout"]


def test_turning_on_raises_when_no_shortcut_appears(appdata, monkeypatch):
    monkeypatch.setattr(wc.subprocess, "run", lambda argv, **kw: subprocess.CompletedProcess(argv, 0))
    with pytest.raises(OSError):
        wc.set_start_with_windows(True)
    assert not wc.startup_enabled()


def test_turning_on_raises_when_shortcut_target_differs(appdata, monkeypatch):
    def fake_run(argv, **kwargs):
        Path(kwargs["env"]["WS_LNK"]).write_bytes(b"lnk")
        return subprocess.CompletedProcess(argv, 0, stdout=r"C:\???\pythonw.exe".encode("utf-8"))

    monkeypatch.setattr(wc.subprocess, "run", fake_run)
    with pytest.raises(OSError):
        wc.set_start_with_windows(True)


class _FakeKernel32:
    def __init__(self, windows_dir: str):
        self.windows_dir = windows_dir

    def GetSystemWindowsDirectoryW(self, buf, size):
        buf.value = self.windows_dir
        return len(self.windows_dir)


def _powershell_used(tmp_path, monkeypatch, kernel32) -> str:
    monkeypatch.setenv("SystemRoot", ".")  # a parent process can set this to anything
    monkeypatch.setattr(wc.ctypes, "windll", types.SimpleNamespace(kernel32=kernel32), raising=False)
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        Path(kwargs["env"]["WS_LNK"]).write_bytes(b"lnk")
        return subprocess.CompletedProcess(argv, 0, stdout=kwargs["env"]["WS_TARGET"].encode("utf-8"))

    monkeypatch.setattr(wc.subprocess, "run", fake_run)
    wc.write_shortcut(tmp_path / "x.lnk", wc.ShortcutSpec(r"C:\py\pythonw.exe", '"s.py"', r"C:\app", r"C:\app\i.ico,0"))
    return calls[0][0]


def test_powershell_comes_from_the_os_windows_folder_not_systemroot(tmp_path, monkeypatch):
    used = _powershell_used(tmp_path, monkeypatch, _FakeKernel32(r"D:\Win"))
    assert used == r"D:\Win\System32\WindowsPowerShell\v1.0\powershell.exe"


def test_relative_os_answer_falls_back_to_c_windows(tmp_path, monkeypatch):
    used = _powershell_used(tmp_path, monkeypatch, _FakeKernel32("."))
    assert used == r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"


def test_turning_off_removes_only_wallswap_lnk(appdata):
    (appdata / wc.STARTUP_SHORTCUT_NAME).write_bytes(b"lnk")
    (appdata / "Other.lnk").write_bytes(b"other")
    (appdata / "notes.txt").write_text("keep")

    wc.set_start_with_windows(False)

    assert not wc.startup_enabled()
    assert sorted(p.name for p in appdata.iterdir()) == ["Other.lnk", "notes.txt"]
    wc.set_start_with_windows(False)  # already off: nothing to remove, no error


def test_startup_path_reads_appdata_at_call_time(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "first"))
    first = wc.startup_shortcut_path()
    monkeypatch.setenv("APPDATA", str(tmp_path / "second"))
    second = wc.startup_shortcut_path()
    assert first.is_relative_to(tmp_path / "first") and second.is_relative_to(tmp_path / "second")
    assert second.name == wc.STARTUP_SHORTCUT_NAME
    assert not os.path.exists(second)


@pytest.mark.parametrize("failure", [
    subprocess.CalledProcessError(1, ["powershell.exe", "-Command", wc.SHORTCUT_PS],
                                  stderr=b"At line:1 char:5\r\nAccess to the path is denied.\r\n"),
    subprocess.TimeoutExpired(["powershell.exe", "-Command", wc.SHORTCUT_PS], 15),
])
def test_failed_powershell_gives_a_short_reason_not_the_script(appdata, monkeypatch, failure):
    def run(*args, **kwargs):
        raise failure
    monkeypatch.setattr(wc.subprocess, "run", run)
    with pytest.raises(OSError) as raised:
        wc.set_start_with_windows(True)
    message = str(raised.value)
    assert "WallSwapShortcut" not in message and len(message) < 250
    if isinstance(failure, subprocess.CalledProcessError):
        assert "Access to the path is denied." in message
