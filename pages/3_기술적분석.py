"""
기술적 분석 차트 페이지
- 이동평균, RSI, MACD, 볼린저밴드 시각화
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data.fetcher import fetch_stock
from analysis.technical import calc_all_indicators, get_signal_summary
from config.styles import inject_pro_css
from config.auth import require_auth, is_paid

st.set_page_config(page_title="기술적 분석", page_icon="📊", layout="wide")
require_auth()
inject_pro_css()
st.title("📊 기술적 분석")

_user_is_paid = is_paid()
_MAX_FREE_INDICATORS = 5

# === 사이드바 설정 ===
st.sidebar.header("설정")
market = str(st.sidebar.selectbox("시장 선택", ["US (미국)", "KR (한국)"]) or "US (미국)")
market_code = market.split(" ")[0]

if market_code == "US":
    ticker = st.sidebar.text_input("종목 티커", value="AAPL")
else:
    ticker = st.sidebar.text_input("종목 코드", value="005930")

period = st.sidebar.selectbox("조회 기간", ["3mo", "6mo", "1y", "2y"], index=2)

st.sidebar.markdown("---")
st.sidebar.header("지표 설정")
if not _user_is_paid:
    st.sidebar.info(f"🔒 Free 플랜: 지표 최대 {_MAX_FREE_INDICATORS}개 (Plus 업그레이드 시 무제한)")
show_sma = st.sidebar.checkbox("이동평균선 (SMA)", value=True)
sma_periods = st.sidebar.multiselect("SMA 기간", [5, 10, 20, 60, 120], default=[5, 20, 60])
show_bb = st.sidebar.checkbox("볼린저밴드", value=True)
bb_period = st.sidebar.slider("볼린저밴드 기간", 10, 50, 20)
bb_std = st.sidebar.slider("볼린저밴드 표준편차", 1.0, 3.0, 2.0, 0.5)
show_rsi = st.sidebar.checkbox("RSI", value=True)
rsi_period = st.sidebar.slider("RSI 기간", 5, 30, 14)
show_macd = st.sidebar.checkbox("MACD", value=True)

if not _user_is_paid:
    _selected = []
    if show_sma:
        for p in sma_periods:
            _selected.append(f"SMA{p}")
    if show_bb:
        _selected.append("BB")
    if show_rsi:
        _selected.append("RSI")
    if show_macd:
        _selected.append("MACD")
    if len(_selected) > _MAX_FREE_INDICATORS:
        _over = len(_selected) - _MAX_FREE_INDICATORS
        _cut = _selected[_MAX_FREE_INDICATORS:]
        st.sidebar.warning(f"⚠️ 지표 {len(_selected)}개 선택됨 (최대 {_MAX_FREE_INDICATORS}개). {', '.join(_cut)} 비활성화됨.")
        for tag in _cut:
            if tag.startswith("SMA"):
                sma_periods = [p for p in sma_periods if f"SMA{p}" not in _cut]
            elif tag == "BB":
                show_bb = False
            elif tag == "RSI":
                show_rsi = False
            elif tag == "MACD":
                show_macd = False

# === 데이터 조회 및 분석 ===
if st.sidebar.button("분석 실행", type="primary", use_container_width=True):
    st.session_state["ta_ticker"] = ticker
    st.session_state["ta_market"] = market_code
    st.session_state["ta_period"] = period

if "ta_ticker" in st.session_state:
    ticker = st.session_state["ta_ticker"]
    market_code = st.session_state["ta_market"]
    period = st.session_state["ta_period"]

    with st.spinner(f"{ticker} 기술적 분석 중..."):
        df = fetch_stock(ticker, market_code, period)

    if df.empty:
        st.error("데이터를 가져올 수 없습니다.")
    else:
        # 모든 지표 계산
        df_ta = calc_all_indicators(df)

        # 시그널 요약
        signal_info = get_signal_summary(df_ta)
        st.subheader(f"종합 시그널: {signal_info['signal']}")
        if signal_info["details"]:
            cols = st.columns(len(signal_info["details"]))
            for i, (key, val) in enumerate(signal_info["details"].items()):
                color = "green" if "매수" in val else ("red" if "매도" in val else "gray")
                cols[i].markdown(f"**{key}**: :{color}[{val}]")

        st.markdown("---")

        # 차트 행 수 계산
        num_rows = 1  # 가격 차트
        if show_rsi:
            num_rows += 1
        if show_macd:
            num_rows += 1
        num_rows += 1  # 거래량

        row_heights = [0.45]
        if show_rsi:
            row_heights.append(0.15)
        if show_macd:
            row_heights.append(0.15)
        row_heights.append(0.1)

        # Normalize heights
        total = sum(row_heights)
        row_heights = [h / total for h in row_heights]

        subtitles = [f"{ticker} 가격"]
        if show_rsi:
            subtitles.append("RSI")
        if show_macd:
            subtitles.append("MACD")
        subtitles.append("거래량")

        fig = make_subplots(
            rows=num_rows, cols=1, shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=row_heights,
            subplot_titles=subtitles
        )

        current_row = 1

        # 1. 캔들스틱 차트
        fig.add_trace(
            go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"],
                low=df["Low"], close=df["Close"], name="가격",
                increasing_line_color="red", decreasing_line_color="blue"
            ), row=current_row, col=1
        )

        # SMA 오버레이
        if show_sma:
            colors = ["orange", "green", "purple", "brown", "pink"]
            for i, p in enumerate(sma_periods):
                col_name = f"SMA_{p}"
                if col_name in df_ta.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=df_ta.index, y=df_ta[col_name],
                            name=f"SMA {p}", line=dict(width=1, color=colors[i % len(colors)])
                        ), row=current_row, col=1
                    )

        # 볼린저밴드 오버레이
        if show_bb:
            fig.add_trace(
                go.Scatter(
                    x=df_ta.index, y=df_ta["BB_Upper"],
                    name="BB 상단", line=dict(width=1, dash="dash", color="rgba(100,100,255,0.5)")
                ), row=current_row, col=1
            )
            fig.add_trace(
                go.Scatter(
                    x=df_ta.index, y=df_ta["BB_Lower"],
                    name="BB 하단", line=dict(width=1, dash="dash", color="rgba(100,100,255,0.5)"),
                    fill="tonexty", fillcolor="rgba(100,100,255,0.05)"
                ), row=current_row, col=1
            )

        current_row += 1

        # 2. RSI 차트
        if show_rsi:
            fig.add_trace(
                go.Scatter(x=df_ta.index, y=df_ta["RSI"], name="RSI", line=dict(color="purple", width=1)),
                row=current_row, col=1
            )
            fig.add_trace(
                go.Scatter(x=df_ta.index, y=[70] * len(df_ta), name="RSI 70", line=dict(color="red", width=1, dash="dash")),
                row=current_row, col=1
            )
            fig.add_trace(
                go.Scatter(x=df_ta.index, y=[30] * len(df_ta), name="RSI 30", line=dict(color="green", width=1, dash="dash")),
                row=current_row, col=1
            )
            current_row += 1

        # 3. MACD 차트
        if show_macd:
            fig.add_trace(
                go.Scatter(x=df_ta.index, y=df_ta["MACD"], name="MACD", line=dict(color="blue", width=1)),
                row=current_row, col=1
            )
            fig.add_trace(
                go.Scatter(x=df_ta.index, y=df_ta["MACD_Signal"], name="Signal", line=dict(color="orange", width=1)),
                row=current_row, col=1
            )
            colors_hist = ["red" if v >= 0 else "blue" for v in df_ta["MACD_Hist"].fillna(0)]
            fig.add_trace(
                go.Bar(x=df_ta.index, y=df_ta["MACD_Hist"], name="Histogram", marker_color=colors_hist, opacity=0.5),
                row=current_row, col=1
            )
            current_row += 1

        # 4. 거래량
        vol_colors = ["red" if c >= o else "blue" for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(
            go.Bar(x=df.index, y=df["Volume"], name="거래량", marker_color=vol_colors, opacity=0.5),
            row=current_row, col=1
        )

        fig.update_layout(
            height=200 * num_rows + 200,
            xaxis_rangeslider_visible=False,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            template="plotly_dark",
            hovermode="x unified",
            xaxis=dict(
                showspikes=True, spikemode="across", spikesnap="cursor",
                spikethickness=1, spikecolor="#00D4AA", spikedash="dot",
            ),
            yaxis=dict(
                showspikes=True, spikemode="across", spikesnap="cursor",
                spikethickness=1, spikecolor="#00D4AA", spikedash="dot",
            ),
            dragmode="zoom",
        )

        config = {"scrollZoom": True, "displayModeBar": True, "modeBarButtonsToAdd": ["drawline", "eraseshape"]}
        st.plotly_chart(fig, use_container_width=True, config=config)

        # 지표 수치 테이블
        with st.expander("현재 지표 수치"):
            latest = df_ta.iloc[-1]
            indicator_data = {}
            for col in df_ta.columns:
                if col not in ["Open", "High", "Low", "Close", "Volume"]:
                    val = latest[col]
                    if not pd.isna(val):
                        indicator_data[col] = round(val, 4)
            st.json(indicator_data)
else:
    st.info("왼쪽 사이드바에서 종목을 입력하고 '분석 실행' 버튼을 클릭하세요.")
