"""
서버 사이드 오토파일럿 엔진
- Streamlit 세션과 독립된 백그라운드 스레드로 실행
- 모바일 화면 잠금 / 브라우저 탭 전환에도 계속 동작
"""
import json
import importlib
import os
import sys
import threading
from datetime import datetime, timedelta
from typing import Any

_ENGINE_LOCK = threading.Lock()
_RUNNING_THREADS: dict[str, threading.Thread] = {}
_STOP_FLAGS: dict[str, threading.Event] = {}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _engine_key(username: str, slot_idx: int) -> str:
    return f"{username}::{slot_idx}"


def _run_slot(username: str, slot_idx: int, stop_event: threading.Event) -> None:
    from data.database import (
        get_autopilot_jobs,
        update_autopilot_job_state,
        add_autopilot_log,
        add_trade,
        stop_autopilot_job,
    )

    def log(msg: str, level: str = "info") -> None:
        add_autopilot_log(username, slot_idx, level, msg)

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    log(f"🚀 AP-{slot_idx+1} 백그라운드 엔진 시작 ({datetime.now().strftime('%H:%M:%S')})")

    while not stop_event.is_set():
        try:
            jobs = get_autopilot_jobs(username)
            job = next((j for j in jobs if _to_int(j["slot_idx"]) == slot_idx), None)
            if not job or str(job["status"]) != "running":
                log(f"AP-{slot_idx+1} 작업이 중지됐습니다.")
                break

            market = str(job["market"])
            mode = str(job["mode"])
            capital = _to_int(job["capital"])
            max_stocks = _to_int(job["max_stocks"])
            max_per = _to_int(job["max_per"])
            sl = _to_float(job["stop_loss"])
            tp = _to_float(job["take_profit"])
            daily_limit = _to_float(job["daily_limit"])
            usdkrw_val = _to_float(job["usdkrw"])
            usdkrw = usdkrw_val if usdkrw_val > 0 else 1350.0
            is_us = market == "US"
            capital_base = float(capital) / usdkrw if is_us else float(capital)
            market_code = "US" if is_us else "KR"

            try:
                holdings: dict[str, dict[str, Any]] = json.loads(str(job["holdings"]) or "{}")
            except Exception:
                holdings = {}

            daily_pnl = _to_float(job["daily_pnl"])
            run_count = _to_int(job["run_count"]) + 1

            log(f"[{datetime.now().strftime('%H:%M:%S')}] AP-{slot_idx+1} 스캔 #{run_count} 시작 | {market} | {mode}")

            if is_us:
                try:
                    recommend_us = importlib.import_module("pages.util_ap_us").recommend_us
                    sdf = recommend_us(mode=mode, max_stocks=max_stocks)
                except Exception as e:
                    sdf = None
                    log(f"US 추천 모듈 오류: {e}", "error")
            else:
                try:
                    if "공격" in mode:
                        from analysis.recommender import recommend_aggressive_stocks
                        sdf = recommend_aggressive_stocks(market=market, top_n=100, result_count=max_stocks)
                    else:
                        from analysis.recommender import recommend_stocks
                        sdf = recommend_stocks(market=market, top_n=50, result_count=max_stocks)
                except Exception as e:
                    sdf = None
                    log(f"스캔 실패: {e}", "error")

            try:
                if sdf is None:
                    log(f"추천 결과 없음 | {market} | mode={mode}", "warn")
                elif getattr(sdf, "empty", True):
                    log(f"추천 결과 없음 | {market} | mode={mode}", "warn")
                else:
                    log(f"추천 결과 {len(sdf)}건 | {market} | mode={mode}")
            except Exception:
                pass

            if sdf is not None and not sdf.empty:
                now_str = datetime.now().strftime("%H:%M:%S")
                import pandas as pd
                for _, r in sdf.iterrows():
                    tk = str(r["종목코드"])
                    pr = float(r["현재가"])
                    name = str(r["종목명"])
                    if tk in holdings:
                        ent = holdings[tk]
                        pct = (pr / float(ent["avg_price"]) - 1) * 100
                        daily_pnl += pct * float(ent["qty"]) * float(ent["avg_price"]) / max(capital_base, 1.0) * 100
                        if pct <= -sl:
                            add_trade(tk, market_code, "SELL", pr, int(ent["qty"]), f"AP-{slot_idx+1} 손절(백그라운드)")
                            log(f"[{now_str}] 손절: {name} {pct:+.1f}%", "warn")
                            del holdings[tk]
                        elif pct >= tp:
                            add_trade(tk, market_code, "SELL", pr, int(ent["qty"]), f"AP-{slot_idx+1} 익절(백그라운드)")
                            log(f"[{now_str}] 익절: {name} {pct:+.1f}%", "info")
                            del holdings[tk]
                    else:
                        if len(holdings) < max_stocks:
                            ps = capital_base * (max_per / 100)
                            qty = max(1, int(ps // pr)) if pr > 0 else 0
                            if qty > 0:
                                add_trade(tk, market_code, "BUY", pr, qty, f"AP-{slot_idx+1} 매수(백그라운드)")
                                holdings[tk] = {"avg_price": pr, "qty": qty, "name": name}
                                log(f"[{now_str}] 매수: {name} x{qty} @ {pr:,.0f}", "info")

                if daily_pnl <= -daily_limit:
                    for t, hh in list(holdings.items()):
                        add_trade(t, market_code, "SELL", float(hh["avg_price"]), int(hh["qty"]), f"AP-{slot_idx+1} 강제청산(백그라운드)")
                        log(f"강제청산: {hh['name']}", "warn")
                    holdings = {}
                    stop_autopilot_job(username, slot_idx)
                    log(f"AP-{slot_idx+1} 일일 손실 한도 도달 → 자동 중지", "error")
                    break

            next_run = (datetime.now() + timedelta(seconds=300)).isoformat()

            update_autopilot_job_state(
                username=username,
                slot_idx=slot_idx,
                holdings=json.dumps(holdings, ensure_ascii=False),
                daily_pnl=daily_pnl,
                run_count=run_count,
                next_run_at=next_run,
            )

        except Exception as e:
            try:
                add_autopilot_log(username, slot_idx, "error", f"엔진 오류: {e}")
            except Exception:
                pass

        stop_event.wait(timeout=300)

    try:
        add_autopilot_log(username, slot_idx, "info",
                          f"AP-{slot_idx+1} 백그라운드 엔진 종료 ({datetime.now().strftime('%H:%M:%S')})")
    except Exception:
        pass

    key = _engine_key(username, slot_idx)
    with _ENGINE_LOCK:
        _RUNNING_THREADS.pop(key, None)
        _STOP_FLAGS.pop(key, None)


def start_background_autopilot(username: str, slot_idx: int, **kwargs: Any) -> bool:
    """백그라운드 스레드로 오토파일럿 시작. 이미 실행 중이면 False 반환."""
    key = _engine_key(username, slot_idx)
    with _ENGINE_LOCK:
        existing = _RUNNING_THREADS.get(key)
        if existing and existing.is_alive():
            return False

        from data.database import upsert_autopilot_job
        upsert_autopilot_job(username=username, slot_idx=slot_idx, status="running", **kwargs)

        stop_event = threading.Event()
        _STOP_FLAGS[key] = stop_event
        t = threading.Thread(
            target=_run_slot,
            args=(username, slot_idx, stop_event),
            daemon=True,
            name=f"archon-ap-{username}-{slot_idx}",
        )
        _RUNNING_THREADS[key] = t
        t.start()
    return True


def stop_background_autopilot(username: str, slot_idx: int) -> None:
    """백그라운드 오토파일럿 중지."""
    key = _engine_key(username, slot_idx)
    with _ENGINE_LOCK:
        flag = _STOP_FLAGS.get(key)
        if flag:
            flag.set()
    from data.database import stop_autopilot_job
    stop_autopilot_job(username, slot_idx)


def stop_all_background_autopilots(username: str) -> None:
    """해당 사용자의 모든 백그라운드 오토파일럿 중지."""
    for key, flag in list(_STOP_FLAGS.items()):
        if key.startswith(f"{username}::"):
            flag.set()
    from data.database import get_autopilot_jobs, stop_autopilot_job
    for job in get_autopilot_jobs(username):
        raw_slot = job.get("slot_idx")
        if isinstance(raw_slot, (int, float, str)):
            stop_autopilot_job(username, int(raw_slot))


def is_running(username: str, slot_idx: int) -> bool:
    """스레드가 살아있는지 확인."""
    key = _engine_key(username, slot_idx)
    t = _RUNNING_THREADS.get(key)
    return bool(t and t.is_alive())


def get_running_count(username: str) -> int:
    return sum(1 for k, t in _RUNNING_THREADS.items()
               if k.startswith(f"{username}::") and t.is_alive())
