"""Unified local verification runner for Archon stock-platform.

Default pipeline:
1) Python compile check (views/tests/scripts)
2) Pytest full suite

Optional:
3) Real UI persistence check (Playwright)

Examples:
  python scripts/run_checks.py
  python scripts/run_checks.py --with-ui
  python scripts/run_checks.py --pytest-args "-q"
"""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run(cmd: list[str], cwd: Path) -> int:
    print(f"\n[RUN] {' '.join(cmd)}")
    completed = subprocess.run(cmd, cwd=str(cwd), check=False)
    print(f"[EXIT {completed.returncode}] {' '.join(cmd)}")
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local verification checks")
    parser.add_argument("--skip-compile", action="store_true", help="Skip compileall syntax checks")
    parser.add_argument("--skip-pytest", action="store_true", help="Skip pytest")
    parser.add_argument("--with-ui", action="store_true", help="Include Playwright UI persistence check")
    parser.add_argument("--pytest-args", default="", help="Extra args for pytest, e.g. '-q -k analysis'")
    args = parser.parse_args()

    root = _repo_root()
    overall_ok = True

    if not args.skip_compile:
        compile_targets = [
            "views",
            "tests",
            "scripts/ui_check_analysis_pred_toggle.py",
            "scripts/ui_check_analysis_chart_toggles.py",
            "scripts/ui_check_analysis_full_subsections.py",
            "scripts/ui_check_analysis_user_switch_isolation.py",
            "scripts/ui_check_data_analysis_blank_state.py",
            "scripts/ui_check_ai_recommendation_non_empty.py",
            "scripts/ui_check_login_navigation_persistence.py",
            "scripts/run_checks.py",
        ]
        rc = _run([sys.executable, "-m", "compileall", *compile_targets], cwd=root)
        if rc != 0:
            overall_ok = False

    if not args.skip_pytest:
        pytest_cmd = ["pytest"]
        if args.pytest_args.strip():
            pytest_cmd.extend(shlex.split(args.pytest_args))
        rc = _run(pytest_cmd, cwd=root)
        if rc != 0:
            overall_ok = False

    if args.with_ui:
        rc_pred = _run([sys.executable, "scripts/ui_check_analysis_pred_toggle.py"], cwd=root)
        if rc_pred != 0:
            overall_ok = False
        rc_chart = _run([sys.executable, "scripts/ui_check_analysis_chart_toggles.py"], cwd=root)
        if rc_chart != 0:
            overall_ok = False
        rc_full = _run([sys.executable, "scripts/ui_check_analysis_full_subsections.py"], cwd=root)
        if rc_full != 0:
            overall_ok = False
        rc_isolation = _run([sys.executable, "scripts/ui_check_analysis_user_switch_isolation.py"], cwd=root)
        if rc_isolation != 0:
            overall_ok = False
        rc_blank = _run([sys.executable, "scripts/ui_check_data_analysis_blank_state.py"], cwd=root)
        if rc_blank != 0:
            overall_ok = False
        rc_recommend = _run([sys.executable, "scripts/ui_check_ai_recommendation_non_empty.py"], cwd=root)
        if rc_recommend != 0:
            overall_ok = False
        rc_login_nav = _run([sys.executable, "scripts/ui_check_login_navigation_persistence.py"], cwd=root)
        if rc_login_nav != 0:
            overall_ok = False

    if overall_ok:
        print("\n[PASS] Requested checks completed successfully.")
        return 0

    print("\n[FAIL] One or more checks failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
