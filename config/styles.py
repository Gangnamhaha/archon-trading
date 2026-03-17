import inspect
import importlib
import json
import os
from typing import Any, Dict

import streamlit as st
import streamlit.components.v1 as components

_PWA_META = """
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Archon">
<meta name="theme-color" content="#0B1220">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<link rel="manifest" href="app/static/manifest.json">
<link rel="apple-touch-icon" sizes="192x192" href="app/static/icon-192.png">
<meta name="description" content="Archon - AI 기반 주식 자동매매 플랫폼. 종목추천, 오토파일럿, 백테스팅, 리스크분석.">
<meta name="keywords" content="주식,자동매매,AI,종목추천,오토파일럿,한국투자증권,키움증권">
<meta property="og:title" content="Archon - AI 주식 자동매매 플랫폼">
<meta property="og:description" content="AI가 종목 추천부터 매매까지 자동화합니다.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://archon-pro.streamlit.app">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Archon - AI 주식 자동매매 플랫폼">
<script>if('serviceWorker' in navigator){navigator.serviceWorker.register('/app/static/sw.js').catch(()=>{});}</script>
"""

_ANALYTICS_CODE = """
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','G-XXXXXXXXXX');</script>
"""

_PRO_CSS = """<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&display=swap');

:root{
    --archon-bg:#0B1220;
    --archon-surface:#111A2E;
    --archon-surface-2:#16233D;
    --archon-border:#2A3A5F;
    --archon-text:#E6EDF8;
    --archon-muted:#9FB0D1;
    --archon-primary:#2F6BFF;
    --archon-primary-2:#2457D6;
    --archon-success:#00A86B;
    --archon-danger:#E14B5A;
    --archon-warning:#F2A93B;
    --archon-mobile-nav-height:68px;
}

html{-webkit-text-size-adjust:100%}
body{-webkit-tap-highlight-color:transparent;overscroll-behavior-y:contain;font-family:'Pretendard',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif !important}
[data-testid="stAppViewContainer"],.stApp,section[data-testid="stMain"]{background:var(--archon-bg) !important;color:var(--archon-text) !important}

.stMetric{background:var(--archon-surface);padding:1rem;border-radius:12px;border:1px solid var(--archon-border);box-shadow:none !important}
.stMetric label,.stMetric [data-testid="stMetricLabel"]{color:var(--archon-muted) !important}
.stMetric [data-testid="stMetricValue"]{color:var(--archon-text) !important;font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace !important;font-variant-numeric:tabular-nums !important}
div[data-testid="stExpander"]{background:var(--archon-surface);border:1px solid var(--archon-border);border-radius:12px}
h1,h2,h3{color:var(--archon-text) !important;letter-spacing:-0.01em}

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
    background:linear-gradient(90deg,rgba(47,107,255,0.2),transparent) !important;
    border-left:3px solid var(--archon-primary) !important;
    font-weight:600 !important;
}
[data-testid="stSidebarNav"] a{
    padding:0.4rem 0.8rem !important;border-radius:4px;transition:background 0.2s;
    border-left:3px solid transparent !important;
}
[data-testid="stSidebarNav"] a:hover{background:rgba(47,107,255,0.12) !important}

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
.archon-toast.success{background:rgba(0,168,107,0.95);color:#08111F}
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

.mobile-bottom-nav{display:none;position:fixed;bottom:0;left:0;right:0;background:var(--archon-surface);border-top:1px solid var(--archon-border);z-index:2147483647;padding:0.3rem 0 env(safe-area-inset-bottom,0.3rem);box-shadow:0 -4px 16px rgba(0,0,0,0.35)}
.mobile-bottom-nav .nav-items{display:flex;justify-content:space-around;align-items:center;max-width:500px;margin:0 auto}
.mobile-bottom-nav .nav-item{display:flex;flex-direction:column;align-items:center;text-decoration:none;color:var(--archon-muted);font-size:0.65rem;padding:0.2rem 0.5rem;transition:color 0.2s}
.mobile-bottom-nav .nav-item:hover{color:var(--archon-primary)}
.mobile-bottom-nav .nav-icon{font-size:1.2rem;margin-bottom:0.15rem}
@media(max-width:768px){
.mobile-bottom-nav{display:block !important}
.mobile-bottom-nav{min-height:var(--archon-mobile-nav-height) !important}
.main .block-container{padding-bottom:calc(var(--archon-mobile-nav-height) + 2.6rem) !important}
[data-testid="manage-app-button"]{position:fixed !important;right:0.75rem !important;bottom:calc(var(--archon-mobile-nav-height) + 0.9rem) !important;z-index:2147483646 !important}
.stDeployButton{position:fixed !important;right:0.75rem !important;bottom:calc(var(--archon-mobile-nav-height) + 4.9rem) !important;z-index:2147483646 !important}
iframe[title="streamlitApp"] ~ * [data-testid="manage-app-button"]{bottom:calc(var(--archon-mobile-nav-height) + 0.9rem) !important}
@media(max-width:560px){
[data-testid="manage-app-button"]{top:0.8rem !important;bottom:auto !important;right:0.6rem !important}
.stDeployButton{top:4.3rem !important;bottom:auto !important;right:0.6rem !important}
iframe[title="streamlitApp"] ~ * [data-testid="manage-app-button"]{top:0.8rem !important;bottom:auto !important}
}
body.archon-sidebar-open .mobile-bottom-nav{opacity:0.22 !important;pointer-events:none !important}
body.archon-sidebar-open [data-testid="manage-app-button"],
body.archon-sidebar-open .stDeployButton{opacity:0 !important;pointer-events:none !important}
}

@media(max-width:768px){
.stMetric{background:var(--archon-surface) !important;border:1px solid var(--archon-border) !important;border-radius:12px !important;padding:0.8rem !important;margin-bottom:0.4rem !important}
[data-testid="stExpander"]{border:1px solid var(--archon-border) !important;border-radius:12px !important;margin-bottom:0.4rem !important}
[data-testid="stExpander"] summary{padding:0.8rem !important;font-size:0.95rem !important}
.stButton>button{border-radius:12px !important;font-weight:600 !important}
.stSelectbox>div>div,.stTextInput>div>div,.stNumberInput>div>div{border-radius:10px !important;font-size:16px !important}
}

/* Institutional surface */
.stMetric,.stForm,[data-testid="stExpander"]>details{
    background:var(--archon-surface) !important;
    border:1px solid var(--archon-border) !important;
    border-radius:12px !important;
    backdrop-filter:none !important;
    -webkit-backdrop-filter:none !important;
}

.stMetric{transition:border-color 0.2s ease,box-shadow 0.2s ease !important}
.stMetric:hover{border-color:#365187 !important;box-shadow:0 8px 20px rgba(7,14,28,0.32) !important}
.stMetric [data-testid="stMetricValue"]{font-weight:700 !important}

/* Buttons */
.stButton>button[kind="primary"]{
    background:linear-gradient(180deg,var(--archon-primary),var(--archon-primary-2)) !important;
    border:1px solid #4D7FFF !important;
    color:#F7FAFF !important;
    box-shadow:0 6px 18px rgba(47,107,255,0.28) !important;
    transition:all 0.2s ease !important;
}
.stButton>button[kind="primary"]:hover{
    box-shadow:0 8px 20px rgba(47,107,255,0.34) !important;
    transform:translateY(-1px) !important;
}
.stButton>button:not([kind="primary"]){
    background:var(--archon-surface-2) !important;
    color:var(--archon-text) !important;
    border:1px solid var(--archon-border) !important;
}

/* Tabs styling */
.stTabs [data-baseweb="tab"][aria-selected="true"]{
    background:linear-gradient(135deg,rgba(47,107,255,0.18),transparent) !important;
    border-bottom:2px solid var(--archon-primary) !important;
    color:var(--archon-primary) !important;
    font-weight:600 !important;
}
.stTabs [data-baseweb="tab"]{
    transition:all 0.2s ease !important;
    border-radius:8px 8px 0 0 !important;
}

/* Sidebar active page */
[data-testid="stSidebarNav"] a[aria-current="page"]{
    background:linear-gradient(90deg,rgba(47,107,255,0.2),transparent) !important;
    border-left:3px solid var(--archon-primary) !important;
    font-weight:700 !important;
    color:var(--archon-primary) !important;
}

/* Inputs glassmorphism */
.stTextInput>div>div,.stSelectbox>div>div,.stNumberInput>div>div,.stTextArea>div>div{
    background:var(--archon-surface-2) !important;
    border:1px solid var(--archon-border) !important;
    border-radius:12px !important;
    transition:border-color 0.2s !important;
}
.stTextInput>div>div:focus-within,.stSelectbox>div>div:focus-within,.stNumberInput>div>div:focus-within,.stTextArea>div>div:focus-within{
    border-color:rgba(47,107,255,0.8) !important;
    box-shadow:0 0 0 3px rgba(47,107,255,0.18) !important;
}

/* Expander glassmorphism */
[data-testid="stExpander"]>details>summary{
    border-radius:16px !important;
    transition:background 0.2s !important;
}
[data-testid="stExpander"]>details>summary:hover{
    background:rgba(47,107,255,0.08) !important;
}

/* Dataframe styling */
.stDataFrame [data-testid="stDataFrameResizable"]{
    border-radius:12px !important;
    border:1px solid var(--archon-border) !important;
    overflow:hidden !important;
}

.stDataFrame table{font-variant-numeric:tabular-nums !important}

/* Spinner custom */
.stSpinner>div{
    border-top-color:var(--archon-primary) !important;
}

/* Scrollbar */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(47,107,255,0.35);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:rgba(47,107,255,0.55)}

/* Page transition */
.main .block-container{
    animation:fadeInUp 0.3s ease-out !important;
}
@keyframes fadeInUp{
    from{opacity:0;transform:translateY(10px)}
    to{opacity:1;transform:translateY(0)}
}
</style>"""


_HIDE_GITHUB_ONLY = """<style>
/* GitHub 아이콘만 숨김 (일반 사용자) */
[data-testid="stToolbarActions"] a[href*="github"],
[data-testid="stToolbarActions"] button[title*="GitHub"],
[data-testid="stToolbarActions"] [aria-label*="GitHub"],
[data-testid="stToolbarActions"] [aria-label*="github"],
.stToolbarActions a[href*="github"] {
    display: none !important;
    visibility: hidden !important;
}
/* 앱매니저(Manage app)는 모두에게 표시 */
[data-testid="manage-app-button"],
.stDeployButton {
    display: flex !important;
    visibility: visible !important;
}
</style>"""

_SHOW_ALL_UI = """<style>
/* 관리자 페이지: GitHub 포함 전체 표시 */
[data-testid="stToolbarActions"],
[data-testid="stToolbarActions"] a,
[data-testid="stToolbarActions"] button,
[data-testid="manage-app-button"],
.stDeployButton {
    display: flex !important;
    visibility: visible !important;
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


_APP_SEARCH_INDEX = [
    {"path": "pages/1_데이터분석.py", "label": "데이터분석", "keywords": "차트 가격 데이터 비교"},
    {"path": "pages/2_글로벌마켓.py", "label": "글로벌마켓", "keywords": "미국시장 글로벌 지수 거시경제"},
    {"path": "pages/3_기술적분석.py", "label": "기술적분석", "keywords": "RSI MACD 볼린저 지표"},
    {"path": "pages/4_종목스크리너.py", "label": "종목스크리너", "keywords": "필터 스캔 배당주"},
    {"path": "pages/5_종목추천.py", "label": "종목추천", "keywords": "추천 매수 신호"},
    {"path": "pages/6_AI예측.py", "label": "AI예측", "keywords": "예측 모델 forecast"},
    {"path": "pages/7_백테스팅.py", "label": "백테스팅", "keywords": "전략 성과 검증"},
    {"path": "pages/8_리스크분석.py", "label": "리스크분석", "keywords": "VaR CVaR 변동성"},
    {"path": "pages/9_포트폴리오.py", "label": "포트폴리오", "keywords": "보유자산 비중 최적화"},
    {"path": "pages/10_자동매매.py", "label": "자동매매", "keywords": "오토파일럿 매수 매도"},
    {"path": "pages/11_AI채팅.py", "label": "AI채팅", "keywords": "챗봇 음성 TTS STT"},
    {"path": "pages/12_뉴스감성분석.py", "label": "뉴스감성분석", "keywords": "뉴스 감성"},
    {"path": "pages/13_마케팅도구.py", "label": "마케팅도구", "keywords": "콘텐츠 자동화"},
    {"path": "pages/14_결제.py", "label": "결제", "keywords": "구독 플랜 결제"},
    {"path": "pages/15_공지사항.py", "label": "공지사항", "keywords": "공지 알림"},
    {"path": "pages/16_약관.py", "label": "약관", "keywords": "이용약관 개인정보"},
    {"path": "pages/17_고객문의.py", "label": "고객문의", "keywords": "문의 고객센터 지원 요청"},
    {"path": "pages/18_자주하는질문.py", "label": "자주하는질문", "keywords": "FAQ 질문 답변 도움말"},
    {"path": "pages/19_외환자동매매.py", "label": "외환자동매매", "keywords": "FX 환율 달러 유로 외환 자동매매"},
    {"path": "pages/20_코인자동매매.py", "label": "코인자동매매", "keywords": "코인 비트코인 이더리움 암호화폐 자동매매"},
    {"path": "pages/99_관리자.py", "label": "관리자", "keywords": "사용자 플랜 운영"},
]


def _render_app_search():
    with st.expander("🔎 앱 검색", expanded=False):
        query = st.text_input("페이지/기능 검색", key="_app_search_query", placeholder="예: 자동매매, TTS, 리스크")
        if st.button("검색", key="_app_search_btn", use_container_width=True):
            q = query.strip().lower()
            if not q:
                st.info("검색어를 입력하세요.")
                return

            matches = []
            for item in _APP_SEARCH_INDEX:
                hay = f"{item['label']} {item['keywords']}".lower()
                if q in hay:
                    matches.append(item)

            if not matches:
                st.warning("검색 결과가 없습니다.")
                return

            st.caption(f"검색 결과 {len(matches)}건")
            for idx, item in enumerate(matches[:8], start=1):
                st.page_link(item["path"], label=f"{idx}. {item['label']}")


def inject_pro_css(hide_toolbar: bool = True, show_logout: bool = True):
    st.markdown(_PWA_META, unsafe_allow_html=True)
    st.markdown(_PRO_CSS, unsafe_allow_html=True)
    _viewer = st.session_state.get("user")
    _is_admin = bool(_viewer and _viewer.get("role") == "admin")
    _caller_file = ""
    try:
        import traceback as _tb
        for _frame in _tb.extract_stack():
            if "pages/" in _frame.filename:
                _caller_file = _frame.filename
                break
    except Exception:
        pass
    _is_admin_page = "관리자" in _caller_file or "99_" in _caller_file
    if hide_toolbar:
        if _is_admin and _is_admin_page:
            st.markdown(_SHOW_ALL_UI, unsafe_allow_html=True)
        else:
            st.markdown(_HIDE_GITHUB_ONLY, unsafe_allow_html=True)

    user = _viewer
    if not user:
        return

    st.markdown(_ANALYTICS_CODE, unsafe_allow_html=True)
    st.markdown("""
<div class="mobile-bottom-nav">
<div class="nav-items">
<a onclick="archonNav('/')" class="nav-item" style="cursor:pointer"><span class="nav-icon">🏠</span>홈</a>
<a onclick="archonNav('/데이터분석')" class="nav-item" style="cursor:pointer"><span class="nav-icon">📊</span>분석</a>
<a onclick="archonNav('/자동매매')" class="nav-item" style="cursor:pointer"><span class="nav-icon">🤖</span>매매</a>
<a onclick="archonNav('/종목추천')" class="nav-item" style="cursor:pointer"><span class="nav-icon">🏆</span>추천</a>
<a onclick="archonNav('/AI채팅')" class="nav-item" style="cursor:pointer"><span class="nav-icon">💬</span>AI</a>
</div>
</div>
""", unsafe_allow_html=True)

    components.html("""
<script>
(function syncArchonMobileOverlay(){
    var rootWindow = window.parent || window;
    var rootDocument = rootWindow.document;

    function archonWithAuth(url) {
        try {
            var token = rootWindow.localStorage.getItem('archon_auth_token') || '';
            if (!token) { return url; }
            var u = new URL(url, rootWindow.location.origin);
            u.searchParams.set('_auth', token);
            return u.pathname + u.search + u.hash;
        } catch (e) {
            return url;
        }
    }

    rootWindow.archonNav = function(path) {
        try {
            rootWindow.location.href = archonWithAuth(path);
        } catch (e) {
            rootWindow.location.href = path;
        }
    };

    function patchSidebarLinks() {
        try {
            var links = rootDocument.querySelectorAll('[data-testid="stSidebarNav"] a[href], [data-testid="stSidebarUserContent"] a[href]');
            links.forEach(function(link) {
                if (link.dataset.archonAuthPatched === '1') {
                    return;
                }
                link.dataset.archonAuthPatched = '1';
                var href = link.getAttribute('href') || '';
                if (!href || href.startsWith('#') || href.startsWith('javascript:') || href.indexOf('mailto:') === 0) {
                    return;
                }
                link.setAttribute('href', archonWithAuth(href));
                link.addEventListener('click', function() {
                    var latest = link.getAttribute('href') || href;
                    link.setAttribute('href', archonWithAuth(latest));
                });
            });
        } catch (e) {}
    }

    function applySidebarState() {
        var sidebar = rootDocument.querySelector('[data-testid="stSidebar"]');
        var opened = !!(sidebar && sidebar.getAttribute('aria-expanded') === 'true');
        rootDocument.body.classList.toggle('archon-sidebar-open', opened);

        var isMobile = rootWindow.matchMedia('(max-width: 768px)').matches;
        var manageBtn = rootDocument.querySelector('[data-testid="manage-app-button"]');
        var deployBtn = rootDocument.querySelector('.stDeployButton');
        var hideFloating = isMobile && opened;

        if (manageBtn) {
            manageBtn.style.opacity = hideFloating ? '0' : '1';
            manageBtn.style.pointerEvents = hideFloating ? 'none' : 'auto';
        }
        if (deployBtn) {
            deployBtn.style.opacity = hideFloating ? '0' : '1';
            deployBtn.style.pointerEvents = hideFloating ? 'none' : 'auto';
        }
    }

    function bindObserver() {
        applySidebarState();
        patchSidebarLinks();
        var sidebar = rootDocument.querySelector('[data-testid="stSidebar"]');
        if (!sidebar || sidebar.dataset.archonObserved === '1') {
            return;
        }
        sidebar.dataset.archonObserved = '1';
        var observer = new MutationObserver(function() {
            applySidebarState();
            patchSidebarLinks();
        });
        observer.observe(sidebar, { attributes: true, childList: true, subtree: true, attributeFilter: ['aria-expanded', 'href'] });
    }

    bindObserver();
    rootWindow.setTimeout(bindObserver, 350);
    rootWindow.setTimeout(bindObserver, 1000);
    rootWindow.setTimeout(patchSidebarLinks, 1500);
})();
</script>
""", height=0, width=0)

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
                from config.auth import logout as _auth_logout
                _auth_logout()

        st.markdown("---")
        from config.i18n import show_lang_selector, t as _t
        with st.expander("🌐 " + _t("language"), expanded=False):
            show_lang_selector()

        _render_app_search()

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
                        _client = importlib.import_module("openai").OpenAI(api_key=g_key)
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


def show_share_buttons():
    _url = "https://archon-pro.streamlit.app"
    _c1, _c2, _c3 = st.columns(3)
    with _c1:
        st.link_button("💬 카카오톡 공유", f"https://sharer.kakao.com/talk/friends/picker/link?url={_url}", use_container_width=True)
    with _c2:
        st.link_button("🐦 트위터 공유", f"https://twitter.com/intent/tweet?text=Archon%20AI&url={_url}", use_container_width=True)
    with _c3:
        if st.button("🔗 링크 복사", use_container_width=True, key="_share_copy"):
            st.code(_url)
            st.toast("링크가 표시되었습니다!")


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


def safe_run(func, fallback_msg="일시적 오류가 발생했습니다. 잠시 후 다시 시도해주세요."):
    try:
        return func()
    except Exception as e:
        st.error(f"{fallback_msg}")
        with st.expander("오류 상세"):
            st.code(str(e))
        return None


def safe_fetch(fetch_func, *args, **kwargs):
    try:
        result = fetch_func(*args, **kwargs)
        if result is None:
            st.warning("데이터를 가져올 수 없습니다. 잠시 후 다시 시도해주세요.")
        return result
    except ConnectionError:
        st.error("네트워크 연결을 확인해주세요.")
        return None
    except TimeoutError:
        st.error("서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.")
        return None
    except Exception as e:
        st.error(f"데이터 로딩 실패: {type(e).__name__}")
        return None
