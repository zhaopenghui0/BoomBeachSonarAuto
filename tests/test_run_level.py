import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import run_level


class RunLevelTests(unittest.TestCase):
    def test_parse_level(self):
        self.assertEqual(run_level.parse_args(["--level", "18"]).level, 18)

    def test_rejects_out_of_range_level(self):
        with self.assertRaises(SystemExit):
            run_level.parse_args(["--level", "51"])

    @patch("run_level.execute", return_value=0)
    def test_cli_passes_selected_level(self, execute):
        self.assertEqual(run_level.cli(["--level", "7"]), 0)
        execute.assert_called_once_with(7)

    @patch("run_level.execute", return_value=0)
    def test_cli_writes_gui_console_log(self, execute):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "launcher.log"
            self.assertEqual(
                run_level.cli(
                    ["--level", "12", "--console-log", str(path)]
                ),
                0,
            )
            self.assertIn("第 12 关", path.read_text(encoding="utf-8"))
        execute.assert_called_once_with(12)


if __name__ == "__main__":
    unittest.main()
