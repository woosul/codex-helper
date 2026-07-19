from pathlib import Path
import re
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SourceContractTests(unittest.TestCase):
    def test_global_guidance_contract(self):
        text = (ROOT / "AGENTS.md").read_text()
        for heading in (
            "Think Before Coding",
            "Simplicity First",
            "Surgical Changes",
            "Goal-Driven Execution",
            "Harness Independence",
        ):
            self.assertIn(heading, text)
        self.assertIn("fresh", text.lower())
        self.assertNotRegex(text, re.compile(r"/[^\n]*/claude-harness-helper"))

    def test_manifest_and_toml_sources_parse(self):
        paths = [
            ROOT / "manifest.toml",
            ROOT / "sources/config/base.toml",
            ROOT / "sources/config/hosts/default.toml",
            ROOT / "sources/config/hosts/rock.toml",
            ROOT / "sources/agents/scanner.toml",
            ROOT / "sources/agents/reviewer.toml",
            ROOT / "sources/agents/verifier.toml",
            ROOT / "sources/profiles/deep-review.config.toml",
            ROOT / "sources/profiles/fast-scan.config.toml",
        ]
        for path in paths:
            with self.subTest(path=path):
                tomllib.loads(path.read_text())

    def test_base_config_uses_supported_feature_keys(self):
        data = tomllib.loads((ROOT / "sources/config/base.toml").read_text())
        self.assertNotIn("rmcp_client", data.get("features", {}))

    def test_agents_are_named_and_read_only(self):
        for name in ("scanner", "reviewer", "verifier"):
            data = tomllib.loads((ROOT / f"sources/agents/{name}.toml").read_text())
            self.assertEqual(name, data["name"])
            self.assertEqual("read-only", data["sandbox_mode"])
            self.assertTrue(data["description"])
            self.assertTrue(data["developer_instructions"])

    def test_manifest_targets_are_unique(self):
        data = tomllib.loads((ROOT / "manifest.toml").read_text())
        assets = data["assets"]
        self.assertEqual(len(assets), len({asset["id"] for asset in assets}))
        self.assertEqual(len(assets), len({asset["target"] for asset in assets}))

    def test_manifest_sources_exist(self):
        data = tomllib.loads((ROOT / "manifest.toml").read_text())
        for asset in data["assets"]:
            with self.subTest(asset=asset["id"]):
                self.assertTrue((ROOT / asset["source"]).exists())

    def test_parallel_review_skill_contract(self):
        skill = ROOT / "sources/skills/parallel-review/SKILL.md"
        text = skill.read_text()
        self.assertIn("name: parallel-review", text)
        self.assertIn("scanner", text)
        self.assertIn("reviewer", text)
        self.assertIn("verifier", text)
        self.assertIn("Wait for all", text)
        self.assertIn("root agent", text)
        self.assertIn("Do not delegate concurrent writes", text)
        self.assertIn("persistent parent task", text)
        self.assertIn("Do not run this workflow with `codex exec --ephemeral`", text)

    def test_operator_docs_exist_and_readme_links_them(self):
        readme = (ROOT / "README.md").read_text()
        for relative in (
            "docs/architecture.md",
            "docs/operations.md",
            "docs/cross-machine-bootstrap.md",
            "docs/sources.md",
            "docs/user-guide.md",
            "docs/research/codex-external-review-agents-2026-07.md",
            "docs/research/sdd-tdd-skills-2026-07.md",
        ):
            self.assertTrue((ROOT / relative).is_file())
            self.assertIn(relative, readme)

    def test_user_guide_covers_skill_lifecycle(self):
        text = (ROOT / "docs/user-guide.md").read_text()
        for phrase in (
            "스킬 추가",
            "스킬 ON/OFF",
            "codex-harness plan",
            "codex-harness inventory",
            "codex-harness doctor",
        ):
            self.assertIn(phrase, text)

    def test_docs_define_safe_update_sequence(self):
        text = (ROOT / "docs/operations.md").read_text()
        sequence = ["git pull --ff-only", "codex-harness plan", "codex-harness apply", "codex-harness doctor"]
        positions = [text.index(item) for item in sequence]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
