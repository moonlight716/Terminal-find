from __future__ import annotations

import os
from pathlib import Path
import tempfile
import time

from tfind.session import state_root

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    class COORD(ctypes.Structure):
        _fields_ = [("X", wintypes.SHORT), ("Y", wintypes.SHORT)]

    class SMALL_RECT(ctypes.Structure):
        _fields_ = [
            ("Left", wintypes.SHORT),
            ("Top", wintypes.SHORT),
            ("Right", wintypes.SHORT),
            ("Bottom", wintypes.SHORT),
        ]

    class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
        _fields_ = [
            ("dwSize", COORD),
            ("dwCursorPosition", COORD),
            ("wAttributes", wintypes.WORD),
            ("srWindow", SMALL_RECT),
            ("dwMaximumWindowSize", COORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    STD_OUTPUT_HANDLE = -11


def capture_windows_console_text() -> str | None:
    if os.name != "nt":
        return None

    handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    if handle in (0, -1):
        return None

    info = CONSOLE_SCREEN_BUFFER_INFO()
    if not kernel32.GetConsoleScreenBufferInfo(handle, ctypes.byref(info)):
        return None

    width = int(info.dwSize.X)
    height = int(info.dwSize.Y)
    if width <= 0 or height <= 0:
        return None

    rows: list[str] = []
    chars_read = wintypes.DWORD()

    for row in range(height):
        buffer = ctypes.create_unicode_buffer(width)
        origin = COORD(0, row)
        ok = kernel32.ReadConsoleOutputCharacterW(
            handle,
            buffer,
            width,
            origin,
            ctypes.byref(chars_read),
        )
        if not ok:
            return None
        rows.append(buffer.value.rstrip())

    while rows and not rows[-1]:
        rows.pop()

    return "\n".join(rows)


def read_powershell_history_snapshot() -> str | None:
    history_path = os.environ.get("TFIND_POWERSHELL_HISTORY_SNAPSHOT")
    if not history_path:
        return None
    path = Path(history_path).expanduser()
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def write_console_snapshot() -> Path | None:
    console_text = capture_windows_console_text()
    history_text = read_powershell_history_snapshot()
    if not console_text and not history_text:
        return None

    sections: list[str] = []
    if history_text:
        sections.append("=== PowerShell Session History ===")
        sections.append(history_text.rstrip())
    if console_text:
        sections.append("=== Windows Console Snapshot ===")
        sections.append(console_text.rstrip())

    text = "\n\n".join(section for section in sections if section).rstrip() + "\n"

    file_name = f"console-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}.log"
    candidates = [
        state_root() / "snapshots",
        Path.cwd() / ".tfind-state" / "snapshots",
        Path(tempfile.gettempdir()) / "tfind" / "snapshots",
    ]

    for snapshot_dir in candidates:
        try:
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            path = snapshot_dir / file_name
            path.write_text(text, encoding="utf-8")
            return path
        except OSError:
            continue

    return None
