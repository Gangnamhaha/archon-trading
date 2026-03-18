from datetime import datetime

import streamlit as st

from config.styles import require_plan, show_legal_disclaimer
from views.settings._marketing_logic import (
    MARKETS,
    PLATFORMS,
    generate_performance_report,
    generate_recommendation_post,
    render_marketing_automation_tab,
)


def _render_article_tab() -> None:
    st.subheader("📝 투자 분석 글 생성")
    st.caption("AI가 특정 종목의 투자 분석 글을 자동 작성합니다.")

    article_ticker = st.text_input("종목코드 (예: 005930)", key="article_ticker")
    article_style = st.selectbox("글 스타일", ["전문가 분석", "초보자 설명", "요약 브리핑"], key="article_style")

    if not st.button("분석 글 생성", type="primary", use_container_width=True, key="gen_article"):
        return
    if not article_ticker:
        st.warning("종목코드를 입력하세요.")
        return

    with st.spinner("종목 분석 + 글 생성 중..."):
        try:
            from analysis.recommender import _calc_all_indicators, _fetch_ohlcv
            from analysis.technical import get_signal_summary
            from pykrx import stock as krx

            name = krx.get_market_ticker_name(article_ticker)
            df = _fetch_ohlcv(article_ticker, days=120)

            if df.empty:
                st.error("데이터를 가져올 수 없습니다.")
                return

            close = df["Close"]
            curr = int(close.iloc[-1])
            ret_5d = round((close.iloc[-1] / close.iloc[-6] - 1) * 100, 2) if len(close) >= 6 else 0
            ret_20d = round((close.iloc[-1] / close.iloc[-21] - 1) * 100, 2) if len(close) >= 21 else 0

            df_ind = _calc_all_indicators(df)
            tech = get_signal_summary(df_ind)
            rsi = round(float(df_ind["RSI"].iloc[-1]), 1) if "RSI" in df_ind.columns else 0
            today = datetime.now().strftime("%Y.%m.%d")

            if article_style == "전문가 분석":
                article = f"""# {name} ({article_ticker}) 기술적 분석 리포트
**작성일**: {today} | **현재가**: {curr:,}원

## 가격 동향
- 5일 수익률: {ret_5d:+.2f}%
- 20일 수익률: {ret_20d:+.2f}%

## 기술적 지표 분석
- **RSI ({rsi})**: {"과매수 구간으로 조정 가능성" if rsi > 70 else "과매도 구간으로 반등 가능성" if rsi < 30 else "중립 구간"}
- **종합 시그널**: {tech["signal"]} (점수: {tech["score"]:+.1f})

## 투자 의견
기술적 지표 종합 분석 결과, {name}은 현재 **{tech["signal"]}** 시그널을 보이고 있습니다.
{"단기적으로 상승 모멘텀이 강하며 추가 상승 여력이 있습니다." if tech["score"] > 20 else "중립적인 흐름으로 추가 관찰이 필요합니다." if tech["score"] > -10 else "하락 압력이 있으므로 신중한 접근이 필요합니다."}

> ⚠️ 본 분석은 투자 참고용이며, 투자 판단의 책임은 본인에게 있습니다.
> Archon AI 분석 플랫폼 | archon-pro.streamlit.app"""
            elif article_style == "초보자 설명":
                article = f"""## {name} 쉽게 분석해볼까요? 🔍

오늘 {name}({article_ticker})의 주가는 **{curr:,}원**입니다.

📈 **최근 흐름**
- 지난 5일간 {ret_5d:+.2f}% {"올랐어요 📈" if ret_5d > 0 else "내렸어요 📉"}
- 지난 20일간 {ret_20d:+.2f}% {"올랐어요 📈" if ret_20d > 0 else "내렸어요 📉"}

🤖 **AI 분석 결과**
RSI라는 지표가 {rsi}인데, {"70 이상이면 너무 많이 올라서 조심해야 해요" if rsi > 70 else "30 이하면 너무 많이 떨어져서 반등할 수도 있어요" if rsi < 30 else "보통 수준이에요"}.

AI가 내린 결론: **{tech["signal"]}**

💡 투자는 항상 신중하게! 이 분석은 참고용입니다.

🏛️ Archon - AI 주식 분석 플랫폼"""
            else:
                article = f"""[{today}] {name} ({article_ticker}) 브리핑
현재가: {curr:,}원 | 5일: {ret_5d:+.2f}% | 20일: {ret_20d:+.2f}%
RSI: {rsi} | 시그널: {tech["signal"]} ({tech["score"]:+.1f}점)
— Archon AI"""

            st.text_area("생성된 분석 글", article, height=400, key="article_result")
        except Exception as e:
            st.error(f"생성 실패: {e}")


def render_marketing(user: dict[str, str]) -> None:
    if not require_plan(user, "pro", "마케팅 도구"):
        show_legal_disclaimer()
        st.stop()
    username = user["username"]

    st.subheader("📣 마케팅")
    tab1, tab2, tab3, tab4 = st.tabs(["SNS 포스트 생성", "투자 분석 글 생성", "성과 리포트", "마케팅 자동화"])

    with tab1:
        st.subheader("📱 SNS 자동 포스팅 콘텐츠")
        st.caption("종목추천 결과를 SNS 포스트로 자동 변환합니다.")
        sns_market = str(st.selectbox("시장", MARKETS, key="sns_market") or MARKETS[0])
        sns_type = str(st.selectbox("플랫폼", PLATFORMS, key="sns_type") or PLATFORMS[0])

        if st.button("종목추천 기반 포스트 생성", type="primary", use_container_width=True, key="gen_sns"):
            with st.spinner("AI 종목 스캔 + 콘텐츠 생성 중..."):
                try:
                    post = generate_recommendation_post(platform=sns_type, market=sns_market)
                    st.text_area("생성된 포스트 (복사해서 사용하세요)", post, height=300, key="sns_result")
                except Exception as e:
                    st.error(f"생성 실패: {e}")

    with tab2:
        _render_article_tab()

    with tab3:
        st.subheader("📊 성과 리포트 생성")
        st.caption("현재 로그인 세션의 거래 로그를 공유 가능한 리포트로 변환합니다.")

        trade_logs = st.session_state.get("trade_log", [])
        if not trade_logs:
            st.info("현재 세션 거래 로그가 없습니다. 자동매매 페이지에서 거래를 실행한 후 생성하세요.")
        else:
            st.text_area("최근 세션 거래 로그", "\n".join(trade_logs[-30:]), height=200)
            if st.button("성과 리포트 생성", type="primary", use_container_width=True, key="gen_report"):
                try:
                    report = generate_performance_report()
                    st.text_area("성과 리포트", report, height=250, key="report_result")
                except Exception as e:
                    st.error(f"리포트 생성 실패: {e}")

    with tab4:
        render_marketing_automation_tab(username)

    show_legal_disclaimer()
