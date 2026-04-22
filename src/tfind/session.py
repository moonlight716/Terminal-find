from __future__ import annotations

import os
from pathlib import Path
import tempfile


def _clean_path_text(value: str) -> str:
    return value.lstrip("\ufeff").strip()


def state_root() -> Path:
    override = os.environ.get("TFIND_STATE_ROOT")
    candidates: list[Path] = []
    if override:
        candidates.append(Path(override).expanduser())

    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            candidates.append(Path(base) / "tfind")
    else:
        base = os.environ.get("XDG_STATE_HOME")
        if base:
            candidates.append(Path(base) / "tfind")
        candidates.append(Path.home() / ".local" / "state" / "tfind")

    candidates.append(Path.cwd() / ".tfind-state")
    candidates.append(Path(tempfile.gettempdir()) / "tfind")

    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue

    return candidates[0]


def sessions_dir() -> Path:
    return state_root() / "sessions"


def current_session_pointer() -> Path:
    return state_root() / "current-session.txt"


def resolve_transcript(explicit_file: str | None = None) -> Path:
    if explicit_file:
        return Path(_clean_path_text(explicit_file)).expanduser()

    env_path = os.environ.get("TFIND_CURRENT_LOG")
    if env_path:
        return Path(_clean_path_text(env_path)).expanduser()

    pointer = current_session_pointer()
    if pointer.exists():
        pointed_path = _clean_path_text(pointer.read_text(encoding="utf-8-sig", errors="replace"))
        if pointed_path:
            return Path(pointed_path).expanduser()

    session_logs = sorted(
        sessions_dir().glob("*.log"),
        key=lambda candidate: candidate.stat().st_mtime,
        reverse=True,
    )
    if session_logs:
        return session_logs[0]

    raise FileNotFoundError(
        "No active terminal transcript was found. Enable capture first, or pass --file <log>."
    )
