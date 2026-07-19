from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/codex-harness"


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.codex_home = self.home / ".codex"
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "CODEX_HOME": str(self.codex_home),
            "CODEX_HELPER_HOST": "default",
        }

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args, check=True):
        return subprocess.run(
            [str(CLI), *args],
            cwd=ROOT,
            env=self.env,
            text=True,
            capture_output=True,
            check=check,
        )

    def test_plan_is_read_only_and_lists_declared_assets(self):
        result = self.run_cli("plan", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual("0.1.0", payload["harness_version"])
        self.assertTrue(any(item["id"] == "global-agents" for item in payload["assets"]))
        self.assertFalse(self.codex_home.exists())

    def test_inventory_filters_by_kind(self):
        result = self.run_cli("list", "--kind", "agents", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(3, len(payload["assets"]))
        self.assertTrue(all(item["category"] == "agents" for item in payload["assets"]))

    def test_status_reports_missing_without_mutating(self):
        result = self.run_cli("status", "--json", check=False)
        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertTrue(all(item["status"] == "missing" for item in payload["assets"]))

    def test_manifest_rejects_target_outside_approved_roots(self):
        bad = self.home / "bad.toml"
        text = (ROOT / "manifest.toml").read_text().replace(
            '${CODEX_HOME:-$HOME/.codex}/AGENTS.md',
            '/tmp/outside/AGENTS.md',
            1,
        )
        bad.write_text(text)
        result = self.run_cli("--manifest", str(bad), "plan", check=False)
        self.assertEqual(2, result.returncode)
        self.assertIn("outside approved roots", result.stderr)
