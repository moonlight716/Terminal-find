import unittest
from pathlib import Path

from tfind.searching import SearchOptions, prepare_transcript_lines, search_lines, strip_ansi


class SearchingTests(unittest.TestCase):
    def test_strip_ansi_removes_color_sequences(self) -> None:
        text = "\x1b[31mwindowsContent\x1b[0m failed"
        self.assertEqual(strip_ansi(text), "windowsContent failed")

    def test_strip_ansi_removes_osc_title_sequences(self) -> None:
        text = "\x1b]0;zyg@host:~/Terminal-find\x07version"
        self.assertEqual(strip_ansi(text), "version")

    def test_strip_ansi_applies_backspace_and_erase_controls(self) -> None:
        text = 'echo "ab"\b\bcd\x1b[K\nvalue\rVALUE'
        self.assertEqual(strip_ansi(text), 'echo "acd\nVALUE')

    def test_prepare_transcript_lines_filters_bash_prompt_noise(self) -> None:
        raw = "\n".join(
            [
                '\x1b[?2004h(base) \x1b]0;zyg@host: ~/repo\x07\x1b[01;32mzyg@host\x1b[00m:\x1b[01;34m~/repo\x1b[00m$ echo "version"',
                '$ builtin fc -ln -1 -1',
                '$ echo "version"',
                'version',
                '(base) zyg@host:~/repo$ ',
            ]
        )
        self.assertEqual(
            prepare_transcript_lines(raw, source=Path("bash-20260423.log")),
            ['$ echo "version"', "version"],
        )

    def test_case_insensitive_search_matches(self) -> None:
        lines = ["windowsContent failed"]
        matches = search_lines(lines, "WINDOWSCONTENT", SearchOptions())
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].start_col, 0)

    def test_whole_word_search_skips_substrings(self) -> None:
        lines = ["alpha windowsContentBeta", "alpha windowsContent beta"]
        matches = search_lines(lines, "windowsContent", SearchOptions(whole_word=True))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].line_index, 1)

    def test_accent_insensitive_search_matches(self) -> None:
        lines = ["resume", "resume", "résumé"]
        matches = search_lines(lines, "résumé", SearchOptions(match_accents=False))
        self.assertEqual(len(matches), 3)

    def test_accent_sensitive_search_respects_marks(self) -> None:
        lines = ["resume", "résumé"]
        matches = search_lines(lines, "résumé", SearchOptions(match_accents=True))
        self.assertEqual(len(matches), 1)


if __name__ == "__main__":
    unittest.main()
