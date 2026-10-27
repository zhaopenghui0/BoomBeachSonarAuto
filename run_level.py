"""按命令行参数运行指定关卡，供 Windows 启动器调用。"""

from __future__ import annotations

import argparse
import contextlib
from collections.abc import Sequence
from pathlib import Path

from config import MAX_LEVEL


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行指定海域的声呐自动探测")
    parser.add_argument(
        "--level",
        type=int,
        required=True,
        choices=range(1, MAX_LEVEL + 1),
        metavar=f"1-{MAX_LEVEL}",
        help=f"要运行的关卡（1 到 {MAX_LEVEL}）",
    )
    parser.add_argument(
        "--console-log",
        type=Path,
        help="把控制台输出写入指定文件，供图形启动器显示",
    )
    return parser.parse_args(argv)


def execute(level: int) -> int:
    # 参数检查完成后再导入 main，确保 --help 和错误参数不会连接 ADB。
    import main as automation

    automation.register_exit_cleanup()
    try:
        automation.adb.ensure_root_shell()
        automation.cleanup_reject_network("主流程启动")
        result = automation.main(level)
        return 0 if result is not None else 2
    except BaseException:
        if automation._has_pending_probe_request():
            automation.offer_manual_network_recovery()
        raise
    finally:
        automation.cleanup_weak_network("主流程结束")
        automation.cleanup_reject_network("主流程结束")


def cli(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.console_log is None:
        return execute(args.level)

    args.console_log.parent.mkdir(parents=True, exist_ok=True)
    with args.console_log.open("w", encoding="utf-8", buffering=1) as output:
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            print(f"海岛奇兵声呐助手：正在运行第 {args.level} 关", flush=True)
            try:
                return execute(args.level)
            except BaseException:
                # traceback 会通过重定向后的 stderr 写入图形界面日志文件。
                import traceback

                traceback.print_exc()
                raise


if __name__ == "__main__":
    raise SystemExit(cli())
