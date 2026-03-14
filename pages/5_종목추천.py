import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from config.styles import inject_pro_css, show_legal_disclaimer
from config.auth import require_pro

st.set_page_config(page_title="종목추천", page_icon="🏆", layout="wide")
require_pro()
inject_pro_css()
st.title("🏆 AI 종목추천")

rec_mode = st.radio("추천 모드", ["📊 일반 추천", "🔥 공격적 추천"], horizontal=True, key="rec_mode")

if rec_mode == "📊 일반 추천":
    st.info(
        "기술적 지표(RSI, MACD, 볼린저밴드, 일목균형표 등) + 모멘텀 + 거래량 + 추세일관성을 "
        "종합 분석하여 종목을 추천합니다. **투자 참고용**이며 투자 판단의 근거로만 활용하세요."
    )
else:
    st.warning(
        "⚠️ **고위험 공격적 추천 모드** — 높은 변동성 + 강한 모멘텀 + 거래량 폭증 종목을 필터링합니다. "
        "이 종목들은 단기 급등 가능성이 있지만, **동일한 수준의 급락 위험**도 있습니다. "
        "100% 수익을 보장하지 않으며, 원금 손실 가능성이 매우 높습니다."
    )

col1, col2, col3 = st.columns(3)
with col1:
    market = st.selectbox("시장", ["KOSPI", "KOSDAQ"]) or "KOSPI"
with col2:
    scan_count = st.selectbox("스캔 종목 수", [30, 50, 100, 200], index=2 if rec_mode == "🔥 공격적 추천" else 1)
    scan_count = int(scan_count or (100 if rec_mode == "🔥 공격적 추천" else 50))
with col3:
    result_count = st.selectbox("추천 표시 수", [10, 20, 30], index=1)
    result_count = int(result_count or 20)

if st.button("종목 추천 시작", type="primary", use_container_width=True):
    if rec_mode == "🔥 공격적 추천":
        with st.spinner(f"{market} 상위 {scan_count}개 종목 공격적 분석 중... (1~3분 소요)"):
            from analysis.recommender import recommend_aggressive_stocks
            df = recommend_aggressive_stocks(market=market, top_n=scan_count, result_count=result_count)
        if df.empty:
            st.error("조건에 맞는 공격적 종목이 없습니다.")
        else:
            st.session_state["aggressive_result"] = df
            st.session_state["recommend_market"] = market
            st.session_state.pop("recommend_result", None)
    else:
        with st.spinner(f"{market} 시가총액 상위 {scan_count}개 종목 분석 중... (1~3분 소요)"):
            from analysis.recommender import recommend_stocks
            df = recommend_stocks(market=market, top_n=scan_count, result_count=result_count)
        if df.empty:
            st.error("추천 결과가 없습니다. 잠시 후 다시 시도해주세요.")
        else:
            st.session_state["recommend_result"] = df
            st.session_state["recommend_market"] = market
            st.session_state.pop("aggressive_result", None)

if "aggressive_result" in st.session_state:
    adf = st.session_state["aggressive_result"]
    market_label = st.session_state.get("recommend_market", "")

    st.subheader(f"🔥 {market_label} 공격적 추천 결과")

    risk_counts = adf["위험등급"].value_counts()
    r1, r2, r3 = st.columns(3)
    r1.metric("🔥🔥🔥 초고위험", f"{risk_counts.get('🔥🔥🔥 초고위험', 0)}종목")
    r2.metric("🔥🔥 고위험", f"{risk_counts.get('🔥🔥 고위험', 0)}종목")
    r3.metric("🔥 위험", f"{risk_counts.get('🔥 위험', 0)}종목")

    st.markdown("---")

    agg_display = adf[["종목명", "현재가", "1일(%)", "5일(%)", "20일(%)",
                        "변동성(%)", "거래량비율", "RSI",
                        "20일최대상승(%)", "20일최대하락(%)", "공격점수", "위험등급"]].copy()

    def color_risk(val):
        if "초고위험" in str(val):
            return "background-color: #FF2020; color: white; font-weight: bold"
        elif "고위험" in str(val):
            return "background-color: #D45050; color: white"
        return "background-color: #8B4513; color: white"

    def color_return(val):
        try:
            v = float(val)
            return "color: #FF4444" if v > 0 else ("color: #4488FF" if v < 0 else "")
        except (ValueError, TypeError):
            return ""

    styled_agg = agg_display.style.applymap(
        color_risk, subset=["위험등급"]
    ).applymap(
        color_return, subset=["1일(%)", "5일(%)", "20일(%)", "20일최대상승(%)", "20일최대하락(%)"]
    ).format({
        "현재가": "{:,}",
        "1일(%)": "{:+.2f}", "5일(%)": "{:+.2f}", "20일(%)": "{:+.2f}",
        "변동성(%)": "{:.1f}", "거래량비율": "{:.1f}x", "RSI": "{:.1f}",
        "20일최대상승(%)": "{:+.2f}", "20일최대하락(%)": "{:+.2f}",
        "공격점수": "{:+.1f}",
    })

    st.dataframe(styled_agg, use_container_width=True, height=600)

    st.markdown("---")
    st.subheader("📊 공격점수 시각화")

    import plotly.graph_objects as go
    top_agg = adf.head(10)
    colors_agg = ["#FF2020" if v >= 40 else ("#FF6644" if v >= 25 else "#FF9944") for v in top_agg["공격점수"]]
    fig_agg = go.Figure()
    fig_agg.add_trace(go.Bar(
        x=top_agg["종목명"], y=top_agg["공격점수"],
        marker_color=colors_agg,
        text=[f"{v:+.1f}" for v in top_agg["공격점수"]],
        textposition="outside",
    ))
    fig_agg.update_layout(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        title="Top 10 공격점수", yaxis_title="점수", height=400, margin=dict(t=40, b=40),
    )
    st.plotly_chart(fig_agg, use_container_width=True)

    st.markdown("---")
    st.subheader("💡 공격적 추천 점수 산출 기준")
    st.markdown("""
    | 팩터 | 비중 | 설명 |
    |---|---|---|
    | **변동성** | 25% | 연환산 변동성이 높을수록 고점수 (일반 추천과 반대) |
    | **모멘텀** | 30% | 20일 수익률이 클수록 고점수 |
    | **거래량 폭증** | 25% | 20일 평균 대비 거래량 비율이 높을수록 고점수 |
    | **RSI 적정구간** | 20% | RSI 40~70 구간이 최적 (과매수 아닌 상승 여력) |

    > ⚠️ **경고**: 이 종목들은 단기 급등 가능성이 있지만, 동일한 수준의 급락 위험이 있습니다.
    > 반드시 손절 라인을 설정하고, 전체 자산의 일부만 투입하세요.
    """)

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

    st.subheader("📊 종합 점수 시각화")

    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    top_10 = df.head(10)

    fig_bar = go.Figure()
    colors = [
        "#00D4AA" if v >= 15 else ("#00A080" if v >= 0 else ("#D45050" if v >= -15 else "#FF2020"))
        for v in top_10["종합점수"]
    ]
    fig_bar.add_trace(go.Bar(
        x=top_10["종목명"], y=top_10["종합점수"],
        marker_color=colors,
        text=[f"{v:+.1f}" for v in top_10["종합점수"]],
        textposition="outside",
    ))
    fig_bar.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        title="Top 10 종합 점수",
        yaxis_title="점수",
        height=400,
        margin=dict(t=40, b=40),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    if len(top_10) >= 1:
        st.subheader("🕸️ 팩터 레이더 차트")
        radar_pick = st.selectbox("종목 선택", top_10["종목명"].tolist(), key="radar_pick")
        row_data = df[df["종목명"] == radar_pick].iloc[0]

        categories = ["기술점수", "모멘텀", "거래량", "추세일관성"]
        values = [float(row_data[c]) for c in categories]
        max_abs = max(abs(v) for v in values) if values else 1
        norm = [((v + max_abs) / (2 * max_abs)) * 100 for v in values]
        norm.append(norm[0])
        categories.append(categories[0])

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=norm, theta=categories, fill="toself",
            fillcolor="rgba(0,212,170,0.2)", line_color="#00D4AA",
            name=radar_pick,
        ))
        fig_radar.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(visible=True, range=[0, 100], showticklabels=False),
            ),
            title=f"{radar_pick} 팩터 분석",
            height=400, margin=dict(t=40, b=40),
            showlegend=False,
        )
        st.plotly_chart(fig_radar, use_container_width=True)

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

    with st.expander("🧠 추천 가중치 자동 학습", expanded=False):
        st.caption("💎 Pro 전용 기능")
        if st.button("가중치 학습", use_container_width=True, key="learn_optimal_weights"):
            progress_bar = st.progress(0)
            progress_bar.progress(15)
            with st.spinner("가중치 조합을 학습 중입니다..."):
                from analysis.recommender import learn_optimal_weights
                learn_market = market_label if isinstance(market_label, str) and market_label else market
                learn_result = learn_optimal_weights(
                    market=learn_market,
                    lookback_days=60,
                    top_n=min(max(scan_count, 30), 200),
                )
            progress_bar.progress(100)
            st.session_state["weight_learning_result"] = learn_result

        if "weight_learning_result" in st.session_state:
            learn_result = st.session_state["weight_learning_result"]
            if "error" in learn_result:
                st.warning(learn_result["error"])
            else:
                default_w = learn_result.get("default_weights", {})
                optimal_w = learn_result.get("optimal_weights", {})
                compare_df = pd.DataFrame([
                    {
                        "팩터": "기술지표",
                        "현재": default_w.get("tech_w", 0),
                        "학습": optimal_w.get("tech_w", 0),
                    },
                    {
                        "팩터": "모멘텀",
                        "현재": default_w.get("mom_w", 0),
                        "학습": optimal_w.get("mom_w", 0),
                    },
                    {
                        "팩터": "거래량",
                        "현재": default_w.get("vol_w", 0),
                        "학습": optimal_w.get("vol_w", 0),
                    },
                    {
                        "팩터": "추세일관성",
                        "현재": default_w.get("trend_w", 0),
                        "학습": optimal_w.get("trend_w", 0),
                    },
                    {
                        "팩터": "변동성 패널티",
                        "현재": default_w.get("vol_penalty_w", 0),
                        "학습": optimal_w.get("vol_penalty_w", 0),
                    },
                ])

                c1, c2, c3 = st.columns(3)
                comp = learn_result.get("comparison", {})
                c1.metric("기본 조합 기대수익", f"{comp.get('default_top_return', 0):+.2f}%")
                c2.metric("학습 조합 기대수익", f"{comp.get('optimized_top_return', 0):+.2f}%")
                c3.metric("개선폭", f"{comp.get('improvement', 0):+.2f}%")

                st.dataframe(compare_df.style.format({"현재": "{:.2f}", "학습": "{:.2f}"}), use_container_width=True, hide_index=True)

                all_results = learn_result.get("all_results", [])
                if all_results:
                    top_rows = []
                    for item in all_results[:5]:
                        w = item.get("weights", {})
                        top_rows.append({
                            "tech_w": w.get("tech_w", 0),
                            "mom_w": w.get("mom_w", 0),
                            "vol_w": w.get("vol_w", 0),
                            "trend_w": w.get("trend_w", 0),
                            "top_return(%)": item.get("top_return", 0),
                            "corr": item.get("corr", 0),
                        })
                    st.markdown("**상위 5개 가중치 조합**")
                    st.dataframe(pd.DataFrame(top_rows), use_container_width=True, hide_index=True)

show_legal_disclaimer()
