import os
from pathlib import Path
import shutil
import unittest

from tfind.session import resolve_transcript


class SessionTests(unittest.TestCase):
    def test_resolve_transcript_reads_pointer_with_utf8_bom(self) -> None:
        previous_state_root = os.environ.get("TFIND_STATE_ROOT")
        previous_current_log = os.environ.get("TFIND_CURRENT_LOG")
        work_root = Path(__file__).resolve().parents[1] / ".test-work"
        work_root.mkdir(parents=True, exist_ok=True)
        temp_dir = work_root / "session-pointer-bom"
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            temp_dir.mkdir(parents=True, exist_ok=True)
            state_root = temp_dir
            transcript = state_root / "sessions" / "powershell.log"
            transcript.parent.mkdir(parents=True, exist_ok=True)
            transcript.write_text("hello", encoding="utf-8")
            (state_root / "current-session.txt").write_text(str(transcript), encoding="utf-8-sig")

            os.environ["TFIND_STATE_ROOT"] = str(state_root)
            os.environ.pop("TFIND_CURRENT_LOG", None)

            self.assertEqual(resolve_transcript(), transcript)
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
