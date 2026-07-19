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

    def test_apply_is_idempotent_and_preserves_unmanaged_entries(self):
        self.codex_home.mkdir(parents=True)
        live = self.codex_home / "config.toml"
        live.write_text('[plugins.demo]\nenabled = true\n')
        external = self.home / ".agents/skills/external"
        external.mkdir(parents=True)
        (external / "SKILL.md").write_text("external")
        self.run_cli("apply", "--yes")
        first = live.read_bytes()
        self.run_cli("apply", "--yes")
        self.assertEqual(first, live.read_bytes())
        self.assertTrue((external / "SKILL.md").exists())
        self.assertEqual((ROOT / "AGENTS.md").resolve(), (self.codex_home / "AGENTS.md").resolve())
        plan = json.loads(self.run_cli("plan", "--json").stdout)
        self.assertFalse(plan["changes"])

    def test_apply_rolls_back_after_injected_failure(self):
        self.codex_home.mkdir(parents=True)
        live = self.codex_home / "config.toml"
        live.write_text('model = "before"\n')
        env = {**self.env, "CODEX_HELPER_FAIL_AFTER": "1"}
        result = subprocess.run(
            [str(CLI), "apply", "--yes"], cwd=ROOT, env=env, text=True, capture_output=True
        )
        self.assertEqual(4, result.returncode)
        self.assertEqual('model = "before"\n', live.read_text())
        self.assertFalse((self.codex_home / "AGENTS.md").exists())

    def test_snapshot_restore_and_unlink_touch_only_managed_state(self):
        self.run_cli("apply", "--yes")
        snapshot = json.loads(self.run_cli("snapshot", "--json").stdout)["snapshot_id"]
        agents_link = self.codex_home / "AGENTS.md"
        agents_link.unlink()
        self.run_cli("restore", snapshot, "--yes")
        self.assertTrue(agents_link.is_symlink())
        self.run_cli("unlink", "--yes")
        self.assertFalse(agents_link.exists())
        self.assertTrue((self.codex_home / "config.toml").exists())

    def test_apply_removes_only_a_stale_previously_owned_link(self):
        stale_source = ROOT / "AGENTS.md"
        stale_target = self.codex_home / "agents/retired.toml"
        stale_target.parent.mkdir(parents=True)
        stale_target.symlink_to(stale_source)
        state = self.codex_home / ".codex-helper/state.json"
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps({
            "managed_paths": [],
            "assets": {
                "retired-agent": {
                    "source": str(stale_source),
                    "target": str(stale_target),
                    "kind": "symlink",
                    "category": "agents",
                    "version": "0.9.0"
                }
            }
        }))
        self.run_cli("apply", "--yes")
        self.assertFalse(stale_target.exists())

    def test_bootstrap_creates_only_parent_directories(self):
        self.run_cli("bootstrap")
        self.assertTrue(self.codex_home.is_dir())
        self.assertTrue((self.home / ".agents/skills").is_dir())
        self.assertTrue((self.home / ".local/bin").is_dir())
        self.assertFalse((self.codex_home / "AGENTS.md").exists())

    def test_host_init_creates_non_secret_skeleton(self):
        checkout = self.home / "checkout"
        subprocess.run(["cp", "-R", str(ROOT), str(checkout)], check=True)
        cli = checkout / "bin/codex-harness"
        subprocess.run([str(cli), "host", "init", "gems"], cwd=checkout, env=self.env, check=True)
        text = (checkout / "sources/config/hosts/gems.toml").read_text()
        self.assertIn("Host-specific non-secret", text)
        self.assertNotRegex(text.lower(), r"token|password|bearer")

    def test_utilities_are_manifest_managed(self):
        self.run_cli("apply", "--yes")
        self.assertEqual(ROOT / "bin/codex-harness", (self.home / ".local/bin/codex-harness").resolve())
        self.assertEqual(ROOT / "bin/codex-external-review", (self.home / ".local/bin/codex-external-review").resolve())
