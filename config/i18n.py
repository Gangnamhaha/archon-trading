from typing import Dict
import streamlit as st

_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "app_title": {"ko": "🏛️ ARCHON", "en": "🏛️ ARCHON"},
    "app_subtitle": {"ko": "AI 기반 주식 자동매매 플랫폼", "en": "AI-Powered Stock Auto-Trading Platform"},
    "login": {"ko": "로그인", "en": "Login"},
    "logout": {"ko": "로그아웃", "en": "Logout"},
    "username": {"ko": "아이디", "en": "Username"},
    "password": {"ko": "비밀번호", "en": "Password"},
    "agree_terms": {"ko": "이용약관 및 개인정보처리방침에 동의합니다", "en": "I agree to the Terms of Service and Privacy Policy"},
    "agree_required": {"ko": "약관에 동의해야 로그인할 수 있습니다.", "en": "You must agree to the terms to log in."},
    "login_failed": {"ko": "아이디 또는 비밀번호가 틀렸습니다.", "en": "Invalid username or password."},
    "home": {"ko": "홈", "en": "Home"},
    "data_analysis": {"ko": "데이터분석", "en": "Data Analysis"},
    "technical": {"ko": "기술적분석", "en": "Technical Analysis"},
    "backtest": {"ko": "백테스팅", "en": "Backtesting"},
    "portfolio": {"ko": "포트폴리오", "en": "Portfolio"},
    "auto_trade": {"ko": "자동매매", "en": "Auto Trading"},
    "ai_predict": {"ko": "AI예측", "en": "AI Prediction"},
    "screener": {"ko": "종목스크리너", "en": "Stock Screener"},
    "news": {"ko": "뉴스감성분석", "en": "News Sentiment"},
    "risk": {"ko": "리스크분석", "en": "Risk Analysis"},
    "recommend": {"ko": "종목추천", "en": "Stock Picks"},
    "admin": {"ko": "관리자", "en": "Admin"},
    "ai_chat": {"ko": "AI채팅", "en": "AI Chat"},
    "payment": {"ko": "결제", "en": "Payment"},
    "terms": {"ko": "약관", "en": "Terms"},
    "notices": {"ko": "공지사항", "en": "Notices"},
    "marketing": {"ko": "마케팅도구", "en": "Marketing Tools"},
    "global_market": {"ko": "글로벌마켓", "en": "Global Market"},
    "welcome": {"ko": "환영합니다", "en": "Welcome"},
    "current_plan": {"ko": "현재 플랜", "en": "Current Plan"},
    "free_plan": {"ko": "Free 플랜", "en": "Free Plan"},
    "pro_plan": {"ko": "Pro 플랜", "en": "Pro Plan"},
    "upgrade": {"ko": "Pro 업그레이드", "en": "Upgrade to Pro"},
    "pro_only": {"ko": "Pro 전용 기능입니다.", "en": "This is a Pro-only feature."},
    "loading": {"ko": "로딩 중...", "en": "Loading..."},
    "no_data": {"ko": "데이터가 없습니다.", "en": "No data available."},
    "save": {"ko": "저장", "en": "Save"},
    "cancel": {"ko": "취소", "en": "Cancel"},
    "delete": {"ko": "삭제", "en": "Delete"},
    "confirm": {"ko": "확인", "en": "Confirm"},
    "search": {"ko": "검색", "en": "Search"},
    "start": {"ko": "시작", "en": "Start"},
    "stop": {"ko": "중지", "en": "Stop"},
    "settings": {"ko": "설정", "en": "Settings"},
    "disclaimer": {
        "ko": "⚠️ 본 서비스는 투자 참고용이며 투자자문에 해당하지 않습니다. 투자 결과의 책임은 이용자에게 있으며, 원금 손실이 발생할 수 있습니다.",
        "en": "⚠️ This service is for reference only and does not constitute investment advice. Users are responsible for their own investment decisions. Loss of principal may occur."
    },
    "language": {"ko": "언어", "en": "Language"},
    "newsletter_title": {"ko": "📧 뉴스레터 구독", "en": "📧 Newsletter"},
    "subscribe": {"ko": "구독", "en": "Subscribe"},
    "subscribed": {"ko": "구독 완료!", "en": "Subscribed!"},
    "already_subscribed": {"ko": "이미 구독 중입니다.", "en": "Already subscribed."},
    "app_guide": {"ko": "🤖 앱 가이드", "en": "🤖 App Guide"},
    "autopilot": {"ko": "오토파일럿", "en": "Autopilot"},
    "scan": {"ko": "스캔", "en": "Scan"},
    "buy": {"ko": "매수", "en": "Buy"},
    "sell": {"ko": "매도", "en": "Sell"},
    "hold": {"ko": "관망", "en": "Hold"},
    "strong_buy": {"ko": "강력 매수", "en": "Strong Buy"},
    "strong_sell": {"ko": "강력 매도", "en": "Strong Sell"},
}


def get_lang() -> str:
    return st.session_state.get("lang", "ko")


def set_lang(lang: str):
    st.session_state["lang"] = lang


def t(key: str) -> str:
    lang = get_lang()
    entry = _TRANSLATIONS.get(key)
    if entry is None:
        return key
    return entry.get(lang, entry.get("ko", key))


def show_lang_selector():
    lang = get_lang()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🇰🇷 한국어", use_container_width=True, key="_lang_ko",
                      type="primary" if lang == "ko" else "secondary"):
            set_lang("ko")
            st.rerun()
    with col2:
        if st.button("🇺🇸 English", use_container_width=True, key="_lang_en",
                      type="primary" if lang == "en" else "secondary"):
            set_lang("en")
            st.rerun()
