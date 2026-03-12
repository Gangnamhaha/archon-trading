import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from data.screener import get_krx_market_data, screen_stocks, PRESETS
from config.styles import inject_pro_css
from config.auth import require_auth

st.set_page_config(page_title="Stock Screener", page_icon="", layout="wide")
require_auth()
inject_pro_css()
st.title("Stock Screener")

st.sidebar.header("Filter Settings")

market = st.sidebar.selectbox("Market", ["KOSPI", "KOSDAQ"])
top_n = st.sidebar.slider("Scan Top N Stocks", 20, 200, 50)

st.sidebar.markdown("---")
st.sidebar.header("Preset Filters")
preset_name = st.sidebar.selectbox("Preset", ["Custom"] + list(PRESETS.keys()))

st.sidebar.markdown("---")
st.sidebar.header("Custom Filters")

rsi_range = st.sidebar.slider("RSI Range", 0, 100, (20, 80))
macd_filter = st.sidebar.selectbox("MACD", ["All", "Golden Cross", "Dead Cross"])
sma_filter = st.sidebar.selectbox("SMA 5/20 Trend", ["All", "Uptrend", "Downtrend"])
vol_ratio_min = st.sidebar.slider("Min Volume Ratio", 0.0, 10.0, 0.0, 0.5)
return_1d_range = st.sidebar.slider("1-Day Return Range (%)", -30.0, 30.0, (-10.0, 10.0))

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

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Scanned", len(raw_data))
        col2.metric("Filtered Results", len(filtered))
        col3.metric("Pass Rate", f"{len(filtered)/len(raw_data)*100:.1f}%" if len(raw_data) > 0 else "0%")

        st.markdown("---")

        if filtered.empty:
            st.warning("No stocks matched the filters.")
        else:
            st.subheader(f"Results ({len(filtered)} stocks)")

            display_cols = [c for c in filtered.columns if c not in ["MACD_Signal"]]
            st.dataframe(
                filtered[display_cols].style.applymap(
                    lambda v: "color: #FF6B6B" if isinstance(v, (int, float)) and v < 0 else (
                        "color: #00D4AA" if isinstance(v, (int, float)) and v > 0 else ""
                    ),
                    subset=[c for c in ["1일수익률(%)", "5일수익률(%)", "20일수익률(%)"] if c in filtered.columns]
                ),
                use_container_width=True, hide_index=True, height=600
            )

            st.subheader("RSI Distribution")
            import plotly.express as px
            if "RSI" in filtered.columns:
                fig = px.histogram(filtered.dropna(subset=["RSI"]), x="RSI", nbins=20,
                                   color_discrete_sequence=["#00D4AA"])
                fig.add_vline(x=30, line_dash="dash", line_color="green", annotation_text="Oversold")
                fig.add_vline(x=70, line_dash="dash", line_color="red", annotation_text="Overbought")
                fig.update_layout(template="plotly_dark", height=350)
                st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Set filters and click 'Run Screener'.")
