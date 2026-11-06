import importlib.util
from pathlib import Path
import hashlib
import tempfile
import unittest


class EasyedaReleaseTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / "tools/easyeda-agent-trial/install-runtime.py"
        spec = importlib.util.spec_from_file_location("easyeda_release", source)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_verified_download_and_repeat_install(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "download"
            source.write_bytes(b"verified release")
            asset = {"browser_download_url": source.as_uri(), "digest": "sha256:" + hashlib.sha256(source.read_bytes()).hexdigest()}
            destination = root / "bin/easyeda"
            self.module.install_asset(asset, destination)
            source.unlink()
            self.module.install_asset(asset, destination)
            self.assertEqual(destination.read_bytes(), b"verified release")

    def test_bad_download_does_not_install(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "download"
            source.write_bytes(b"corrupted")
            destination = root / "bin/easyeda"
            with self.assertRaises(ValueError):
                self.module.install_asset({"browser_download_url": source.as_uri(), "digest": "sha256:" + "0" * 64}, destination)
            self.assertFalse(destination.exists())

    def test_existing_different_runtime_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "easyeda"
            destination.write_bytes(b"user installation")
            with self.assertRaises(ValueError):
                self.module.install_asset({"digest": "sha256:" + "0" * 64}, destination)
            self.assertEqual(destination.read_bytes(), b"user installation")
