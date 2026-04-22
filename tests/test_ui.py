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


if __name__ == "__main__":
    unittest.main()
