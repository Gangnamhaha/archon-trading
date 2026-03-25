"""Direct engine check: US autopilot scan produces recommendations and logs.

This validates the US autopilot backend path without needing browser UI:
- start_background_autopilot(market='US')
- wait for scan log + '추천 결과 N건 | US' log
- stop autopilot

Run:
  python scripts/check_autopilot_us_engine.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = _repo_root()
    sys.path.insert(0, str(root))

    from auth.core import create_user, delete_user, verify_user
    from data import database
    from data.database import create_session_token, get_autopilot_logs
    from trading.autopilot_engine import start_background_autopilot, stop_background_autopilot

    database.init_db()

    username = f"ap_us_{int(time.time())}"
    password = f"P@ss-{int(time.time())}"

    if not create_user(username, password, role="user", plan="pro"):
        raise RuntimeError("Failed to create user")
    user = verify_user(username, password)
    if user is None:
        raise RuntimeError("Failed to verify user")
    raw_id = user.get("id")
    if isinstance(raw_id, int):
        user_id = raw_id
    elif isinstance(raw_id, str) and raw_id.isdigit():
        user_id = int(raw_id)
    else:
        raise RuntimeError(f"Unexpected user id type: {type(raw_id).__name__}")

    # Create a token just to emulate normal session setup (not used by engine).
    _ = create_session_token(username=username, user_id=user_id, role="user", plan="pro")

    try:
        started = start_background_autopilot(
            username=username,
            slot_idx=0,
            market="US",
            mode="일반 추천",
            capital=1_000_000,
            max_stocks=2,
            max_per=50,
            stop_loss=5.0,
            take_profit=15.0,
            daily_limit=10.0,
            usdkrw=1350.0,
        )
        if not started:
            raise RuntimeError("Autopilot thread did not start")

        deadline = time.time() + 45
        saw_scan = False
        saw_recs = False
        while time.time() < deadline:
            logs = get_autopilot_logs(username, 0, limit=80)
            if isinstance(logs, list):
                joined = "\n".join([str(x) for x in logs])
            else:
                joined = str(logs)

            if "스캔 #" in joined and "| US |" in joined:
                saw_scan = True
            if "추천 결과" in joined and "| US |" in joined and "결과 없음" not in joined:
                saw_recs = True

            if saw_scan and saw_recs:
                break
            time.sleep(1.0)

        if not saw_scan:
            raise AssertionError("Did not observe US scan log")
        if not saw_recs:
            raise AssertionError("Did not observe non-empty US recommendation log")

        print("[PASS] US autopilot engine produced scan + recommendation logs.")
        return 0
    finally:
        try:
            stop_background_autopilot(username, 0)
        except Exception:
            pass
        try:
            delete_user(user_id)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
