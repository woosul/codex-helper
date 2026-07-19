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
        self.assertEqual("0.3.0", payload["harness_version"])
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

    def test_manifest_can_disable_a_skill_by_default(self):
        manifest = self.home / "manifest.toml"
        manifest.write_text((ROOT / "manifest.toml").read_text().replace(
            'id = "skill-parallel-review"\nkind = "symlink"\ncategory = "skills"\nenabled = true',
            'id = "skill-parallel-review"\nkind = "symlink"\ncategory = "skills"\nenabled = false',
            1,
        ))
        self.run_cli("--manifest", str(manifest), "apply", "--yes")
        self.assertFalse((self.home / ".agents/skills/parallel-review").exists())
        self.assertTrue((self.home / ".agents/skills/dual-loop-review").is_symlink())

    def test_omitted_manifest_enabled_defaults_to_true(self):
        manifest = self.home / "manifest.toml"
        manifest.write_text((ROOT / "manifest.toml").read_text().replace(
            'category = "skills"\nenabled = true\nsource = "sources/skills/parallel-review"',
            'category = "skills"\nsource = "sources/skills/parallel-review"',
            1,
        ))
        self.run_cli("--manifest", str(manifest), "apply", "--yes")
        self.assertTrue((self.home / ".agents/skills/parallel-review").is_symlink())

    def test_manifest_default_change_removes_only_matching_skill_link(self):
        self.run_cli("apply", "--yes")
        manifest = self.home / "manifest.toml"
        manifest.write_text((ROOT / "manifest.toml").read_text().replace(
            'id = "skill-parallel-review"\nkind = "symlink"\ncategory = "skills"\nenabled = true',
            'id = "skill-parallel-review"\nkind = "symlink"\ncategory = "skills"\nenabled = false',
            1,
        ))
        self.run_cli("--manifest", str(manifest), "apply", "--yes")
        self.assertFalse((self.home / ".agents/skills/parallel-review").exists())
        self.assertTrue((self.home / ".agents/skills/dual-loop-review").is_symlink())

    def test_apply_never_removes_foreign_target_for_disabled_skill(self):
        target = self.home / ".agents/skills/parallel-review"
        target.parent.mkdir(parents=True)
        target.write_text("foreign")
        manifest = self.home / "manifest.toml"
        manifest.write_text((ROOT / "manifest.toml").read_text().replace(
            'id = "skill-parallel-review"\nkind = "symlink"\ncategory = "skills"\nenabled = true',
            'id = "skill-parallel-review"\nkind = "symlink"\ncategory = "skills"\nenabled = false',
            1,
        ))
        result = self.run_cli(
            "--manifest", str(manifest), "apply", "--yes", check=False
        )
        self.assertEqual(3, result.returncode)
        self.assertEqual("foreign", target.read_text())

    def test_invalid_local_skill_preferences_fail_closed(self):
        preferences = self.codex_home / ".codex-helper/preferences.toml"
        preferences.parent.mkdir(parents=True)
        preferences.write_text(
            'schema_version = 1\n[skills]\nenabled = ["skill-parallel-review"]\n'
            'disabled = ["skill-parallel-review"]\n'
        )
        result = self.run_cli("plan", "--json", check=False)
        self.assertEqual(2, result.returncode)

    def test_local_skill_override_lifecycle(self):
        self.run_cli("apply", "--yes")
        disabled = json.loads(self.run_cli(
            "skill", "disable", "parallel-review", "--json"
        ).stdout)
        self.assertFalse(disabled["effective_enabled"])
        self.assertEqual("disabled", disabled["local_override"])
        self.assertFalse((self.home / ".agents/skills/parallel-review").exists())
        preferences = self.codex_home / ".codex-helper/preferences.toml"
        self.assertEqual(0o600, preferences.stat().st_mode & 0o777)

        status = self.run_cli("status", "--json")
        item = next(
            asset for asset in json.loads(status.stdout)["assets"]
            if asset["id"] == "skill-parallel-review"
        )
        self.assertEqual("disabled", item["status"])

        enabled = json.loads(self.run_cli(
            "skill", "enable", "parallel-review", "--json"
        ).stdout)
        self.assertTrue(enabled["effective_enabled"])
        self.assertEqual("enabled", enabled["local_override"])
        self.assertTrue((self.home / ".agents/skills/parallel-review").is_symlink())

        reset = json.loads(self.run_cli(
            "skill", "reset", "parallel-review", "--json"
        ).stdout)
        self.assertIsNone(reset["local_override"])
        self.assertTrue(reset["effective_enabled"])

    def test_disabled_skill_is_healthy_but_manual_unlink_is_drift(self):
        self.run_cli("apply", "--yes")
        self.run_cli("skill", "disable", "parallel-review", "--json")
        self.assertEqual(0, self.run_cli("status", "--json").returncode)

        link = self.home / ".agents/skills/dual-loop-review"
        link.unlink()
        self.assertEqual(1, self.run_cli("status", "--json", check=False).returncode)

    def test_skill_toggle_never_replaces_conflict(self):
        target = self.home / ".agents/skills/parallel-review"
        target.parent.mkdir(parents=True)
        target.write_text("foreign")
        result = self.run_cli(
            "skill", "disable", "parallel-review", "--json", check=False
        )
        self.assertEqual(3, result.returncode)
        self.assertEqual("foreign", target.read_text())
        self.assertFalse((self.codex_home / ".codex-helper/preferences.toml").exists())

    def test_local_enable_overrides_manifest_default_and_reset_restores_it(self):
        manifest = self.home / "manifest.toml"
        manifest.write_text((ROOT / "manifest.toml").read_text().replace(
            'id = "skill-parallel-review"\nkind = "symlink"\ncategory = "skills"\nenabled = true',
            'id = "skill-parallel-review"\nkind = "symlink"\ncategory = "skills"\nenabled = false',
            1,
        ))
        prefix = ("--manifest", str(manifest))
        self.run_cli(*prefix, "apply", "--yes")
        enabled = json.loads(self.run_cli(
            *prefix, "skill", "enable", "parallel-review", "--json"
        ).stdout)
        self.assertFalse(enabled["default_enabled"])
        self.assertTrue(enabled["effective_enabled"])

        reset = json.loads(self.run_cli(
            *prefix, "skill", "reset", "parallel-review", "--json"
        ).stdout)
        self.assertFalse(reset["effective_enabled"])
        self.assertEqual("disabled", reset["status"])

    def test_snapshot_restores_skill_preferences_and_link(self):
        self.run_cli("apply", "--yes")
        self.run_cli("skill", "disable", "parallel-review", "--json")
        snapshot = json.loads(self.run_cli("snapshot", "--json").stdout)["snapshot_id"]
        self.run_cli("skill", "enable", "parallel-review", "--json")
        self.run_cli("restore", snapshot, "--yes")

        status = json.loads(self.run_cli(
            "skill", "status", "parallel-review", "--json"
        ).stdout)
        self.assertEqual("disabled", status["local_override"])
        self.assertEqual("disabled", status["status"])

    def test_doctor_is_healthy_with_intentionally_disabled_skill(self):
        self.run_cli("apply", "--yes")
        self.run_cli("skill", "disable", "parallel-review", "--json")
        result = self.run_cli("doctor", "--json", check=False)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertEqual("healthy", json.loads(result.stdout)["health"])

    def test_skill_list_reports_default_override_and_effective_state(self):
        self.run_cli("apply", "--yes")
        self.run_cli("skill", "disable", "parallel-review", "--json")
        payload = json.loads(self.run_cli("skill", "list", "--json").stdout)
        item = next(
            skill for skill in payload["skills"]
            if skill["id"] == "skill-parallel-review"
        )
        self.assertTrue(item["default_enabled"])
        self.assertEqual("disabled", item["local_override"])
        self.assertFalse(item["effective_enabled"])

    def test_enabled_is_rejected_for_non_skill_assets(self):
        manifest = self.home / "manifest.toml"
        manifest.write_text((ROOT / "manifest.toml").read_text().replace(
            'id = "global-agents"',
            'id = "global-agents"\nenabled = false',
            1,
        ))
        result = self.run_cli("--manifest", str(manifest), "plan", check=False)
        self.assertEqual(2, result.returncode)
        self.assertIn("only supported for skills", result.stderr)

    def test_malformed_skill_preferences_return_usage_error(self):
        preferences = self.codex_home / ".codex-helper/preferences.toml"
        preferences.parent.mkdir(parents=True)
        preferences.write_text('schema_version = 1\nskills = "invalid"\n')
        result = self.run_cli("plan", "--json", check=False)
        self.assertEqual(2, result.returncode)
        self.assertIn("skills must be a table", result.stderr)

    def test_doctor_reports_malformed_preferences_as_unhealthy_json(self):
        self.run_cli("apply", "--yes")
        preferences = self.codex_home / ".codex-helper/preferences.toml"
        preferences.write_text('schema_version = 1\nskills = "invalid"\n')
        result = self.run_cli("doctor", "--json", check=False)
        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("unhealthy", payload["health"])
        check = next(item for item in payload["checks"] if item["id"] == "preferences")
        self.assertEqual("fail", check["status"])

    def test_skill_toggle_rolls_back_preferences_and_link_after_failure(self):
        self.run_cli("apply", "--yes")
        env = {**self.env, "CODEX_HELPER_SKILL_FAIL_AFTER": "1"}
        result = subprocess.run(
            [str(CLI), "skill", "disable", "parallel-review", "--json"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(4, result.returncode, result.stderr)
        self.assertTrue(json.loads(result.stdout)["rolled_back"])
        self.assertFalse((self.codex_home / ".codex-helper/preferences.toml").exists())
        self.assertTrue((self.home / ".agents/skills/parallel-review").is_symlink())

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

    def test_installed_harness_utility_executes_through_symlink(self):
        self.run_cli("apply", "--yes")
        installed = self.home / ".local/bin/codex-harness"
        result = subprocess.run(
            [str(installed), "version", "--json"],
            cwd=self.home,
            env=self.env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("0.3.0", json.loads(result.stdout)["harness_version"])

    def test_doctor_passes_for_sources_and_applied_temp_home(self):
        self.run_cli("apply", "--yes")
        result = self.run_cli("doctor", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual("healthy", payload["health"])
        self.assertTrue(all(check["status"] == "pass" for check in payload["checks"]))

    def test_doctor_detects_secret_in_managed_source_without_printing_value(self):
        checkout = self.home / "secret-checkout"
        subprocess.run(["cp", "-R", str(ROOT), str(checkout)], check=True)
        bad = checkout / "sources/config/hosts/default.local.toml"
        bad.write_text('api_token = "super-secret-value"\n')
        result = subprocess.run(
            [str(checkout / "bin/codex-harness"), "doctor", "--json"],
            cwd=checkout,
            env=self.env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("suspected secret", result.stdout)
        self.assertNotIn("super-secret-value", result.stdout)

    def test_operational_sources_have_no_sibling_harness_path(self):
        self.run_cli("apply", "--yes")
        result = self.run_cli("doctor", "--json")
        payload = json.loads(result.stdout)
        boundary = next(check for check in payload["checks"] if check["id"] == "self-contained")
        self.assertEqual("pass", boundary["status"])
