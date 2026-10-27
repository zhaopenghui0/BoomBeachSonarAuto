"""PyInstaller 单文件运行器入口，由图形启动器在后台调用。"""

from __future__ import annotations

import multiprocessing
import sys
from pathlib import Path

import run_level


def main() -> int:
    multiprocessing.freeze_support()
    if sys.argv[1:] == ["--self-test"]:
        from config import SAVED_POINTS_FILE, TEMPLATE_DIR
        from utils.adb_control import resolve_adb_executable

        adb_path = Path(resolve_adb_executable())
        required_paths = [
            adb_path,
            adb_path.with_name("AdbWinApi.dll"),
            adb_path.with_name("AdbWinUsbApi.dll"),
            TEMPLATE_DIR / "activity_button.png",
            SAVED_POINTS_FILE,
        ]
        missing = [str(path) for path in required_paths if not path.is_file()]
        if missing:
            print("MISSING=" + "|".join(missing))
            return 1
        print("STANDALONE_OK")
        print(f"ADB={adb_path}")
        print(f"TEMPLATE_DIR={TEMPLATE_DIR}")
        return 0
    return run_level.cli(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
