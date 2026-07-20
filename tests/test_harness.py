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
        self.assertEqual("0.4.1", payload["harness_version"])
        self.assertTrue(any(item["id"] == "global-agents" for item in payload["assets"]))
        config = next(item for item in payload["assets"] if item["id"] == "global-config")
        self.assertEqual("config", config["category"])
        self.assertEqual("symlink", config["kind"])
        self.assertEqual(ROOT / "sources/config/config-default.toml", Path(config["source"]))
        self.assertFalse(self.codex_home.exists())

    def test_global_config_target_ignores_runtime_codex_home(self):
        runtime_home = self.home / "runtime-codex-home"
        env = {**self.env, "CODEX_HOME": str(runtime_home)}
        result = subprocess.run(
            [str(CLI), "--host", "gems", "plan", "--json"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        config = next(item for item in payload["assets"] if item["id"] == "global-config")
        guidance = next(item for item in payload["assets"] if item["id"] == "global-agents")
        self.assertEqual(self.home / ".codex/config.toml", Path(config["target"]))
        self.assertEqual(runtime_home / "AGENTS.md", Path(guidance["target"]))
        self.assertFalse((self.home / ".codex").exists())
        self.assertFalse(runtime_home.exists())

    def test_explicit_and_environment_unknown_hosts_fail_closed(self):
        explicit = self.run_cli("--host", "unknown", "plan", "--json", check=False)
        self.assertEqual(2, explicit.returncode)
        self.assertIn("unknown host", explicit.stderr)

        env = {**self.env, "CODEX_HELPER_HOST": "unknown"}
        selected = subprocess.run(
            [str(CLI), "plan", "--json"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(2, selected.returncode)
        self.assertIn("unknown host", selected.stderr)

    def test_host_name_is_normalized_before_selection(self):
        payload = json.loads(self.run_cli("--host", "GEMS.local", "plan", "--json").stdout)
        self.assertEqual("gems", payload["host"]["name"])
        self.assertFalse(payload["host"]["fallback"])
        config = next(item for item in payload["assets"] if item["id"] == "global-config")
        self.assertTrue(config["source"].endswith("sources/config/config-gems.toml"))

    def test_inventory_filters_by_kind(self):
        result = self.run_cli("list", "--kind", "agents", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(
            {
                "agent-scanner",
                "agent-planner",
                "agent-developer",
                "agent-reviewer",
                "agent-verifier",
            },
            {item["id"] for item in payload["assets"]},
        )
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

    def test_manifest_schema_one_is_rejected_cleanly(self):
        legacy = self.home / "legacy-manifest.toml"
        legacy.write_text((ROOT / "manifest.toml").read_text().replace(
            "schema_version = 2",
            "schema_version = 1",
            1,
        ))
        result = self.run_cli("--manifest", str(legacy), "plan", "--json", check=False)
        self.assertEqual(2, result.returncode)
        self.assertIn("unsupported manifest schema_version", result.stderr)

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

    def test_apply_is_idempotent_and_links_selected_config(self):
        self.codex_home.mkdir(parents=True)
        live = self.codex_home / "config.toml"
        external = self.home / ".agents/skills/external"
        external.mkdir(parents=True)
        (external / "SKILL.md").write_text("external")
        self.run_cli("apply", "--yes")
        self.assertTrue(live.is_symlink())
        self.assertEqual(ROOT / "sources/config/config-default.toml", live.resolve())
        self.run_cli("apply", "--yes")
        self.assertTrue(live.is_symlink())
        self.assertTrue((external / "SKILL.md").exists())
        self.assertEqual((ROOT / "AGENTS.md").resolve(), (self.codex_home / "AGENTS.md").resolve())
        plan = json.loads(self.run_cli("plan", "--json").stdout)
        self.assertFalse(plan["changes"])

    def test_first_apply_over_real_config_requires_yes_and_snapshots_it(self):
        self.codex_home.mkdir(parents=True)
        live = self.codex_home / "config.toml"
        live.write_text('model = "before"\n')
        live.chmod(0o640)

        rejected = self.run_cli("apply", check=False)
        self.assertEqual(3, rejected.returncode)
        self.assertFalse(live.is_symlink())
        self.assertEqual('model = "before"\n', live.read_text())

        applied = json.loads(self.run_cli("apply", "--yes").stdout)
        self.assertTrue(applied["snapshot_id"])
        self.assertTrue(live.is_symlink())

        self.run_cli("restore", applied["snapshot_id"], "--yes")
        self.assertFalse(live.is_symlink())
        self.assertEqual('model = "before"\n', live.read_text())
        self.assertEqual(0o640, live.stat().st_mode & 0o777)

    def test_host_switch_is_reported_as_drift_and_updates_state(self):
        self.run_cli("--host", "gems", "apply", "--yes")
        gems_link = os.readlink(self.codex_home / "config.toml")
        gems_state = (self.codex_home / ".codex-helper/state.json").read_bytes()
        status = self.run_cli("--host", "rock", "status", "--json", check=False)
        self.assertEqual(1, status.returncode)
        config = next(
            item for item in json.loads(status.stdout)["assets"]
            if item["id"] == "global-config"
        )
        self.assertEqual("drifted", config["status"])

        rejected = self.run_cli("--host", "rock", "apply", check=False)
        self.assertEqual(3, rejected.returncode)
        self.assertEqual(gems_link, os.readlink(self.codex_home / "config.toml"))
        self.assertEqual(
            gems_state,
            (self.codex_home / ".codex-helper/state.json").read_bytes(),
        )

        self.run_cli("--host", "rock", "apply", "--yes")
        self.assertEqual(
            ROOT / "sources/config/config-rock.toml",
            (self.codex_home / "config.toml").resolve(),
        )
        state = json.loads((self.codex_home / ".codex-helper/state.json").read_text())
        self.assertTrue(state["assets"]["global-config"]["source"].endswith("config-rock.toml"))

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

    def test_apply_failure_after_config_link_restores_real_file_and_mode(self):
        self.codex_home.mkdir(parents=True)
        live = self.codex_home / "config.toml"
        live.write_text('model = "before"\n')
        live.chmod(0o640)
        asset_count = len(json.loads(self.run_cli("plan", "--json").stdout)["assets"])
        env = {**self.env, "CODEX_HELPER_FAIL_AFTER": str(asset_count)}
        result = subprocess.run(
            [str(CLI), "apply", "--yes"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(4, result.returncode)
        self.assertFalse(live.is_symlink())
        self.assertEqual('model = "before"\n', live.read_text())
        self.assertEqual(0o640, live.stat().st_mode & 0o777)

    def test_snapshot_restore_and_unlink_touch_only_managed_state(self):
        self.run_cli("apply", "--yes")
        snapshot = json.loads(self.run_cli("snapshot", "--json").stdout)["snapshot_id"]
        agents_link = self.codex_home / "AGENTS.md"
        agents_link.unlink()
        self.run_cli("restore", snapshot, "--yes")
        self.assertTrue(agents_link.is_symlink())
        self.run_cli("unlink", "--yes")
        self.assertFalse(agents_link.exists())
        config = self.codex_home / "config.toml"
        self.assertTrue(config.is_file())
        self.assertFalse(config.is_symlink())
        self.assertEqual(0o600, config.stat().st_mode & 0o777)
        self.assertEqual((ROOT / "sources/config/config-default.toml").read_bytes(), config.read_bytes())

    def test_unlink_preserves_foreign_config_as_conflict(self):
        self.run_cli("apply", "--yes")
        live = self.codex_home / "config.toml"
        live.unlink()
        live.write_text('model = "foreign"\n')
        result = self.run_cli("unlink", "--yes", check=False)
        self.assertEqual(3, result.returncode)
        self.assertEqual('model = "foreign"\n', live.read_text())
        self.assertIn("global-config", json.loads(result.stdout)["conflicts"])

    def test_unlink_retry_accepts_already_materialized_recorded_config(self):
        self.run_cli("apply", "--yes")
        conflict = self.codex_home / "AGENTS.md"
        conflict.unlink()
        conflict.write_text("foreign")

        first = self.run_cli("unlink", "--yes", check=False)
        self.assertEqual(3, first.returncode)
        config = self.codex_home / "config.toml"
        self.assertTrue(config.is_file())
        self.assertFalse(config.is_symlink())
        self.assertEqual(
            (ROOT / "sources/config/config-default.toml").read_bytes(),
            config.read_bytes(),
        )
        self.assertTrue((self.codex_home / ".codex-helper/state.json").exists())

        conflict.unlink()
        second = self.run_cli("unlink", "--yes", check=False)
        self.assertEqual(0, second.returncode, second.stdout)
        self.assertFalse((self.codex_home / ".codex-helper/state.json").exists())
        self.assertEqual(0o600, config.stat().st_mode & 0o777)

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

    def test_current_asset_state_target_outside_roots_is_rejected_before_snapshot_or_unlink(self):
        self.run_cli("apply", "--yes")
        state_path = self.codex_home / ".codex-helper/state.json"
        state = json.loads(state_path.read_text())
        outside = self.home / "outside-current-target"
        outside.symlink_to(ROOT / "AGENTS.md")
        state["assets"]["global-agents"]["target"] = str(outside)
        state_path.write_text(json.dumps(state))
        before_state = state_path.read_bytes()

        snapshot = self.run_cli("snapshot", "--json", check=False)
        self.assertEqual(2, snapshot.returncode)
        self.assertIn("recorded target outside approved roots", snapshot.stderr)
        self.assertTrue(outside.is_symlink())
        self.assertEqual(before_state, state_path.read_bytes())

        unlink = self.run_cli("unlink", "--yes", check=False)
        self.assertEqual(2, unlink.returncode)
        self.assertIn("recorded target outside approved roots", unlink.stderr)
        self.assertTrue(outside.is_symlink())
        self.assertEqual(before_state, state_path.read_bytes())

    def test_current_asset_state_cannot_redefine_manifest_target_within_approved_root(self):
        self.run_cli("apply", "--yes")
        state_path = self.codex_home / ".codex-helper/state.json"
        state = json.loads(state_path.read_text())
        poisoned = self.codex_home / "state-selected-agents-target"
        poisoned.symlink_to(ROOT / "AGENTS.md")
        state["assets"]["global-agents"]["target"] = str(poisoned)
        state_path.write_text(json.dumps(state))

        receipt = json.loads(self.run_cli("snapshot", "--json").stdout)
        targets = {entry["target"] for entry in receipt["entries"]}
        self.assertIn(str(self.codex_home / "AGENTS.md"), targets)
        self.assertNotIn(str(poisoned), targets)

        self.run_cli("unlink", "--yes")
        self.assertFalse((self.codex_home / "AGENTS.md").exists())
        self.assertTrue(poisoned.is_symlink())

    def test_stale_asset_state_target_outside_roots_is_rejected_before_snapshot_or_unlink(self):
        self.run_cli("apply", "--yes")
        state_path = self.codex_home / ".codex-helper/state.json"
        state = json.loads(state_path.read_text())
        outside = self.home / "outside-stale-target"
        outside.write_text("preserve")
        state["assets"]["retired-agent"] = {
            "source": str(ROOT / "AGENTS.md"),
            "target": str(outside),
            "kind": "symlink",
            "category": "agents",
            "version": "0.9.0",
        }
        state_path.write_text(json.dumps(state))
        before_state = state_path.read_bytes()

        snapshot = self.run_cli("snapshot", "--json", check=False)
        self.assertEqual(2, snapshot.returncode)
        self.assertIn("recorded target outside approved roots", snapshot.stderr)
        self.assertEqual("preserve", outside.read_text())
        self.assertEqual(before_state, state_path.read_bytes())

        unlink = self.run_cli("unlink", "--yes", check=False)
        self.assertEqual(2, unlink.returncode)
        self.assertIn("recorded target outside approved roots", unlink.stderr)
        self.assertEqual("preserve", outside.read_text())
        self.assertEqual(before_state, state_path.read_bytes())

    def test_stale_target_through_in_root_parent_symlink_is_rejected(self):
        self.run_cli("apply", "--yes")
        outside_dir = self.home / "outside-parent-target"
        outside_dir.mkdir()
        victim = outside_dir / "victim"
        victim.symlink_to(ROOT / "AGENTS.md")
        escape = self.codex_home / "escape"
        escape.symlink_to(outside_dir, target_is_directory=True)

        state_path = self.codex_home / ".codex-helper/state.json"
        state = json.loads(state_path.read_text())
        state["assets"]["retired-agent"] = {
            "source": str(ROOT / "AGENTS.md"),
            "target": str(escape / "victim"),
            "kind": "symlink",
            "category": "agents",
            "version": "0.9.0",
        }
        state_path.write_text(json.dumps(state))
        before_state = state_path.read_bytes()

        snapshot = self.run_cli("snapshot", "--json", check=False)
        self.assertEqual(2, snapshot.returncode)
        self.assertIn("recorded target outside approved roots", snapshot.stderr)
        self.assertTrue(victim.is_symlink())
        self.assertEqual(before_state, state_path.read_bytes())

        unlink = self.run_cli("unlink", "--yes", check=False)
        self.assertEqual(2, unlink.returncode)
        self.assertTrue(victim.is_symlink())
        self.assertEqual(before_state, state_path.read_bytes())

    def test_restore_target_through_in_root_parent_symlink_is_rejected(self):
        self.run_cli("apply", "--yes")
        outside_dir = self.home / "outside-restore-parent"
        outside_dir.mkdir()
        victim = outside_dir / "victim"
        victim.write_text("preserve")
        escape = self.codex_home / "restore-escape"
        escape.symlink_to(outside_dir, target_is_directory=True)

        snapshot_id = "parent-symlink-escape"
        snapshot_dir = self.codex_home / "backups/codex-helper" / snapshot_id
        snapshot_dir.mkdir(parents=True)
        receipt_path = snapshot_dir / "receipt.json"
        receipt_path.write_text(json.dumps({
            "snapshot_id": snapshot_id,
            "entries": [{"target": str(escape / "victim"), "type": "missing"}],
        }))
        state_path = self.codex_home / ".codex-helper/state.json"
        before_state = state_path.read_bytes()
        before_receipt = receipt_path.read_bytes()

        restore = self.run_cli("restore", snapshot_id, "--yes", check=False)
        self.assertEqual(2, restore.returncode)
        self.assertIn("snapshot target outside approved roots", restore.stderr)
        self.assertEqual("preserve", victim.read_text())
        self.assertEqual(before_state, state_path.read_bytes())
        self.assertEqual(before_receipt, receipt_path.read_bytes())

    def test_stale_target_with_symlink_component_before_dotdot_is_rejected(self):
        self.run_cli("apply", "--yes")
        outside_base = self.home / "outside-dotdot-state"
        nested = outside_base / "nested"
        nested.mkdir(parents=True)
        victim = outside_base / "victim"
        victim.symlink_to(ROOT / "AGENTS.md")
        escape = self.codex_home / "dotdot-escape"
        escape.symlink_to(nested, target_is_directory=True)
        escaped_target = escape / ".." / "victim"

        state_path = self.codex_home / ".codex-helper/state.json"
        state = json.loads(state_path.read_text())
        state["assets"]["retired-agent"] = {
            "source": str(ROOT / "AGENTS.md"),
            "target": str(escaped_target),
            "kind": "symlink",
            "category": "agents",
            "version": "0.9.0",
        }
        state_path.write_text(json.dumps(state))
        before_state = state_path.read_bytes()

        snapshot = self.run_cli("snapshot", "--json", check=False)
        self.assertEqual(2, snapshot.returncode)
        self.assertIn("recorded target outside approved roots", snapshot.stderr)
        self.assertTrue(victim.is_symlink())
        self.assertEqual(before_state, state_path.read_bytes())

        unlink = self.run_cli("unlink", "--yes", check=False)
        self.assertEqual(2, unlink.returncode)
        self.assertTrue(victim.is_symlink())
        self.assertEqual(before_state, state_path.read_bytes())

    def test_restore_target_with_symlink_component_before_dotdot_is_rejected(self):
        self.run_cli("apply", "--yes")
        outside_base = self.home / "outside-dotdot-restore"
        nested = outside_base / "nested"
        nested.mkdir(parents=True)
        victim = outside_base / "victim"
        victim.write_text("preserve")
        escape = self.codex_home / "restore-dotdot-escape"
        escape.symlink_to(nested, target_is_directory=True)
        escaped_target = escape / ".." / "victim"

        snapshot_id = "dotdot-symlink-escape"
        snapshot_dir = self.codex_home / "backups/codex-helper" / snapshot_id
        snapshot_dir.mkdir(parents=True)
        receipt_path = snapshot_dir / "receipt.json"
        receipt_path.write_text(json.dumps({
            "snapshot_id": snapshot_id,
            "entries": [{"target": str(escaped_target), "type": "missing"}],
        }))
        state_path = self.codex_home / ".codex-helper/state.json"
        before_state = state_path.read_bytes()
        before_receipt = receipt_path.read_bytes()

        restore = self.run_cli("restore", snapshot_id, "--yes", check=False)
        self.assertEqual(2, restore.returncode)
        self.assertIn("snapshot target outside approved roots", restore.stderr)
        self.assertEqual("preserve", victim.read_text())
        self.assertEqual(before_state, state_path.read_bytes())
        self.assertEqual(before_receipt, receipt_path.read_bytes())

    def test_state_target_equal_to_approved_root_is_rejected(self):
        self.run_cli("apply", "--yes")
        state_path = self.codex_home / ".codex-helper/state.json"
        state = json.loads(state_path.read_text())
        skills_root = self.home / ".agents/skills"
        state["assets"]["retired-skill"] = {
            "source": str(ROOT / "sources/skills/parallel-review"),
            "target": str(skills_root),
            "kind": "symlink",
            "category": "skills",
            "version": "0.9.0",
        }
        state_path.write_text(json.dumps(state))
        before_state = state_path.read_bytes()

        snapshot = self.run_cli("snapshot", "--json", check=False)
        self.assertEqual(2, snapshot.returncode)
        self.assertIn("recorded target outside approved roots", snapshot.stderr)
        self.assertTrue(skills_root.is_dir())
        self.assertEqual(before_state, state_path.read_bytes())

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
        env = {**self.env, "CODEX_HELPER_HOST": "unregistered"}
        subprocess.run([str(cli), "host", "init", "laptop"], cwd=checkout, env=env, check=True)
        created = checkout / "sources/config/config-laptop.toml"
        text = created.read_text()
        self.assertEqual(
            (checkout / "sources/config/config-default.toml").read_bytes(),
            created.read_bytes(),
        )
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
        self.assertEqual("0.4.1", json.loads(result.stdout)["harness_version"])

    def test_doctor_passes_for_sources_and_applied_temp_home(self):
        self.run_cli("apply", "--yes")
        result = self.run_cli("doctor", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual("healthy", payload["health"])
        self.assertTrue(all(check["status"] == "pass" for check in payload["checks"]))

    def test_doctor_detects_secret_in_managed_source_without_printing_value(self):
        checkout = self.home / "secret-checkout"
        subprocess.run(["cp", "-R", str(ROOT), str(checkout)], check=True)
        bad = checkout / "sources/config/config-bad.toml"
        bad.write_text(
            (checkout / "sources/config/config-default.toml").read_text()
            + '\n[mcp_servers.bad]\n'
            + 'args = ["Authorization: Bearer super-secret-value"]\n'
        )
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

    def test_doctor_rejects_config_missing_required_keys(self):
        checkout = self.home / "config-hygiene-checkout"
        subprocess.run(["cp", "-R", str(ROOT), str(checkout)], check=True)
        bad = checkout / "sources/config/config-rock.toml"
        bad.write_text('[features]\nrmcp_client = true\npath = "/machine/specific"\n')
        result = subprocess.run(
            [str(checkout / "bin/codex-harness"), "doctor", "--json"],
            cwd=checkout,
            env=self.env,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        hygiene = next(item for item in payload["checks"] if item["id"] == "config-sources")
        self.assertEqual(1, result.returncode)
        self.assertEqual("fail", hygiene["status"])
        self.assertNotIn("/machine/specific", result.stdout)

    def test_doctor_rejects_unapproved_workspace_write_agent(self):
        checkout = self.home / "workspace-write-checkout"
        subprocess.run(["cp", "-R", str(ROOT), str(checkout)], check=True)
        scanner = checkout / "sources/agents/scanner.toml"
        scanner.write_text(scanner.read_text().replace(
            'sandbox_mode = "read-only"',
            'sandbox_mode = "workspace-write"',
            1,
        ))
        result = subprocess.run(
            [str(checkout / "bin/codex-harness"), "doctor", "--json"],
            cwd=checkout,
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )
        payload = json.loads(result.stdout)
        agents = next(check for check in payload["checks"] if check["id"] == "agents")
        self.assertEqual(1, result.returncode)
        self.assertEqual("fail", agents["status"])
        self.assertEqual(
            "custom agents are named and use declared sandbox boundaries",
            agents["message"],
        )

    def test_operational_sources_have_no_sibling_harness_path(self):
        self.run_cli("apply", "--yes")
        result = self.run_cli("doctor", "--json")
        payload = json.loads(result.stdout)
        boundary = next(check for check in payload["checks"] if check["id"] == "self-contained")
        self.assertEqual("pass", boundary["status"])
