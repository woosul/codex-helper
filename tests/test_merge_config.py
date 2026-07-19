from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from merge_config import merge_config


class MergeConfigTests(unittest.TestCase):
    def test_add_change_delete_and_preserve(self):
        live = """
model = "old"
obsolete = true
[features]
multi_agent = false
[plugins.demo]
enabled = true
"""
        overlay = """
model = "new"
[features]
multi_agent = true
"""
        result = merge_config(
            live,
            overlay,
            previous_paths=(("model",), ("obsolete",), ("features", "multi_agent")),
        )
        self.assertIn('model = "new"', result.text)
        self.assertNotIn("obsolete", result.text)
        self.assertIn("multi_agent = true", result.text)
        self.assertIn("[plugins.demo]", result.text)
        self.assertIn("enabled = true", result.text)
        self.assertEqual(
            (("features", "multi_agent"), ("model",)),
            result.managed_paths,
        )

    def test_preserves_unmanaged_array_of_tables(self):
        live = """
[[skills.config]]
path = "/tmp/demo/SKILL.md"
enabled = false
"""
        result = merge_config(live, "[agents]\nmax_depth = 1\n", previous_paths=())
        self.assertIn("[[skills.config]]", result.text)
        self.assertIn('path = "/tmp/demo/SKILL.md"', result.text)
        self.assertIn("max_depth = 1", result.text)

    def test_invalid_toml_fails_before_output(self):
        with self.assertRaisesRegex(ValueError, "invalid live TOML"):
            merge_config("[broken", 'model = "x"', previous_paths=())


if __name__ == "__main__":
    unittest.main()
