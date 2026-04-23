import io
import os
from pathlib import Path
import shutil
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from unittest.mock import patch

from tfind.cli import main


class CliTests(unittest.TestCase):
    def test_savepath_prints_storage_locations(self) -> None:
        previous_state_root = os.environ.get("TFIND_STATE_ROOT")
        previous_current_log = os.environ.get("TFIND_CURRENT_LOG")
        work_root = Path(__file__).resolve().parents[1] / ".test-work"
        work_root.mkdir(parents=True, exist_ok=True)
        temp_dir = work_root / "savepath"
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir.mkdir(parents=True, exist_ok=True)
            root = temp_dir
            transcript = root / "sessions" / "session.log"
            transcript.parent.mkdir(parents=True, exist_ok=True)
            transcript.write_text("hello", encoding="utf-8")

            os.environ["TFIND_STATE_ROOT"] = str(root)
            os.environ["TFIND_CURRENT_LOG"] = str(transcript)

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["--savepath"])

            text = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn(f"state root: {root}", text)
            self.assertIn(f"current transcript: {transcript}", text)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            if previous_state_root is None:
                os.environ.pop("TFIND_STATE_ROOT", None)
            else:
                os.environ["TFIND_STATE_ROOT"] = previous_state_root

            if previous_current_log is None:
                os.environ.pop("TFIND_CURRENT_LOG", None)
            else:
                os.environ["TFIND_CURRENT_LOG"] = previous_current_log

    def test_interactive_search_uses_attached_terminal_context(self) -> None:
        transcript = Path("/tmp/tfind-session.log")

        @contextmanager
        def interactive_terminal() -> bool:
            yield True

        with (
            patch("tfind.cli._resolve_source_with_fallback", return_value=(transcript, True, None)),
            patch("tfind.cli._interactive_terminal", side_effect=interactive_terminal),
            patch("tfind.cli.run_tui") as run_tui,
        ):
            exit_code = main(["version"])

        self.assertEqual(exit_code, 0)
        run_tui.assert_called_once_with(source=transcript, query="version", follow=True)

    def test_interactive_search_errors_when_no_terminal_is_available(self) -> None:
        transcript = Path("/tmp/tfind-session.log")

        @contextmanager
        def interactive_terminal() -> bool:
            yield False

        stderr = io.StringIO()
        with (
            patch("tfind.cli._resolve_source_with_fallback", return_value=(transcript, True, None)),
            patch("tfind.cli._interactive_terminal", side_effect=interactive_terminal),
            patch("tfind.cli.run_tui") as run_tui,
            redirect_stderr(stderr),
        ):
            exit_code = main(["version"])

        self.assertEqual(exit_code, 2)
        self.assertIn("Interactive mode requires a real terminal.", stderr.getvalue())
        run_tui.assert_not_called()


if __name__ == "__main__":
    unittest.main()
