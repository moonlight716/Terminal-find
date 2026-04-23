from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import sys
import time

from tfind.searching import Match, SearchOptions, prepare_transcript_lines, search_lines

if os.name == "nt":
    import ctypes
    import msvcrt
else:
    import select
    import termios
    import tty

LINE_NUMBER_WIDTH = 7
REFRESH_INTERVAL = 0.5
RIGHT_MARGIN = 1
MOUSE_SCROLL_STEP = 3

ESC = "\x1b"
RESET = f"{ESC}[0m"
ALT_SCREEN_ON = f"{ESC}[?1049h"
ALT_SCREEN_OFF = f"{ESC}[?1049l"
CURSOR_HIDE = f"{ESC}[?25l"
CURSOR_SHOW = f"{ESC}[?25h"
ALT_SCROLL_ON = f"{ESC}[?1007h"
ALT_SCROLL_OFF = f"{ESC}[?1007l"
CLEAR_AND_HOME = f"{ESC}[2J{ESC}[H"
TERM_NEWLINE = "\r\n"
HEADER_STYLE = f"{ESC}[48;5;236m{ESC}[38;5;255m{ESC}[1m"
HEADER_META_STYLE = f"{ESC}[48;5;236m{ESC}[38;5;250m"
LINE_NUMBER_STYLE = f"{ESC}[38;5;244m"
ACTIVE_LINE_NUMBER_STYLE = f"{ESC}[48;5;238m{ESC}[38;5;255m{ESC}[1m"
HINT_STYLE = f"{ESC}[38;5;109m"
MATCH_STYLE = f"{ESC}[48;5;130m{ESC}[38;5;255m"
CURRENT_MATCH_STYLE = f"{ESC}[48;5;214m{ESC}[38;5;16m{ESC}[1m"
FOOTER_STYLE = f"{ESC}[48;5;234m{ESC}[38;5;252m"
FOOTER_ON_STYLE = f"{ESC}[48;5;234m{ESC}[38;5;82m{ESC}[1m"
FOOTER_OFF_STYLE = f"{ESC}[48;5;234m{ESC}[38;5;245m"
FOOTER_MATCH_STYLE = f"{ESC}[48;5;234m{ESC}[38;5;255m{ESC}[1m"
FOOTER_WARN_STYLE = f"{ESC}[48;5;234m{ESC}[38;5;217m{ESC}[1m"


def _styled(style: str, text: str) -> str:
    if not text:
        return ""
    return f"{style}{text}{RESET}"


def _truncate(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text.ljust(width)
    if width == 1:
        return text[:1]
    if width == 2:
        return f"{text[:1]}."
    if width == 3:
        return "..."
    return f"{text[: width - 3]}..."


def _ellipsize_end(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 3:
        return "." * width
    return f"{text[: width - 3]}..."


def _ellipsize_middle(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width <= 3:
        return "." * width

    left = max(1, (width - 3) // 2)
    right = max(1, width - 3 - left)
    return f"{text[:left]}...{text[-right:]}"


def _finalize_line(rendered_parts: list[str], plain_length: int, width: int, fill_style: str) -> str:
    parts = list(rendered_parts)
    if plain_length < width:
        padding = " " * (width - plain_length)
        parts.append(_styled(fill_style, padding) if fill_style else padding)
    return "".join(parts)


def _render_single_line(segments: list[tuple[str, str]], width: int, fill_style: str = "") -> str:
    rendered_parts: list[str] = []
    plain_length = 0

    for style, text in segments:
        if not text:
            continue

        remaining = width - plain_length
        if remaining <= 0:
            break

        chunk = text[:remaining]
        rendered_parts.append(_styled(style, chunk) if style else chunk)
        plain_length += len(chunk)

    return _finalize_line(rendered_parts, plain_length, width, fill_style)


def _wrap_segments(segments: list[tuple[str, str]], width: int, fill_style: str = "") -> list[str]:
    if width <= 0:
        return [""]

    lines: list[str] = []
    rendered_parts: list[str] = []
    plain_length = 0

    def flush_line() -> None:
        nonlocal rendered_parts, plain_length
        lines.append(_finalize_line(rendered_parts, plain_length, width, fill_style))
        rendered_parts = []
        plain_length = 0

    for style, text in segments:
        remainder = text
        while remainder:
            available = width - plain_length
            if available <= 0:
                flush_line()
                available = width

            chunk = remainder[:available]
            rendered_parts.append(_styled(style, chunk) if style else chunk)
            plain_length += len(chunk)
            remainder = remainder[available:]

            if plain_length >= width:
                flush_line()

    if rendered_parts or not lines:
        flush_line()

    return lines


@dataclass
class TranscriptState:
    source: Path
    query: str
    follow: bool = True
    options: SearchOptions = field(default_factory=SearchOptions)
    lines: list[str] = field(default_factory=list)
    matches: list[Match] = field(default_factory=list)
    matches_by_line: dict[int, list[Match]] = field(default_factory=dict)
    current_match_index: int | None = None
    top_row: int = 0
    error: str | None = None
    _signature: tuple[int, int] | None = None

    def refresh(self, force: bool = False) -> bool:
        try:
            stat = self.source.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
        except FileNotFoundError:
            signature = None

        if not force and signature == self._signature:
            return False

        self._signature = signature

        if signature is None:
            self.lines = []
            self.matches = []
            self.matches_by_line = {}
            self.current_match_index = None
            self.error = f"Waiting for transcript: {self.source}"
            return True

        raw_text = self.source.read_text(encoding="utf-8-sig", errors="replace")
        self.lines = prepare_transcript_lines(raw_text, source=self.source)
        self.error = None
        self._recompute_matches()
        return True

    def _recompute_matches(self) -> None:
        previous_ordinal = self.current_match_index
        self.matches = search_lines(self.lines, self.query, self.options)
        self.matches_by_line = {}
        for match in self.matches:
            self.matches_by_line.setdefault(match.line_index, []).append(match)

        if not self.matches:
            self.current_match_index = None
        elif previous_ordinal is None:
            self.current_match_index = 0
        else:
            self.current_match_index = min(previous_ordinal, len(self.matches) - 1)

    def toggle(self, index: int) -> None:
        self.options = self.options.toggled(index)
        self._recompute_matches()

    def current_match(self) -> Match | None:
        if self.current_match_index is None:
            return None
        return self.matches[self.current_match_index]

    def move_next(self) -> None:
        if not self.matches:
            return
        if self.current_match_index is None:
            self.current_match_index = 0
            return
        self.current_match_index = (self.current_match_index + 1) % len(self.matches)

    def move_previous(self) -> None:
        if not self.matches:
            return
        if self.current_match_index is None:
            self.current_match_index = 0
            return
        self.current_match_index = (self.current_match_index - 1) % len(self.matches)

    def move_first(self) -> None:
        if self.matches:
            self.current_match_index = 0

    def move_last(self) -> None:
        if self.matches:
            self.current_match_index = len(self.matches) - 1

    def option_marker(self, enabled: bool) -> str:
        return "[*]" if enabled else "[ ]"

    def center_current(self, body_height: int, width: int) -> None:
        current_row = self.current_visual_row_index(width)
        if current_row is None:
            return

        self.top_row = max(0, current_row - max(2, body_height // 2))

    def _available_width(self, width: int) -> int:
        return max(1, width - LINE_NUMBER_WIDTH)

    def _line_chunk_ranges(self, line: str, available_width: int) -> list[tuple[int, int]]:
        if not line:
            return [(0, 0)]
        return [
            (start, min(len(line), start + available_width))
            for start in range(0, len(line), available_width)
        ]

    def visual_rows(self, width: int) -> list[tuple[int, int, int]]:
        available_width = self._available_width(width)
        rows: list[tuple[int, int, int]] = []
        for line_index, line in enumerate(self.lines):
            for start_col, end_col in self._line_chunk_ranges(line, available_width):
                rows.append((line_index, start_col, end_col))
        return rows

    def current_visual_row_index(self, width: int) -> int | None:
        current = self.current_match()
        if current is None:
            return None

        available_width = self._available_width(width)
        row_index = 0
        for line_index, line in enumerate(self.lines):
            chunk_ranges = self._line_chunk_ranges(line, available_width)
            if line_index == current.line_index:
                for start_col, end_col in chunk_ranges:
                    if current.start_col < end_col or (start_col == end_col == 0):
                        return row_index
                    row_index += 1
                return row_index
            row_index += len(chunk_ranges)

        return None

    def clamp_view(self, body_height: int, width: int) -> None:
        max_top = max(0, len(self.visual_rows(width)) - max(1, body_height))
        self.top_row = min(max(0, self.top_row), max_top)

    def build_header_lines(self, width: int) -> list[str]:
        title_text = " tfind "
        follow_text = f"follow:{'on' if self.follow else 'off'} "
        query_text = f'query="{self.query}" '
        source_prefix = "source="
        source_text = str(self.source)

        available = max(0, width - len(title_text) - len(follow_text))
        if available <= 0:
            return [_render_single_line([(HEADER_STYLE, title_text), (HEADER_META_STYLE, follow_text)], width, fill_style=HEADER_STYLE)]

        preferred_query = len(query_text)
        min_query = min(preferred_query, max(12, available // 3))
        min_source_value = 12

        query_budget = min(preferred_query, max(min_query, available - len(source_prefix) - min_source_value))
        query_budget = min(query_budget, available)
        source_budget = max(0, available - query_budget)

        if 0 < source_budget < len(source_prefix) + min_source_value + 1:
            shrink = len(source_prefix) + min_source_value + 1 - source_budget
            query_budget = max(min(12, preferred_query), query_budget - shrink)
            source_budget = max(0, available - query_budget)

        rendered_query = _ellipsize_end(query_text, query_budget)
        source_value_budget = max(0, source_budget - len(source_prefix))
        rendered_source = ""
        if source_value_budget > 0:
            rendered_source = f"{source_prefix}{_ellipsize_middle(source_text, source_value_budget)} "

        segments = [
            (HEADER_STYLE, title_text),
            (HEADER_META_STYLE, rendered_query),
            (HEADER_META_STYLE, rendered_source),
            (HEADER_META_STYLE, follow_text),
        ]
        return [_render_single_line(segments, width, fill_style=HEADER_STYLE)]

    def build_footer_lines(self, width: int) -> list[str]:
        option_style = FOOTER_ON_STYLE if self.options.highlight_all else FOOTER_OFF_STYLE
        case_style = FOOTER_ON_STYLE if self.options.case_sensitive else FOOTER_OFF_STYLE
        accent_style = FOOTER_ON_STYLE if self.options.match_accents else FOOTER_OFF_STYLE
        whole_style = FOOTER_ON_STYLE if self.options.whole_word else FOOTER_OFF_STYLE

        if self.matches and self.current_match_index is not None:
            match_label = f"Match {self.current_match_index + 1} of {len(self.matches)}"
            match_style = FOOTER_MATCH_STYLE
        else:
            match_label = "No matches"
            match_style = FOOTER_WARN_STYLE

        segments = [
            (option_style, f" {self.option_marker(self.options.highlight_all)} (1) Highlight all "),
            (case_style, f" {self.option_marker(self.options.case_sensitive)} (2) Case sensitive "),
            (accent_style, f" {self.option_marker(self.options.match_accents)} (3) Match accents "),
            (whole_style, f" {self.option_marker(self.options.whole_word)} (4) Whole word "),
            (match_style, f"  {match_label}  "),
            (FOOTER_STYLE, " r reload  q quit "),
        ]
        return _wrap_segments(segments, width, fill_style=FOOTER_STYLE)

    def _build_line_body(self, line_index: int, start_col: int, end_col: int, width: int) -> str:
        current = self.current_match()
        line = self.lines[line_index]
        visible = line[start_col:end_col]
        rendered: list[str] = []
        cursor = 0

        visible_ordinals = None
        if not self.options.highlight_all and current is not None:
            visible_ordinals = {current.ordinal}

        for match in self.matches_by_line.get(line_index, []):
            if visible_ordinals is not None and match.ordinal not in visible_ordinals:
                continue

            overlap_start = max(match.start_col, start_col)
            overlap_end = min(match.end_col, end_col)
            if overlap_start >= overlap_end:
                continue

            relative_start = overlap_start - start_col
            relative_end = overlap_end - start_col

            rendered.append(visible[cursor:relative_start])
            style = CURRENT_MATCH_STYLE if current and match.ordinal == current.ordinal else MATCH_STYLE
            rendered.append(_styled(style, visible[relative_start:relative_end]))
            cursor = relative_end

        rendered.append(visible[cursor:])
        plain_length = len(visible)
        if plain_length < width:
            rendered.append(" " * (width - plain_length))
        return "".join(rendered)

    def build_body_lines(self, body_height: int, width: int) -> list[str]:
        self.clamp_view(body_height, width)
        rows: list[str] = []
        if self.error:
            hints = [
                self.error,
                "Enable shell capture, run a few commands, and search again.",
            ]
            for index in range(body_height):
                text = hints[index] if index < len(hints) else ""
                rows.append(_styled(HINT_STYLE, _truncate(text, width)))
        elif not self.lines:
            rows.append(_styled(HINT_STYLE, _truncate("The transcript is empty.", width)))
            rows.extend([" " * width for _ in range(max(0, body_height - 1))])
        else:
            current = self.current_match()
            visible_rows = self.visual_rows(width)
            for row_index in range(body_height):
                visual_row_index = self.top_row + row_index
                if visual_row_index >= len(visible_rows):
                    rows.append(" " * width)
                    continue

                line_index, start_col, end_col = visible_rows[visual_row_index]
                is_current_line = current is not None and current.line_index == line_index
                prefix_style = ACTIVE_LINE_NUMBER_STYLE if is_current_line else LINE_NUMBER_STYLE
                prefix_text = f"{line_index + 1:>6} " if start_col == 0 else "       "
                prefix = _styled(prefix_style, prefix_text)
                body_width = self._available_width(width)
                rows.append(prefix + self._build_line_body(line_index, start_col, end_col, body_width))

        return rows[:body_height]


class _TerminalSession(AbstractContextManager["_TerminalSession"]):
    def __init__(self) -> None:
        self._stdout = sys.stdout
        self._stdin = sys.stdin
        self._stdin_fd: int | None = None
        self._saved_termios: list[int] | None = None

    def __enter__(self) -> "_TerminalSession":
        if os.name == "nt":
            _enable_windows_virtual_terminal()
        else:
            self._stdin_fd = self._stdin.fileno()
            self._saved_termios = termios.tcgetattr(self._stdin_fd)
            tty.setraw(self._stdin_fd)

        alt_scroll_sequence = "" if os.name == "nt" else ALT_SCROLL_ON
        self._stdout.write(f"{ALT_SCREEN_ON}{CURSOR_HIDE}{alt_scroll_sequence}")
        self._stdout.flush()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._stdin_fd is not None and self._saved_termios is not None:
            termios.tcsetattr(self._stdin_fd, termios.TCSADRAIN, self._saved_termios)
        alt_scroll_sequence = "" if os.name == "nt" else ALT_SCROLL_OFF
        self._stdout.write(f"{RESET}{alt_scroll_sequence}{CURSOR_SHOW}{ALT_SCREEN_OFF}")
        self._stdout.flush()
        return None

    def render(self, frame: str) -> None:
        self._stdout.write(frame)
        self._stdout.flush()

    def read_key(self, timeout: float | None) -> str | None:
        if os.name == "nt":
            return _read_windows_key(timeout)
        return _read_posix_key(timeout)


def _enable_windows_virtual_terminal() -> None:
    kernel32 = ctypes.windll.kernel32
    output_handle = kernel32.GetStdHandle(-11)
    mode = ctypes.c_uint()
    if kernel32.GetConsoleMode(output_handle, ctypes.byref(mode)):
        kernel32.SetConsoleMode(output_handle, mode.value | 0x0004)


def _read_windows_key(timeout: float | None) -> str | None:
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        if msvcrt.kbhit():
            first = msvcrt.getwch()
            if first in ("\x00", "\xe0"):
                second = msvcrt.getwch()
                mapping = {
                    "H": "UP",
                    "P": "DOWN",
                    "K": "LEFT",
                    "M": "RIGHT",
                    "I": "PGUP",
                    "Q": "PGDN",
                    "G": "HOME",
                    "O": "END",
                }
                return mapping.get(second)
            if first == "\r":
                return "ENTER"
            if first == "\x1b":
                return "ESC"
            if first == "\x03":
                return "CTRL_C"
            return first

        if deadline is not None and time.monotonic() >= deadline:
            return None
        time.sleep(0.03)


def _read_posix_key(timeout: float | None) -> str | None:
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if not ready:
        return None

    first = os.read(sys.stdin.fileno(), 1).decode("utf-8", errors="ignore")
    if first == "\x03":
        return "CTRL_C"
    if first in ("\r", "\n"):
        return "ENTER"
    if first != "\x1b":
        return first

    sequence = ""
    while True:
        ready, _, _ = select.select([sys.stdin], [], [], 0.01)
        if not ready:
            break
        sequence += os.read(sys.stdin.fileno(), 1).decode("utf-8", errors="ignore")
        if sequence.endswith(("A", "B", "C", "D", "F", "H", "~", "M", "m")):
            break

    return _parse_posix_escape_sequence(sequence)


def _parse_posix_escape_sequence(sequence: str) -> str:
    mouse_key = _parse_sgr_mouse(sequence)
    if mouse_key is not None:
        return mouse_key

    mapping = {
        "[A": "UP",
        "[B": "DOWN",
        "[C": "RIGHT",
        "[D": "LEFT",
        "[H": "HOME",
        "[F": "END",
        "[5~": "PGUP",
        "[6~": "PGDN",
        "OH": "HOME",
        "OF": "END",
    }
    return mapping.get(sequence, "ESC")


def _parse_sgr_mouse(sequence: str) -> str | None:
    if not sequence.startswith("[<") or not sequence.endswith(("M", "m")):
        return None

    payload = sequence[2:-1]
    parts = payload.split(";")
    if len(parts) != 3:
        return None

    try:
        button_code = int(parts[0])
    except ValueError:
        return None

    normalized_button = button_code & ~0b11100
    if normalized_button == 64:
        return "SCROLL_UP"
    if normalized_button == 65:
        return "SCROLL_DOWN"
    return "MOUSE"


def _terminal_size() -> os.terminal_size:
    for stream in (sys.stdout, sys.stdin):
        try:
            return os.get_terminal_size(stream.fileno())
        except (OSError, ValueError):
            continue
    return shutil.get_terminal_size(fallback=(120, 32))


def _frame_dimensions() -> tuple[int, int]:
    size = _terminal_size()
    width = max(1, size.columns - RIGHT_MARGIN)
    height = max(1, size.lines)
    return width, height


def _layout_sections(state: TranscriptState, width: int, height: int) -> tuple[list[str], list[str], int]:
    header_lines = state.build_header_lines(width)
    footer_lines = state.build_footer_lines(width)

    max_meta_lines = max(2, height - 1)
    while len(header_lines) + len(footer_lines) > max_meta_lines:
        if len(header_lines) > 1 and len(header_lines) >= len(footer_lines):
            header_lines = header_lines[:-1]
            continue
        if len(footer_lines) > 1:
            footer_lines = footer_lines[:-1]
            continue
        break

    body_height = max(1, height - len(header_lines) - len(footer_lines))
    return header_lines, footer_lines, body_height


def _build_frame(state: TranscriptState) -> str:
    width, height = _frame_dimensions()
    header_lines, footer_lines, body_height = _layout_sections(state, width, height)

    state.clamp_view(body_height, width)
    body_rows = state.build_body_lines(body_height=body_height, width=width)

    return f"{CLEAR_AND_HOME}" + TERM_NEWLINE.join([*header_lines, *body_rows, *footer_lines])


def _handle_key(key: str, state: TranscriptState) -> bool:
    width, height = _frame_dimensions()
    _, _, body_height = _layout_sections(state, width, height)

    if key in {"q", "Q", "ESC", "CTRL_C"}:
        return False
    if key in {"n", "N", "j", "J", "ENTER", "DOWN", "RIGHT"}:
        state.move_next()
        state.center_current(body_height, width)
        return True
    if key in {"p", "P", "k", "K", "UP", "LEFT"}:
        state.move_previous()
        state.center_current(body_height, width)
        return True
    if key == "HOME":
        state.move_first()
        state.center_current(body_height, width)
        return True
    if key == "END":
        state.move_last()
        state.center_current(body_height, width)
        return True
    if key == "PGUP":
        state.top_row = max(0, state.top_row - max(1, body_height - 2))
        return True
    if key == "PGDN":
        visible_row_count = len(state.visual_rows(width))
        state.top_row = min(max(0, visible_row_count - body_height), state.top_row + max(1, body_height - 2))
        return True
    if key == "SCROLL_UP":
        if state.matches:
            state.move_previous()
            state.center_current(body_height, width)
            return True
        state.top_row = max(0, state.top_row - MOUSE_SCROLL_STEP)
        return True
    if key == "SCROLL_DOWN":
        if state.matches:
            state.move_next()
            state.center_current(body_height, width)
            return True
        visible_row_count = len(state.visual_rows(width))
        state.top_row = min(max(0, visible_row_count - body_height), state.top_row + MOUSE_SCROLL_STEP)
        return True
    if key == "MOUSE":
        return True
    if key in {"1", "2", "3", "4"}:
        state.toggle(int(key))
        state.center_current(body_height, width)
        return True
    if key in {"r", "R"}:
        state.refresh(force=True)
        state.center_current(body_height, width)
        return True
    return True


def run_tui(source: Path, query: str, follow: bool = True) -> None:
    state = TranscriptState(source=source, query=query, follow=follow)
    state.refresh(force=True)
    width, height = _frame_dimensions()
    _, _, body_height = _layout_sections(state, width, height)
    state.center_current(body_height=body_height, width=width)

    try:
        with _TerminalSession() as session:
            while True:
                session.render(_build_frame(state))
                key = session.read_key(REFRESH_INTERVAL if follow else None)

                changed = False
                if follow:
                    changed = state.refresh()
                    if changed and state.current_match() is None and state.matches:
                        width, height = _frame_dimensions()
                        _, _, body_height = _layout_sections(state, width, height)
                        state.center_current(body_height=body_height, width=width)

                if key is None:
                    continue

                keep_running = _handle_key(key, state)
                if not keep_running:
                    break
    except KeyboardInterrupt:
        return
