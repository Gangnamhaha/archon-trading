import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from config.styles import inject_pro_css
from config.auth import require_auth

st.set_page_config(page_title="종목추천", page_icon="🏆", layout="wide")
require_auth()
inject_pro_css()
st.title("🏆 AI 종목추천")

st.info(
    "기술적 지표(RSI, MACD, 볼린저밴드, 일목균형표 등) + 모멘텀 + 거래량 + 추세일관성을 "
    "종합 분석하여 종목을 추천합니다. **투자 참고용**이며 투자 판단의 근거로만 활용하세요."
)

col1, col2, col3 = st.columns(3)
with col1:
    market = st.selectbox("시장", ["KOSPI", "KOSDAQ"])
with col2:
    scan_count = st.selectbox("스캔 종목 수", [30, 50, 100, 200], index=1)
with col3:
    result_count = st.selectbox("추천 표시 수", [10, 20, 30], index=1)

if st.button("종목 추천 시작", type="primary", use_container_width=True):
    with st.spinner(f"{market} 시가총액 상위 {scan_count}개 종목 분석 중... (1~3분 소요)"):
        from analysis.recommender import recommend_stocks
        df = recommend_stocks(market=market, top_n=scan_count, result_count=result_count)

    if df.empty:
        st.error("추천 결과가 없습니다. 잠시 후 다시 시도해주세요.")
    else:
        st.session_state["recommend_result"] = df
        st.session_state["recommend_market"] = market

if "recommend_result" in st.session_state:
    df = st.session_state["recommend_result"]
    market_label = st.session_state.get("recommend_market", "")

    st.subheader(f"📊 {market_label} 추천 결과")

    buy_strong = len(df[df["추천"] == "강력 매수"])
    buy_normal = len(df[df["추천"] == "매수"])
    hold = len(df[df["추천"].str.contains("관망")])
    sell_count = len(df[df["추천"].str.contains("매도")])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("강력 매수", f"{buy_strong}종목")
    m2.metric("매수", f"{buy_normal}종목")
    m3.metric("관망", f"{hold}종목")
    m4.metric("매도", f"{sell_count}종목")

    st.markdown("---")

    def color_recommendation(val):
        colors = {
            "강력 매수": "background-color: #00D4AA; color: black; font-weight: bold",
            "매수": "background-color: #00A080; color: white",
            "관망 (매수 우위)": "background-color: #2D5A3D; color: white",
            "관망 (매도 우위)": "background-color: #5A3D2D; color: white",
            "매도": "background-color: #D45050; color: white",
            "강력 매도": "background-color: #FF2020; color: white; font-weight: bold",
        }
        return colors.get(val, "")

    def color_score(val):
        try:
            v = float(val)
            if v >= 30:
                return "color: #00FF88; font-weight: bold"
            elif v >= 15:
                return "color: #00D4AA"
            elif v >= 0:
                return "color: #88CC88"
            elif v >= -15:
                return "color: #CC8888"
            elif v >= -30:
                return "color: #FF6666"
            else:
                return "color: #FF2020; font-weight: bold"
        except (ValueError, TypeError):
            return ""

    def color_return(val):
        try:
            v = float(val)
            if v > 0:
                return "color: #FF4444"
            elif v < 0:
                return "color: #4488FF"
            return ""
        except (ValueError, TypeError):
            return ""

    display_cols = ["종목명", "현재가", "1일(%)", "5일(%)", "20일(%)", "RSI",
                    "종합점수", "추천", "기술신호"]
    display_df = df[display_cols].copy()

    styled = display_df.style.applymap(
        color_recommendation, subset=["추천"]
    ).applymap(
        color_score, subset=["종합점수"]
    ).applymap(
        color_return, subset=["1일(%)", "5일(%)", "20일(%)"]
    ).format({
        "현재가": "{:,}",
        "1일(%)": "{:+.2f}",
        "5일(%)": "{:+.2f}",
        "20일(%)": "{:+.2f}",
        "RSI": "{:.1f}",
        "종합점수": "{:+.1f}",
    })

    st.dataframe(styled, use_container_width=True, height=600)

    st.markdown("---")

    st.subheader("📈 세부 점수 분석")

    detail_cols = ["종목명", "기술점수", "모멘텀", "거래량", "추세일관성", "종합점수", "추천"]
    detail_df = df[detail_cols].copy()

    st.dataframe(
        detail_df.style.applymap(color_recommendation, subset=["추천"]).format({
            "기술점수": "{:+.1f}",
            "모멘텀": "{:+.1f}",
            "거래량": "{:+.1f}",
            "추세일관성": "{:+.1f}",
            "종합점수": "{:+.1f}",
        }),
        use_container_width=True,
    )

    st.markdown("---")

    st.subheader("💡 점수 산출 기준")
    st.markdown("""
    | 팩터 | 비중 | 설명 |
    |---|---|---|
    | **기술적 지표** | 35% | RSI, MACD, 볼린저밴드, 일목균형표, ADX, Williams %R 종합 |
    | **모멘텀** | 25% | 5일/20일/60일 수익률 가중 합산 |
    | **거래량** | 15% | 20일 평균 대비 금일 거래량 비율 |
    | **추세 일관성** | 15% | 최근 10일간 5일선이 20일선 위에 있는 비율 |
    | **변동성 패널티** | 10% | 연환산 변동성이 높을수록 감점 |
    """)
