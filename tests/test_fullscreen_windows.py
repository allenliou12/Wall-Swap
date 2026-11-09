"""INV-14 against real windows; run on an unlocked, interactive Windows desktop."""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

import pytest

import wallpaper_changer as wc

if sys.platform == "win32":
    try:
        import tkinter as tk
    except ImportError:
        tk = None
else:
    tk = None

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="real fullscreen windows require Windows")

WS_CAPTION = 0x00C00000  # Both bits must be present for a full title bar.
GWL_STYLE = -16  # Read the native style, not Tk's requested appearance.
GA_ROOT = 2  # Tk's widget HWND is a child of the actual top-level window.
MONITOR_DEFAULTTONEAREST = 2  # Match the monitor selection used by the app.
MONITORINFOF_PRIMARY = 1  # Enumeration order does not identify the primary monitor.
SWP_NOZORDER = 0x0004  # Moving a window must not change another app's stacking order.
SETTLE_SECONDS = 1.0  # Bound event processing while Windows applies focus and geometry changes.

Rect = tuple[int, int, int, int]


class _MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


@dataclass(frozen=True)
class _WindowState:
    hwnd: int
    zoomed: bool
    style: int
    rect: Rect
    monitor: int
    monitor_rect: Rect
    work_rect: Rect


@pytest.fixture
def user32() -> ctypes.WinDLL:
    # A separate DLL object keeps these prototypes from repairing the app's own ctypes calls.
    api = ctypes.WinDLL("user32", use_last_error=True)
    signatures = {
        "GetAncestor": ([wintypes.HWND, wintypes.UINT], wintypes.HWND),
        "GetForegroundWindow": ([], wintypes.HWND),
        "SetForegroundWindow": ([wintypes.HWND], wintypes.BOOL),
        "IsWindowVisible": ([wintypes.HWND], wintypes.BOOL),
        "IsIconic": ([wintypes.HWND], wintypes.BOOL),
        "IsZoomed": ([wintypes.HWND], wintypes.BOOL),
        "GetWindowLongW": ([wintypes.HWND, ctypes.c_int], wintypes.LONG),
        "GetWindowRect": ([wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
        "MonitorFromWindow": ([wintypes.HWND, wintypes.DWORD], wintypes.HANDLE),
        "GetMonitorInfoW": ([wintypes.HANDLE, ctypes.POINTER(_MonitorInfo)], wintypes.BOOL),
        "SetWindowPos": (
            [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
             ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.BOOL,
        ),
    }
    for name, (args, result) in signatures.items():
        function = getattr(api, name)
        function.argtypes = args
        function.restype = result
    return api


@pytest.fixture
def window(user32: ctypes.WinDLL) -> Iterator[tk.Tk]:
    if tk is None:
        pytest.skip("tkinter is unavailable in this Windows Python installation")
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Windows could not create an interactive Tk window: {error}")
    try:
        root.title("WallSwap fullscreen test")
        root.geometry("480x320")
        root.update()
        hwnd = user32.GetAncestor(root.winfo_id(), GA_ROOT)
        monitor = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        info = _monitor_info(user32, monitor)
        left, top, right, bottom = _rect(info.rcMonitor)
        # Use native coordinates so monitors left of the primary work too.
        _place(root, user32, (left + (right - left) // 4, top + (bottom - top) // 4,
                              left + 3 * (right - left) // 4, top + 3 * (bottom - top) // 4))
        yield root
    except tk.TclError as error:
        pytest.skip(f"Tk/Windows refused the initial window setup: {error}")
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass  # The user may already have closed the window during event processing.


def _rect(rect: wintypes.RECT) -> Rect:
    return rect.left, rect.top, rect.right, rect.bottom


def _monitor_info(api: ctypes.WinDLL, monitor: int) -> _MonitorInfo:
    info = _MonitorInfo()
    info.cbSize = ctypes.sizeof(info)
    if not monitor or not api.GetMonitorInfoW(monitor, ctypes.byref(info)):
        pytest.skip("Windows refused GetMonitorInfoW for the test monitor")
    return info


def _place(root: tk.Tk, api: ctypes.WinDLL, rect: Rect) -> None:
    try:
        root.update()
        hwnd = api.GetAncestor(root.winfo_id(), GA_ROOT)
        left, top, right, bottom = rect
        if not hwnd or not api.SetWindowPos(hwnd, None, left, top, right - left, bottom - top, SWP_NOZORDER):
            pytest.skip(f"Windows refused to place the test window at {rect}")
        root.update()
    except tk.TclError as error:
        pytest.skip(f"Tk/Windows refused window placement: {error}")


def _state(api: ctypes.WinDLL, hwnd: int) -> _WindowState:
    if api.GetForegroundWindow() != hwnd:
        pytest.skip("Windows refused to keep the test HWND in the foreground (foreground lock or focus changed)")
    if not api.IsWindowVisible(hwnd) or api.IsIconic(hwnd):
        pytest.skip("Windows left the test window hidden or minimized")
    rect = wintypes.RECT()
    if not api.GetWindowRect(hwnd, ctypes.byref(rect)):
        pytest.skip("Windows refused GetWindowRect for the test window")
    ctypes.set_last_error(0)
    style = api.GetWindowLongW(hwnd, GWL_STYLE)
    if style == 0 and ctypes.get_last_error():
        pytest.skip("Windows refused GetWindowLongW for the test window")
    monitor = api.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    info = _monitor_info(api, monitor)
    return _WindowState(hwnd, bool(api.IsZoomed(hwnd)), style, _rect(rect), monitor,
                        _rect(info.rcMonitor), _rect(info.rcWork))


def _ready(root: tk.Tk, api: ctypes.WinDLL, precondition: Callable[[_WindowState], bool],
           description: str) -> _WindowState:
    try:
        root.update()
        hwnd = api.GetAncestor(root.winfo_id(), GA_ROOT)
        if not hwnd:
            pytest.skip("Windows did not provide a top-level HWND for the Tk window")
        root.lift()
        root.focus_force()
        api.SetForegroundWindow(hwnd)
        deadline = time.monotonic() + SETTLE_SECONDS
        while time.monotonic() < deadline:
            root.update()
            time.sleep(0.02)
    except tk.TclError as error:
        pytest.skip(f"Tk/Windows refused to show/focus/settle the test window: {error}")
    before = _state(api, hwnd)
    if not precondition(before):
        pytest.skip(f"Windows refused {description}; observed {before}")
    return before


def _assert_rule(root: tk.Tk, api: ctypes.WinDLL, precondition: Callable[[_WindowState], bool],
                 description: str, expected: bool) -> None:
    before = _ready(root, api, precondition, description)
    actual = wc.is_fullscreen_app_running()
    if _state(api, before.hwnd) != before:
        pytest.skip("Windows changed the test window's zoom/style/rectangle/monitor during the rule check")
    assert actual is expected, f"Observed real Windows state: {before}"


def _contains(outer: Rect, inner: Rect) -> bool:
    return (outer[0] <= inner[0] and outer[1] <= inner[1]
            and outer[2] >= inner[2] and outer[3] >= inner[3])


@pytest.mark.parametrize("mode, expected", [
    # A game switches from an ordinary window into fullscreen.
    pytest.param("fullscreen", True, id="fullscreen"),
    # A borderless game fills its monitor without being maximized.
    pytest.param("borderless", True, id="borderless_exact_monitor"),
    # Explorer is maximized but still has its ordinary title bar.
    pytest.param("zoomed", False, id="maximized_captioned"),
    # An ordinary app occupies only part of its monitor.
    pytest.param("normal", False, id="ordinary_smaller_window"),
])
def test_real_window(window: tk.Tk, user32: ctypes.WinDLL, mode: str, expected: bool) -> None:
    hwnd = user32.GetAncestor(window.winfo_id(), GA_ROOT)
    info = _monitor_info(user32, user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST))
    try:
        if mode == "fullscreen":
            window.attributes("-fullscreen", True)
        elif mode == "borderless":
            window.withdraw()
            window.overrideredirect(True)
            window.deiconify()
            _place(window, user32, _rect(info.rcMonitor))
        elif mode == "zoomed":
            window.state("zoomed")
    except tk.TclError as error:
        pytest.skip(f"Tk/Windows refused {mode}: {error}")

    def ready(state: _WindowState) -> bool:
        caption = state.style & WS_CAPTION
        if mode == "fullscreen":
            # Tk may use either zoom state; fullscreen must remove the caption and cover the monitor.
            return caption == 0 and _contains(state.rect, state.monitor_rect)
        if mode == "borderless":
            return not state.zoomed and caption == 0 and state.rect == state.monitor_rect
        if mode == "zoomed":
            return state.zoomed and caption == WS_CAPTION and _contains(state.rect, state.work_rect)
        left, top, right, bottom = state.rect
        ml, mt, mr, mb = state.monitor_rect
        return not state.zoomed and caption == WS_CAPTION and ml < left < right < mr and mt < top < bottom < mb

    _assert_rule(window, user32, ready, f"the requested {mode} zoom/style/rectangle", expected)


@pytest.mark.xfail(strict=False, raises=AssertionError,
                   reason="Open review question: maximized-then-fullscreen keeps its title bar; INV-14 wants True")
def test_maximized_then_fullscreen(window: tk.Tk, user32: ctypes.WinDLL) -> None:
    # A game enters fullscreen after its ordinary window was already maximized.
    try:
        window.state("zoomed")
    except tk.TclError as error:
        pytest.skip(f"Tk/Windows refused maximization before fullscreen: {error}")
    _ready(window, user32,
           lambda s: s.zoomed and (s.style & WS_CAPTION) == WS_CAPTION and _contains(s.rect, s.work_rect),
           "a captioned maximized window before switching to fullscreen")
    try:
        window.attributes("-fullscreen", True)
    except tk.TclError as error:
        pytest.skip(f"Tk/Windows refused fullscreen after maximization: {error}")
    # Do not require caption removal or a particular zoom state: those are the open question.
    _assert_rule(window, user32, lambda s: _contains(s.rect, s.monitor_rect),
                 "monitor coverage after switching from maximized to fullscreen", True)


def test_fullscreen_on_secondary_monitor(window: tk.Tk, user32: ctypes.WinDLL) -> None:
    # A game runs fullscreen on a display other than the primary monitor.
    handles: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
                                      ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    @callback_type
    def collect(monitor: int, _dc: int, _rect: object, _data: int) -> bool:
        handles.append(monitor)
        return True

    user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                                         callback_type, wintypes.LPARAM]
    user32.EnumDisplayMonitors.restype = wintypes.BOOL
    if not user32.EnumDisplayMonitors(None, None, collect, 0):
        pytest.skip("Windows refused EnumDisplayMonitors")
    if len(handles) < 2:
        pytest.skip("Fullscreen on a secondary monitor requires at least two monitors")
    secondary = next((handle for handle in handles
                      if not _monitor_info(user32, handle).dwFlags & MONITORINFOF_PRIMARY), None)
    if secondary is None:
        pytest.skip("Windows did not enumerate a non-primary monitor")
    left, top, right, bottom = _rect(_monitor_info(user32, secondary).rcMonitor)
    _place(window, user32, (left + (right - left) // 4, top + (bottom - top) // 4,
                            left + 3 * (right - left) // 4, top + 3 * (bottom - top) // 4))
    _ready(window, user32,
           lambda s: s.monitor == secondary and not s.zoomed and (s.style & WS_CAPTION) == WS_CAPTION
           and not _contains(s.rect, s.monitor_rect),
           "placement on the non-primary monitor before entering fullscreen")
    try:
        window.attributes("-fullscreen", True)
    except tk.TclError as error:
        pytest.skip(f"Tk/Windows refused fullscreen on the secondary monitor: {error}")
    _assert_rule(window, user32,
                 lambda s: s.monitor == secondary and (s.style & WS_CAPTION) == 0
                 and _contains(s.rect, s.monitor_rect),
                 "fullscreen zoom/style/rectangle on the chosen non-primary monitor", True)


_DPI_CHILD = "WALLSWAP_DPI_AWARE_CHILD"  # set for the child run, so it doesn't start another child
_DPI_BOOTSTRAP = """
import ctypes, sys
ctypes.windll.shcore.SetProcessDpiAwareness(2)  # what the CustomTkinter root does to the running app
awareness = ctypes.c_int()
ctypes.windll.shcore.GetProcessDpiAwareness(None, ctypes.byref(awareness))
if awareness.value != 2:
    print(f"process DPI awareness is {awareness.value}, not per-monitor (2)")
    sys.exit(3)
import pytest
sys.exit(pytest.main([sys.argv[1], "-q", "-rsxX", "-p", "no:cacheprovider", "-k", "not dpi_aware"]))
"""


@pytest.mark.skipif(os.environ.get(_DPI_CHILD) == "1", reason="already inside the DPI-aware child run")
def test_checks_hold_in_a_dpi_aware_process() -> None:
    # The app is per-monitor DPI-aware once its Tk root exists, and INV-14 must hold there too. Awareness is set
    # once per process, so the checks above run again in a fresh process that sets it before any window exists.
    result = subprocess.run([sys.executable, "-c", _DPI_BOOTSTRAP, str(Path(__file__).resolve())],
                            cwd=Path(__file__).resolve().parent.parent, env={**os.environ, _DPI_CHILD: "1"},
                            capture_output=True, text=True, timeout=300)
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    if " passed" not in output:
        pytest.skip(f"every check was skipped in the DPI-aware process:\n{output}")
    print(output)
