import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import Any, Dict, List
from pykrx import stock as krx
from data.screener import get_krx_market_data, screen_stocks, PRESETS
from analysis.technical import calc_rsi
from config.styles import inject_pro_css
from config.auth import require_auth, is_pro

st.set_page_config(page_title="Stock Screener", page_icon="", layout="wide")
require_auth()
inject_pro_css()
st.title("Stock Screener")

_user_is_pro = is_pro()
_MAX_FREE_FILTERS = 3


@st.cache_data(ttl=300)
def get_momentum_scalping_signals(market: str) -> pd.DataFrame:
    columns = ["종목코드", "종목명", "현재가", "등락률(%)", "거래량비율", "RSI"]
    today = datetime.now()
    daily_frames: List[pd.DataFrame] = []
    cursor = today
    attempts = 0

    while len(daily_frames) < 21 and attempts < 45:
        date_str = cursor.strftime("%Y%m%d")
        daily = krx.get_market_ohlcv_by_ticker(date_str, market=market)
        if not daily.empty:
            daily_frames.append(daily)
        cursor -= timedelta(days=1)
        attempts += 1

    if len(daily_frames) < 2:
        return pd.DataFrame(columns=columns)

    current = daily_frames[0].copy()
    avg_volume_obj = pd.concat([frame["거래량"] for frame in daily_frames[1:]], axis=1).mean(axis=1)
    if not isinstance(avg_volume_obj, pd.Series):
        return pd.DataFrame(columns=columns)
    avg_volume = avg_volume_obj.mask(avg_volume_obj == 0)

    current["거래량비율"] = current["거래량"] / avg_volume
    current["등락률(%)"] = (current["종가"] / current["시가"] - 1) * 100

    candidates = current[(current["거래량비율"] > 3) & (current["등락률(%)"] > 2)].copy()
    if candidates.empty:
        return pd.DataFrame(columns=columns)

    start = (today - timedelta(days=120)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    results: List[Dict[str, Any]] = []

    for ticker, row in candidates.iterrows():
        try:
            ohlcv = krx.get_market_ohlcv(start, end, ticker)
            if ohlcv.empty or len(ohlcv) < 15:
                continue

            close_df: pd.DataFrame = ohlcv.rename(columns={"종가": "Close"}).loc[:, ["Close"]].copy()
            rsi_df = calc_rsi(close_df)
            rsi_value = rsi_df["RSI"].iloc[-1]
            if pd.isna(rsi_value) or rsi_value >= 70:
                continue

            results.append({
                "종목코드": ticker,
                "종목명": krx.get_market_ticker_name(str(ticker)),
                "현재가": int(row["종가"]),
                "등락률(%)": round(float(row["등락률(%)"]), 2),
                "거래량비율": round(float(row["거래량비율"]), 2),
                "RSI": round(float(rsi_value), 2),
            })
        except Exception:
            continue

    if not results:
        return pd.DataFrame(columns=columns)

    return pd.DataFrame(results).sort_values("등락률(%)", ascending=False).reset_index(drop=True)

st.sidebar.header("Filter Settings")

market = str(st.sidebar.selectbox("Market", ["KOSPI", "KOSDAQ"]))
top_n = st.sidebar.slider("Scan Top N Stocks", 20, 200, 50)

st.sidebar.markdown("---")
st.sidebar.header("Preset Filters")
preset_name = str(st.sidebar.selectbox("Preset", ["Custom"] + list(PRESETS.keys())))

st.sidebar.markdown("---")
st.sidebar.header("Custom Filters")
if not _user_is_pro:
    st.sidebar.info(f"🔒 Free 플랜: 커스텀 필터 최대 {_MAX_FREE_FILTERS}개")

rsi_range = st.sidebar.slider("RSI Range", 0, 100, (20, 80))
macd_filter = st.sidebar.selectbox("MACD", ["All", "Golden Cross", "Dead Cross"])
sma_filter = st.sidebar.selectbox("SMA 5/20 Trend", ["All", "Uptrend", "Downtrend"])

if _user_is_pro:
    vol_ratio_min = st.sidebar.slider("Min Volume Ratio", 0.0, 10.0, 0.0, 0.5)
    return_1d_range = st.sidebar.slider("1-Day Return Range (%)", -30.0, 30.0, (-10.0, 10.0))
    st.sidebar.markdown("---")
    st.sidebar.header("배당주 필터")
    div_filter = st.sidebar.checkbox("배당주만 표시", value=False, key="div_filter")
    min_div_yield = st.sidebar.slider("최소 배당수익률 (%)", 0.0, 10.0, 2.0, 0.5, key="min_div") if div_filter else 0.0
else:
    vol_ratio_min = 0.0
    return_1d_range = (-10.0, 10.0)
    div_filter = False
    min_div_yield = 0.0
    st.sidebar.caption("🔒 Volume Ratio, Return Range, 배당 필터는 Pro 전용입니다.")

if st.sidebar.button("Run Screener", type="primary", use_container_width=True):
    with st.spinner(f"Scanning {market} top {top_n} stocks..."):
        raw_data = get_krx_market_data(market, top_n)

    if raw_data.empty:
        st.error("Failed to fetch market data.")
    else:
        st.success(f"Scanned {len(raw_data)} stocks")

        if preset_name != "Custom":
            filters = PRESETS[preset_name]
            st.info(f"Preset: **{preset_name}** | Filters: {filters}")
        else:
            filters = {
                "RSI_min": rsi_range[0],
                "RSI_max": rsi_range[1],
                "return_1d_min": return_1d_range[0],
                "return_1d_max": return_1d_range[1],
            }
            if macd_filter == "Golden Cross":
                filters["MACD_cross"] = "golden"
            elif macd_filter == "Dead Cross":
                filters["MACD_cross"] = "dead"
            if sma_filter == "Uptrend":
                filters["SMA_trend"] = "up"
            elif sma_filter == "Downtrend":
                filters["SMA_trend"] = "down"
            if vol_ratio_min > 0:
                filters["vol_ratio_min"] = vol_ratio_min

        filtered = screen_stocks(raw_data, filters)
        filtered_df = pd.DataFrame(filtered)

        if div_filter and not filtered_df.empty:
            from pykrx import stock as krx
            from datetime import datetime as _dt, timedelta
            try:
                year = str(_dt.now().year - 1)
                div_data = krx.get_market_ohlcv_by_ticker(
                    (_dt.now() - timedelta(days=1)).strftime("%Y%m%d"), market=market
                )
                if not div_data.empty:
                    div_yields = {}
                    for t in filtered_df.index if filtered_df.index.name else filtered_df["ticker"] if "ticker" in filtered_df.columns else []:
                        try:
                            div_fn = getattr(krx, "get_market_trading_value_and_volume", None)
                            if div_fn is None:
                                continue
                            div_info = div_fn(year + "0101", year + "1231", t)
                            if hasattr(div_info, "배당수익률") and len(div_info) > 0:
                                div_yields[t] = float(div_info["배당수익률"].iloc[-1])
                        except Exception:
                            div_yields[t] = 0.0
                    if div_yields:
                        filtered_df["배당수익률(%)"] = filtered_df.index.map(lambda x: div_yields.get(x, 0.0))
                        filtered_df = filtered_df[filtered_df["배당수익률(%)"] >= min_div_yield]
            except Exception:
                st.caption("배당 데이터 조회 실패 — 배당 필터 미적용")

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Scanned", len(raw_data))
        col2.metric("Filtered Results", len(filtered_df))
        col3.metric("Pass Rate", f"{len(filtered_df)/len(raw_data)*100:.1f}%" if len(raw_data) > 0 else "0%")

        st.markdown("---")

        if filtered_df.empty:
            st.warning("No stocks matched the filters.")
        else:
            st.subheader(f"Results ({len(filtered_df)} stocks)")

            display_cols = [c for c in filtered_df.columns if c not in ["MACD_Signal"]]
            display_df = pd.DataFrame(filtered_df.loc[:, display_cols])
            st.dataframe(display_df, use_container_width=True, hide_index=True, height=600)

            st.subheader("RSI Distribution")
            import plotly.express as px
            if "RSI" in filtered_df.columns:
                rsi_series = pd.Series(filtered_df["RSI"])
                rsi_df = filtered_df[rsi_series.notna()]
                fig = px.histogram(rsi_df, x="RSI", nbins=20,
                                   color_discrete_sequence=["#00D4AA"])
                fig.add_vline(x=30, line_dash="dash", line_color="green", annotation_text="Oversold")
                fig.add_vline(x=70, line_dash="dash", line_color="red", annotation_text="Overbought")
                fig.update_layout(template="plotly_dark", height=350)
                st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Set filters and click 'Run Screener'.")

st.markdown("---")
st.subheader("모멘텀 스캘핑 시그널")
if _user_is_pro:
    try:
        momentum_df = get_momentum_scalping_signals(market)
        if momentum_df.empty:
            st.info("조건을 만족하는 종목이 없습니다.")
        else:
            st.dataframe(momentum_df, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"모멘텀 스캘핑 데이터 조회 실패: {e}")
else:
    st.caption("Pro 전용")
