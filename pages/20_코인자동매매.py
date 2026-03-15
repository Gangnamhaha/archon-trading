import os
import sys
from datetime import datetime

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.auth import is_pro, require_auth
from config.styles import inject_pro_css, show_legal_disclaimer
from data.database import add_trade, get_trades, load_user_setting, save_user_setting
from data.fetcher import CRYPTO_PAIRS, fetch_crypto, get_crypto_price
from trading.exchange_api import BinanceAPI, UpbitAPI

st.set_page_config(page_title="코인 자동매매", page_icon="🪙", layout="wide")
user = require_auth()
inject_pro_css()
username = user["username"]

if not is_pro(user):
    st.warning("코인 자동매매는 Pro 플랜 전용입니다.")
    st.stop()

st.title("🪙 코인 자동매매 (Crypto Autopilot)")
st.caption("주요 암호화폐의 기술적 지표 기반 시뮬레이션 자동매매 | 실제 거래소 API 연결 시 실거래 가능")

COIN_LIST = list(CRYPTO_PAIRS.keys())

AP_DEFAULTS_C = {
    "c_symbol": "BTC/USD",
    "c_capital_usd": 1000.0,
    "c_amount": 0.001,
    "c_sl_pct": 2.0,
    "c_tp_pct": 4.0,
    "c_strategy": "MA 크로스",
    "c_running": False,
    "c_position": None,
    "c_trade_log": [],
    "c_pnl": 0.0,
}
for k, v in AP_DEFAULTS_C.items():
    if k not in st.session_state:
        st.session_state[k] = v

tab1, tab2, tab3, tab4 = st.tabs(["📊 시장 현황", "⚡ 자동매매", "📋 거래 로그", "🔑 거래소 API 연결"])

with tab1:
    st.subheader("주요 코인 현재 가격 (USD)")
    TOP_COINS = ["BTC/USD", "ETH/USD", "BNB/USD", "XRP/USD", "SOL/USD", "ADA/USD", "DOGE/USD", "AVAX/USD"]
    price_cols = st.columns(4)
    for idx, coin in enumerate(TOP_COINS):
        price = get_crypto_price(coin)
        price_cols[idx % 4].metric(coin, f"${price:,.2f}" if price else "로딩중...")

    st.markdown("---")
    chart_coin = str(st.selectbox("차트 조회", COIN_LIST, key="c_chart_coin") or COIN_LIST[0])
    chart_period = str(st.selectbox("기간", ["1mo", "3mo", "6mo", "1y"], index=2, key="c_period") or "6mo")

    if st.button("차트 불러오기", use_container_width=True, key="c_load_chart"):
        with st.spinner("데이터 로딩 중..."):
            df_c = fetch_crypto(chart_coin, period=chart_period)
        if df_c.empty:
            st.error("데이터를 가져올 수 없습니다.")
        else:
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=df_c.index, open=df_c["Open"], high=df_c["High"],
                low=df_c["Low"], close=df_c["Close"], name=chart_coin
            ))
            ma20 = df_c["Close"].rolling(20).mean()
            ma60 = df_c["Close"].rolling(60).mean()
            fig.add_trace(go.Scatter(x=df_c.index, y=ma20, name="MA20", line=dict(color="#38BDF8", width=1)))
            fig.add_trace(go.Scatter(x=df_c.index, y=ma60, name="MA60", line=dict(color="#F97316", width=1)))
            fig.update_layout(
                plot_bgcolor="#0E1117", paper_bgcolor="#0E1117",
                font_color="#E2E8F0", height=420, xaxis_rangeslider_visible=False,
                title=f"{chart_coin} 캔들차트"
            )
            st.plotly_chart(fig, use_container_width=True)

            close = df_c["Close"]
            ret_1d = float((close.iloc[-1] / close.iloc[-2] - 1) * 100) if len(close) >= 2 else 0.0
            ret_7d = float((close.iloc[-1] / close.iloc[-8] - 1) * 100) if len(close) >= 8 else 0.0
            ret_30d = float((close.iloc[-1] / close.iloc[-31] - 1) * 100) if len(close) >= 31 else 0.0
            ic1, ic2, ic3, ic4 = st.columns(4)
            ic1.metric("현재가", f"${float(close.iloc[-1]):,.2f}")
            ic2.metric("1일 수익률", f"{ret_1d:+.2f}%")
            ic3.metric("7일 수익률", f"{ret_7d:+.2f}%")
            ic4.metric("30일 수익률", f"{ret_30d:+.2f}%")

with tab2:
    st.subheader("코인 오토파일럿 설정")
    col1, col2 = st.columns(2)
    with col1:
        c_symbol = str(st.selectbox("코인", COIN_LIST,
            index=COIN_LIST.index(st.session_state["c_symbol"])
            if st.session_state["c_symbol"] in COIN_LIST else 0) or COIN_LIST[0])
        c_capital = float(st.number_input("투자금 (USD)", min_value=10.0, value=float(st.session_state["c_capital_usd"]), step=10.0))
        c_amount = float(st.number_input("1회 매매 수량", min_value=0.0001, value=float(st.session_state["c_amount"]), step=0.001, format="%.4f"))
        c_strategy = str(st.selectbox("전략", ["MA 크로스", "RSI 역추세", "볼린저 밴드 돌파", "모멘텀 추종"], key="c_strat_sel") or "MA 크로스")
    with col2:
        c_sl = float(st.slider("손절 (%)", 1.0, 10.0, float(st.session_state["c_sl_pct"]), 0.5))
        c_tp = float(st.slider("익절 (%)", 1.0, 20.0, float(st.session_state["c_tp_pct"]), 0.5))
        current_price = get_crypto_price(c_symbol)
        st.info(
            f"코인: {c_symbol}\n\n"
            f"현재가: ${current_price:,.2f} | 수량: {c_amount:.4f}\n\n"
            f"손절 -{c_sl}% / 익절 +{c_tp}%"
        )

    if st.session_state["c_running"]:
        if st.button("⏹️ 오토파일럿 중지", type="primary", use_container_width=True, key="c_stop"):
            st.session_state["c_running"] = False
            st.session_state["c_position"] = None
            st.rerun()
    else:
        if st.button("▶️ 오토파일럿 시작", type="primary", use_container_width=True, key="c_start"):
            st.session_state.update({
                "c_symbol": c_symbol, "c_capital_usd": c_capital,
                "c_amount": c_amount, "c_sl_pct": c_sl,
                "c_tp_pct": c_tp, "c_strategy": c_strategy,
                "c_running": True, "c_pnl": 0.0,
            })
            st.rerun()

    if st.session_state["c_running"]:
        st.success(f"🟢 코인 오토파일럿 실행 중 | {st.session_state['c_symbol']} | {st.session_state['c_strategy']}")
        run_ph = st.empty()

        with st.spinner("코인 데이터 분석 중..."):
            df_run = fetch_crypto(st.session_state["c_symbol"], period="6mo")

        if df_run.empty or len(df_run) < 30:
            st.error("데이터 부족")
            st.session_state["c_running"] = False
        else:
            close_r = df_run["Close"]
            now_str = datetime.now().strftime("%H:%M:%S")
            cur_price = float(close_r.iloc[-1])

            strategy_c = st.session_state["c_strategy"]
            signal_c = "HOLD"

            if strategy_c == "MA 크로스":
                ma5 = float(close_r.rolling(5).mean().iloc[-1])
                ma20 = float(close_r.rolling(20).mean().iloc[-1])
                ma5p = float(close_r.rolling(5).mean().iloc[-2])
                ma20p = float(close_r.rolling(20).mean().iloc[-2])
                if ma5p <= ma20p and ma5 > ma20:
                    signal_c = "BUY"
                elif ma5p >= ma20p and ma5 < ma20:
                    signal_c = "SELL"

            elif strategy_c == "RSI 역추세":
                delta = close_r.diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rsi = float((100 - 100 / (1 + gain / loss.replace(0, 1e-10))).iloc[-1])
                signal_c = "BUY" if rsi < 30 else ("SELL" if rsi > 70 else "HOLD")

            elif strategy_c == "볼린저 밴드 돌파":
                ma20b = close_r.rolling(20).mean()
                std20 = close_r.rolling(20).std()
                upper = float((ma20b + 2 * std20).iloc[-1])
                lower = float((ma20b - 2 * std20).iloc[-1])
                signal_c = "BUY" if cur_price < lower else ("SELL" if cur_price > upper else "HOLD")

            elif strategy_c == "모멘텀 추종":
                ret7 = float((close_r.iloc[-1] / close_r.iloc[-8] - 1) * 100) if len(close_r) >= 8 else 0.0
                ret3 = float((close_r.iloc[-1] / close_r.iloc[-4] - 1) * 100) if len(close_r) >= 4 else 0.0
                if ret7 > 5 and ret3 > 1:
                    signal_c = "BUY"
                elif ret7 < -5 and ret3 < -1:
                    signal_c = "SELL"

            pos_c = st.session_state.get("c_position")
            amt = float(st.session_state["c_amount"])
            sl_c = float(st.session_state["c_sl_pct"])
            tp_c = float(st.session_state["c_tp_pct"])

            if pos_c is not None:
                entry_c = float(pos_c["entry_price"])
                pct_c = (cur_price / entry_c - 1) * 100
                st.session_state["c_pnl"] = pct_c

                if pct_c <= -sl_c:
                    st.session_state["c_trade_log"].append(
                        f"[{now_str}] 손절 {st.session_state['c_symbol']} @ ${cur_price:,.2f} ({pct_c:+.2f}%)"
                    )
                    add_trade(st.session_state["c_symbol"].replace("/", ""), "CRYPTO", "SELL", cur_price, amt, "코인 손절")
                    st.session_state["c_position"] = None
                elif pct_c >= tp_c:
                    st.session_state["c_trade_log"].append(
                        f"[{now_str}] 익절 {st.session_state['c_symbol']} @ ${cur_price:,.2f} ({pct_c:+.2f}%)"
                    )
                    add_trade(st.session_state["c_symbol"].replace("/", ""), "CRYPTO", "SELL", cur_price, amt, "코인 익절")
                    st.session_state["c_position"] = None
            else:
                if signal_c == "BUY":
                    st.session_state["c_position"] = {"entry_price": cur_price, "amount": amt, "symbol": st.session_state["c_symbol"]}
                    st.session_state["c_trade_log"].append(
                        f"[{now_str}] BUY {st.session_state['c_symbol']} @ ${cur_price:,.2f} | qty {amt:.4f}"
                    )
                    add_trade(st.session_state["c_symbol"].replace("/", ""), "CRYPTO", "BUY", cur_price, amt, f"코인 {strategy_c}")

            with run_ph.container():
                rc1, rc2, rc3, rc4 = st.columns(4)
                rc1.metric("현재가 (USD)", f"${cur_price:,.2f}")
                rc2.metric("시그널", signal_c)
                pos_str = f"보유 @ ${float(pos_c['entry_price']):,.2f}" if pos_c else "없음"
                rc3.metric("포지션", pos_str)
                rc4.metric("평가손익", f"{float(st.session_state['c_pnl']):+.2f}%")

            if st.session_state["c_trade_log"]:
                st.text_area("실행 로그", "\n".join(st.session_state["c_trade_log"][-20:]), height=140, key="c_log_area")

with tab3:
    st.subheader("코인 거래 내역")
    trades_c = get_trades(limit=200)
    if not trades_c.empty and "market" in trades_c.columns:
        crypto_trades = trades_c[trades_c["market"] == "CRYPTO"]
        if crypto_trades.empty:
            st.info("코인 거래 내역이 없습니다.")
        else:
            st.dataframe(crypto_trades, use_container_width=True, hide_index=True)
    else:
        st.info("거래 내역이 없습니다.")

with tab4:
    st.subheader("🔑 거래소 API 연결")
    st.caption("업비트 또는 바이낸스 API 키를 등록하면 실거래 주문이 가능합니다.")
    st.warning("⚠️ 실거래 API 키는 절대 타인에게 공유하지 마세요. 키는 암호화되어 저장됩니다.")

    exchange_tab_u, exchange_tab_b = st.tabs(["🇰🇷 업비트 (Upbit)", "🌐 바이낸스 (Binance)"])

    with exchange_tab_u:
        st.markdown("**업비트 API 키 설정**")
        st.markdown("[업비트 API 발급](https://upbit.com/mypage/open_api_management) → 읽기+주문 권한 필요")
        saved_upbit_access = load_user_setting(username, "upbit_access_key", "")
        saved_upbit_secret = load_user_setting(username, "upbit_secret_key", "")

        upbit_access = st.text_input("Upbit Access Key", type="password",
            value=saved_upbit_access, key="upbit_access", placeholder="업비트 Access Key")
        upbit_secret = st.text_input("Upbit Secret Key", type="password",
            value=saved_upbit_secret, key="upbit_secret", placeholder="업비트 Secret Key")

        uc1, uc2 = st.columns(2)
        with uc1:
            if st.button("API 키 저장", key="save_upbit", use_container_width=True):
                save_user_setting(username, "upbit_access_key", upbit_access)
                save_user_setting(username, "upbit_secret_key", upbit_secret)
                st.success("업비트 API 키가 저장되었습니다.")
        with uc2:
            if st.button("잔고 조회", key="check_upbit", use_container_width=True):
                if not upbit_access or not upbit_secret:
                    st.error("API 키를 먼저 입력하세요.")
                else:
                    with st.spinner("업비트 잔고 조회 중..."):
                        api_u = UpbitAPI(upbit_access, upbit_secret)
                        balances = api_u.get_balance()
                    if balances:
                        df_b = pd.DataFrame(balances)
                        show_cols = [c for c in ["currency", "balance", "locked", "avg_buy_price"] if c in df_b.columns]
                        st.dataframe(df_b[show_cols], use_container_width=True, hide_index=True)
                    else:
                        st.error("잔고 조회 실패 (API 키 확인 필요)")

        st.markdown("---")
        st.markdown("**업비트 실거래 주문**")
        upbit_market = str(st.selectbox("마켓", ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE"], key="u_market") or "KRW-BTC")
        u_col1, u_col2 = st.columns(2)
        with u_col1:
            upbit_amount = float(st.number_input("매수 금액 (KRW)", min_value=5000.0, value=10000.0, step=1000.0, key="u_amount"))
            if st.button("매수 주문", type="primary", use_container_width=True, key="u_buy"):
                if not upbit_access or not upbit_secret:
                    st.error("API 키를 먼저 저장하세요.")
                else:
                    with st.spinner("매수 주문 중..."):
                        api_u = UpbitAPI(upbit_access, upbit_secret)
                        result = api_u.place_buy_order(upbit_market, upbit_amount)
                    if "error" in result:
                        st.error(f"주문 실패: {result['error']}")
                    else:
                        st.success(f"매수 주문 완료: {result}")
        with u_col2:
            upbit_volume = float(st.number_input("매도 수량", min_value=0.0001, value=0.0001, step=0.0001, format="%.4f", key="u_volume"))
            if st.button("매도 주문", use_container_width=True, key="u_sell"):
                if not upbit_access or not upbit_secret:
                    st.error("API 키를 먼저 저장하세요.")
                else:
                    with st.spinner("매도 주문 중..."):
                        api_u = UpbitAPI(upbit_access, upbit_secret)
                        result = api_u.place_sell_order(upbit_market, upbit_volume)
                    if "error" in result:
                        st.error(f"주문 실패: {result['error']}")
                    else:
                        st.success(f"매도 주문 완료: {result}")

    with exchange_tab_b:
        st.markdown("**바이낸스 API 키 설정**")
        st.markdown("[바이낸스 API 발급](https://www.binance.com/ko/my/settings/api-management) → Spot 거래 권한 필요")
        saved_binance_api = load_user_setting(username, "binance_api_key", "")
        saved_binance_secret = load_user_setting(username, "binance_secret_key", "")

        binance_api_key = st.text_input("Binance API Key", type="password",
            value=saved_binance_api, key="binance_api", placeholder="바이낸스 API Key")
        binance_secret_key = st.text_input("Binance Secret Key", type="password",
            value=saved_binance_secret, key="binance_secret", placeholder="바이낸스 Secret Key")

        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("API 키 저장", key="save_binance", use_container_width=True):
                save_user_setting(username, "binance_api_key", binance_api_key)
                save_user_setting(username, "binance_secret_key", binance_secret_key)
                st.success("바이낸스 API 키가 저장되었습니다.")
        with bc2:
            if st.button("잔고 조회", key="check_binance", use_container_width=True):
                if not binance_api_key or not binance_secret_key:
                    st.error("API 키를 먼저 입력하세요.")
                else:
                    with st.spinner("바이낸스 잔고 조회 중..."):
                        api_b = BinanceAPI(binance_api_key, binance_secret_key)
                        account = api_b.get_balance()
                    if account and "balances" in account:
                        balances_b = [b for b in account["balances"] if float(b.get("free", 0)) > 0]
                        if balances_b:
                            st.dataframe(pd.DataFrame(balances_b), use_container_width=True, hide_index=True)
                        else:
                            st.info("보유 자산 없음")
                    else:
                        st.error("잔고 조회 실패 (API 키 확인 필요)")

        st.markdown("---")
        st.markdown("**바이낸스 실거래 주문**")
        binance_symbol = str(st.selectbox("심볼", ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT"], key="b_symbol") or "BTCUSDT")
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            b_qty = float(st.number_input("수량", min_value=0.0001, value=0.001, step=0.001, format="%.4f", key="b_qty"))
            if st.button("매수 주문 (BUY)", type="primary", use_container_width=True, key="b_buy"):
                if not binance_api_key or not binance_secret_key:
                    st.error("API 키를 먼저 저장하세요.")
                else:
                    with st.spinner("바이낸스 매수 중..."):
                        api_b = BinanceAPI(binance_api_key, binance_secret_key)
                        result = api_b.place_market_order(binance_symbol, "BUY", b_qty)
                    if "error" in result:
                        st.error(f"주문 실패: {result['error']}")
                    else:
                        st.success(f"매수 완료: {result}")
        with b_col2:
            b_sell_qty = float(st.number_input("매도 수량", min_value=0.0001, value=0.001, step=0.001, format="%.4f", key="b_sell_qty"))
            if st.button("매도 주문 (SELL)", use_container_width=True, key="b_sell"):
                if not binance_api_key or not binance_secret_key:
                    st.error("API 키를 먼저 저장하세요.")
                else:
                    with st.spinner("바이낸스 매도 중..."):
                        api_b = BinanceAPI(binance_api_key, binance_secret_key)
                        result = api_b.place_market_order(binance_symbol, "SELL", b_sell_qty)
                    if "error" in result:
                        st.error(f"주문 실패: {result['error']}")
                    else:
                        st.success(f"매도 완료: {result}")

show_legal_disclaimer()
