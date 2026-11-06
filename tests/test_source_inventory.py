from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from harness import _operational_files


class SourceInventoryTests(unittest.TestCase):
    def test_ignored_dependencies_are_not_operational_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("node_modules/\n.runtime/\n")
            source = root / "tools/server.mjs"
            dependency = root / "tools/node_modules/vendor/package.json"
            runtime = root / "tools/.runtime/log.json"
            for path in [source, dependency, runtime]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}")
            files = _operational_files(SimpleNamespace(root=root))
            self.assertIn(source, files)
            self.assertNotIn(dependency, files)
            self.assertNotIn(runtime, files)

    def test_tracked_files_are_scanned_even_when_an_ignore_rule_matches(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            source = root / "tools/kept.json"
            source.parent.mkdir()
            source.write_text("{}")
            subprocess.run(["git", "-C", str(root), "add", "tools/kept.json"], check=True)
            (root / ".gitignore").write_text("tools/\n")
            self.assertIn(source, _operational_files(SimpleNamespace(root=root)))

    def test_source_export_without_git_still_scans_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "sources/example.json"
            source.parent.mkdir()
            source.write_text("{}")
            self.assertIn(source, _operational_files(SimpleNamespace(root=root)))
