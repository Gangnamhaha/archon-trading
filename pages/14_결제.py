import sys
import os
import importlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from config.auth import require_auth, is_pro, update_user_plan, get_plan_expiry
from config.styles import inject_pro_css
from data.database import (
    get_referral_code,
    use_referral_code,
    get_referral_stats,
    apply_verified_payment,
)

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


ALLOW_DEMO_PAYMENTS = str(st.secrets.get("ALLOW_DEMO_PAYMENTS", "false")).lower() in {"1", "true", "yes", "on"}
PLAN_CONFIG = {
    "monthly": {"amount": 99000, "currency": "krw"},
    "annual": {"amount": 990000, "currency": "krw"},
}


def _verify_stripe_checkout_for_user(session_id: str):
    if stripe is None or not stripe_api_key:
        return False, "Stripe 검증에 필요한 설정이 없습니다.", None

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        return False, f"Stripe 세션 조회 실패: {e}", None

    if getattr(session, "payment_status", "") != "paid":
        return False, "결제가 완료되지 않았습니다.", None
    if getattr(session, "status", "") != "complete":
        return False, "체크아웃 완료 상태가 아닙니다.", None

    metadata = getattr(session, "metadata", {}) or {}
    metadata_user_id = str(metadata.get("user_id", ""))
    if metadata_user_id != str(user.get("id")):
        return False, "현재 사용자와 결제 메타데이터가 일치하지 않습니다.", None

    plan_type = metadata.get("plan_type", "monthly")
    expected = PLAN_CONFIG.get(plan_type)
    if expected is None:
        return False, "알 수 없는 플랜 결제입니다.", None

    if int(getattr(session, "amount_total", 0) or 0) != int(expected["amount"]):
        return False, "결제 금액 검증에 실패했습니다.", None

    if str(getattr(session, "currency", "")).lower() != expected["currency"]:
        return False, "결제 통화 검증에 실패했습니다.", None

    return True, plan_type, session


def _sync_payment_success():
    payment_status = st.query_params.get("payment", "")
    provider = st.query_params.get("provider", "")

    if payment_status != "success" or is_pro(user):
        return

    if provider == "stripe":
        session_id = st.query_params.get("session_id", "")
        if not session_id:
            st.error("Stripe 결제 검증 정보가 누락되었습니다.")
            return

        verified, result, checkout_session = _verify_stripe_checkout_for_user(session_id)
        if verified:
            metadata = getattr(checkout_session, "metadata", {}) or {}
            plan_type = metadata.get("plan_type", "monthly")
            amount_total = int(getattr(checkout_session, "amount_total", 0) or 0)
            currency = str(getattr(checkout_session, "currency", "")).lower()
            payment_apply_status = apply_verified_payment(
                provider="stripe",
                payment_id=session_id,
                username=user["username"],
                plan_type=plan_type,
                amount=amount_total,
                currency=currency,
            )
            if payment_apply_status == "duplicate":
                st.warning("이미 처리된 결제입니다. 중복 반영하지 않습니다.")
                st.query_params.clear()
                return
            if payment_apply_status == "applied":
                st.success("Stripe 결제가 검증되어 Pro 플랜으로 업그레이드되었습니다.")
                st.query_params.clear()
                return
            if payment_apply_status == "user_not_found":
                st.error("결제 사용자 정보를 찾을 수 없습니다. 관리자에게 문의하세요.")
                st.query_params.clear()
                return
            st.error("결제 반영 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
            st.query_params.clear()
        else:
            st.error(f"결제 검증 실패: {result}")
            st.query_params.clear()
        return

    st.warning("자동 결제 확인이 지원되지 않는 결제수단입니다. 관리자 검증 후 플랜이 반영됩니다.")
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
        success_url=f"{base_url}?payment=success&provider=stripe&session_id={{CHECKOUT_SESSION_ID}}",
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

st.subheader("결제 수단")
pay_method = st.selectbox("결제 수단 선택", [
    "Stripe (해외 카드)",
    "토스페이먼츠 (카드/계좌이체/카카오페이)",
    "아임포트 Portone (통합 PG)",
    "카카오페이 (간편결제)",
])

def _show_pricing():
    p1, p2 = st.columns(2)
    with p1:
        st.markdown("### 월간\n## 월 99,000원")
    with p2:
        st.markdown("### 연간\n## 연 990,000원 (2개월 무료)")

if pay_method == "토스페이먼츠 (카드/계좌이체/카카오페이)":
    st.subheader("요금제")
    _show_pricing()
    toss_client_key = st.secrets.get("TOSS_CLIENT_KEY", "")
    if toss_client_key:
        import streamlit.components.v1 as components
        _toss_html = f"""
        <script src="https://js.tosspayments.com/v1/payment"></script>
        <button onclick="tossPayment()" style="width:100%;padding:14px;background:#0064FF;color:white;border:none;border-radius:8px;font-size:16px;font-weight:bold;cursor:pointer;">토스페이먼츠로 결제</button>
        <script>
        var tossPayments = TossPayments(\'{toss_client_key}\');
        function tossPayment() {{
            tossPayments.requestPayment(\'카드\', {{
                amount: 99000,
                orderId: \'archon-{user["username"]}-\' + Date.now(),
                orderName: \'Archon Pro 월간 플랜\',
                customerName: \'{user["username"]}\',
                successUrl: window.location.origin + \'?payment=success\',
                failUrl: window.location.origin + \'?payment=fail\',
            }});
        }}
        </script>
        """
        components.html(_toss_html, height=70)
    else:
        st.warning("토스페이먼츠 키 미설정. `.streamlit/secrets.toml`에 `TOSS_CLIENT_KEY`를 추가하세요.")
        if ALLOW_DEMO_PAYMENTS:
            if st.button("데모 결제 (토스)", type="primary", use_container_width=True, key="toss_demo"):
                update_user_plan(user["id"], "pro")
                st.success("데모 결제 완료! Pro 업그레이드됨.")
                st.rerun()
        else:
            st.info("데모 결제는 비활성화되어 있습니다. 운영 환경에서는 실제 결제 키를 사용하세요.")

elif pay_method == "아임포트 Portone (통합 PG)":
    st.subheader("요금제")
    _show_pricing()
    portone_code = st.secrets.get("PORTONE_IMP_CODE", "")
    if portone_code:
        import streamlit.components.v1 as components
        _portone_html = f"""
        <script src="https://cdn.iamport.kr/v1/iamport.js"></script>
        <button onclick="portonePayment()" style="width:100%;padding:14px;background:#FF6B35;color:white;border:none;border-radius:8px;font-size:16px;font-weight:bold;cursor:pointer;">아임포트로 결제</button>
        <script>
        var IMP = window.IMP;
        IMP.init(\'{portone_code}\');
        function portonePayment() {{
            IMP.request_pay({{
                pg: \'html5_inicis\',
                pay_method: \'card\',
                merchant_uid: \'archon-{user["username"]}-\' + Date.now(),
                name: \'Archon Pro 월간 플랜\',
                amount: 99000,
                buyer_name: \'{user["username"]}\',
            }}, function(rsp) {{
                if (rsp.success) {{
                    window.location.href = window.location.origin + \'?payment=success\';
                }} else {{
                    alert(\'결제 실패: \' + rsp.error_msg);
                }}
            }});
        }}
        </script>
        """
        components.html(_portone_html, height=70)
    else:
        st.warning("아임포트 코드 미설정. `.streamlit/secrets.toml`에 `PORTONE_IMP_CODE`를 추가하세요.")
        if ALLOW_DEMO_PAYMENTS:
            if st.button("데모 결제 (아임포트)", type="primary", use_container_width=True, key="portone_demo"):
                update_user_plan(user["id"], "pro")
                st.success("데모 결제 완료! Pro 업그레이드됨.")
                st.rerun()
        else:
            st.info("데모 결제는 비활성화되어 있습니다. 운영 환경에서는 실제 결제 키를 사용하세요.")

elif pay_method == "카카오페이 (간편결제)":
    st.subheader("요금제")
    _show_pricing()
    kakao_admin_key = st.secrets.get("KAKAO_ADMIN_KEY", "")
    if kakao_admin_key:
        import requests as _req
        if st.button("카카오페이로 결제", type="primary", use_container_width=True, key="kakao_pay"):
            try:
                _headers = {"Authorization": f"KakaoAK {kakao_admin_key}", "Content-Type": "application/x-www-form-urlencoded"}
                _data = {
                    "cid": "TC0ONETIME",
                    "partner_order_id": f"archon-{user['username']}",
                    "partner_user_id": user["username"],
                    "item_name": "Archon Pro 월간 플랜",
                    "quantity": 1,
                    "total_amount": 99000,
                    "tax_free_amount": 0,
                    "approval_url": st.secrets.get("APP_BASE_URL", "http://localhost:8501") + "?payment=success",
                    "cancel_url": st.secrets.get("APP_BASE_URL", "http://localhost:8501") + "?payment=cancel",
                    "fail_url": st.secrets.get("APP_BASE_URL", "http://localhost:8501") + "?payment=fail",
                }
                _resp = _req.post(
                    "https://kapi.kakao.com/v1/payment/ready",
                    headers=_headers,
                    data=_data,
                    timeout=10,
                )
                _resp.raise_for_status()
                _result = _resp.json()
                if "next_redirect_pc_url" in _result:
                    st.link_button("카카오페이 결제 페이지로 이동", _result["next_redirect_pc_url"], use_container_width=True)
                else:
                    st.error(f"카카오페이 오류: {_result}")
            except Exception as e:
                st.error(f"카카오페이 연동 실패: {e}")
    else:
        st.warning("카카오페이 키 미설정. `.streamlit/secrets.toml`에 `KAKAO_ADMIN_KEY`를 추가하세요.")
        if ALLOW_DEMO_PAYMENTS:
            if st.button("데모 결제 (카카오페이)", type="primary", use_container_width=True, key="kakao_demo"):
                update_user_plan(user["id"], "pro")
                st.success("데모 결제 완료! Pro 업그레이드됨.")
                st.rerun()
        else:
            st.info("데모 결제는 비활성화되어 있습니다. 운영 환경에서는 실제 결제 키를 사용하세요.")

else:
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
                        f"<script>window.location.href=\'{checkout.url}\';</script>",
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
                        f"<script>window.location.href=\'{checkout.url}\';</script>",
                        unsafe_allow_html=True,
                    )
                except Exception as e:
                    st.error(f"결제 세션 생성 실패: {e}")

    if not stripe_api_key or stripe is None:
        st.warning("Stripe 키가 설정되지 않아 데모 결제 모드로 동작합니다.")
        if ALLOW_DEMO_PAYMENTS:
            if st.button("데모 결제하기 (테스트 업그레이드)", type="primary", use_container_width=True):
                update_user_plan(user["id"], "pro")
                st.success("데모 결제가 완료되어 Pro 플랜으로 변경되었습니다.")
                st.rerun()
        else:
            st.info("데모 결제는 비활성화되어 있습니다. 운영 환경에서는 실제 결제 키를 사용하세요.")

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

st.markdown("---")
with st.expander("📋 환불 정책"):
    st.markdown("""
    - 전자상거래법에 따라 결제 후 **7일 이내** 청약철회 가능
    - 이미 이용한 기간은 **일할 계산**하여 차감
    - 환불 요청: 관리자에게 문의
    - 무료 체험(추천인 리워드) 기간은 환불 대상 아님
    """)
