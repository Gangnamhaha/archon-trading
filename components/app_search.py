# pyright: basic
import streamlit as st


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


def render_app_search():
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
