import unittest
from pathlib import Path

from tfind.searching import strip_ansi
from tfind.ui import TranscriptState


class UiLayoutTests(unittest.TestCase):
    def test_header_wraps_without_navigation_hint(self) -> None:
        state = TranscriptState(
            source=Path("C:/Users/example/AppData/Local/tfind/sessions/powershell-long-session-name.log"),
            query="conda",
        )
        lines = state.build_header_lines(40)
        plain = "\n".join(strip_ansi(line) for line in lines)

        self.assertGreater(len(lines), 1)
        self.assertIn('query="conda"', plain)
        self.assertNotIn("keys:n/p", plain)

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


if __name__ == "__main__":
    unittest.main()
