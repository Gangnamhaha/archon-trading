# pyright: basic
import importlib

import streamlit as st


_APP_GUIDE = """
**Archon** - AI 주식 자동매매 플랫폼

📊 **데이터분석** - 실시간 가격, 캔들차트, 멀티종목 비교
📉 **기술적분석** - RSI, MACD, 볼린저, 일목균형표 등 15+ 지표
🔬 **백테스팅** - 전략 과거 성과 테스트 (변동성돌파, 모멘텀 포함)
💼 **포트폴리오** - 보유종목 관리, 켈리사이징, 상관관계, 최적화
🤖 **자동매매** - 전략/DCA/오토파일럿 + AI 어시스턴트
🔮 **AI예측** - Holt-Winters, ARIMA, ML 앙상블 예측
🔍 **종목스크리너** - 다조건 필터 + 모멘텀 스캘핑
📰 **뉴스감성분석** - RSS 뉴스 수집 + 감성 분석
⚠️ **리스크분석** - VaR, 효율적 프론티어, 레버리지 시뮬
🏆 **종목추천** - 일반/🔥공격적 AI 추천
💬 **AI채팅** - GPT 기반 범용 AI 대화
"""

_GUIDE_SYSTEM_PROMPT = (
    "당신은 Archon AI 주식 트레이딩 플랫폼의 안내 도우미입니다. 한국어로 답변하세요.\n"
    "사용자가 기능에 대해 물어보면 친절하고 간결하게 안내합니다.\n\n"
    "앱 기능 목록:\n"
    "- 데이터분석: 실시간 가격 데이터, 캔들차트, 멀티종목 비교 (KR+US)\n"
    "- 기술적분석: RSI, MACD, 볼린저밴드, 일목균형표, ADX 등 15+ 지표\n"
    "- 백테스팅: 골든크로스, RSI, MACD, 볼린저, 변동성돌파, 공격적모멘텀 전략 테스트\n"
    "- 포트폴리오: 보유종목 관리, 수익률 추적, 켈리 포지션 사이징, 상관관계 분석, 분산투자 최적화\n"
    "- 자동매매: KIS/키움 API 연동, 전략기반/DCA/오토파일럿 모드, 손절익절, AI 어시스턴트\n"
    "- AI예측: Holt-Winters, ARIMA, ML 회귀 앙상블 예측\n"
    "- 종목스크리너: RSI/MACD/거래량 필터, 배당주 필터, 모멘텀 스캘핑 시그널\n"
    "- 뉴스감성분석: RSS 뉴스 수집, 키워드 감성 분석\n"
    "- 리스크분석: VaR, CVaR, 샤프/소르티노, 몬테카를로, 효율적 프론티어, 레버리지 시뮬레이터\n"
    "- 종목추천: 기술지표+모멘텀+거래량+추세 기반 일반/공격적 추천\n"
    "- AI채팅: OpenAI GPT 기반 범용 대화\n"
    "- 관리자: 사용자 관리, 플랜(Free/Pro) 관리\n\n"
    "Free 플랜 제한: 데이터분석(일봉만), 기술적분석(5개 지표), 포트폴리오(5종목), 워치리스트(3종목), 뉴스(5건/일)\n"
    "Pro 전용: 백테스팅, AI예측, 리스크분석, 종목추천, 자동매매\n\n"
    "오토파일럿 사용법: 자동매매 → API 연결 → 오토파일럿 설정 → 시작\n"
    "답변은 2-3문장으로 간결하게. 해당 페이지 이름을 알려주세요."
)


def render_guide_chatbot(user: dict[str, object]):
    username = str(user.get("username", ""))
    if not username:
        return

    if "guide_messages" not in st.session_state:
        st.session_state["guide_messages"] = []
    if "guide_api_key" not in st.session_state:
        from data.database import load_user_setting as _load_setting

        st.session_state["guide_api_key"] = _load_setting(username, "openai_api_key", "")

    st.markdown(_APP_GUIDE, unsafe_allow_html=True)
    st.markdown("---")

    g_key = st.text_input("OpenAI Key (선택)", type="password", value=st.session_state["guide_api_key"], key="_guide_key")
    if g_key and g_key != st.session_state["guide_api_key"]:
        st.session_state["guide_api_key"] = g_key
        from data.database import save_user_setting as _save_setting

        _save_setting(username, "openai_api_key", g_key)

    if g_key:
        for gm in st.session_state["guide_messages"][-6:]:
            role_icon = "🧑" if gm["role"] == "user" else "🤖"
            st.markdown(f"**{role_icon}** {gm['content']}")

        g_input = st.text_input("질문하세요", key="_guide_input", placeholder="이 앱에서 뭘 할 수 있어?")
        if g_input and st.button("전송", key="_guide_send", use_container_width=True):
            st.session_state["guide_messages"].append({"role": "user", "content": g_input})
            try:
                _client = importlib.import_module("openai").OpenAI(api_key=g_key)
                _msgs = [{"role": "system", "content": _GUIDE_SYSTEM_PROMPT}]
                for gm in st.session_state["guide_messages"][-10:]:
                    _msgs.append({"role": gm["role"], "content": gm["content"]})
                _resp = _client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=_msgs,
                    temperature=0.3,
                    max_tokens=512,
                )
                _reply = _resp.choices[0].message.content
                st.session_state["guide_messages"].append({"role": "assistant", "content": _reply})
            except Exception as _e:
                st.session_state["guide_messages"].append({"role": "assistant", "content": f"오류: {_e}"})
            st.rerun()
    else:
        st.caption("API Key 입력 시 AI 질의응답이 가능합니다.")
