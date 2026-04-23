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
                'version',
                '(base) zyg@host:~/repo$ ',
            ]
        )
        self.assertEqual(
            prepare_transcript_lines(raw, source=Path("bash-20260423.log")),
            ['$ echo "version"', "version"],
        )

    def test_prepare_transcript_lines_preserves_prompt_command_order(self) -> None:
        raw = "\n".join(
            [
                "(base) zyg@host:~/repo$ ls",
                "README.md  src  tests",
                "(base) zyg@host:~/repo$ conda env list",
                "# conda environments:",
                "#",
            ]
        )
        self.assertEqual(
            prepare_transcript_lines(raw, source=Path("bash-20260423.log")),
            [
                "$ ls",
                "README.md  src  tests",
                "$ conda env list",
                "# conda environments:",
                "#",
            ],
        )

    def test_prepare_transcript_lines_extracts_command_from_truncated_prompt_line(self) -> None:
        raw = "\n".join(
            [
                "<rminal-find$ printf 'Alpha\\nBeta\\nGamma\\n' | grep B",
                "Beta",
            ]
        )
        self.assertEqual(
            prepare_transcript_lines(raw, source=Path("bash-20260423.log")),
            [
                "$ printf 'Alpha\\nBeta\\nGamma\\n' | grep B",
                "Beta",
            ],
        )

    def test_prepare_transcript_lines_filters_script_session_metadata(self) -> None:
        raw = "\n".join(
            [
                'Script started on 2026-04-23 18:40:10+08:00 [TERM="xterm-256color" TTY="/dev/pts/0" COLUMNS="80" LINES="24"]',
                '$ echo "version"',
                "version",
                'Script done on 2026-04-23 18:40:11+08:00 [COMMAND_EXIT_CODE="0"]',
            ]
        )
        self.assertEqual(
            prepare_transcript_lines(raw, source=Path("bash-20260423.log")),
            ['$ echo "version"', "version"],
        )

    def test_prepare_transcript_lines_preserves_colored_grep_output(self) -> None:
        raw = "\n".join(
            [
                "$ pip list | grep py",
                "s\x1b[01;31m\x1b[Kpy\x1b[m\x1b[Kder-kernels                       2.5.0",
                "uc-micro-\x1b[01;31m\x1b[Kpy\x1b[m\x1b[K                          1.0.1",
            ]
        )
        self.assertEqual(
            prepare_transcript_lines(raw, source=Path("bash-20260423.log")),
            [
                "$ pip list | grep py",
                "spyder-kernels                       2.5.0",
                "uc-micro-py                          1.0.1",
            ],
        )

    def test_prepare_transcript_lines_skips_interactive_tfind_ui_blocks(self) -> None:
        raw = "\n".join(
            [
                'tfind "version"',
                "__TFIND_INTERACTIVE_BEGIN__",
                'tfind query="version" source=/home/example/.local/state/tfind/sessions/bash-20260423.log follow:on',
                '[*] (1) Highlight all  [ ] (2) Case sensitive  [ ] (3) Match accents',
                'r reload  q quit',
                "__TFIND_INTERACTIVE_END__",
                '$ tfind "version"',
                "__TFIND_INTERACTIVE_BEGIN__",
                'tfind query="version" source=/home/example/.local/state/tfind/sessions/bash-20260423.log follow:on',
                '[*] (1) Highlight all  [ ] (2) Case sensitive  [ ] (3) Match accents',
                'r reload  q quit',
                "__TFIND_INTERACTIVE_END__",
                '$ echo "version"',
                "version",
                '$ tfind --plain "version"',
                '2 matches for "version" in /tmp/bash.log',
            ]
        )
        self.assertEqual(
            prepare_transcript_lines(raw, source=Path("bash-20260423.log")),
            [
                'tfind "version"',
                '$ tfind "version"',
                '$ echo "version"',
                "version",
                '$ tfind --plain "version"',
                '2 matches for "version" in /tmp/bash.log',
            ],
        )

    def test_prepare_transcript_lines_leaves_non_bash_logs_unchanged(self) -> None:
        raw = "\n".join(
            [
                "PS C:\\Terminal-find> tfind \"version\"",
                "\x1b[31mversion\x1b[0m output",
            ]
        )
        self.assertEqual(
            prepare_transcript_lines(raw, source=Path("powershell-20260423.log")),
            ['PS C:\\Terminal-find> tfind "version"', "version output"],
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
