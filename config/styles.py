import inspect
import json
import os
from typing import Any, Dict

import streamlit as st

_PWA_META = """
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Archon">
<meta name="theme-color" content="#0E1117">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<link rel="manifest" href="app/static/manifest.json">
<link rel="apple-touch-icon" sizes="192x192" href="app/static/icon-192.png">
"""

_PRO_CSS = """<style>
html{-webkit-text-size-adjust:100%}
body{-webkit-tap-highlight-color:transparent;overscroll-behavior-y:contain}

.stMetric{background:#1A1F2E;padding:1rem;border-radius:8px;border:1px solid #2D3748}
.stMetric label{color:#A0AEC0 !important}
.stMetric [data-testid="stMetricValue"]{color:#00D4AA !important}
div[data-testid="stExpander"]{background:#1A1F2E;border:1px solid #2D3748;border-radius:8px}
h1,h2,h3{color:#E2E8F0 !important}

input,select,textarea{font-size:16px !important}
.stButton>button{-webkit-tap-highlight-color:transparent;touch-action:manipulation}
.stSelectbox,.stTextInput,.stNumberInput{touch-action:manipulation}

@media(max-width:768px){
    .main .block-container{padding:0.5rem 0.8rem !important}
    [data-testid="stHorizontalBlock"]{flex-wrap:wrap !important;gap:0.3rem !important}
    [data-testid="stHorizontalBlock"]>div{flex:1 1 100% !important;min-width:100% !important}
    .stMetric{padding:0.5rem;margin-bottom:0.2rem}
    .stButton>button{min-height:2.8rem;font-size:1rem}
    h1{font-size:1.4rem !important}
    h2{font-size:1.15rem !important}
    h3{font-size:1rem !important}
    [data-testid="stForm"]{padding:0.5rem !important}
    .stTabs [data-baseweb="tab-list"]{gap:0 !important;overflow-x:auto;-webkit-overflow-scrolling:touch}
    .stTabs [data-baseweb="tab"]{padding:0.5rem 0.8rem !important;font-size:0.85rem !important;white-space:nowrap}
    .stDataFrame{font-size:0.75rem !important}
    .stDataFrame [data-testid="stDataFrameResizable"]{overflow-x:auto !important;-webkit-overflow-scrolling:touch}
    .js-plotly-plot .plotly .modebar{display:none !important}
    .stPlotlyChart{margin-left:-0.5rem;margin-right:-0.5rem}
    div[data-testid="stSidebarNav"]{padding-top:1rem}
    .feature-grid{grid-template-columns:1fr !important}
    .main-header h1{font-size:1.3rem !important}
    section[data-testid="stMain"]{margin-left:0 !important;width:100% !important}
    [data-testid="stSidebar"]{position:fixed !important;top:0 !important;left:0 !important;height:100vh !important;z-index:999999 !important;transition:transform 0.3s ease !important}
    [data-testid="stSidebar"][aria-expanded="true"]{min-width:85vw !important;max-width:85vw !important;transform:translateX(0) !important;box-shadow:4px 0 20px rgba(0,0,0,0.5) !important}
    [data-testid="stSidebar"][aria-expanded="false"]{min-width:0 !important;max-width:0 !important;transform:translateX(-100%) !important;overflow:hidden !important;box-shadow:none !important}
    [data-testid="stSidebar"] .block-container{padding:0.5rem !important}
}

@media(max-width:1024px) and (min-width:769px){
    .main .block-container{padding:1rem 1.5rem !important}
    [data-testid="stHorizontalBlock"]{flex-wrap:wrap !important}
    [data-testid="stHorizontalBlock"]>div{flex:1 1 45% !important;min-width:45% !important}
    .feature-grid{grid-template-columns:repeat(2,1fr) !important}
}

@media(max-width:480px){
    .main .block-container{padding:0.3rem 0.5rem !important}
    .stMetric{padding:0.4rem;font-size:0.85rem}
    .stMetric [data-testid="stMetricValue"]{font-size:1.1rem !important}
    .stMetric [data-testid="stMetricDelta"]{font-size:0.7rem !important}
    h1{font-size:1.2rem !important}
    .stButton>button{min-height:3rem;font-size:1.05rem}
    .stSelectbox>div>div,.stTextInput>div>div,.stNumberInput>div>div{min-height:2.5rem}
    [data-testid="stSidebar"][aria-expanded="true"]{min-width:100vw !important;max-width:100vw !important}
}

[data-testid="stSidebarNav"] a[aria-current="page"]{
    background:linear-gradient(90deg,rgba(0,212,170,0.15),transparent) !important;
    border-left:3px solid #00D4AA !important;
    font-weight:600 !important;
}
[data-testid="stSidebarNav"] a{
    padding:0.4rem 0.8rem !important;border-radius:4px;transition:background 0.2s;
    border-left:3px solid transparent !important;
}
[data-testid="stSidebarNav"] a:hover{background:rgba(0,212,170,0.08) !important}

@keyframes skeleton-pulse{
    0%{background-position:-200px 0}
    100%{background-position:calc(200px + 100%) 0}
}
.skeleton-loader{
    background:linear-gradient(90deg,rgba(26,31,46,1) 25%,rgba(45,55,72,1) 50%,rgba(26,31,46,1) 75%);
    background-size:200px 100%;
    animation:skeleton-pulse 1.5s ease-in-out infinite;
    border-radius:8px;height:80px;margin:0.5rem 0;
}

@keyframes toast-in{0%{transform:translateX(100%);opacity:0}100%{transform:translateX(0);opacity:1}}
@keyframes toast-out{0%{opacity:1}100%{opacity:0;transform:translateY(-20px)}}
.archon-toast{
    position:fixed;top:1rem;right:1rem;z-index:99999;
    padding:0.8rem 1.2rem;border-radius:8px;
    font-size:0.9rem;font-weight:500;
    animation:toast-in 0.3s ease-out,toast-out 0.3s ease-in 2.7s forwards;
    box-shadow:0 4px 12px rgba(0,0,0,0.3);pointer-events:none;
}
.archon-toast.success{background:rgba(0,212,170,0.95);color:black}
.archon-toast.error{background:rgba(212,80,80,0.95);color:white}
.archon-toast.info{background:rgba(66,133,244,0.95);color:white}

@media(hover:none) and (pointer:coarse){
    .stButton>button{min-height:3rem;padding:0.6rem 1rem}
    .stSelectbox>div>div{min-height:2.8rem}
    .stTextInput>div>div{min-height:2.8rem}
    .stNumberInput>div>div{min-height:2.8rem}
    a,button{cursor:default}
    .stSlider [role="slider"]{width:24px !important;height:24px !important}
    .stCheckbox label{padding:0.4rem 0 !important}
}
</style>"""


_HIDE_ADMIN_UI = """<style>
.stToolbarActions,
.stDeployButton,
[data-testid="stToolbarActions"],
[data-testid="manage-app-button"] {
    display: none !important;
    visibility: hidden !important;
}
</style>"""


_APP_GUIDE = """
**Archon** — AI 주식 자동매매 플랫폼

📊 **데이터분석** — 실시간 가격, 캔들차트, 멀티종목 비교
📉 **기술적분석** — RSI, MACD, 볼린저, 일목균형표 등 15+ 지표
🔬 **백테스팅** — 전략 과거 성과 테스트 (변동성돌파, 모멘텀 포함)
💼 **포트폴리오** — 보유종목 관리, 켈리사이징, 상관관계, 최적화
🤖 **자동매매** — 전략/DCA/오토파일럿 + AI 어시스턴트
🔮 **AI예측** — Holt-Winters, ARIMA, ML 앙상블 예측
🔍 **종목스크리너** — 다조건 필터 + 모멘텀 스캘핑
📰 **뉴스감성분석** — RSS 뉴스 수집 + 감성 분석
⚠️ **리스크분석** — VaR, 효율적 프론티어, 레버리지 시뮬
🏆 **종목추천** — 일반/🔥공격적 AI 추천
💬 **AI채팅** — GPT 기반 범용 AI 대화
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


def inject_pro_css(hide_toolbar: bool = True, show_logout: bool = True):
    st.markdown(_PWA_META, unsafe_allow_html=True)
    st.markdown(_PRO_CSS, unsafe_allow_html=True)
    if hide_toolbar:
        st.markdown(_HIDE_ADMIN_UI, unsafe_allow_html=True)

    user = st.session_state.get("user")
    if not user:
        return

    from data.database import log_activity
    _caller = inspect.stack()[1].filename
    _page_name = os.path.basename(_caller).replace(".py", "")
    _last_page = st.session_state.get("_last_logged_page", "")
    if _page_name != _last_page:
        log_activity(user["username"], "page_visit", _page_name)
        st.session_state["_last_logged_page"] = _page_name

    with st.sidebar:
        if show_logout:
            st.markdown("---")
            if st.button("Logout", key="_global_logout", use_container_width=True):
                from config.auth import logout
                logout()

        st.markdown("---")
        with st.expander("🤖 앱 가이드", expanded=False):
            if "guide_messages" not in st.session_state:
                st.session_state["guide_messages"] = []
            if "guide_api_key" not in st.session_state:
                from data.database import load_user_setting as _load_setting
                st.session_state["guide_api_key"] = _load_setting(user["username"], "openai_api_key", "")

            st.markdown(_APP_GUIDE, unsafe_allow_html=True)
            st.markdown("---")

            g_key = st.text_input("OpenAI Key (선택)", type="password",
                                  value=st.session_state["guide_api_key"], key="_guide_key")
            if g_key and g_key != st.session_state["guide_api_key"]:
                st.session_state["guide_api_key"] = g_key
                from data.database import save_user_setting as _save_setting
                _save_setting(user["username"], "openai_api_key", g_key)

            if g_key:
                for gm in st.session_state["guide_messages"][-6:]:
                    role_icon = "🧑" if gm["role"] == "user" else "🤖"
                    st.markdown(f"**{role_icon}** {gm['content']}")

                g_input = st.text_input("질문하세요", key="_guide_input", placeholder="이 앱에서 뭘 할 수 있어?")
                if g_input and st.button("전송", key="_guide_send", use_container_width=True):
                    st.session_state["guide_messages"].append({"role": "user", "content": g_input})
                    try:
                        from openai import OpenAI
                        _client = OpenAI(api_key=g_key)
                        _msgs = [{"role": "system", "content": _GUIDE_SYSTEM_PROMPT}]
                        for gm in st.session_state["guide_messages"][-10:]:
                            _msgs.append({"role": gm["role"], "content": gm["content"]})
                        _resp = _client.chat.completions.create(
                            model="gpt-4o-mini", messages=_msgs,
                            temperature=0.3, max_tokens=512,
                        )
                        _reply = _resp.choices[0].message.content
                        st.session_state["guide_messages"].append({"role": "assistant", "content": _reply})
                    except Exception as _e:
                        st.session_state["guide_messages"].append({"role": "assistant", "content": f"오류: {_e}"})
                    st.rerun()
            else:
                st.caption("API Key 입력 시 AI 질의응답이 가능합니다.")


def show_toast(message: str, toast_type: str = "success"):
    st.markdown(
        f'<div class="archon-toast {toast_type}">{message}</div>',
        unsafe_allow_html=True,
    )


def show_skeleton(count: int = 3):
    for _ in range(count):
        st.markdown('<div class="skeleton-loader"></div>', unsafe_allow_html=True)


def save_user_preferences(username: str, page: str, settings: Dict[str, Any]):
    from data.database import save_user_setting
    save_user_setting(username, f"page_{page}", json.dumps(settings))


def load_user_preferences(username: str, page: str) -> Dict[str, Any]:
    from data.database import load_user_setting
    raw = load_user_setting(username, f"page_{page}")
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def show_legal_disclaimer():
    st.caption("⚠️ 본 서비스는 투자 참고용이며 투자자문에 해당하지 않습니다. 투자 결과의 책임은 이용자에게 있으며, 원금 손실이 발생할 수 있습니다.")
