import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from utils.adb_control import AdbController, resolve_adb_executable


class AdbExecutableTests(unittest.TestCase):
    def test_uses_adb_path_override(self):
        with TemporaryDirectory() as temp_dir:
            adb_path = Path(temp_dir) / "adb.exe"
            adb_path.touch()
            with patch.dict(os.environ, {"ADB_PATH": str(adb_path)}):
                self.assertEqual(resolve_adb_executable(), str(adb_path))

    def test_rejects_missing_adb_path_override(self):
        missing = str(Path("missing") / "adb.exe")
        with patch.dict(os.environ, {"ADB_PATH": missing}):
            with self.assertRaisesRegex(FileNotFoundError, "ADB_PATH"):
                resolve_adb_executable()

    def test_controller_uses_explicit_adb_executable(self):
        adb = AdbController(auto_connect=False, adb_executable=r"C:\tools\adb.exe")
        self.assertEqual(
            adb._build_command(["devices"], device=False),
            [r"C:\tools\adb.exe", "devices"],
        )


class AdbNetworkStateTests(unittest.TestCase):
    def test_weak_network_query_detects_ipv6_only_residue(self):
        adb = AdbController(auto_connect=False)
        with (
            patch.object(adb, "_get_package_uid", return_value=10051),
            patch.object(adb, "_is_weak_network_rule_active", return_value=False),
            patch.object(adb, "_is_ip6tables_available", return_value=True),
            patch.object(
                adb,
                "_run_privileged_script",
                return_value=SimpleNamespace(returncode=0),
            ) as run_script,
        ):
            self.assertTrue(adb.is_weak_network_enabled("example.package"))

        run_script.assert_called_once_with(
            "ip6tables -C OUTPUT -m owner --uid-owner 10051 -j BBMA_WEAKNET",
            check=False,
        )

    def test_reject_network_query_detects_ipv6_only_residue(self):
        adb = AdbController(auto_connect=False)
        with (
            patch.object(adb, "_get_package_uid", return_value=10051),
            patch.object(adb, "_is_reject_network_rule_active", return_value=False),
            patch.object(adb, "_is_ip6tables_available", return_value=True),
            patch.object(
                adb,
                "_run_privileged_script",
                return_value=SimpleNamespace(returncode=0),
            ) as run_script,
        ):
            self.assertTrue(adb.is_reject_network_enabled("example.package"))

        run_script.assert_called_once_with(
            "ip6tables -C OUTPUT -m owner --uid-owner 10051 -j BBMA_REJECTNET",
            check=False,
        )


class AdbScreenshotTests(unittest.TestCase):
    def setUp(self):
        self.adb = AdbController(auto_connect=False)
        self.image = np.zeros((12, 18, 3), dtype=np.uint8)
        self.image[:, :, 1] = 127
        ok, encoded = cv2.imencode(".png", self.image)
        self.assertTrue(ok)
        self.png_bytes = encoded.tobytes()

    def test_read_screenshot_uses_exec_out_without_writing_file(self):
        result = SimpleNamespace(stdout=self.png_bytes)
        with (
            patch.object(self.adb, "_run_binary", return_value=result) as run_binary,
            patch.object(self.adb, "_write_screenshot") as write_screenshot,
        ):
            actual = self.adb.read_screenshot()

        run_binary.assert_called_once_with(["exec-out", "screencap", "-p"])
        write_screenshot.assert_not_called()
        np.testing.assert_array_equal(actual, self.image)

    def test_read_screenshot_saves_only_when_output_path_is_requested(self):
        result = SimpleNamespace(stdout=self.png_bytes)
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "截图.png"
            with patch.object(self.adb, "_run_binary", return_value=result):
                actual = self.adb.read_screenshot(path)

            self.assertTrue(path.exists())
            saved = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)

        np.testing.assert_array_equal(actual, self.image)
        np.testing.assert_array_equal(saved, self.image)

    def test_invalid_exec_out_image_falls_back_to_legacy_capture(self):
        result = SimpleNamespace(stdout=b"not a png")
        with (
            patch.object(self.adb, "_run_binary", return_value=result),
            patch.object(
                self.adb,
                "_capture_screenshot_legacy",
                return_value=self.image,
            ) as legacy,
        ):
            actual = self.adb.read_screenshot()

        legacy.assert_called_once_with()
        np.testing.assert_array_equal(actual, self.image)


if __name__ == "__main__":
    unittest.main()
