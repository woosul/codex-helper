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
            ROOT / "sources/agents/planner.toml",
            ROOT / "sources/agents/developer.toml",
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

    def test_agents_have_declared_role_permissions(self):
        expected_modes = {
            "scanner": "read-only",
            "planner": "read-only",
            "developer": "workspace-write",
            "reviewer": "read-only",
            "verifier": "read-only",
        }
        expected_nicknames = {
            "scanner": ["Scanner"],
            "planner": ["Planner"],
            "developer": ["Developer 1", "Developer 2", "Developer 3"],
            "reviewer": ["Reviewer 1", "Reviewer 2", "Reviewer 3"],
            "verifier": ["Verifier 1", "Verifier 2", "Verifier 3"],
        }
        for name, sandbox_mode in expected_modes.items():
            data = tomllib.loads((ROOT / f"sources/agents/{name}.toml").read_text())
            self.assertEqual(name, data["name"])
            self.assertEqual(sandbox_mode, data["sandbox_mode"])
            self.assertTrue(data["description"])
            self.assertTrue(data["developer_instructions"])
            self.assertIsInstance(data.get("nickname_candidates"), list)
            self.assertTrue(data["nickname_candidates"])
            self.assertEqual(
                len(data["nickname_candidates"]), len(set(data["nickname_candidates"]))
            )
            self.assertEqual(expected_nicknames[name], data["nickname_candidates"])

        planner = tomllib.loads((ROOT / "sources/agents/planner.toml").read_text())
        developer = tomllib.loads((ROOT / "sources/agents/developer.toml").read_text())
        for agent in (planner, developer):
            self.assertEqual("gpt-5.6-sol", agent["model"])
            self.assertEqual("high", agent["model_reasoning_effort"])

        for phrase in (
            "Do not edit files",
            "commit",
            "push",
            "material ambiguity",
            "evidence from inference",
            "ordered steps",
        ):
            self.assertIn(phrase, planner["developer_instructions"])

        for phrase in (
            "approved assignment and owned paths",
            "test-first",
            "broaden scope",
            "commit",
            "push",
            "self-approve",
            "unrelated changes",
            "one developer per checkout",
            "separate worktrees",
        ):
            self.assertIn(phrase, developer["developer_instructions"])

    def test_manifest_targets_are_unique(self):
        data = tomllib.loads((ROOT / "manifest.toml").read_text())
        assets = data["assets"]
        self.assertEqual(len(assets), len({asset["id"] for asset in assets}))
        self.assertEqual(len(assets), len({asset["target"] for asset in assets}))

    def test_manifest_defines_skill_activation_contract(self):
        data = tomllib.loads((ROOT / "manifest.toml").read_text())
        self.assertEqual("0.3.0", data["harness_version"])
        self.assertIn("preferences", data["config"])
        for asset in data["assets"]:
            if asset["category"] == "skills":
                self.assertIsInstance(asset.get("enabled", True), bool)

    def test_feature_delivery_manifest_contract(self):
        data = tomllib.loads((ROOT / "manifest.toml").read_text())
        self.assertEqual("0.3.0", data["harness_version"])
        assets = {asset["id"]: asset for asset in data["assets"]}

        for asset_id, source, target in (
            (
                "agent-planner",
                "sources/agents/planner.toml",
                "${CODEX_HOME:-$HOME/.codex}/agents/planner.toml",
            ),
            (
                "agent-developer",
                "sources/agents/developer.toml",
                "${CODEX_HOME:-$HOME/.codex}/agents/developer.toml",
            ),
        ):
            asset = assets[asset_id]
            self.assertEqual("agents", asset["category"])
            self.assertEqual(source, asset["source"])
            self.assertEqual(target, asset["target"])

        skill = assets["skill-feature-delivery"]
        self.assertEqual("skills", skill["category"])
        self.assertEqual("sources/skills/feature-delivery", skill["source"])
        self.assertEqual("$HOME/.agents/skills/feature-delivery", skill["target"])
        self.assertTrue(skill["enabled"])

    def test_feature_delivery_skill_contract(self):
        skill = ROOT / "sources/skills/feature-delivery/SKILL.md"
        text = skill.read_text()
        for phrase in (
            "name: feature-delivery",
            "planner",
            "scanner",
            "developer",
            "reviewer",
            "verifier",
            "root plan gate",
            "Subagent-Driven by default",
            "inline workflow override",
            "separate worktree per developer",
            "three-cycle default",
            "add, remove, reorder, or skip",
            "The root agent owns commits, pushes, and final integration",
            "delegating parent/root task remains persistent until every spawned subagent has returned",
            "Start this workflow only from the coordinating root task",
            "When dispatched as a role within an active feature-delivery workflow",
            "do not re-enter this workflow",
            "Return validated findings to the developer as a narrower assignment",
            "planner - plan feature delivery",
            "developer 1 - implement role badges",
            "reviewer 1 - review role spec",
            "reviewer 2 - review role quality",
            "verifier 1 - verify acceptance criteria",
            "reviewer_2__review_role_quality",
            "increase monotonically",
            "never recycled",
            "follow-up to the same agent thread reuses its number",
            "Subagents echo the assigned label and never allocate numbers",
        ):
            self.assertIn(phrase, text)

        metadata = (ROOT / "sources/skills/feature-delivery/agents/openai.yaml").read_text()
        self.assertIn("Feature Delivery", metadata)

        guidance = (ROOT / "AGENTS.md").read_text()
        self.assertIn("$feature-delivery", guidance)
        self.assertIn("When `$feature-delivery` is available and enabled", guidance)
        self.assertIn("If `$feature-delivery` is unavailable or disabled", guidance)
        self.assertIn("execute or reconfigure the workflow inline", guidance)
        self.assertIn("must not attempt to invoke the missing skill", guidance)
        self.assertIn("non-trivial feature", guidance)
        self.assertIn("delegated role", guidance)
        self.assertIn("do not re-enter", guidance)
        self.assertIn("coordinating root", guidance)
        self.assertIn("role instance - task name", guidance)
        self.assertIn("monotonically", guidance)
        self.assertIn("same-thread", guidance)

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

    def test_operator_docs_cover_two_level_skill_activation(self):
        readme = (ROOT / "README.md").read_text()
        guide = (ROOT / "docs/user-guide.md").read_text()
        operations = (ROOT / "docs/operations.md").read_text()
        for command in (
            "codex-harness skill list",
            "codex-harness skill status",
            "codex-harness skill enable",
            "codex-harness skill disable",
            "codex-harness skill reset",
        ):
            self.assertIn(command, readme)
            self.assertIn(command, guide)
        self.assertIn("preferences.toml", guide)
        self.assertIn("local override", guide)
        self.assertIn("skill reset", operations)

    def test_operator_docs_cover_feature_delivery(self):
        documents = {
            "README.md": (ROOT / "README.md").read_text(),
            "docs/architecture.md": (ROOT / "docs/architecture.md").read_text(),
            "docs/user-guide.md": (ROOT / "docs/user-guide.md").read_text(),
            "docs/operations.md": (ROOT / "docs/operations.md").read_text(),
            "docs/sources.md": (ROOT / "docs/sources.md").read_text(),
        }
        for document, text in documents.items():
            with self.subTest(document=document):
                self.assertIn("feature-delivery", text)

        guide = documents["docs/user-guide.md"]
        for phrase in (
            "planner",
            "developer",
            "기본 Subagent-Driven",
            "인라인 override",
            "별도 worktree",
            "기본 세 번",
            "workspace-write",
            "사용자/시스템 권한 경계",
            "커밋과 푸시",
            "말줄임",
            "client-owned",
            "본문 label",
            "developer 1 - implement role badges",
            "reviewer 2 - review role quality",
            "`feature-delivery`가 없거나 머신 로컬에서 비활성화",
            "전역 지침은 사용할 수 없는 스킬을 요구하지 않는다",
            "인라인 또는 루트가 선택한 다른 워크플로",
        ):
            self.assertIn(phrase, guide)

        operations = documents["docs/operations.md"]
        for phrase in (
            "codex-harness skill disable feature-delivery",
            "codex-harness skill enable feature-delivery",
            "codex-harness skill reset feature-delivery",
            "parent/user/system permission boundary",
            "workspace-write",
            "commits and pushes",
            "user/system authorization",
            "native badge",
            "client-owned",
            "full label",
            "role instance - task name",
            "unavailable or machine-locally disabled",
            "global guidance does not require the missing skill",
            "continue inline or use another chosen workflow",
        ):
            self.assertIn(phrase, operations)

    def test_docs_define_safe_update_sequence(self):
        text = (ROOT / "docs/operations.md").read_text()
        sequence = ["git pull --ff-only", "codex-harness plan", "codex-harness apply", "codex-harness doctor"]
        positions = [text.index(item) for item in sequence]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
