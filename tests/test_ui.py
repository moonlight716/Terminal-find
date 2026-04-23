import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tfind.searching import strip_ansi
from tfind.ui import (
    TERM_NEWLINE,
    TranscriptState,
    _PENDING_POSIX_KEYS,
    _build_frame,
    _frame_dimensions,
    _handle_key,
    _parse_posix_escape_sequence,
    _read_posix_key,
)


class UiLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        _PENDING_POSIX_KEYS.clear()

    def test_header_stays_single_line_and_truncates_source_in_middle(self) -> None:
        state = TranscriptState(
            source=Path("C:/Users/example/AppData/Local/tfind/sessions/powershell-long-session-name.log"),
            query="conda",
        )
        lines = state.build_header_lines(80)
        plain = strip_ansi(lines[0])

        self.assertEqual(len(lines), 1)
        self.assertIn('query="conda"', plain)
        self.assertIn("follow:on", plain)
        self.assertIn("source=", plain)
        self.assertIn(".log", plain)
        self.assertIn("...", plain)

    def test_header_shows_full_source_when_width_allows(self) -> None:
        state = TranscriptState(
            source=Path("/home/example/.local/state/tfind/sessions/bash-20260423-123733-21915.log"),
            query="version",
        )
        lines = state.build_header_lines(160)
        plain = strip_ansi(lines[0])

        self.assertEqual(len(lines), 1)
        self.assertIn(f"source={state.source}", plain)
        self.assertIn('query="version"', plain)
        self.assertIn("follow:on", plain)

    def test_header_shows_full_windows_source_when_width_allows(self) -> None:
        state = TranscriptState(
            source=Path(r"C:/Users/25237/AppData/Local/tfind/sessions/powershell-20260423-005432-8068.log"),
            query="version",
        )
        lines = state.build_header_lines(120)
        plain = strip_ansi(lines[0])

        self.assertEqual(len(lines), 1)
        self.assertIn(f"source={state.source}", plain)
        self.assertIn('query="version"', plain)
        self.assertIn("follow:on", plain)

    def test_footer_wraps_without_next_prev_hint(self) -> None:
        sample = Path(__file__).resolve().parents[1] / "examples" / "sample-terminal.log"
        state = TranscriptState(source=sample, query="windowsContent")
        state.refresh(force=True)
        lines = state.build_footer_lines(45)
        plain = "\n".join(strip_ansi(line) for line in lines)

        self.assertGreater(len(lines), 1)
        self.assertIn("Match 1 of 4", plain)
        self.assertIn("r reload  q quit", plain)
        self.assertNotIn("n/p next-prev", plain)

    def test_body_wraps_long_lines_without_horizontal_cropping(self) -> None:
        state = TranscriptState(
            source=Path("C:/Users/example/AppData/Local/tfind/sessions/powershell.log"),
            query="version",
        )
        state.lines = [
            "usage: tfind [-h] [--file FILE] [--follow | --no-follow] [--plain] [--version]",
            "Search the current terminal transcript or, on Windows, fall back to a console snapshot.",
        ]
        state._recompute_matches()
        state.center_current(body_height=6, width=40)

        body_lines = state.build_body_lines(body_height=6, width=40)
        plain = "\n".join(strip_ansi(line) for line in body_lines)

        self.assertIn("usage: tfind [-h]", plain)
        self.assertIn("[--version]", plain)
        self.assertIn("Search the current terminal", plain)
        self.assertIn("console snapshot.", plain)

    def test_frame_leaves_right_margin_to_avoid_terminal_auto_wrap(self) -> None:
        sample = Path(__file__).resolve().parents[1] / "examples" / "sample-terminal.log"
        state = TranscriptState(source=sample, query="windowsContent")
        state.refresh(force=True)

        with patch("tfind.ui.shutil.get_terminal_size", return_value=os.terminal_size((80, 24))):
            frame = _build_frame(state)

        plain_lines = strip_ansi(frame).splitlines()[1:]
        self.assertTrue(plain_lines)
        self.assertTrue(all(len(line) <= 79 for line in plain_lines))
        self.assertIn(TERM_NEWLINE, frame)
        self.assertNotIn("\n", frame.replace(TERM_NEWLINE, ""))

    def test_parse_posix_escape_sequence_maps_mouse_wheel(self) -> None:
        self.assertEqual(_parse_posix_escape_sequence("[<64;12;8M"), "SCROLL_UP")
        self.assertEqual(_parse_posix_escape_sequence("[<65;12;8M"), "SCROLL_DOWN")
        self.assertEqual(_parse_posix_escape_sequence("[<0;12;8M"), "MOUSE")

    def test_read_posix_key_reads_down_arrow_sequence(self) -> None:
        select_results = [([0], [], []), ([0], [], []), ([0], [], []), ([], [], [])]
        read_results = [b"\x1b", b"[", b"B"]

        with (
            patch("tfind.ui.select.select", side_effect=select_results),
            patch("tfind.ui.os.read", side_effect=read_results),
            patch("tfind.ui.sys.stdin.fileno", return_value=0),
        ):
            self.assertEqual(_read_posix_key(timeout=0.2), "DOWN")

    def test_read_posix_key_coalesces_immediate_repeated_down_sequences(self) -> None:
        select_results = [
            ([0], [], []),
            ([0], [], []),
            ([0], [], []),
            ([0], [], []),
            ([0], [], []),
            ([0], [], []),
            ([], [], []),
        ]
        read_results = [b"\x1b", b"[", b"B", b"\x1b", b"[", b"B"]

        with (
            patch("tfind.ui.select.select", side_effect=select_results),
            patch("tfind.ui.os.read", side_effect=read_results),
            patch("tfind.ui.sys.stdin.fileno", return_value=0),
        ):
            self.assertEqual(_read_posix_key(timeout=0.2), "DOWN")

    def test_read_posix_key_preserves_next_non_navigation_key_after_coalescing(self) -> None:
        select_results = [
            ([0], [], []),
            ([0], [], []),
            ([0], [], []),
            ([0], [], []),
        ]
        read_results = [b"\x1b", b"[", b"B", b"q"]

        with (
            patch("tfind.ui.select.select", side_effect=select_results),
            patch("tfind.ui.os.read", side_effect=read_results),
            patch("tfind.ui.sys.stdin.fileno", return_value=0),
        ):
            self.assertEqual(_read_posix_key(timeout=0.2), "DOWN")
            self.assertEqual(_read_posix_key(timeout=0.2), "q")

    def test_frame_dimensions_ignore_stale_columns_environment(self) -> None:
        with (
            patch.dict(os.environ, {"COLUMNS": "220", "LINES": "60"}, clear=False),
            patch("tfind.ui.os.get_terminal_size", return_value=os.terminal_size((80, 24))),
        ):
            self.assertEqual(_frame_dimensions(), (79, 24))

    def test_mouse_wheel_moves_current_match_when_matches_exist(self) -> None:
        state = TranscriptState(source=Path("session.log"), query="version")
        state.lines = ["version a", "version b", "version c"]
        state._recompute_matches()

        keep_running = _handle_key("SCROLL_DOWN", state)
        self.assertTrue(keep_running)
        self.assertEqual(state.current_match_index, 1)

        keep_running = _handle_key("SCROLL_UP", state)
        self.assertTrue(keep_running)
        self.assertEqual(state.current_match_index, 0)

    def test_refresh_ignores_tfind_ui_only_log_growth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            transcript = Path(temp_dir) / "bash-20260423.log"
            transcript.write_text(
                '$ echo "version"\nversion\ntfind "version"\n',
                encoding="utf-8",
            )

            state = TranscriptState(source=transcript, query="version")
            self.assertTrue(state.refresh(force=True))
            initial_lines = list(state.lines)

            transcript.write_text(
                "\n".join(
                    [
                        '$ echo "version"',
                        "version",
                        'tfind "version"',
                        "__TFIND_INTERACTIVE_BEGIN__",
                        'tfind query="version" source=/tmp/bash-20260423.log follow:on',
                        "[*] (1) Highlight all",
                        "r reload  q quit",
                        "__TFIND_INTERACTIVE_END__",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            self.assertFalse(state.refresh())
            self.assertEqual(state.lines, initial_lines)


if __name__ == "__main__":
    unittest.main()
