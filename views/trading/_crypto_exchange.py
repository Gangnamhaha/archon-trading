from typing import cast

import pandas as pd
import streamlit as st

from data.database import load_user_setting, save_user_setting
from trading.exchange_api import BinanceAPI, UpbitAPI


def render_exchange_api_tab(username: str) -> None:
    st.subheader("🔑 거래소 API 연결")
    st.caption("업비트 또는 바이낸스 API 키를 등록하면 실거래 주문이 가능합니다.")
    st.warning("⚠️ 실거래 API 키는 절대 타인에게 공유하지 마세요. 키는 암호화되어 저장됩니다.")

    exchange_tab_u, exchange_tab_b = st.tabs(["🇰🇷 업비트 (Upbit)", "🌐 바이낸스 (Binance)"])

    with exchange_tab_u:
        st.markdown("**업비트 API 키 설정**")
        st.markdown("[업비트 API 발급](https://upbit.com/mypage/open_api_management) → 읽기+주문 권한 필요")
        saved_upbit_access = load_user_setting(username, "upbit_access_key", "")
        saved_upbit_secret = load_user_setting(username, "upbit_secret_key", "")

        upbit_access = st.text_input("Upbit Access Key", type="password", value=saved_upbit_access, key="upbit_access", placeholder="업비트 Access Key")
        upbit_secret = st.text_input("Upbit Secret Key", type="password", value=saved_upbit_secret, key="upbit_secret", placeholder="업비트 Secret Key")

        uc1, uc2 = st.columns(2)
        with uc1:
            if st.button("API 키 저장", key="save_upbit", use_container_width=True):
                save_user_setting(username, "upbit_access_key", cast(str, upbit_access))
                save_user_setting(username, "upbit_secret_key", cast(str, upbit_secret))
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
                        cols = [c for c in ["currency", "balance", "locked", "avg_buy_price"] if c in df_b.columns]
                        st.dataframe(df_b[cols], use_container_width=True, hide_index=True)
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
                        result = UpbitAPI(upbit_access, upbit_secret).place_buy_order(upbit_market, upbit_amount)
                    st.error(f"주문 실패: {result['error']}") if "error" in result else st.success(f"매수 주문 완료: {result}")
        with u_col2:
            upbit_volume = float(st.number_input("매도 수량", min_value=0.0001, value=0.0001, step=0.0001, format="%.4f", key="u_volume"))
            if st.button("매도 주문", use_container_width=True, key="u_sell"):
                if not upbit_access or not upbit_secret:
                    st.error("API 키를 먼저 저장하세요.")
                else:
                    with st.spinner("매도 주문 중..."):
                        result = UpbitAPI(upbit_access, upbit_secret).place_sell_order(upbit_market, upbit_volume)
                    st.error(f"주문 실패: {result['error']}") if "error" in result else st.success(f"매도 주문 완료: {result}")

    with exchange_tab_b:
        st.markdown("**바이낸스 API 키 설정**")
        st.markdown("[바이낸스 API 발급](https://www.binance.com/ko/my/settings/api-management) → Spot 거래 권한 필요")
        saved_binance_api = load_user_setting(username, "binance_api_key", "")
        saved_binance_secret = load_user_setting(username, "binance_secret_key", "")

        binance_api_key = st.text_input("Binance API Key", type="password", value=saved_binance_api, key="binance_api", placeholder="바이낸스 API Key")
        binance_secret_key = st.text_input("Binance Secret Key", type="password", value=saved_binance_secret, key="binance_secret", placeholder="바이낸스 Secret Key")

        bc1, bc2 = st.columns(2)
        with bc1:
            if st.button("API 키 저장", key="save_binance", use_container_width=True):
                save_user_setting(username, "binance_api_key", cast(str, binance_api_key))
                save_user_setting(username, "binance_secret_key", cast(str, binance_secret_key))
                st.success("바이낸스 API 키가 저장되었습니다.")
        with bc2:
            if st.button("잔고 조회", key="check_binance", use_container_width=True):
                if not binance_api_key or not binance_secret_key:
                    st.error("API 키를 먼저 입력하세요.")
                else:
                    with st.spinner("바이낸스 잔고 조회 중..."):
                        account = BinanceAPI(binance_api_key, binance_secret_key).get_balance()
                    if account and "balances" in account:
                        balances_b = [b for b in account["balances"] if float(b.get("free", 0)) > 0]
                        st.dataframe(pd.DataFrame(balances_b), use_container_width=True, hide_index=True) if balances_b else st.info("보유 자산 없음")
                    else:
                        st.error("잔고 조회 실패 (API 키 확인 필요)")

        st.markdown("---")
        st.markdown("**바이낸스 실거래 주문**")
        symbol = str(st.selectbox("심볼", ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT"], key="b_symbol") or "BTCUSDT")
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            qty = float(st.number_input("수량", min_value=0.0001, value=0.001, step=0.001, format="%.4f", key="b_qty"))
            if st.button("매수 주문 (BUY)", type="primary", use_container_width=True, key="b_buy"):
                if not binance_api_key or not binance_secret_key:
                    st.error("API 키를 먼저 저장하세요.")
                else:
                    with st.spinner("바이낸스 매수 중..."):
                        result = BinanceAPI(binance_api_key, binance_secret_key).place_market_order(symbol, "BUY", qty)
                    st.error(f"주문 실패: {result['error']}") if "error" in result else st.success(f"매수 완료: {result}")
        with b_col2:
            sell_qty = float(st.number_input("매도 수량", min_value=0.0001, value=0.001, step=0.001, format="%.4f", key="b_sell_qty"))
            if st.button("매도 주문 (SELL)", use_container_width=True, key="b_sell"):
                if not binance_api_key or not binance_secret_key:
                    st.error("API 키를 먼저 저장하세요.")
                else:
                    with st.spinner("바이낸스 매도 중..."):
                        result = BinanceAPI(binance_api_key, binance_secret_key).place_market_order(symbol, "SELL", sell_qty)
                    st.error(f"주문 실패: {result['error']}") if "error" in result else st.success(f"매도 완료: {result}")
