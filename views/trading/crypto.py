from datetime import datetime
from typing import Any, cast

import streamlit as st

from config.auth import is_paid, is_pro, require_auth
from config.styles import inject_pro_css, load_user_preferences, save_user_preferences, show_legal_disclaimer
from data.database import add_trade, get_trades, log_user_activity
from data.fetcher import CRYPTO_PAIRS, fetch_crypto, get_crypto_price
from views.trading._crypto_exchange import render_exchange_api_tab


def _run_signal(df_run: Any, strategy: str, cur_price: float) -> str:
    close_r = cast(Any, df_run["Close"])
    if strategy == "MA 크로스":
        ma5, ma20 = float(close_r.rolling(5).mean().iloc[-1]), float(close_r.rolling(20).mean().iloc[-1])
        ma5p, ma20p = float(close_r.rolling(5).mean().iloc[-2]), float(close_r.rolling(20).mean().iloc[-2])
        return "BUY" if ma5p <= ma20p and ma5 > ma20 else ("SELL" if ma5p >= ma20p and ma5 < ma20 else "HOLD")
    if strategy == "RSI 역추세":
        delta = cast(Any, close_r.diff())
        gain = cast(Any, delta.clip(lower=0).rolling(14).mean())
        loss = cast(Any, (-delta.clip(upper=0)).rolling(14).mean())
        rsi = float((100 - 100 / (1 + gain / loss.replace(0, 1e-10))).iloc[-1])
        return "BUY" if rsi < 30 else ("SELL" if rsi > 70 else "HOLD")
    if strategy == "볼린저 밴드 돌파":
        ma20b = cast(Any, close_r.rolling(20).mean())
        std20 = cast(Any, close_r.rolling(20).std())
        upper, lower = float((ma20b + 2 * std20).iloc[-1]), float((ma20b - 2 * std20).iloc[-1])
        return "BUY" if cur_price < lower else ("SELL" if cur_price > upper else "HOLD")
    ret7 = float((close_r.iloc[-1] / close_r.iloc[-8] - 1) * 100) if len(close_r) >= 8 else 0.0
    ret3 = float((close_r.iloc[-1] / close_r.iloc[-4] - 1) * 100) if len(close_r) >= 4 else 0.0
    return "BUY" if ret7 > 5 and ret3 > 1 else ("SELL" if ret7 < -5 and ret3 < -1 else "HOLD")


def render_crypto(user: dict[str, object]) -> None:
    _ = (require_auth, inject_pro_css, is_paid)
    username = str(user["username"])
    if not is_pro(user):
        st.warning("코인 자동매매는 Pro 플랜 전용입니다.")
        st.stop()

    visit_key = f"_visit_logged_crypto_{username}"
    if not st.session_state.get(visit_key):
        log_user_activity(username, "page_visit", "", "매매(코인)")
        st.session_state[visit_key] = True

    saved_crypto = load_user_preferences(username, "trading_crypto")

    st.title("🪙 코인 자동매매 (Crypto Autopilot)")
    st.caption("주요 암호화폐의 기술적 지표 기반 시뮬레이션 자동매매 | 실제 거래소 API 연결 시 실거래 가능")

    coins = list(CRYPTO_PAIRS.keys())
    defaults = {
        "c_symbol": str(saved_crypto.get("last_coin", "BTC/USD") or "BTC/USD"),
        "c_capital_usd": 1000.0,
        "c_amount": 0.001,
        "c_sl_pct": 2.0,
        "c_tp_pct": 4.0,
        "c_strategy": str(saved_crypto.get("last_strategy", "MA 크로스") or "MA 크로스"),
        "c_exchange": str(saved_crypto.get("last_exchange", "시뮬레이션") or "시뮬레이션"),
        "c_running": False,
        "c_position": None,
        "c_trade_log": [],
        "c_pnl": 0.0,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
    st.session_state.setdefault("c_strat_sel", str(st.session_state.get("c_strategy") or "MA 크로스"))
    st.session_state.setdefault(
        "_crypto_pref_last",
        (
            str(st.session_state.get("c_exchange") or "시뮬레이션"),
            str(st.session_state.get("c_symbol") or "BTC/USD"),
            str(st.session_state.get("c_strategy") or "MA 크로스"),
        ),
    )

    tab1, tab2, tab3, tab4 = st.tabs(["📊 시장 현황", "⚡ 자동매매", "📋 거래 로그", "🔑 거래소 API 연결"])

    with tab1:
        st.subheader("주요 코인 현재 가격 (USD)")
        top_coins = ["BTC/USD", "ETH/USD", "BNB/USD", "XRP/USD", "SOL/USD", "ADA/USD", "DOGE/USD", "AVAX/USD"]
        cols = st.columns(4)
        for idx, coin in enumerate(top_coins):
            price = get_crypto_price(coin)
            cols[idx % 4].metric(coin, f"${price:,.2f}" if price else "로딩중...")

        st.markdown("---")
        chart_coin = str(st.selectbox("차트 조회", coins, key="c_chart_coin") or coins[0])
        chart_period = str(st.selectbox("기간", ["1mo", "3mo", "6mo", "1y"], index=2, key="c_period") or "6mo")
        if st.button("차트 불러오기", use_container_width=True, key="c_load_chart"):
            with st.spinner("데이터 로딩 중..."):
                df_c = fetch_crypto(chart_coin, period=chart_period)
            if df_c.empty:
                st.error("데이터를 가져올 수 없습니다.")
            else:
                import plotly.graph_objects as go
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df_c.index, open=df_c["Open"], high=df_c["High"], low=df_c["Low"], close=df_c["Close"], name=chart_coin))
                fig.add_trace(go.Scatter(x=df_c.index, y=df_c["Close"].rolling(20).mean(), name="MA20", line=dict(color="#38BDF8", width=1)))
                fig.add_trace(go.Scatter(x=df_c.index, y=df_c["Close"].rolling(60).mean(), name="MA60", line=dict(color="#F97316", width=1)))
                fig.update_layout(plot_bgcolor="#0E1117", paper_bgcolor="#0E1117", font_color="#E2E8F0", height=420, xaxis_rangeslider_visible=False, title=f"{chart_coin} 캔들차트")
                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("코인 오토파일럿 설정")
        c1, c2 = st.columns(2)
        with c1:
            exchange = str(st.selectbox("거래소", ["시뮬레이션", "업비트", "바이낸스"], key="c_exchange") or "시뮬레이션")
            symbol = str(st.selectbox("코인", coins, index=coins.index(st.session_state["c_symbol"]) if st.session_state["c_symbol"] in coins else 0) or coins[0])
            capital = float(st.number_input("투자금 (USD)", min_value=10.0, value=float(st.session_state["c_capital_usd"]), step=10.0))
            amount = float(st.number_input("1회 매매 수량", min_value=0.0001, value=float(st.session_state["c_amount"]), step=0.001, format="%.4f"))
            strategy_opts = ["MA 크로스", "RSI 역추세", "볼린저 밴드 돌파", "모멘텀 추종"]
            if st.session_state.get("c_strat_sel") not in strategy_opts:
                st.session_state["c_strat_sel"] = strategy_opts[0]
            strategy = str(
                st.selectbox(
                    "전략",
                    strategy_opts,
                    index=strategy_opts.index(str(st.session_state.get("c_strat_sel") or strategy_opts[0])),
                    key="c_strat_sel",
                )
                or "MA 크로스"
            )
        with c2:
            sl = float(st.slider("손절 (%)", 1.0, 10.0, float(st.session_state["c_sl_pct"]), 0.5))
            tp = float(st.slider("익절 (%)", 1.0, 20.0, float(st.session_state["c_tp_pct"]), 0.5))
            st.info(f"거래소: {exchange}\n\n코인: {symbol}\n\n현재가: ${get_crypto_price(symbol):,.2f} | 수량: {amount:.4f}\n\n손절 -{sl}% / 익절 +{tp}%")

        current_pref = (exchange, symbol, strategy)
        if current_pref != st.session_state.get("_crypto_pref_last"):
            save_user_preferences(
                username,
                "trading_crypto",
                {
                    "last_exchange": exchange,
                    "last_coin": symbol,
                    "last_strategy": strategy,
                },
            )
            log_user_activity(username, "settings_changed", "코인 자동매매 설정 변경", "매매(코인)")
            st.session_state["_crypto_pref_last"] = current_pref

        if st.session_state["c_running"]:
            if st.button("⏹️ 오토파일럿 중지", type="primary", use_container_width=True, key="c_stop"):
                st.session_state.update({"c_running": False, "c_position": None})
                st.rerun()
        elif st.button("▶️ 오토파일럿 시작", type="primary", use_container_width=True, key="c_start"):
            st.session_state.update({"c_symbol": symbol, "c_capital_usd": capital, "c_amount": amount, "c_sl_pct": sl, "c_tp_pct": tp, "c_strategy": strategy, "c_running": True, "c_pnl": 0.0})
            st.rerun()

        if st.session_state["c_running"]:
            st.success(f"🟢 코인 오토파일럿 실행 중 | {st.session_state['c_symbol']} | {st.session_state['c_strategy']}")
            with st.spinner("코인 데이터 분석 중..."):
                df_run = fetch_crypto(st.session_state["c_symbol"], period="6mo")
            if df_run.empty or len(df_run) < 30:
                st.error("데이터 부족")
                st.session_state["c_running"] = False
            else:
                now_str, cur_price = datetime.now().strftime("%H:%M:%S"), float(df_run["Close"].iloc[-1])
                signal = _run_signal(df_run, str(st.session_state["c_strategy"]), cur_price)
                pos = st.session_state.get("c_position")
                amt, sl_v, tp_v = float(st.session_state["c_amount"]), float(st.session_state["c_sl_pct"]), float(st.session_state["c_tp_pct"])
                if pos is not None:
                    pct = (cur_price / float(pos["entry_price"]) - 1) * 100
                    st.session_state["c_pnl"] = pct
                    if pct <= -sl_v or pct >= tp_v:
                        reason = "손절" if pct <= -sl_v else "익절"
                        st.session_state["c_trade_log"].append(f"[{now_str}] {reason} {st.session_state['c_symbol']} @ ${cur_price:,.2f} ({pct:+.2f}%)")
                        trade_qty = max(1, int(round(amt * 10000)))
                        add_trade(
                            st.session_state["c_symbol"].replace("/", ""),
                            "CRYPTO",
                            "SELL",
                            cur_price,
                            trade_qty,
                            f"코인 {reason} | qty={amt:.4f}",
                        )
                        st.session_state["c_position"] = None
                elif signal == "BUY":
                    st.session_state["c_position"] = {"entry_price": cur_price, "amount": amt, "symbol": st.session_state["c_symbol"]}
                    st.session_state["c_trade_log"].append(f"[{now_str}] BUY {st.session_state['c_symbol']} @ ${cur_price:,.2f} | qty {amt:.4f}")
                    trade_qty = max(1, int(round(amt * 10000)))
                    add_trade(
                        st.session_state["c_symbol"].replace("/", ""),
                        "CRYPTO",
                        "BUY",
                        cur_price,
                        trade_qty,
                        f"코인 {st.session_state['c_strategy']} | qty={amt:.4f}",
                    )

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("현재가 (USD)", f"${cur_price:,.2f}")
                m2.metric("시그널", signal)
                m3.metric("포지션", f"보유 @ ${float(pos['entry_price']):,.2f}" if pos else "없음")
                m4.metric("평가손익", f"{float(st.session_state['c_pnl']):+.2f}%")
                if st.session_state["c_trade_log"]:
                    st.text_area("실행 로그", "\n".join(st.session_state["c_trade_log"][-20:]), height=140, key="c_log_area")

    with tab3:
        st.subheader("코인 거래 내역")
        trades = get_trades(limit=200)
        if not trades.empty and "market" in trades.columns:
            filtered = trades[trades["market"] == "CRYPTO"]
            st.dataframe(filtered, use_container_width=True, hide_index=True) if not filtered.empty else st.info("코인 거래 내역이 없습니다.")
        else:
            st.info("거래 내역이 없습니다.")

    with tab4:
        render_exchange_api_tab(username)

    show_legal_disclaimer()
