from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import pandas as pd
import streamlit as st

from data.database import add_trade, log_user_activity
from trading.kis_api import market_status_text


def render_manual_order(save_preferences: Callable[[bool], None]) -> None:
    api = st.session_state.get("broker_api")
    if api is None:
        st.info("수동 주문을 사용하려면 증권사 API를 연결하세요.")
        return

    required_methods = ("get_status", "get_balance", "buy_order", "sell_order")
    missing = [name for name in required_methods if not hasattr(api, name)]
    if missing:
        st.error("API 연결 상태가 유효하지 않습니다. 다시 연결해 주세요.")
        return

    try:
        status = api.get_status()
    except Exception as e:
        st.error(f"API 상태 조회 실패: {e}")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("연결 상태", "연결됨" if status.get("has_token") else "미연결")
    c2.metric("증권사", str(st.session_state.get("broker_name") or "-"))
    c3.metric("계좌", str(status.get("account") or "-"))
    st.caption(market_status_text())

    if st.button("💰 잔고 조회", use_container_width=True, key="stock_btn_balance"):
        username = str(st.session_state.get("user", {}).get("username") or "")
        if username:
            log_user_activity(username, "balance_checked", "", "매매(국내주식)")
        try:
            with st.spinner("잔고 조회 중..."):
                bal = api.get_balance()
        except Exception as e:
            st.error(f"잔고 조회 실패: {e}")
            bal = {"error": str(e)}
        if "error" in bal:
            st.error(f"잔고 조회 실패: {bal['error']}")
        else:
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("예수금", f"{int(bal.get('예수금', 0)):,}원")
            b2.metric("총매입금액", f"{int(bal.get('총매입금액', 0)):,}원")
            b3.metric("총평가금액", f"{int(bal.get('총평가금액', 0)):,}원")
            pnl = int(bal.get("총평가손익", 0))
            b4.metric("총평가손익", f"{pnl:+,}원", delta=f"{pnl:+,}")

            holdings = bal.get("holdings", [])
            if holdings:
                st.markdown("##### 보유 종목")
                st.dataframe(
                    pd.DataFrame(holdings),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "수익률": st.column_config.NumberColumn(format="%.2f%%"),
                        "평가금액": st.column_config.NumberColumn(format="%d"),
                        "평가손익": st.column_config.NumberColumn(format="%d"),
                    },
                )
            else:
                st.info("보유 종목이 없습니다.")

    st.markdown("---")

    def place(side: str, ticker: str, qty: int, price: int) -> None:
        try:
            result = api.buy_order(ticker, qty, price) if side == "BUY" else api.sell_order(ticker, qty, price)
        except Exception as e:
            st.error(f"주문 요청 실패: {e}")
            return

        if result.get("status") == "success":
            add_trade(ticker, "KR", side, price, qty, "수동 주문")
            st.session_state.setdefault("trade_log", []).append(
                f"[{datetime.now().strftime('%H:%M:%S')}] {side} {ticker} x{qty}"
            )
            st.session_state["stock_last_ticker"] = ticker
            st.session_state["stock_buy_ticker"] = ticker
            st.session_state["stock_sell_ticker"] = ticker

            username = str(st.session_state.get("user", {}).get("username") or "")
            if username:
                save_preferences(True)
                log_user_activity(username, "order_placed", f"{side} {ticker} x{qty}", "매매(국내주식)")
            st.success(f"{side} 주문 완료")
        else:
            st.error(str(result.get("error") or "주문 실패"))

    left, right = st.columns(2)
    with left:
        st.markdown("**매수 주문**")
        buy_code = st.text_input("매수 종목코드", placeholder="005930", key="stock_buy_ticker")
        buy_qty = int(st.number_input("매수 수량", min_value=1, value=1, key="stock_buy_qty"))
        buy_price = int(st.number_input("매수 가격 (0=시장가)", min_value=0, value=0, step=1, format="%d", key="stock_buy_price"))
        if st.button("매수 주문", key="stock_buy_btn", type="primary"):
            place("BUY", buy_code, buy_qty, buy_price)
    with right:
        st.markdown("**매도 주문**")
        sell_code = st.text_input("매도 종목코드", placeholder="005930", key="stock_sell_ticker")
        sell_qty = int(st.number_input("매도 수량", min_value=1, value=1, key="stock_sell_qty"))
        sell_price = int(st.number_input("매도 가격 (0=시장가)", min_value=0, value=0, step=1, format="%d", key="stock_sell_price"))
        if st.button("매도 주문", key="stock_sell_btn", type="primary"):
            place("SELL", sell_code, sell_qty, sell_price)
