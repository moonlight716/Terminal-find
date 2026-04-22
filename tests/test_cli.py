import io
import os
from pathlib import Path
import shutil
import unittest
from contextlib import redirect_stdout

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


if __name__ == "__main__":
    unittest.main()
