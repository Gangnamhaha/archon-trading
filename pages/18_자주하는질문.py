import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.auth import require_auth
from config.styles import inject_pro_css, show_legal_disclaimer


st.set_page_config(page_title="자주하는 질문", page_icon="❓", layout="wide")
require_auth()
inject_pro_css()

st.title("❓ 자주하는 질문")
st.caption("사용 중 자주 문의되는 내용을 먼저 확인해보세요.")

faq_items = [
    (
        "로그인이 안 돼요.",
        "아이디/비밀번호를 다시 확인하고, 비밀번호를 잊은 경우 관리자 페이지에서 초기화 요청을 진행하세요. "
        "세션 만료가 짧게 설정된 경우 재로그인이 필요할 수 있습니다.",
    ),
    (
        "오토파일럿은 미국 주식도 되나요?",
        "네. 자동매매 페이지에서 시장을 US로 선택하면 미국 종목 추천/시뮬레이션 매매 흐름으로 동작합니다.",
    ),
    (
        "결제가 완료됐는데 Pro가 안 바뀌어요.",
        "결제 페이지는 공급사 검증 후에만 Pro를 반영합니다. 결제 직후 반영이 안 되면 고객문의에 결제 시각/수단을 남겨주세요.",
    ),
    (
        "AI 채팅에서 마이크가 동작하지 않아요.",
        "브라우저 마이크 권한을 허용했는지 확인하세요. 회사망/브라우저 정책으로 차단될 수 있습니다.",
    ),
    (
        "추천 종목은 어떤 기준으로 나오나요?",
        "기술적 지표, 모멘텀, 거래량, 추세 일관성 등을 종합한 점수 기반으로 추천됩니다.",
    ),
    (
        "데이터가 느리거나 비어 있어요.",
        "시장 휴장, 데이터 공급 지연, 네트워크 상태에 따라 일부 지표가 지연될 수 있습니다. 잠시 후 다시 시도하세요.",
    ),
]

for question, answer in faq_items:
    with st.expander(f"Q. {question}"):
        st.markdown(f"A. {answer}")

st.markdown("---")
st.info("원하는 답변이 없다면 `고객문의` 메뉴에서 문의를 남겨주세요.")

show_legal_disclaimer()
