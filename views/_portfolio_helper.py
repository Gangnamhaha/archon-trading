from typing import Any

import pandas as pd
import streamlit as st

from data.fetcher import get_crypto_price, get_fx_spot_rate
from views._portfolio_pro import render_pro_analytics


def render_holdings_table(holdings: pd.DataFrame) -> None:
    st.subheader("보유 종목 상세")
    display_df = holdings[
        [
            "id",
            "name",
            "ticker",
            "market",
            "buy_price",
            "quantity",
            "현재가",
            "매수금액",
            "평가금액",
            "평가손익",
            "수익률(%)",
        ]
    ].copy()
    display_df.columns = [
        "ID",
        "종목명",
        "코드",
        "시장",
        "매수단가",
        "수량",
        "현재가",
        "매수금액",
        "평가금액",
        "평가손익",
        "수익률(%)",
    ]

    st.dataframe(
        display_df.style.map(
            lambda v: "color: red"
            if isinstance(v, (int, float)) and v > 0
            else ("color: blue" if isinstance(v, (int, float)) and v < 0 else ""),
            subset=["평가손익", "수익률(%)"],
        ),
        use_container_width=True,
        hide_index=True,
    )


def render_rebalancing_section(tracker) -> None:
    st.subheader("⚖️ 리밸런싱 분석")
    alloc_data = tracker.get_allocation()
    if alloc_data.empty or len(alloc_data) < 2:
        return

    total_val = alloc_data["평가금액"].sum()
    alloc_data["현재비율(%)"] = (alloc_data["평가금액"] / total_val * 100).round(1)
    equal_target = round(100.0 / len(alloc_data), 1)
    alloc_data["목표비율(%)"] = equal_target
    alloc_data["차이(%)"] = (alloc_data["현재비율(%)"] - alloc_data["목표비율(%)"]).round(1)
    alloc_data["조정"] = alloc_data["차이(%)"].apply(
        lambda d: "🔴 매도 필요" if d > 5 else ("🟢 매수 필요" if d < -5 else "✅ 적정")
    )

    rebal_display = alloc_data[["name", "평가금액", "현재비율(%)", "목표비율(%)", "차이(%)", "조정"]].copy()
    rebal_display.columns = ["종목명", "평가금액", "현재비율(%)", "목표비율(%)", "차이(%)", "조정"]
    st.dataframe(rebal_display, use_container_width=True, hide_index=True)

    needs_rebal = alloc_data[alloc_data["차이(%)"].abs() > 5]
    if not needs_rebal.empty:
        st.warning(f"⚠️ {len(needs_rebal)}개 종목이 목표 비율 대비 5%p 이상 벗어났습니다. 리밸런싱을 검토하세요.")
    else:
        st.success("✅ 모든 종목이 균등 배분 기준 ±5%p 이내입니다.")

    st.caption("※ 목표비율은 균등 배분 기준입니다. 향후 사용자 지정 비율 설정 기능이 추가될 예정입니다.")


def render_fx_crypto_alert_tabs() -> None:
    st.markdown("---")
    st.subheader("💱 FX · 🪙 코인 자산 현황")

    fx_tab, crypto_tab, alert_tab = st.tabs(["💱 외환 포지션", "🪙 코인 포지션", "🔔 가격 알림"])

    with fx_tab:
        fx_log = st.session_state.get("fx_trade_log", [])
        fx_pos = st.session_state.get("fx_position")
        if fx_pos:
            fx_pair = str(fx_pos.get("pair", st.session_state.get("fx_pair", "")))
            fx_entry = float(fx_pos.get("entry_rate", 0))
            fx_curr = get_fx_spot_rate(fx_pair) if fx_pair else 0.0
            fx_pct = (fx_curr / fx_entry - 1) * 100 if fx_entry else 0.0
            direction = str(fx_pos.get("direction", ""))
            lot = int(fx_pos.get("lot", 0))
            pc1, pc2, pc3, pc4 = st.columns(4)
            pc1.metric("보유 통화쌍", fx_pair)
            pc2.metric("진입 환율", f"{fx_entry:.4f}")
            pc3.metric("현재 환율", f"{fx_curr:.4f}")
            pc4.metric("평가손익", f"{fx_pct:+.2f}%", delta=f"{direction} {lot:,}단위")
        else:
            st.info("현재 FX 포지션이 없습니다. 외환자동매매 페이지에서 오토파일럿을 시작하세요.")
        if fx_log:
            with st.expander(f"FX 거래 로그 ({len(fx_log)}건)", expanded=False):
                st.text("\n".join(fx_log[-20:]))

    with crypto_tab:
        crypto_pos = st.session_state.get("c_position")
        crypto_log = st.session_state.get("c_trade_log", [])
        if crypto_pos:
            symbol = str(crypto_pos.get("symbol", st.session_state.get("c_symbol", "")))
            entry = float(crypto_pos.get("entry_price", 0))
            curr = get_crypto_price(symbol) if symbol else 0.0
            amount = float(crypto_pos.get("amount", 0))
            pct = (curr / entry - 1) * 100 if entry else 0.0
            pnl_usd = (curr - entry) * amount
            cc1, cc2, cc3, cc4 = st.columns(4)
            cc1.metric("보유 코인", symbol)
            cc2.metric("매수가", f"${entry:,.2f}")
            cc3.metric("현재가", f"${curr:,.2f}")
            cc4.metric("평가손익", f"{pct:+.2f}%", delta=f"${pnl_usd:+.2f}")
        else:
            st.info("현재 코인 포지션이 없습니다. 코인자동매매 페이지에서 오토파일럿을 시작하세요.")
        if crypto_log:
            with st.expander(f"코인 거래 로그 ({len(crypto_log)}건)", expanded=False):
                st.text("\n".join(crypto_log[-20:]))

    with alert_tab:
        st.caption("목표 가격 도달 시 화면에 알림을 표시합니다.")
        if "price_alerts" not in st.session_state:
            st.session_state["price_alerts"] = []

        with st.form("add_alert_form"):
            alert_col1, alert_col2, alert_col3 = st.columns(3)
            with alert_col1:
                alert_type = str(st.selectbox("자산 유형", ["코인", "외환"]) or "코인")
            with alert_col2:
                from data.fetcher import CRYPTO_PAIRS, FX_PAIRS

                symbols = list(CRYPTO_PAIRS.keys()) if alert_type == "코인" else list(FX_PAIRS.keys())
                alert_symbol = str(st.selectbox("종목", symbols) or symbols[0])
            with alert_col3:
                alert_price = float(st.number_input("목표 가격", min_value=0.0001, value=100.0, step=1.0))
            alert_direction = str(st.selectbox("조건", ["이상 (상단 돌파)", "이하 (하단 이탈)"]) or "이상 (상단 돌파)")
            alert_submitted = st.form_submit_button("알림 추가", use_container_width=True)

        if alert_submitted:
            st.session_state["price_alerts"].append(
                {
                    "type": alert_type,
                    "symbol": alert_symbol,
                    "price": alert_price,
                    "direction": alert_direction,
                    "triggered": False,
                }
            )
            st.success(f"알림 추가: {alert_symbol} {alert_direction} {alert_price:,.4f}")

        alerts = st.session_state.get("price_alerts", [])
        if alerts:
            for idx, alert in enumerate(alerts):
                if alert.get("triggered"):
                    continue
                symbol = str(alert["symbol"])
                curr = get_crypto_price(symbol) if alert["type"] == "코인" else get_fx_spot_rate(symbol)
                target = float(alert["price"])
                if (curr >= target) if "이상" in str(alert["direction"]) else (curr <= target):
                    st.toast(f"🔔 {symbol} 알림 도달! 현재: {curr:,.4f} / 목표: {target:,.4f}")
                    st.session_state["price_alerts"][idx]["triggered"] = True

            alert_df = pd.DataFrame(
                [
                    {
                        "자산": alert["symbol"],
                        "유형": alert["type"],
                        "조건": alert["direction"],
                        "목표가": alert["price"],
                        "상태": "✅ 도달" if alert.get("triggered") else "⏳ 대기",
                    }
                    for alert in alerts
                ]
            )
            st.dataframe(alert_df, use_container_width=True, hide_index=True)

            if st.button("완료된 알림 삭제", use_container_width=True):
                st.session_state["price_alerts"] = [alert for alert in alerts if not alert.get("triggered")]
                st.rerun()
        else:
            st.info("설정된 알림이 없습니다.")
