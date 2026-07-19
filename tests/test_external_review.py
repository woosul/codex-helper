from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/codex-external-review"


class ExternalReviewTests(unittest.TestCase):
    def test_external_review_is_ephemeral_read_only_and_structured(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            log = root / "args.json"
            stub = root / "codex"
            stub.write_text(
                "#!/bin/sh\n"
                "python3 - \"$@\" <<'PY'\n"
                "import json, pathlib, sys\n"
                f"pathlib.Path({str(log)!r}).write_text(json.dumps(sys.argv[1:]))\n"
                "args = sys.argv[1:]\n"
                "out = args[args.index('--output-last-message') + 1]\n"
                "pathlib.Path(out).write_text(json.dumps({'verdict':'pass','summary':'ok','findings':[],'requested_evidence':[]}))\n"
                "PY\n"
            )
            stub.chmod(0o755)
            env = {**os.environ, "PATH": f"{root}:{os.environ['PATH']}"}
            result = subprocess.run(
                [str(CLI), "--repo", str(repo), "--cycle", "1"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual("pass", json.loads(result.stdout)["verdict"])
            args = json.loads(log.read_text())
            self.assertIn("--ephemeral", args)
            self.assertEqual("read-only", args[args.index("--sandbox") + 1])
            self.assertIn("--output-schema", args)

    def test_cycle_must_be_between_one_and_three(self):
        result = subprocess.run(
            [str(CLI), "--repo", str(ROOT), "--cycle", "4"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("cycle must be between 1 and 3", result.stderr)
