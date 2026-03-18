from typing import Any, Optional

import pandas as pd
import streamlit as st

from config.auth import get_plan_expiry, is_paid
from views.settings._payment_forms import (
    render_demo_button,
    render_kakao_button,
    render_plan_card,
    render_portone_button,
    render_referral_section,
    render_toss_button,
)
from views.settings._payment_logic import (
    apply_demo_plan,
    get_current_plan,
    get_plan_details,
    get_plan_name,
    setup_payment_runtime,
    start_stripe_checkout,
    sync_payment_success,
)


def _refresh_user_plan_in_session(user: dict[str, Any], plan: str) -> None:
    refreshed = dict(st.session_state.get("user") or user)
    refreshed["plan"] = plan
    st.session_state["user"] = refreshed
    user["plan"] = plan


def _render_plan_comparison_table() -> None:
    plan_df = pd.DataFrame(
        {
            "기능": [
                "지원 데이터 주기",
                "기술적 분석 지표",
                "포트폴리오",
                "뉴스감성분석",
                "백테스팅",
                "오토파일럿",
                "AI 예측",
                "종목추천 / 마케팅도구 / US 자동매매",
            ],
            "Free": ["일봉", "5개", "5종목", "-", "-", "-", "-", "-"],
            "Plus": ["분봉 / 주봉 / 월봉", "무제한", "무제한", "사용 가능", "사용 가능", "-", "-", "-"],
            "Pro": ["Plus 전체 포함", "무제한", "무제한", "사용 가능", "사용 가능", "사용 가능", "사용 가능", "사용 가능"],
        }
    )
    st.subheader("플랜 비교")
    st.table(plan_df)


def _render_stripe_section(user: dict[str, Any], stripe_api_key: str, stripe_module: Optional[object], allow_demo: bool) -> None:
    if not stripe_api_key or stripe_module is None:
        with st.expander("🔑 Stripe 키 발급 방법 (5분)", expanded=not allow_demo):
            st.markdown(
                """
1. [https://dashboard.stripe.com](https://dashboard.stripe.com) 접속 → 회원가입/로그인
2. 좌측 메뉴 **Developers → API keys**
3. **Secret key** 복사 (`sk_test_xxx...`)
4. `.streamlit/secrets.toml` 또는 Streamlit Cloud Secrets에 추가:
```toml
STRIPE_SECRET_KEY = "sk_test_xxx"
APP_BASE_URL = "https://archon-pro.streamlit.app"
```
5. 앱 재시작하면 실결제 버튼 자동 활성화
            """
            )

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        st.markdown("#### Plus")
        if stripe_api_key and stripe_module is not None:
            if st.button("Plus 월간 결제", type="primary", use_container_width=True, key="stripe_plus_monthly"):
                start_stripe_checkout(user, "plus_monthly")
            if st.button("Plus 연간 결제", use_container_width=True, key="stripe_plus_annual"):
                start_stripe_checkout(user, "plus_annual")
        else:
            st.warning("Stripe 키 미설정 — 데모 모드")
            render_demo_button(
                allow_demo,
                "✅ Plus 데모 결제 (테스트)",
                "stripe_plus_demo",
                lambda: apply_demo_plan(user, "plus_monthly", lambda plan: _refresh_user_plan_in_session(user, plan)),
            )
    with action_col2:
        st.markdown("#### Pro")
        if stripe_api_key and stripe_module is not None:
            if st.button("Pro 월간 결제", type="primary", use_container_width=True, key="stripe_pro_monthly"):
                start_stripe_checkout(user, "pro_monthly")
            if st.button("Pro 연간 결제", use_container_width=True, key="stripe_pro_annual"):
                start_stripe_checkout(user, "pro_annual")
        else:
            render_demo_button(
                allow_demo,
                "✅ Pro 데모 결제 (테스트)",
                "stripe_pro_demo",
                lambda: apply_demo_plan(user, "pro_monthly", lambda plan: _refresh_user_plan_in_session(user, plan)),
            )


def render_payment(user: dict[str, Any]) -> None:
    stripe_module, stripe_api_key, allow_demo_payments = setup_payment_runtime()
    sync_payment_success(user, stripe_api_key, lambda plan: _refresh_user_plan_in_session(user, plan))

    st.title("💳 Archon 플랜 결제")

    current_plan = get_current_plan(user)
    if current_plan == "pro":
        plan_expiry = get_plan_expiry(int(user["id"]))
        if plan_expiry:
            st.success(f"현재 Pro 플랜 이용 중 (만료일: {plan_expiry.strftime('%Y-%m-%d %H:%M')})")
        else:
            st.success("현재 Pro 플랜 이용 중 (만료일: 무제한)")
    elif current_plan == "plus" and is_paid(user):
        st.success("현재 Plus 플랜 이용 중")
    else:
        st.info("현재 Free 플랜 이용 중")

    _render_plan_comparison_table()

    st.subheader("결제 수단")
    pay_method = st.selectbox(
        "결제 수단 선택",
        [
            "Stripe (해외 카드)",
            "토스페이먼츠 (카드/계좌이체/카카오페이)",
            "아임포트 Portone (통합 PG)",
            "카카오페이 (간편결제)",
        ],
    )

    billing_cycle = "monthly"
    if pay_method != "Stripe (해외 카드)":
        billing_label = st.radio("결제 주기", ["월간", "연간"], horizontal=True, key="billing_cycle")
        billing_cycle = "annual" if billing_label == "연간" else "monthly"

    st.subheader("3-Tier 요금제")
    card_col1, card_col2, card_col3 = st.columns(3)
    with card_col1:
        render_plan_card("Free", "무료", "#94A3B8", ["기본 기능", "일봉 데이터", "지표 5개", "포트폴리오 5종목"])
    with card_col2:
        render_plan_card(
            "Plus",
            "₩49,000/월",
            "#38BDF8",
            ["분봉·주봉·월봉", "지표 무제한", "포트폴리오 무제한", "뉴스감성분석", "백테스팅"],
            badge="가장 균형잡힌 플랜",
        )
    with card_col3:
        render_plan_card(
            "Pro",
            "₩99,000/월",
            "#00D4AA",
            ["Plus 전체 포함", "오토파일럿", "AI예측", "종목추천", "마케팅도구 / US 자동매매"],
            badge="풀스택 자동매매",
        )

    st.subheader("결제 버튼")

    if pay_method == "Stripe (해외 카드)":
        _render_stripe_section(user, stripe_api_key, stripe_module, allow_demo_payments)
    else:
        plus_plan_type = f"plus_{billing_cycle}"
        pro_plan_type = f"pro_{billing_cycle}"
        action_col1, action_col2 = st.columns(2)

        if pay_method == "토스페이먼츠 (카드/계좌이체/카카오페이)":
            try:
                toss_client_key = st.secrets.get("TOSS_CLIENT_KEY", "")
            except Exception:
                toss_client_key = ""
            if not toss_client_key:
                with st.expander("🔑 토스페이먼츠 키 발급 방법 (5분)", expanded=not allow_demo_payments):
                    st.markdown(
                        """
1. [https://developers.tosspayments.com](https://developers.tosspayments.com) 접속 → 회원가입/로그인
2. **내 개발정보** → 테스트 Client Key 복사 (`test_ck_xxx...`)
3. `.streamlit/secrets.toml` 또는 Streamlit Cloud Secrets에 추가:
```toml
TOSS_CLIENT_KEY = "test_ck_xxx"
APP_BASE_URL = "https://archon-pro.streamlit.app"
```
4. 앱 재시작하면 토스페이먼츠 버튼 자동 활성화
                """
                    )
                st.warning("토스페이먼츠 키 미설정 — 데모 모드")
            with action_col1:
                st.markdown(f"#### Plus {str(get_plan_details(plus_plan_type)['price_label'])}")
                if toss_client_key:
                    render_toss_button(plus_plan_type, toss_client_key, str(user["username"]))
                else:
                    render_demo_button(
                        allow_demo_payments,
                        "✅ Plus 데모 결제 (테스트)",
                        "toss_plus_demo",
                        lambda: apply_demo_plan(
                            user,
                            plus_plan_type,
                            lambda plan: _refresh_user_plan_in_session(user, plan),
                        ),
                    )
            with action_col2:
                st.markdown(f"#### Pro {str(get_plan_details(pro_plan_type)['price_label'])}")
                if toss_client_key:
                    render_toss_button(pro_plan_type, toss_client_key, str(user["username"]))
                else:
                    render_demo_button(
                        allow_demo_payments,
                        "✅ Pro 데모 결제 (테스트)",
                        "toss_pro_demo",
                        lambda: apply_demo_plan(
                            user,
                            pro_plan_type,
                            lambda plan: _refresh_user_plan_in_session(user, plan),
                        ),
                    )
        elif pay_method == "아임포트 Portone (통합 PG)":
            try:
                portone_code = st.secrets.get("PORTONE_IMP_CODE", "")
            except Exception:
                portone_code = ""
            if not portone_code:
                st.warning("아임포트 코드 미설정. `.streamlit/secrets.toml`에 `PORTONE_IMP_CODE`를 추가하세요.")
            with action_col1:
                st.markdown(f"#### Plus {str(get_plan_details(plus_plan_type)['price_label'])}")
                if portone_code:
                    render_portone_button(plus_plan_type, portone_code, str(user["username"]))
                else:
                    render_demo_button(
                        allow_demo_payments,
                        "Plus 데모 결제",
                        "portone_plus_demo",
                        lambda: apply_demo_plan(
                            user,
                            plus_plan_type,
                            lambda plan: _refresh_user_plan_in_session(user, plan),
                        ),
                    )
            with action_col2:
                st.markdown(f"#### Pro {str(get_plan_details(pro_plan_type)['price_label'])}")
                if portone_code:
                    render_portone_button(pro_plan_type, portone_code, str(user["username"]))
                else:
                    render_demo_button(
                        allow_demo_payments,
                        "Pro 데모 결제",
                        "portone_pro_demo",
                        lambda: apply_demo_plan(
                            user,
                            pro_plan_type,
                            lambda plan: _refresh_user_plan_in_session(user, plan),
                        ),
                    )
        else:
            try:
                kakao_admin_key = st.secrets.get("KAKAO_ADMIN_KEY", "")
            except Exception:
                kakao_admin_key = ""
            if not kakao_admin_key:
                st.warning("카카오페이 키 미설정. `.streamlit/secrets.toml`에 `KAKAO_ADMIN_KEY`를 추가하세요.")
            with action_col1:
                st.markdown(f"#### Plus {str(get_plan_details(plus_plan_type)['price_label'])}")
                if kakao_admin_key:
                    render_kakao_button(plus_plan_type, kakao_admin_key, "Plus 카카오페이 결제", str(user["username"]))
                else:
                    render_demo_button(
                        allow_demo_payments,
                        "Plus 데모 결제",
                        "kakao_plus_demo",
                        lambda: apply_demo_plan(
                            user,
                            plus_plan_type,
                            lambda plan: _refresh_user_plan_in_session(user, plan),
                        ),
                    )
            with action_col2:
                st.markdown(f"#### Pro {str(get_plan_details(pro_plan_type)['price_label'])}")
                if kakao_admin_key:
                    render_kakao_button(pro_plan_type, kakao_admin_key, "Pro 카카오페이 결제", str(user["username"]))
                else:
                    render_demo_button(
                        allow_demo_payments,
                        "Pro 데모 결제",
                        "kakao_pro_demo",
                        lambda: apply_demo_plan(
                            user,
                            pro_plan_type,
                            lambda plan: _refresh_user_plan_in_session(user, plan),
                        ),
                    )

    render_referral_section(str(user["username"]), int(user["id"]), lambda plan: _refresh_user_plan_in_session(user, plan))
