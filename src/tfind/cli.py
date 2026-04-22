from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from tfind import __version__
from tfind.console_capture import write_console_snapshot
from tfind.searching import SearchOptions, search_lines, strip_ansi
from tfind.session import current_session_pointer, resolve_transcript, state_root
from tfind.ui import run_tui


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_search_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tfind",
        description="Search the current terminal transcript or, on Windows, fall back to a console snapshot.",
        epilog="Extra commands: `tfind doctor`, `tfind bootstrap powershell`, `tfind bootstrap bash`",
    )
    parser.add_argument("query", help="Text to search for.")
    parser.add_argument("--file", help="Search a specific transcript/log file.")
    parser.add_argument(
        "--follow",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Refresh while the log file grows.",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Print matches instead of opening the TUI.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def build_doctor_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tfind doctor", description="Show capture and path status.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def build_bootstrap_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tfind bootstrap",
        description="Print a shell integration script.",
    )
    parser.add_argument("shell", choices=["powershell", "bash"])
    parser.add_argument(
        "--path-only",
        action="store_true",
        help="Print the script path instead of the script contents.",
    )
    return parser


def _read_lines(path: Path) -> list[str]:
    raw_text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    return strip_ansi(raw_text).splitlines()


def run_plain_search(query: str, source: Path) -> int:
    lines = _read_lines(source)
    matches = search_lines(lines=lines, query=query, options=SearchOptions())
    if not matches:
        print(f'No matches for "{query}" in {source}')
        return 1

    print(f'{len(matches)} matches for "{query}" in {source}')
    for match in matches:
        line_text = lines[match.line_index] if match.line_index < len(lines) else ""
        preview = line_text.strip()
        print(f"{match.ordinal + 1:>3}. line {match.line_index + 1}, col {match.start_col + 1}: {preview}")
    return 0


def run_doctor() -> int:
    pointer = current_session_pointer()
    try:
        transcript = resolve_transcript()
        transcript_error = None
    except FileNotFoundError as exc:
        transcript = None
        transcript_error = str(exc)

    print(f"tfind version: {__version__}")
    print(f"repo root: {repo_root()}")
    print(f"state root: {state_root()}")
    print(f"current pointer: {pointer}")
    print(f"pointer exists: {'yes' if pointer.exists() else 'no'}")

    if transcript is not None:
        print(f"resolved transcript: {transcript}")
        print(f"transcript exists: {'yes' if transcript.exists() else 'no'}")
    else:
        print(f"resolved transcript: {transcript_error}")

    print(f"PowerShell integration: {repo_root() / 'integrations' / 'powershell' / 'tfind-profile.ps1'}")
    print(f"Bash integration: {repo_root() / 'integrations' / 'bash' / 'tfind.bash'}")
    print(f"Windows wrapper: {repo_root() / 'bin' / 'tfind.cmd'}")
    print(f"POSIX wrapper: {repo_root() / 'bin' / 'tfind'}")
    return 0


def run_bootstrap(shell: str, path_only: bool) -> int:
    if shell == "powershell":
        script_path = repo_root() / "integrations" / "powershell" / "tfind-profile.ps1"
    else:
        script_path = repo_root() / "integrations" / "bash" / "tfind.bash"

    if path_only:
        print(script_path)
        return 0

    print(script_path.read_text(encoding="utf-8"))
    return 0


def _resolve_source_with_fallback(explicit_file: str | None) -> tuple[Path | None, bool, str | None]:
    try:
        return resolve_transcript(explicit_file), True, None
    except FileNotFoundError as exc:
        if explicit_file:
            return None, False, str(exc)

        snapshot = write_console_snapshot() if os.name == "nt" else None
        if snapshot is not None:
            return (
                snapshot,
                False,
                "No active transcript was found, so tfind is using a snapshot of the current Windows console buffer.",
            )
        return None, False, str(exc)


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list:
        build_search_parser().print_help(sys.stderr)
        return 2

    command = args_list[0]
    if command == "doctor":
        build_doctor_parser().parse_args(args_list[1:])
        return run_doctor()

    if command == "bootstrap":
        parsed = build_bootstrap_parser().parse_args(args_list[1:])
        return run_bootstrap(shell=parsed.shell, path_only=parsed.path_only)

    parsed = build_search_parser().parse_args(args_list)
    transcript, follow, source_note = _resolve_source_with_fallback(parsed.file)
    if transcript is None:
        print(source_note, file=sys.stderr)
        if os.name == "nt":
            print(
                'PowerShell tip: add `. "D:\\Terminal-find\\integrations\\powershell\\tfind-profile.ps1"` to $PROFILE, then open a new shell.',
                file=sys.stderr,
            )
        return 2

    if parsed.file and not transcript.exists():
        print(f"Transcript file does not exist yet: {transcript}", file=sys.stderr)
        return 2

    if parsed.plain:
        if source_note:
            print(source_note, file=sys.stderr)
        return run_plain_search(query=parsed.query, source=transcript)

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("Interactive mode requires a real terminal. Use --plain for non-interactive output.", file=sys.stderr)
        return 2

    if source_note:
        print(source_note, file=sys.stderr)
    run_tui(source=transcript, query=parsed.query, follow=(parsed.follow and follow))
    return 0
