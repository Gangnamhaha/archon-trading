import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from datetime import datetime
from config.styles import inject_pro_css
from config.auth import require_auth, is_pro

st.set_page_config(page_title="마케팅 도구", page_icon="📣", layout="wide")
user = require_auth()
inject_pro_css()
_user_is_pro = is_pro(user)
username = user["username"]

st.title("📣 마케팅 콘텐츠 생성기")

tab1, tab2, tab3 = st.tabs(["SNS 포스트 생성", "투자 분석 글 생성", "성과 리포트"])

with tab1:
    st.subheader("📱 SNS 자동 포스팅 콘텐츠")
    st.caption("종목추천 결과를 SNS 포스트로 자동 변환합니다.")

    _sns_type = st.selectbox("플랫폼", ["트위터 (280자)", "인스타그램", "블로그 요약", "카카오톡 메시지"], key="sns_type")

    if st.button("종목추천 기반 포스트 생성", type="primary", use_container_width=True, key="gen_sns"):
        with st.spinner("AI 종목 스캔 + 콘텐츠 생성 중..."):
            try:
                from analysis.recommender import recommend_stocks
                df = recommend_stocks(market="KOSPI", top_n=30, result_count=5)
                if df.empty:
                    st.error("추천 결과가 없습니다.")
                else:
                    today = datetime.now().strftime("%Y.%m.%d")
                    top3 = df.head(3)

                    if _sns_type == "트위터 (280자)":
                        lines = [f"📊 Archon AI 종목추천 ({today})"]
                        for _, r in top3.iterrows():
                            lines.append(f"🔹 {r['종목명']} | {r['현재가']:,}원 | {r['추천']} (점수:{r['종합점수']:+.1f})")
                        lines.append("")
                        lines.append("🤖 AI가 분석한 오늘의 추천종목")
                        lines.append("#주식 #AI자동매매 #Archon #종목추천")
                        post = "\n".join(lines)

                    elif _sns_type == "인스타그램":
                        lines = [f"📊 오늘의 AI 종목추천 ({today})", ""]
                        for _, r in top3.iterrows():
                            emoji = "🟢" if r["종합점수"] > 20 else "🟡"
                            lines.append(f"{emoji} {r['종목명']}")
                            lines.append(f"   현재가: {r['현재가']:,}원")
                            lines.append(f"   추천: {r['추천']} (점수: {r['종합점수']:+.1f})")
                            lines.append(f"   RSI: {r['RSI']}")
                            lines.append("")
                        lines.append("💡 Archon AI가 기술적 지표 + 모멘텀 + 거래량을 종합 분석했습니다.")
                        lines.append("")
                        lines.append("#주식투자 #AI주식 #종목추천 #자동매매 #Archon #주식분석 #투자 #재테크")
                        post = "\n".join(lines)

                    elif _sns_type == "블로그 요약":
                        lines = [f"# Archon AI 종목추천 리포트 ({today})", ""]
                        lines.append("## 오늘의 추천 종목")
                        lines.append("")
                        lines.append("| 종목 | 현재가 | 추천 | 점수 | RSI |")
                        lines.append("|---|---|---|---|---|")
                        for _, r in df.head(5).iterrows():
                            lines.append(f"| {r['종목명']} | {r['현재가']:,}원 | {r['추천']} | {r['종합점수']:+.1f} | {r['RSI']} |")
                        lines.append("")
                        lines.append("## 분석 기준")
                        lines.append("- 기술적 지표 (RSI, MACD, 볼린저밴드 등) 35%")
                        lines.append("- 모멘텀 (5일/20일/60일 수익률) 25%")
                        lines.append("- 거래량 (20일 평균 대비) 15%")
                        lines.append("- 추세 일관성 (SMA5 vs SMA20) 15%")
                        lines.append("- 변동성 조정 10%")
                        lines.append("")
                        lines.append("> ⚠️ 본 분석은 투자 참고용이며, 투자 판단의 책임은 본인에게 있습니다.")
                        lines.append("")
                        lines.append("**Archon** - AI 기반 주식 자동매매 플랫폼")
                        post = "\n".join(lines)

                    else:
                        lines = [f"[Archon AI 종목추천] {today}", ""]
                        for _, r in top3.iterrows():
                            lines.append(f"▶ {r['종목명']} | {r['현재가']:,}원 | {r['추천']}")
                        lines.append("")
                        lines.append("AI가 기술적 지표+모멘텀+거래량을 종합 분석한 결과입니다.")
                        lines.append("archon-pro.streamlit.app")
                        post = "\n".join(lines)

                    st.text_area("생성된 포스트 (복사해서 사용하세요)", post, height=300, key="sns_result")
                    st.button("📋 복사", key="sns_copy", help="텍스트를 선택하고 Ctrl+C로 복사하세요")

            except Exception as e:
                st.error(f"생성 실패: {e}")

with tab2:
    st.subheader("📝 투자 분석 글 생성")
    st.caption("AI가 특정 종목의 투자 분석 글을 자동 작성합니다.")

    _article_ticker = st.text_input("종목코드 (예: 005930)", key="article_ticker")
    _article_style = st.selectbox("글 스타일", ["전문가 분석", "초보자 설명", "요약 브리핑"], key="article_style")

    if st.button("분석 글 생성", type="primary", use_container_width=True, key="gen_article"):
        if not _article_ticker:
            st.warning("종목코드를 입력하세요.")
        else:
            with st.spinner("종목 분석 + 글 생성 중..."):
                try:
                    from pykrx import stock as krx
                    from analysis.recommender import _fetch_ohlcv, _calc_all_indicators
                    from analysis.technical import get_signal_summary

                    name = krx.get_market_ticker_name(_article_ticker)
                    df = _fetch_ohlcv(_article_ticker, days=120)

                    if df.empty:
                        st.error("데이터를 가져올 수 없습니다.")
                    else:
                        close = df["Close"]
                        curr = int(close.iloc[-1])
                        ret_5d = round((close.iloc[-1] / close.iloc[-6] - 1) * 100, 2) if len(close) >= 6 else 0
                        ret_20d = round((close.iloc[-1] / close.iloc[-21] - 1) * 100, 2) if len(close) >= 21 else 0

                        df_ind = _calc_all_indicators(df)
                        tech = get_signal_summary(df_ind)
                        rsi = round(float(df_ind["RSI"].iloc[-1]), 1) if "RSI" in df_ind.columns else 0

                        today = datetime.now().strftime("%Y.%m.%d")

                        if _article_style == "전문가 분석":
                            article = f"""# {name} ({_article_ticker}) 기술적 분석 리포트
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

                        elif _article_style == "초보자 설명":
                            article = f"""## {name} 쉽게 분석해볼까요? 🔍

오늘 {name}({_article_ticker})의 주가는 **{curr:,}원**입니다.

📈 **최근 흐름**
- 지난 5일간 {ret_5d:+.2f}% {"올랐어요 📈" if ret_5d > 0 else "내렸어요 📉"}
- 지난 20일간 {ret_20d:+.2f}% {"올랐어요 📈" if ret_20d > 0 else "내렸어요 📉"}

🤖 **AI 분석 결과**
RSI라는 지표가 {rsi}인데, {"70 이상이면 너무 많이 올라서 조심해야 해요" if rsi > 70 else "30 이하면 너무 많이 떨어져서 반등할 수도 있어요" if rsi < 30 else "보통 수준이에요"}.

AI가 내린 결론: **{tech["signal"]}**

💡 투자는 항상 신중하게! 이 분석은 참고용입니다.

🏛️ Archon - AI 주식 분석 플랫폼"""

                        else:
                            article = f"""[{today}] {name} ({_article_ticker}) 브리핑
현재가: {curr:,}원 | 5일: {ret_5d:+.2f}% | 20일: {ret_20d:+.2f}%
RSI: {rsi} | 시그널: {tech["signal"]} ({tech["score"]:+.1f}점)
— Archon AI"""

                        st.text_area("생성된 분석 글", article, height=400, key="article_result")

                except Exception as e:
                    st.error(f"생성 실패: {e}")

with tab3:
    st.subheader("📊 성과 리포트 생성")
    st.caption("오토파일럿 거래 내역을 공유 가능한 리포트로 변환합니다.")

    from data.database import get_trades

    trades = get_trades(limit=50)
    if trades.empty:
        st.info("거래 내역이 없습니다. 자동매매를 실행한 후 리포트를 생성할 수 있습니다.")
    else:
        st.dataframe(trades.head(10), use_container_width=True, hide_index=True)

        if st.button("성과 리포트 생성", type="primary", use_container_width=True, key="gen_report"):
            total_trades = len(trades)
            buy_count = len(trades[trades["action"] == "BUY"])
            sell_count = len(trades[trades["action"] == "SELL"])

            today = datetime.now().strftime("%Y.%m.%d")
            report = f"""📊 Archon 자동매매 성과 리포트
━━━━━━━━━━━━━━━━━━━━
📅 기준일: {today}
🤖 총 거래 횟수: {total_trades}회
📈 매수: {buy_count}회 | 📉 매도: {sell_count}회

💡 AI 기반 자동매매로 감정 없는 체계적 투자!
🏛️ Archon - archon-pro.streamlit.app
#자동매매 #AI투자 #Archon"""

            st.text_area("성과 리포트", report, height=250, key="report_result")

from config.styles import show_legal_disclaimer
show_legal_disclaimer()
