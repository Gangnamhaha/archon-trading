import importlib
from typing import Any, cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from analysis.technical import calc_all_indicators, get_signal_summary
from config.auth import is_paid
from config.styles import load_user_preferences, save_user_preferences, show_legal_disclaimer
from data.fetcher import fetch_stock, get_us_popular_stocks


def _market_data_module() -> Any:
    try:
        return importlib.import_module("views.analysis._charts_market_data")
    except ModuleNotFoundError as e:
        st.error(f"분석 모듈 로드 실패: {e}")
        return None


def render_charts(user: dict[str, Any]) -> None:
    section = st.radio("하위 섹션", ["📈 데이터분석", "🌍 글로벌마켓", "📊 기술적분석"], horizontal=True, key="charts_subsection")
    if section == "📈 데이터분석":
        _render_data_analysis(user)
    elif section == "🌍 글로벌마켓":
        _render_global_market()
    else:
        _render_technical_analysis(user)


def _persist_auto_toggle(username: str, key: str) -> None:
    if not username:
        return
    pref = load_user_preferences(username, "analysis")
    pref[key] = bool(st.session_state.get(key, False))
    save_user_preferences(username, "analysis", pref)
    snapshot = st.session_state.get("_analysis_pref_last")
    if isinstance(snapshot, dict):
        snapshot[key] = pref[key]
        st.session_state["_analysis_pref_last"] = snapshot


def _render_data_analysis(user: dict[str, Any]) -> None:
    st.subheader("📈 주가 데이터 분석")
    user_is_paid = is_paid()
    username = str((user or {}).get("username") or "")

    def _persist_data_toggle() -> None:
        _persist_auto_toggle(username, "data_auto_rerun")

    market = str(st.sidebar.selectbox("시장 선택", ["US (미국)", "KR (한국)"], key="data_market") or "US (미국)")
    market_code = market.split(" ")[0]

    if st.session_state.get("_prev_data_market") != market_code:
        st.session_state["_prev_data_market"] = market_code
        if market_code == "US":
            st.session_state["data_ticker_input"] = "AAPL"
        else:
            st.session_state["data_ticker_code"] = "005930"
        st.session_state.pop("data_ticker", None)
        st.session_state.pop("data_market_code", None)
        st.session_state.pop("data_run_period", None)
        st.session_state.pop("data_run_interval", None)

    if market_code == "US":
        popular = get_us_popular_stocks()
        popular_tickers = popular["ticker"].tolist() if (not popular.empty and "ticker" in popular.columns) else []
        if popular_tickers:
            selected = st.sidebar.selectbox("인기 종목", popular_tickers, index=0, key="data_popular")
            if selected and st.session_state.get("_prev_data_popular") != selected:
                st.session_state["data_ticker_input"] = selected
                st.session_state["_prev_data_popular"] = selected
        else:
            st.sidebar.warning("인기 종목 목록을 불러오지 못했습니다. 티커를 직접 입력하세요.")
        ticker = st.sidebar.text_input("종목 티커", key="data_ticker_input")
    else:
        ticker = st.sidebar.text_input("종목 코드", key="data_ticker_code")
    period = st.sidebar.selectbox("조회 기간", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3, key="data_period")
    auto_fetch = bool(
        st.sidebar.toggle(
            "입력 변경 시 자동 조회",
            value=bool(st.session_state.get("data_auto_rerun", st.session_state.get("_analysis_pref_last", {}).get("data_auto_rerun", False))),
            key="data_auto_rerun",
            on_change=_persist_data_toggle,
        )
    )
    if user_is_paid:
        interval = st.sidebar.selectbox("차트 간격", ["1d", "1wk", "1mo", "5m", "15m", "1h"], key="data_interval")
    else:
        interval = "1d"
        st.sidebar.info("🔒 차트 간격: 일봉만 (Plus 업그레이드 시 분봉/주봉 가능)")
        st.session_state["data_run_interval"] = "1d"

    current_ticker = str(ticker or "").strip().upper() if market_code == "US" else str(ticker or "").strip()
    current_signature = {
        "ticker": current_ticker,
        "market": market_code,
        "period": period,
        "interval": interval,
    }

    if st.sidebar.button("조회", type="primary", use_container_width=True, key="data_fetch"):
        clean_ticker = current_ticker
        # NOTE:
        # data_market / data_period / data_interval are bound to sidebar widgets.
        # Updating those widget keys after creation causes StreamlitAPIException.
        st.session_state.update(
            {
                "data_ticker": clean_ticker,
                "data_market_code": market_code,
                "data_run_period": period,
                "data_run_interval": interval,
            }
        )
    if "data_ticker" not in st.session_state:
        clean_ticker = current_ticker
        if clean_ticker:
            st.session_state.update(
                {
                    "data_ticker": clean_ticker,
                    "data_market_code": market_code,
                    "data_run_period": period,
                    "data_run_interval": interval,
                }
            )
        else:
            st.info("왼쪽 사이드바에 종목을 입력하고 '조회' 버튼을 클릭하세요.")
            return

    if "data_ticker" in st.session_state:
        run_signature = {
            "ticker": str(st.session_state.get("data_ticker") or ""),
            "market": str(st.session_state.get("data_market_code") or market_code),
            "period": str(st.session_state.get("data_run_period") or period),
            "interval": "1d" if not user_is_paid else str(st.session_state.get("data_run_interval") or st.session_state.get("data_interval") or "1d"),
        }
        if run_signature != current_signature:
            if auto_fetch and current_ticker:
                st.session_state.update(
                    {
                        "data_ticker": current_ticker,
                        "data_market_code": market_code,
                        "data_run_period": period,
                        "data_run_interval": interval,
                    }
                )
            else:
                st.info("입력 조건이 변경되었습니다. 최신 차트를 보려면 '조회'를 다시 클릭하세요.")
                return

        module = _market_data_module()
        if module is None:
            return
        module.render_price_and_compare(
            st.session_state["data_ticker"],
            st.session_state.get("data_market_code", str(st.session_state.get("data_market", "US")).split(" ")[0]),
            str(st.session_state.get("data_run_period") or st.session_state.get("data_period") or "1y"),
            "1d" if not user_is_paid else str(st.session_state.get("data_run_interval") or st.session_state.get("data_interval") or "1d"),
        )


def _render_global_market() -> None:
    st.subheader("🌍 글로벌 마켓 & 경제지표")
    tab1, tab2, tab3, tab4 = st.tabs(["암호화폐", "경제지표", "글로벌 지수", "투자자 동향"])

    with tab1:
        if st.button("암호화폐 데이터 로드", type="primary", use_container_width=True, key="load_crypto"):
            module = _market_data_module()
            if module is None:
                return
            cdf = module.fetch_crypto_market_table()
            st.dataframe(cdf, use_container_width=True, hide_index=True) if not cdf.empty else st.error("데이터를 가져올 수 없습니다.")
        coin = st.selectbox("차트 보기", ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "BNB-USD"], key="crypto_chart_sel")
        cperiod = st.selectbox("기간", ["1mo", "3mo", "6mo", "1y"], key="crypto_period")
        if st.button("차트 로드", use_container_width=True, key="load_crypto_chart"):
            hist = yf.Ticker(coin).history(period=cperiod)
            if not hist.empty:
                fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist["Open"], high=hist["High"], low=hist["Low"], close=hist["Close"])])
                fig.update_layout(template="plotly_dark", height=450, xaxis_rangeslider_visible=False, title=f"{coin} 캔들차트")
                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        if st.button("경제지표 로드", type="primary", use_container_width=True, key="load_econ"):
            module = _market_data_module()
            if module is None:
                return
            edf = module.fetch_economic_indicators()
            if edf.empty:
                st.error("데이터를 가져올 수 없습니다.")
            else:
                cols = st.columns(3)
                for i, (_, row) in enumerate(edf.iterrows()):
                    cols[i % 3].metric(cast(Any, row["지표"]), cast(Any, row["현재값"]), f"{row['전일비(%)']:+.2f}%")

    with tab3:
        if st.button("글로벌 지수 로드", type="primary", use_container_width=True, key="load_global"):
            module = _market_data_module()
            if module is None:
                return
            gdf = module.fetch_global_indices()
            if gdf.empty:
                st.error("데이터를 가져올 수 없습니다.")
            else:
                cols = st.columns(3)
                for i, (_, row) in enumerate(gdf.iterrows()):
                    cols[i % 3].metric(cast(Any, row["지수"]), cast(Any, row["현재"]), f"{row['전일비(%)']:+.2f}%")

    with tab4:
        if st.button("투자자 동향 로드", type="primary", use_container_width=True, key="load_investor"):
            module = _market_data_module()
            if module is None:
                return
            idf = module.fetch_investor_trend()
            if idf.empty:
                st.error("데이터를 가져올 수 없습니다.")
            else:
                st.dataframe(idf, use_container_width=True, hide_index=True)
    show_legal_disclaimer()


def _render_technical_analysis(user: dict[str, Any]) -> None:
    st.subheader("📊 기술적 분석")
    user_is_paid = is_paid()
    username = str((user or {}).get("username") or "")

    def _persist_ta_toggle() -> None:
        _persist_auto_toggle(username, "ta_auto_rerun")

    max_free = 5
    market = str(st.sidebar.selectbox("시장 선택", ["US (미국)", "KR (한국)"], key="ta_market") or "US (미국)")
    market_code = market.split(" ")[0]
    if st.session_state.get("_prev_ta_market") != market_code:
        st.session_state["_prev_ta_market"] = market_code
        st.session_state["ta_ticker"] = "AAPL" if market_code == "US" else "005930"
        st.session_state.pop("ta_run_ticker", None)
        st.session_state.pop("ta_market_code", None)
        st.session_state.pop("ta_run_period", None)
    ticker = st.sidebar.text_input("종목 티커" if market_code == "US" else "종목 코드", value="AAPL" if market_code == "US" else "005930", key="ta_ticker")
    period = st.sidebar.selectbox("조회 기간", ["3mo", "6mo", "1y", "2y"], index=2, key="ta_period")
    auto_run = bool(
        st.sidebar.toggle(
            "입력 변경 시 자동 재분석",
            value=bool(st.session_state.get("ta_auto_rerun", st.session_state.get("_analysis_pref_last", {}).get("ta_auto_rerun", False))),
            key="ta_auto_rerun",
            on_change=_persist_ta_toggle,
        )
    )
    show_sma = st.sidebar.checkbox("이동평균선 (SMA)", value=True, key="ta_show_sma")
    sma_periods = st.sidebar.multiselect("SMA 기간", [5, 10, 20, 60, 120], default=[5, 20, 60], key="ta_sma_periods")
    show_bb = st.sidebar.checkbox("볼린저밴드", value=True, key="ta_show_bb")
    show_rsi = st.sidebar.checkbox("RSI", value=True, key="ta_show_rsi")
    show_macd = st.sidebar.checkbox("MACD", value=True, key="ta_show_macd")
    if not user_is_paid:
        selected = [f"SMA{p}" for p in sma_periods] if show_sma else []
        if show_bb:
            selected.append("BB")
        if show_rsi:
            selected.append("RSI")
        if show_macd:
            selected.append("MACD")
        if len(selected) > max_free:
            st.sidebar.warning(f"⚠️ Free 플랜: 지표 최대 {max_free}개")
            show_macd = show_macd and "MACD" not in selected[max_free:]
            show_rsi = show_rsi and "RSI" not in selected[max_free:]
            show_bb = show_bb and "BB" not in selected[max_free:]
            sma_periods = [p for p in sma_periods if f"SMA{p}" not in selected[max_free:]]
    if st.sidebar.button("분석 실행", type="primary", use_container_width=True, key="ta_run"):
        clean_ticker = str(ticker or "").strip().upper() if market_code == "US" else str(ticker or "").strip()
        # NOTE:
        # ta_market / ta_ticker / ta_period are widget-bound keys.
        # Persist run snapshots in separate keys to avoid Streamlit widget-state mutation errors.
        st.session_state.update(
            {
                "ta_run_ticker": clean_ticker,
                "ta_market_code": market_code,
                "ta_run_period": period,
            }
        )

    current_signature = {
        "ticker": str(ticker or "").strip().upper() if market_code == "US" else str(ticker or "").strip(),
        "market": market_code,
        "period": period,
    }

    if "ta_run_ticker" not in st.session_state:
        clean_ticker = str(ticker or "").strip().upper() if market_code == "US" else str(ticker or "").strip()
        if clean_ticker:
            st.session_state.update(
                {
                    "ta_run_ticker": clean_ticker,
                    "ta_market_code": market_code,
                    "ta_run_period": period,
                }
            )

    if "ta_run_ticker" not in st.session_state:
        st.info("왼쪽 사이드바에서 종목을 입력하고 '분석 실행' 버튼을 클릭하세요.")
        return

    run_signature = {
        "ticker": str(st.session_state.get("ta_run_ticker") or ""),
        "market": str(st.session_state.get("ta_market_code") or market_code),
        "period": str(st.session_state.get("ta_run_period") or period),
    }
    if run_signature != current_signature:
        if auto_run and current_signature["ticker"]:
            st.session_state.update(
                {
                    "ta_run_ticker": current_signature["ticker"],
                    "ta_market_code": market_code,
                    "ta_run_period": period,
                }
            )
        else:
            st.info("입력 조건이 변경되었습니다. 최신 분석을 보려면 '분석 실행'을 다시 클릭하세요.")
            return

    ta_market_code = st.session_state.get("ta_market_code", str(st.session_state.get("ta_market", "US")).split(" ")[0])
    run_ticker = str(st.session_state.get("ta_run_ticker") or st.session_state.get("ta_ticker") or ticker)
    run_period = str(st.session_state.get("ta_run_period") or st.session_state.get("ta_period") or period)
    df = fetch_stock(run_ticker, ta_market_code, run_period)
    if df.empty:
        st.error("데이터를 가져올 수 없습니다.")
        return
    ta = calc_all_indicators(df)
    if ta.empty:
        st.error("지표 계산 결과가 없습니다.")
        return
    signal = get_signal_summary(ta)
    st.write(f"종합 시그널: **{signal['signal']}**")
    with st.expander("현재 지표 수치"):
        latest = ta.iloc[-1]
        st.json({k: round(float(v), 4) for k, v in latest.items() if k not in ["Open", "High", "Low", "Close", "Volume"] and pd.notna(v)})
