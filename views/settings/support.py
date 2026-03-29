import streamlit as st

from config.auth import is_admin
from config.styles import show_legal_disclaimer
from data.database import add_customer_inquiry, get_customer_inquiries, add_notice, get_notices


def render_support(user: dict[str, str]):
    st.subheader("📞 고객지원")
    tab_inquiry, tab_faq, tab_notice, tab_terms = st.tabs(["📩 고객문의", "❓ 자주하는질문", "📢 공지사항", "📜 약관"])

    with tab_inquiry:
        st.caption("문의 내용을 남기면 관리자 페이지에서 확인하고 답변 상태를 업데이트합니다.")

        with st.form("customer_inquiry_form"):
            category = str(st.selectbox("문의 유형", ["계정", "결제", "자동매매", "버그", "기능요청", "기타"]) or "기타")
            title = st.text_input("제목", max_chars=120)
            content = st.text_area("문의 내용", height=180, placeholder="문제 상황, 재현 방법, 기대 결과를 적어주세요.")
            submitted = st.form_submit_button("문의 접수", type="primary", use_container_width=True)

        if submitted:
            if not title.strip() or not content.strip():
                st.error("제목과 문의 내용을 입력하세요.")
            else:
                add_customer_inquiry(user["username"], category, title.strip(), content.strip())
                st.success("문의가 접수되었습니다. 관리자 확인 후 상태가 업데이트됩니다.")
                st.rerun()

        st.markdown("---")
        st.markdown("#### 내 문의 내역")

        all_inquiries = get_customer_inquiries(status="전체", limit=300)
        if all_inquiries.empty:
            st.info("아직 문의 내역이 없습니다.")
        else:
            my_inquiries = all_inquiries[all_inquiries["username"] == user["username"]].copy()
            if my_inquiries.empty:
                st.info("아직 문의 내역이 없습니다.")
            else:
                display_cols = ["id", "category", "title", "status", "admin_note", "created_at", "updated_at"]
                for col in display_cols:
                    if col not in my_inquiries.columns:
                        my_inquiries[col] = ""
                st.dataframe(my_inquiries[display_cols], use_container_width=True, hide_index=True)

    with tab_faq:
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
        st.info("원하는 답변이 없다면 고객문의 탭에서 문의를 남겨주세요.")

    with tab_notice:
        if is_admin():
            with st.expander("공지 작성", expanded=False):
                with st.form("notice_form"):
                    n_title = st.text_input("제목")
                    n_content = st.text_area("내용", height=200)
                    if st.form_submit_button("발행", type="primary", use_container_width=True):
                        if n_title and n_content:
                            add_notice(n_title, n_content, user["username"])
                            st.success("공지가 발행되었습니다.")
                            st.rerun()

        st.markdown("---")
        notices = get_notices()
        if notices.empty:
            st.info("등록된 공지사항이 없습니다.")
        else:
            for _, row in notices.iterrows():
                with st.expander(f"**{row['title']}** - {row['created_at'][:10]}"):
                    st.markdown(row["content"])
                    st.caption(f"작성자: {row['author']} | {row['created_at']}")

    with tab_terms:
        tab_policy_terms, tab_policy_privacy = st.tabs(["이용약관", "개인정보처리방침"])

        with tab_policy_terms:
            st.markdown(
                """
### 서비스 기본 안내
- **서비스 명칭**: Archon AI 주식 분석 플랫폼
- **서비스 성격**: 본 서비스는 투자 '참고' 정보를 제공하는 도구이며, 금융투자업(투자자문업/투자일임업)에 해당하지 않습니다.

### 투자 관련 고지 및 면책
- **면책조항**: 본 서비스에서 제공하는 AI 추천, 분석 결과, 오토파일럿 매매는 투자 판단의 참고 자료일 뿐이며, 투자 결과에 대한 모든 책임은 이용자 본인에게 있습니다.
- 과거 수익률은 미래 수익을 보장하지 않습니다.
- 주식 투자는 원금 손실이 발생할 수 있으며, 그 손실은 투자자에게 귀속됩니다.
- 자동매매 관련: 오토파일럿 기능은 사용자가 설정한 조건에 따라 자동으로 매매 주문을 실행합니다. API 오류, 네트워크 장애, 시장 급변 등으로 인한 손실에 대해 서비스 제공자는 책임지지 않습니다.

### 구독, 결제 및 서비스 운영
- 구독/결제: Pro 플랜은 월 99,000원 / 연 990,000원이며, 전자상거래법에 따라 결제 후 7일 이내 청약철회가 가능합니다. 단, 이미 서비스를 이용한 기간에 대해서는 일할 계산하여 차감됩니다.
- 서비스 변경/중단: 서비스 제공자는 서비스 내용을 사전 고지 후 변경하거나 중단할 수 있습니다.
- 지적재산권: 본 서비스의 모든 코드, UI, 알고리즘은 서비스 제공자에게 귀속됩니다.
                """
            )

        with tab_policy_privacy:
            st.markdown(
                """
### 수집 항목 및 목적
- **수집하는 개인정보**: 사용자명, 비밀번호(해시), 증권사 API 키(암호화 저장), AI 대화 이력, 거래 내역, 포트폴리오 정보, 접속 로그
- **수집 목적**: 서비스 제공, 투자 분석, 자동매매 실행, 사용자 설정 복원

### 보관 및 제3자 제공
- **보관 기간**: 회원 탈퇴 시까지 (탈퇴 후 즉시 삭제, 법적 의무 보관 제외)
- **제3자 제공**: 증권사 API를 통한 매매 주문 시 해당 증권사에 주문 정보가 전송됩니다. 그 외 제3자에게 개인정보를 제공하지 않습니다.
- **AI API**: AI 채팅 기능 사용 시 대화 내용이 선택한 AI 제공사(OpenAI/Anthropic/Google)에 전송됩니다.

### 보안 및 이용자 권리
- **API 키 보안**: 증권사 API 키 및 AI API 키는 Fernet(AES-128-CBC+HMAC) 대칭 암호화를 적용하여 저장됩니다.
- **이용자 권리**: 이용자는 언제든지 자신의 개인정보 열람, 수정, 삭제를 요청할 수 있습니다.
- **개인정보보호 책임자**: [관리자에게 문의]
                """
            )

    show_legal_disclaimer()
