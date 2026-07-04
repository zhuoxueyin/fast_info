"""
fastInfo · 回归测试运行脚本
===========================
用法:
    python scripts/run_regression.py              # 运行全部回归测试
    python scripts/run_regression.py --smoke      # 仅冒烟测试
    python scripts/run_regression.py --fast       # 快速模式（跳过慢速测试）
    python scripts/run_regression.py -k auth      # 按关键字过滤
    python scripts/run_regression.py --report     # 生成 HTML 报告
"""

from __future__ import annotations
import subprocess
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = PROJECT_ROOT / "tests"


def banner(text: str):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def run_tests(args: list[str]) -> int:
    """运行 pytest,返回 exit code"""
    cmd = [sys.executable, "-m", "pytest"] + args
    print(f"\n[run_regression] {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="fastInfo 回归测试运行器")
    parser.add_argument("--smoke", action="store_true", help="仅冒烟测试（核心链路）")
    parser.add_argument("--fast", action="store_true", help="快速模式（跳过慢速测试）")
    parser.add_argument("--report", action="store_true", help="生成 HTML 报告")
    parser.add_argument("--no-cleanup", action="store_true", help="运行后不清理测试数据")
    parser.add_argument("-k", "--keyword", type=str, default="", help="按关键字过滤测试")
    parser.add_argument("-x", "--exitfirst", action="store_true", help="首次失败即停止")
    parser.add_argument("--quiet", action="store_true", help="安静模式")
    args_extra = parser.parse_args()

    banner(f"fastInfo 回归测试 · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 构建 pytest 参数
    pytest_args = [str(TESTS_DIR)]

    if args_extra.quiet:
        pytest_args.extend(["-q", "--no-header"])
    else:
        pytest_args.append("-v")

    if args_extra.smoke:
        pytest_args.extend(["-m", "smoke"])

    if args_extra.fast:
        pytest_args.extend(["-m", "not slow"])

    if args_extra.keyword:
        pytest_args.extend(["-k", args_extra.keyword])

    if args_extra.exitfirst:
        pytest_args.append("-x")

    if args_extra.report:
        report_dir = PROJECT_ROOT / "data" / "test-reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_file = report_dir / f"regression_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        pytest_args.extend([
            "--html", str(report_file),
            "--self-contained-html",
        ])
        print(f"[run_regression] Report will be saved to: {report_file}")

    pytest_args.extend(["--tb=short", "--strict-markers"])

    # Run
    exit_code = run_tests(pytest_args)

    # Cleanup
    if not args_extra.no_cleanup:
        print("\n[run_regression] Cleaning test data...")
        from tests.conftest import _cleanup_prefix
        deleted = _cleanup_prefix()
        total = sum(deleted.values())
        print(f"  Total cleaned: {total}")
    else:
        print("\n[run_regression] Skip cleanup (--no-cleanup)")

    # Summary
    banner(f"Regression {'PASSED' if exit_code == 0 else 'FAILED'} (exit={exit_code})")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
