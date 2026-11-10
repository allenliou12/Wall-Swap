"""Start with Windows: WallSwap writes and removes only Startup\\WallSwap.lnk (INV-16)."""
import os
import sys
from pathlib import Path

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


def test_frozen_shortcut_spec_targets_the_exe(tmp_path):
    exe = tmp_path / "WallSwap" / "WallSwap.exe"
    spec = wc.startup_shortcut_spec(exe, tmp_path / "_internal" / "wallpaper_changer.py",
                                    tmp_path / "_internal" / "wallswap.ico", pythonw_exists=False, frozen=True)
    assert spec == wc.ShortcutSpec(target=str(exe), arguments="", working_dir=str(exe.parent), icon=f"{exe},0")


def test_turning_on_when_frozen_writes_the_exe_shortcut(appdata, monkeypatch, tmp_path):
    exe = tmp_path / "WallSwap" / "WallSwap.exe"
    monkeypatch.setattr(wc, "FROZEN", True)
    monkeypatch.setattr(wc.sys, "executable", str(exe))
    written = []
    wc.set_start_with_windows(True, write=lambda path, spec: written.append((path, spec)))
    (path, spec), = written
    assert path == appdata / wc.STARTUP_SHORTCUT_NAME
    assert (spec.target, spec.arguments, spec.working_dir) == (str(exe), "", str(exe.parent))


@pytest.fixture
def appdata(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    startup = tmp_path / "AppData" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    startup.mkdir(parents=True)
    return startup


class _FakeShell:
    """Stands in for the shell link object: records the calls, and "saves" by creating the file."""

    def __init__(self, monkeypatch, saves: bool = True, stored: str | None = None):
        self.calls, self.saves, self.stored, self.target = [], saves, stored, ""
        monkeypatch.setattr(wc, "_with_shell_link", lambda work: work("link", "file"))
        monkeypatch.setattr(wc, "_com", self.com)

    def com(self, pointer, slot, argtypes, *args):
        self.calls.append((pointer, slot, args))
        if slot == wc.LINK_SET_PATH:
            self.target = args[0]
        elif slot == wc.PERSIST_SAVE and self.saves:
            Path(args[0]).write_bytes(b"lnk")
        elif slot == wc.LINK_GET_PATH:
            args[0].value = self.target if self.stored is None else self.stored


def test_turning_on_writes_the_shortcut_in_this_process(appdata, monkeypatch):
    shell = _FakeShell(monkeypatch)
    started = []
    monkeypatch.setattr(wc.subprocess, "run", lambda *a, **k: started.append(a))
    monkeypatch.setattr(wc.subprocess, "Popen", lambda *a, **k: started.append(a))
    wc.set_start_with_windows(True)

    lnk = appdata / wc.STARTUP_SHORTCUT_NAME
    assert lnk.exists() and wc.startup_enabled()
    assert started == []  # no PowerShell or any other program: antivirus takes that for malware
    script = str(wc.SCRIPT_DIR / "wallpaper_changer.py")
    sets = {slot: args for pointer, slot, args in shell.calls if pointer == "link"}
    assert Path(sets[wc.LINK_SET_PATH][0]).parent == Path(sys.executable).parent
    assert sets[wc.LINK_SET_ARGUMENTS] == (f'"{script}"',)
    assert sets[wc.LINK_SET_WORKING_DIR] == (str(wc.SCRIPT_DIR),)
    assert sets[wc.LINK_SET_ICON] == (str(wc.ICON_PATH), 0)
    assert ("file", wc.PERSIST_SAVE, (str(lnk), 1)) in shell.calls


def test_turning_on_raises_when_no_shortcut_appears(appdata, monkeypatch):
    _FakeShell(monkeypatch, saves=False)
    with pytest.raises(OSError):
        wc.set_start_with_windows(True)
    assert not wc.startup_enabled()


def test_turning_on_raises_when_shortcut_target_differs(appdata, monkeypatch):
    _FakeShell(monkeypatch, stored=r"C:\???\pythonw.exe")
    with pytest.raises(OSError):
        wc.set_start_with_windows(True)


def test_a_shortcut_call_windows_refuses_raises_oserror(appdata, monkeypatch):
    def refuse(work):
        raise OSError("Windows shortcut call 6 failed (0x80070005)")
    monkeypatch.setattr(wc, "_with_shell_link", refuse)
    with pytest.raises(OSError) as raised:
        wc.set_start_with_windows(True)
    assert len(str(raised.value)) < 250
    assert not wc.startup_enabled()


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


# ── Taking over an existing Start with Windows shortcut (installed exe only) ──

@pytest.mark.parametrize("existing, expected", [
    (r"C:\Apps\WallSwap\WallSwap.exe", False),  # already this exe
    (r"c:\apps\wallswap\WALLSWAP.EXE", False),  # Windows paths ignore case
    (r"C:\src\WallSwap\.venv\Scripts\pythonw.exe", True),  # an older copy run from source
    ("", True),  # empty or unreadable
    ("   ", True),
])
def test_should_repoint(existing, expected):
    assert wc.should_repoint(existing, r"C:\Apps\WallSwap\WallSwap.exe") is expected


def _take_over(monkeypatch, tmp_path, *, frozen, existing):
    exe = tmp_path / "WallSwap" / "WallSwap.exe"
    monkeypatch.setattr(wc.sys, "executable", str(exe))
    reads, writes = [], []

    def read(path):
        reads.append(path)
        if isinstance(existing, Exception):
            raise existing
        return existing

    changed = wc.take_over_startup_shortcut(frozen=frozen, read=read,
                                            write=lambda path, spec: writes.append((path, spec)))
    return exe, changed, reads, writes


def test_take_over_never_runs_from_source(appdata, monkeypatch, tmp_path):
    (appdata / wc.STARTUP_SHORTCUT_NAME).write_bytes(b"lnk")
    _, changed, reads, writes = _take_over(monkeypatch, tmp_path, frozen=False, existing=r"C:\old\pythonw.exe")
    assert not changed and reads == [] and writes == []


def test_take_over_never_creates_the_shortcut(appdata, monkeypatch, tmp_path):
    _, changed, reads, writes = _take_over(monkeypatch, tmp_path, frozen=True, existing=r"C:\old\pythonw.exe")
    assert not changed and reads == [] and writes == []
    assert list(appdata.iterdir()) == []


def test_take_over_rewrites_an_old_target(appdata, monkeypatch, tmp_path):
    (appdata / wc.STARTUP_SHORTCUT_NAME).write_bytes(b"lnk")
    exe, changed, _, writes = _take_over(monkeypatch, tmp_path, frozen=True, existing=r"C:\old\pythonw.exe")
    (path, spec), = writes
    assert changed and path == appdata / wc.STARTUP_SHORTCUT_NAME
    assert spec == wc.ShortcutSpec(target=str(exe), arguments="", working_dir=str(exe.parent), icon=f"{exe},0")


def test_take_over_leaves_a_current_shortcut_alone(appdata, monkeypatch, tmp_path):
    (appdata / wc.STARTUP_SHORTCUT_NAME).write_bytes(b"lnk")
    exe = tmp_path / "WallSwap" / "WallSwap.exe"
    _, changed, reads, writes = _take_over(monkeypatch, tmp_path, frozen=True, existing=str(exe).upper())
    assert not changed and len(reads) == 1 and writes == []


def test_take_over_rewrites_an_unreadable_shortcut(appdata, monkeypatch, tmp_path):
    (appdata / wc.STARTUP_SHORTCUT_NAME).write_bytes(b"not a shortcut")
    _, changed, _, writes = _take_over(monkeypatch, tmp_path, frozen=True, existing=OSError("bad"))
    assert changed and len(writes) == 1


def test_a_failing_take_over_never_stops_the_app(monkeypatch):
    def boom():
        raise OSError("Access is denied.")
    monkeypatch.setattr(wc, "take_over_startup_shortcut", boom)
    wc.WallSwapApp._take_over_startup_shortcut(object())  # logged, not raised


def test_take_over_leaves_a_shortcut_removed_while_it_was_reading(appdata, monkeypatch, tmp_path):
    # The user turns Start with Windows off while the slow read runs (here: the read fails because the file went)
    lnk = appdata / wc.STARTUP_SHORTCUT_NAME
    lnk.write_bytes(b"lnk")
    exe = tmp_path / "WallSwap" / "WallSwap.exe"
    monkeypatch.setattr(wc.sys, "executable", str(exe))
    writes = []

    def read(path):
        wc.set_start_with_windows(False)
        raise OSError("the shortcut is gone")

    assert wc.take_over_startup_shortcut(frozen=True, read=read,
                                         write=lambda path, spec: writes.append(path)) is False
    assert writes == [] and not lnk.exists()
