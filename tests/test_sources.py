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


if __name__ == "__main__":
    unittest.main()
