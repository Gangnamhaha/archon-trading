import sys
import os
import importlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from config.auth import require_auth, is_pro, update_user_plan, get_plan_expiry
from config.styles import inject_pro_css
from data.database import get_referral_code, use_referral_code, get_referral_stats

try:
    stripe = importlib.import_module("stripe")
except ModuleNotFoundError:
    stripe = None

st.set_page_config(page_title="💳 Pro 플랜 결제", page_icon="💳", layout="wide")
user = require_auth()
inject_pro_css()

stripe_api_key = st.secrets.get("STRIPE_SECRET_KEY", "")
if stripe is not None:
    setattr(stripe, "api_key", stripe_api_key)


def _sync_payment_success():
    payment_status = st.query_params.get("payment", "")
    if payment_status == "success" and not is_pro(user):
        update_user_plan(user["id"], "pro")
        st.success("결제가 완료되어 Pro 플랜으로 업그레이드되었습니다.")
        st.query_params.clear()


def _create_checkout_session(plan_type: str):
    if stripe is None:
        raise RuntimeError("stripe 패키지가 설치되어 있지 않습니다.")

    base_url = st.secrets.get("APP_BASE_URL", "http://localhost:8501")

    if plan_type == "annual":
        amount = 990000
        product_name = "Archon Pro 연간 플랜"
        description = "연 990,000원 (2개월 무료)"
    else:
        amount = 99000
        product_name = "Archon Pro 월간 플랜"
        description = "월 99,000원"

    return stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "krw",
                    "unit_amount": amount,
                    "product_data": {
                        "name": product_name,
                        "description": description,
                    },
                },
                "quantity": 1,
            }
        ],
        success_url=f"{base_url}?payment=success",
        cancel_url=f"{base_url}?payment=cancel",
        metadata={
            "user_id": str(user["id"]),
            "username": user["username"],
            "plan_type": plan_type,
        },
    )


_sync_payment_success()

st.title("💳 Pro 플랜 결제")

if is_pro(user):
    plan_expiry = get_plan_expiry(user["id"])
    if plan_expiry:
        st.success(f"현재 Pro 플랜 이용 중 (만료일: {plan_expiry.strftime('%Y-%m-%d %H:%M')})")
    else:
        st.success("현재 Pro 플랜 이용 중 (만료일: 무제한)")
else:
    st.info("현재 Free 플랜 이용 중")

plan_df = pd.DataFrame(
    {
        "기능": [
            "데이터분석",
            "기술적 분석 지표",
            "포트폴리오/워치리스트",
            "백테스팅",
            "AI 예측",
            "리스크 분석",
            "AI 종목추천",
            "자동매매",
        ],
        "Free": [
            "일봉만",
            "5개 제한",
            "제한 있음",
            "-",
            "-",
            "-",
            "-",
            "-",
        ],
        "Pro": [
            "분봉/주봉/월봉",
            "무제한",
            "무제한",
            "사용 가능",
            "사용 가능",
            "사용 가능",
            "사용 가능",
            "사용 가능",
        ],
    }
)

st.subheader("플랜 비교")
st.table(plan_df)

st.subheader("요금제")
price_col1, price_col2 = st.columns(2)

with price_col1:
    st.markdown("### 월간")
    st.markdown("## 월 99,000원")
    if stripe_api_key and stripe is not None:
        if st.button("결제하기 (월간)", type="primary", use_container_width=True):
            try:
                checkout = _create_checkout_session("monthly")
                st.link_button("Stripe Checkout으로 이동", checkout.url, use_container_width=True)
                st.markdown(
                    f"<script>window.location.href='{checkout.url}';</script>",
                    unsafe_allow_html=True,
                )
            except Exception as e:
                st.error(f"결제 세션 생성 실패: {e}")

with price_col2:
    st.markdown("### 연간")
    st.markdown("## 연 990,000원 (2개월 무료)")
    if stripe_api_key and stripe is not None:
        if st.button("결제하기 (연간)", type="primary", use_container_width=True):
            try:
                checkout = _create_checkout_session("annual")
                st.link_button("Stripe Checkout으로 이동", checkout.url, use_container_width=True)
                st.markdown(
                    f"<script>window.location.href='{checkout.url}';</script>",
                    unsafe_allow_html=True,
                )
            except Exception as e:
                st.error(f"결제 세션 생성 실패: {e}")

if not stripe_api_key or stripe is None:
    st.warning("Stripe 키가 설정되지 않아 데모 결제 모드로 동작합니다.")
    if st.button("데모 결제하기 (테스트 업그레이드)", type="primary", use_container_width=True):
        update_user_plan(user["id"], "pro")
        st.success("데모 결제가 완료되어 Pro 플랜으로 변경되었습니다.")
        st.rerun()

st.markdown("---")
st.subheader("추천인 리워드")
st.caption("친구 초대 시 양쪽 모두 Pro 7일 무료!")

my_code = get_referral_code(user["username"])
success_count = get_referral_stats(user["username"])

metric_col1, metric_col2 = st.columns([2, 1])
with metric_col1:
    st.markdown("내 추천인 코드")
    st.code(my_code)
    st.markdown(
        f"""
        <button onclick=\"navigator.clipboard.writeText('{my_code}')\" style=\"
            background:#00D4AA;color:#111;border:none;padding:0.45rem 0.8rem;
            border-radius:8px;cursor:pointer;font-weight:600;\">코드 복사</button>
        """,
        unsafe_allow_html=True,
    )
with metric_col2:
    st.metric("성공 초대 수", success_count)

with st.form("referral_use_form"):
    input_code = st.text_input("추천인 코드 입력", max_chars=8).strip().upper()
    submitted = st.form_submit_button("코드 적용", type="primary", use_container_width=True)

if submitted:
    ok, message = use_referral_code(input_code, user["username"])
    if ok:
        update_user_plan(user["id"], "pro")
        st.success(message)
        st.rerun()
    else:
        st.error(message)
