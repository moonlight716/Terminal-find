import io
import os
from pathlib import Path
import shlex
import shutil
import stat
import unittest
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from unittest.mock import patch

from tfind.cli import main


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work_root = Path(__file__).resolve().parents[1] / ".test-work"
        self.work_root.mkdir(parents=True, exist_ok=True)

    def test_savepath_prints_storage_locations(self) -> None:
        previous_state_root = os.environ.get("TFIND_STATE_ROOT")
        previous_current_log = os.environ.get("TFIND_CURRENT_LOG")
        temp_dir = self.work_root / "savepath"
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

    def test_bootstrap_bash_install_writes_config_and_bashrc(self) -> None:
        temp_dir = self.work_root / "bootstrap-install"
        shutil.rmtree(temp_dir, ignore_errors=True)
        home = temp_dir / "home"
        repo = temp_dir / "repo"
        python_bin = temp_dir / "python3.11"
        bash_script = repo / "integrations" / "bash" / "tfind.bash"
        bash_script.parent.mkdir(parents=True, exist_ok=True)
        bash_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        home.mkdir(parents=True, exist_ok=True)
        python_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        python_bin.chmod(python_bin.stat().st_mode | stat.S_IXUSR)

        stdout = io.StringIO()
        with (
            patch.dict(os.environ, {"HOME": str(home)}, clear=False),
            patch("tfind.cli.repo_root", return_value=repo),
            redirect_stdout(stdout),
        ):
            exit_code = main(["bootstrap", "bash", "--install", "--python", str(python_bin)])

        config_path = home / ".config" / "tfind" / "config.sh"
        bashrc = home / ".bashrc"
        self.assertEqual(exit_code, 0)
        self.assertTrue(config_path.exists())
        self.assertTrue(bashrc.exists())
        self.assertIn(f"export TFIND_PYTHON={shlex.quote(str(python_bin))}", config_path.read_text(encoding="utf-8"))
        self.assertIn(f"export TFIND_REPO_ROOT={shlex.quote(str(repo))}", config_path.read_text(encoding="utf-8"))
        self.assertIn(f"source {shlex.quote(str(bash_script))}", bashrc.read_text(encoding="utf-8"))
        self.assertIn("Installed Bash integration.", stdout.getvalue())

    def test_bootstrap_bash_install_replaces_existing_block(self) -> None:
        temp_dir = self.work_root / "bootstrap-reinstall"
        shutil.rmtree(temp_dir, ignore_errors=True)
        home = temp_dir / "home"
        repo = temp_dir / "repo"
        old_repo = temp_dir / "old-repo"
        python_bin = temp_dir / "python3.11"
        home.mkdir(parents=True, exist_ok=True)
        python_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        python_bin.chmod(python_bin.stat().st_mode | stat.S_IXUSR)
        (repo / "integrations" / "bash").mkdir(parents=True, exist_ok=True)
        (old_repo / "integrations" / "bash").mkdir(parents=True, exist_ok=True)
        bashrc = home / ".bashrc"
        bashrc.write_text(
            "\n".join(
                [
                    "export PATH=\"$HOME/bin:$PATH\"",
                    "# >>> tfind >>>",
                    f"source '{old_repo / 'integrations' / 'bash' / 'tfind.bash'}'",
                    "# <<< tfind <<<",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        with (
            patch.dict(os.environ, {"HOME": str(home)}, clear=False),
            patch("tfind.cli.repo_root", return_value=repo),
        ):
            exit_code = main(["bootstrap", "bash", "--install", "--python", str(python_bin)])

        bashrc_text = bashrc.read_text(encoding="utf-8")
        self.assertEqual(exit_code, 0)
        self.assertEqual(bashrc_text.count("# >>> tfind >>>"), 1)
        self.assertIn(
            f"source {shlex.quote(str(repo / 'integrations' / 'bash' / 'tfind.bash'))}",
            bashrc_text,
        )
        self.assertNotIn(str(old_repo), bashrc_text)

    def test_bootstrap_bash_install_requires_absolute_python(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = main(["bootstrap", "bash", "--install", "--python", "python3.11"])

        self.assertEqual(exit_code, 2)
        self.assertIn("--python must be an absolute path", stderr.getvalue())

    def test_bootstrap_bash_install_requires_python_argument(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = main(["bootstrap", "bash", "--install"])

        self.assertEqual(exit_code, 2)
        self.assertIn("requires `--python /absolute/path/to/python`", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
