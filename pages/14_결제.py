import sys
import os
import importlib
from typing import TypedDict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st

from config.auth import require_auth, is_paid, update_user_plan, get_plan_expiry
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

st.set_page_config(page_title="💳 Archon 플랜 결제", page_icon="💳", layout="wide")
user = require_auth()
inject_pro_css()

try:
    stripe_api_key = st.secrets.get("STRIPE_SECRET_KEY", "")
except Exception:
    stripe_api_key = ""
if stripe is not None and stripe_api_key:
    setattr(stripe, "api_key", stripe_api_key)


try:
    allow_demo_payments = str(st.secrets.get("ALLOW_DEMO_PAYMENTS", "false")).lower() in {"1", "true", "yes", "on"}
except Exception:
    allow_demo_payments = False


class PlanDetails(TypedDict):
    tier: str
    amount: int
    currency: str
    billing: str
    label: str
    price_label: str
    product_name: str
    description: str


def _clear_payment_query_params_keep_auth() -> None:
    auth_token = str(st.query_params.get("_auth", "") or "")
    st.query_params.clear()
    if auth_token:
        st.query_params["_auth"] = auth_token


PLAN_CONFIG: dict[str, PlanDetails] = {
    "plus_monthly": {
        "tier": "plus",
        "amount": 49000,
        "currency": "krw",
        "billing": "monthly",
        "label": "Plus 월간",
        "price_label": "월 49,000원",
        "product_name": "Archon Plus 월간 플랜",
        "description": "월 49,000원",
    },
    "plus_annual": {
        "tier": "plus",
        "amount": 490000,
        "currency": "krw",
        "billing": "annual",
        "label": "Plus 연간",
        "price_label": "연 490,000원 (2개월 무료)",
        "product_name": "Archon Plus 연간 플랜",
        "description": "연 490,000원 (2개월 무료)",
    },
    "pro_monthly": {
        "tier": "pro",
        "amount": 99000,
        "currency": "krw",
        "billing": "monthly",
        "label": "Pro 월간",
        "price_label": "월 99,000원",
        "product_name": "Archon Pro 월간 플랜",
        "description": "월 99,000원",
    },
    "pro_annual": {
        "tier": "pro",
        "amount": 990000,
        "currency": "krw",
        "billing": "annual",
        "label": "Pro 연간",
        "price_label": "연 990,000원 (2개월 무료)",
        "product_name": "Archon Pro 연간 플랜",
        "description": "연 990,000원 (2개월 무료)",
    },
}


def _get_plan_details(plan_type: str) -> PlanDetails:
    details = PLAN_CONFIG.get(plan_type)
    if details is None:
        raise ValueError(f"지원하지 않는 플랜입니다: {plan_type}")
    return details


def _get_plan_tier(plan_type: str) -> str:
    details = PLAN_CONFIG.get(plan_type, {})
    return str(details.get("tier", "free"))


def _get_plan_name(plan: str) -> str:
    return {"free": "Free", "plus": "Plus", "pro": "Pro"}.get(plan, "Free")


def _refresh_user_plan_in_session(plan: str) -> None:
    refreshed = dict(st.session_state.get("user") or user)
    refreshed["plan"] = plan
    st.session_state["user"] = refreshed
    user["plan"] = plan


def _get_current_plan() -> str:
    if user.get("role") == "admin":
        return "pro"
    current_plan = str(user.get("plan", "free"))
    return current_plan if current_plan in {"free", "plus", "pro"} else "free"


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

    if payment_status != "success":
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
            target_plan = _get_plan_tier(plan_type)
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
                _clear_payment_query_params_keep_auth()
                return
            if payment_apply_status == "applied":
                update_user_plan(user["id"], target_plan)
                _refresh_user_plan_in_session(target_plan)
                st.success(f"Stripe 결제가 검증되어 {_get_plan_name(target_plan)} 플랜으로 업그레이드되었습니다.")
                _clear_payment_query_params_keep_auth()
                return
            if payment_apply_status == "user_not_found":
                st.error("결제 사용자 정보를 찾을 수 없습니다. 관리자에게 문의하세요.")
                _clear_payment_query_params_keep_auth()
                return
            st.error("결제 반영 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
            _clear_payment_query_params_keep_auth()
        else:
            st.error(f"결제 검증 실패: {result}")
            _clear_payment_query_params_keep_auth()
        return

    plan_type = st.query_params.get("plan_type", "")
    target_plan = _get_plan_tier(plan_type)
    if target_plan == "free":
        st.warning("자동 결제 확인이 지원되지 않는 결제수단입니다. 관리자 검증 후 플랜이 반영됩니다.")
    else:
        st.warning(f"선택한 {_get_plan_name(target_plan)} 결제는 관리자 검증 후 플랜이 반영됩니다.")
    _clear_payment_query_params_keep_auth()


def _create_checkout_session(plan_type: str):
    if stripe is None:
        raise RuntimeError("stripe 패키지가 설치되어 있지 않습니다.")

    plan_details = _get_plan_details(plan_type)

    try:
        base_url = st.secrets.get("APP_BASE_URL", "http://localhost:8501")
    except Exception:
        base_url = "http://localhost:8501"

    return stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": str(plan_details["currency"]),
                    "unit_amount": int(plan_details["amount"]),
                    "product_data": {
                        "name": str(plan_details["product_name"]),
                        "description": str(plan_details["description"]),
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


def _start_stripe_checkout(plan_type: str):
    try:
        checkout = _create_checkout_session(plan_type)
        st.link_button("Stripe Checkout으로 이동", checkout.url, use_container_width=True)
        st.markdown(
            f"<script>window.location.href='{checkout.url}';</script>",
            unsafe_allow_html=True,
        )
    except Exception as e:
        st.error(f"결제 세션 생성 실패: {e}")


def _apply_demo_plan(plan_type: str):
    target_plan = _get_plan_tier(plan_type)
    update_user_plan(user["id"], target_plan)
    _refresh_user_plan_in_session(target_plan)
    st.success(f"데모 결제가 완료되어 {_get_plan_name(target_plan)} 플랜으로 변경되었습니다.")
    st.rerun()


def _render_plan_card(title: str, price: str, accent_color: str, features: list[str], badge: str = ""):
    is_free = price == "무료"
    price_main = price
    price_sub = ""
    if "/" in price:
        parts = price.split("/")
        price_main = parts[0]
        price_sub = "/" + parts[1]

    badge_html = ""
    if badge:
        badge_html = f"""
        <div style="
            display:inline-block;padding:0.25rem 0.75rem;border-radius:999px;
            background:linear-gradient(90deg,{accent_color}33,{accent_color}18);
            color:{accent_color};font-size:0.75rem;font-weight:700;
            border:1px solid {accent_color}44;margin-bottom:1rem;
            letter-spacing:0.03em;
        ">{badge}</div>"""

    feature_rows = "".join(f"""
        <div style="display:flex;align-items:center;gap:0.55rem;margin-bottom:0.55rem;">
            <span style="color:{accent_color};font-size:0.95rem;flex-shrink:0;">✓</span>
            <span style="color:#CBD5E0;font-size:0.92rem;">{f}</span>
        </div>""" for f in features)

    glow = f"0 0 0 1px {accent_color}33, 0 8px 32px {accent_color}18, 0 24px 48px rgba(0,0,0,0.45)"
    top_border = f"3px solid {accent_color}" if not is_free else f"3px solid #334155"
    bg = "linear-gradient(160deg, rgba(22,30,50,0.98) 0%, rgba(12,16,28,0.98) 100%)"

    st.markdown(f"""
    <div style="
        position:relative;height:100%;padding:1.6rem 1.5rem 1.8rem;
        border-radius:20px;border:1px solid {accent_color}30;
        border-top:{top_border};
        background:{bg};
        box-shadow:{glow};
        transition:transform 0.2s;
    ">
        {badge_html}
        <div style="font-size:1.1rem;font-weight:700;color:{accent_color};letter-spacing:0.04em;margin-bottom:0.5rem;">{title}</div>
        <div style="display:flex;align-items:baseline;gap:0.15rem;margin-bottom:1.2rem;">
            <span style="font-size:2.2rem;font-weight:900;color:#F1F5F9;line-height:1;">{price_main}</span>
            <span style="font-size:0.9rem;color:#64748B;font-weight:500;">{price_sub}</span>
        </div>
        <div style="height:1px;background:linear-gradient(90deg,{accent_color}44,transparent);margin-bottom:1.1rem;"></div>
        <div>{feature_rows}</div>
    </div>""", unsafe_allow_html=True)


def _render_toss_button(plan_type: str, toss_client_key: str):
    plan_details = _get_plan_details(plan_type)
    import streamlit.components.v1 as components

    button_suffix = plan_type.replace("_", "")
    button_label = f"토스 {_get_plan_name(_get_plan_tier(plan_type))} 결제"
    components.html(
        f"""
        <script src="https://js.tosspayments.com/v1/payment"></script>
        <button onclick="tossPayment{button_suffix}()" style="width:100%;padding:14px;background:#0064FF;color:white;border:none;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;">{button_label}</button>
        <script>
        var tossPayments{button_suffix} = TossPayments('{toss_client_key}');
        function tossPayment{button_suffix}() {{
            tossPayments{button_suffix}.requestPayment('카드', {{
                amount: {int(plan_details['amount'])},
                orderId: 'archon-{user["username"]}-{button_suffix}-' + Date.now(),
                orderName: '{str(plan_details['product_name'])}',
                customerName: '{user["username"]}',
                successUrl: window.location.origin + '?payment=success&provider=toss&plan_type={plan_type}',
                failUrl: window.location.origin + '?payment=fail',
            }});
        }}
        </script>
        """,
        height=72,
    )


def _render_portone_button(plan_type: str, portone_code: str):
    plan_details = _get_plan_details(plan_type)
    import streamlit.components.v1 as components

    button_suffix = plan_type.replace("_", "")
    button_label = f"아임포트 {_get_plan_name(_get_plan_tier(plan_type))} 결제"
    components.html(
        f"""
        <script src="https://cdn.iamport.kr/v1/iamport.js"></script>
        <button onclick="portonePayment{button_suffix}()" style="width:100%;padding:14px;background:#FF6B35;color:white;border:none;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;">{button_label}</button>
        <script>
        var IMP{button_suffix} = window.IMP;
        IMP{button_suffix}.init('{portone_code}');
        function portonePayment{button_suffix}() {{
            IMP{button_suffix}.request_pay({{
                pg: 'html5_inicis',
                pay_method: 'card',
                merchant_uid: 'archon-{user["username"]}-{button_suffix}-' + Date.now(),
                name: '{str(plan_details['product_name'])}',
                amount: {int(plan_details['amount'])},
                buyer_name: '{user["username"]}',
            }}, function(rsp) {{
                if (rsp.success) {{
                    window.location.href = window.location.origin + '?payment=success&provider=portone&plan_type={plan_type}';
                }} else {{
                    alert('결제 실패: ' + rsp.error_msg);
                }}
            }});
        }}
        </script>
        """,
        height=72,
    )


def _render_kakao_button(plan_type: str, kakao_admin_key: str, button_key: str):
    plan_details = _get_plan_details(plan_type)
    if st.button(button_key, type="primary", use_container_width=True, key=f"kakao_{plan_type}"):
        import requests as _req

        try:
            try:
                app_base_url = st.secrets.get("APP_BASE_URL", "http://localhost:8501")
            except Exception:
                app_base_url = "http://localhost:8501"
            response = _req.post(
                "https://kapi.kakao.com/v1/payment/ready",
                headers={
                    "Authorization": f"KakaoAK {kakao_admin_key}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "cid": "TC0ONETIME",
                    "partner_order_id": f"archon-{user['username']}-{plan_type}",
                    "partner_user_id": user["username"],
                    "item_name": str(plan_details["product_name"]),
                    "quantity": 1,
                    "total_amount": int(plan_details["amount"]),
                    "tax_free_amount": 0,
                    "approval_url": f"{app_base_url}?payment=success&provider=kakao&plan_type={plan_type}",
                    "cancel_url": f"{app_base_url}?payment=cancel",
                    "fail_url": f"{app_base_url}?payment=fail",
                },
                timeout=10,
            )
            response.raise_for_status()
            result = response.json()
            if "next_redirect_pc_url" in result:
                st.link_button("카카오페이 결제 페이지로 이동", result["next_redirect_pc_url"], use_container_width=True)
            else:
                st.error(f"카카오페이 오류: {result}")
        except Exception as e:
            st.error(f"카카오페이 연동 실패: {e}")


def _render_demo_button(plan_type: str, label: str, key: str):
    if allow_demo_payments:
        if st.button(label, type="primary", use_container_width=True, key=key):
            _apply_demo_plan(plan_type)
    else:
        st.info("데모 결제는 비활성화되어 있습니다. 운영 환경에서는 실제 결제 키를 사용하세요.")


_sync_payment_success()

st.title("💳 Archon 플랜 결제")

current_plan = _get_current_plan()
if current_plan == "pro":
    plan_expiry = get_plan_expiry(user["id"])
    if plan_expiry:
        st.success(f"현재 Pro 플랜 이용 중 (만료일: {plan_expiry.strftime('%Y-%m-%d %H:%M')})")
    else:
        st.success("현재 Pro 플랜 이용 중 (만료일: 무제한)")
elif current_plan == "plus" and is_paid(user):
    st.success("현재 Plus 플랜 이용 중")
else:
    st.info("현재 Free 플랜 이용 중")

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
        "Free": [
            "일봉",
            "5개",
            "5종목",
            "-",
            "-",
            "-",
            "-",
            "-",
        ],
        "Plus": [
            "분봉 / 주봉 / 월봉",
            "무제한",
            "무제한",
            "사용 가능",
            "사용 가능",
            "-",
            "-",
            "-",
        ],
        "Pro": [
            "Plus 전체 포함",
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
    _render_plan_card("Free", "무료", "#94A3B8", ["기본 기능", "일봉 데이터", "지표 5개", "포트폴리오 5종목"])
with card_col2:
    _render_plan_card(
        "Plus",
        "₩49,000/월",
        "#38BDF8",
        ["분봉·주봉·월봉", "지표 무제한", "포트폴리오 무제한", "뉴스감성분석", "백테스팅"],
        badge="가장 균형잡힌 플랜",
    )
with card_col3:
    _render_plan_card(
        "Pro",
        "₩99,000/월",
        "#00D4AA",
        ["Plus 전체 포함", "오토파일럿", "AI예측", "종목추천", "마케팅도구 / US 자동매매"],
        badge="풀스택 자동매매",
    )

st.subheader("결제 버튼")

if pay_method == "Stripe (해외 카드)":
    if not stripe_api_key or stripe is None:
        with st.expander("🔑 Stripe 키 발급 방법 (5분)", expanded=not allow_demo_payments):
            st.markdown("""
1. [https://dashboard.stripe.com](https://dashboard.stripe.com) 접속 → 회원가입/로그인
2. 좌측 메뉴 **Developers → API keys**
3. **Secret key** 복사 (`sk_test_xxx...`)
4. `.streamlit/secrets.toml` 또는 Streamlit Cloud Secrets에 추가:
```toml
STRIPE_SECRET_KEY = "sk_test_xxx"
APP_BASE_URL = "https://archon-pro.streamlit.app"
```
5. 앱 재시작하면 실결제 버튼 자동 활성화
            """)

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        st.markdown("#### Plus")
        if stripe_api_key and stripe is not None:
            if st.button("Plus 월간 결제", type="primary", use_container_width=True, key="stripe_plus_monthly"):
                _start_stripe_checkout("plus_monthly")
            if st.button("Plus 연간 결제", use_container_width=True, key="stripe_plus_annual"):
                _start_stripe_checkout("plus_annual")
        else:
            st.warning("Stripe 키 미설정 — 데모 모드")
            _render_demo_button("plus_monthly", "✅ Plus 데모 결제 (테스트)", "stripe_plus_demo")
    with action_col2:
        st.markdown("#### Pro")
        if stripe_api_key and stripe is not None:
            if st.button("Pro 월간 결제", type="primary", use_container_width=True, key="stripe_pro_monthly"):
                _start_stripe_checkout("pro_monthly")
            if st.button("Pro 연간 결제", use_container_width=True, key="stripe_pro_annual"):
                _start_stripe_checkout("pro_annual")
        else:
            _render_demo_button("pro_monthly", "✅ Pro 데모 결제 (테스트)", "stripe_pro_demo")

elif pay_method == "토스페이먼츠 (카드/계좌이체/카카오페이)":
    plus_plan_type = f"plus_{billing_cycle}"
    pro_plan_type = f"pro_{billing_cycle}"
    try:
        toss_client_key = st.secrets.get("TOSS_CLIENT_KEY", "")
    except Exception:
        toss_client_key = ""
    if not toss_client_key:
        with st.expander("🔑 토스페이먼츠 키 발급 방법 (5분)", expanded=not allow_demo_payments):
            st.markdown("""
1. [https://developers.tosspayments.com](https://developers.tosspayments.com) 접속 → 회원가입/로그인
2. **내 개발정보** → 테스트 Client Key 복사 (`test_ck_xxx...`)
3. `.streamlit/secrets.toml` 또는 Streamlit Cloud Secrets에 추가:
```toml
TOSS_CLIENT_KEY = "test_ck_xxx"
APP_BASE_URL = "https://archon-pro.streamlit.app"
```
4. 앱 재시작하면 토스페이먼츠 버튼 자동 활성화
            """)
        st.warning("토스페이먼츠 키 미설정 — 데모 모드")
    action_col1, action_col2 = st.columns(2)
    with action_col1:
        st.markdown(f"#### Plus {str(_get_plan_details(plus_plan_type)['price_label'])}")
        if toss_client_key:
            _render_toss_button(plus_plan_type, toss_client_key)
        else:
            _render_demo_button(plus_plan_type, "✅ Plus 데모 결제 (테스트)", "toss_plus_demo")
    with action_col2:
        st.markdown(f"#### Pro {str(_get_plan_details(pro_plan_type)['price_label'])}")
        if toss_client_key:
            _render_toss_button(pro_plan_type, toss_client_key)
        else:
            _render_demo_button(pro_plan_type, "✅ Pro 데모 결제 (테스트)", "toss_pro_demo")

elif pay_method == "아임포트 Portone (통합 PG)":
    plus_plan_type = f"plus_{billing_cycle}"
    pro_plan_type = f"pro_{billing_cycle}"
    try:
        portone_code = st.secrets.get("PORTONE_IMP_CODE", "")
    except Exception:
        portone_code = ""
    if not portone_code:
        st.warning("아임포트 코드 미설정. `.streamlit/secrets.toml`에 `PORTONE_IMP_CODE`를 추가하세요.")
    action_col1, action_col2 = st.columns(2)
    with action_col1:
        st.markdown(f"#### Plus {str(_get_plan_details(plus_plan_type)['price_label'])}")
        if portone_code:
            _render_portone_button(plus_plan_type, portone_code)
        else:
            _render_demo_button(plus_plan_type, "Plus 데모 결제", "portone_plus_demo")
    with action_col2:
        st.markdown(f"#### Pro {str(_get_plan_details(pro_plan_type)['price_label'])}")
        if portone_code:
            _render_portone_button(pro_plan_type, portone_code)
        else:
            _render_demo_button(pro_plan_type, "Pro 데모 결제", "portone_pro_demo")

else:
    plus_plan_type = f"plus_{billing_cycle}"
    pro_plan_type = f"pro_{billing_cycle}"
    try:
        kakao_admin_key = st.secrets.get("KAKAO_ADMIN_KEY", "")
    except Exception:
        kakao_admin_key = ""
    if not kakao_admin_key:
        st.warning("카카오페이 키 미설정. `.streamlit/secrets.toml`에 `KAKAO_ADMIN_KEY`를 추가하세요.")
    action_col1, action_col2 = st.columns(2)
    with action_col1:
        st.markdown(f"#### Plus {str(_get_plan_details(plus_plan_type)['price_label'])}")
        if kakao_admin_key:
            _render_kakao_button(plus_plan_type, kakao_admin_key, "Plus 카카오페이 결제")
        else:
            _render_demo_button(plus_plan_type, "Plus 데모 결제", "kakao_plus_demo")
    with action_col2:
        st.markdown(f"#### Pro {str(_get_plan_details(pro_plan_type)['price_label'])}")
        if kakao_admin_key:
            _render_kakao_button(pro_plan_type, kakao_admin_key, "Pro 카카오페이 결제")
        else:
            _render_demo_button(pro_plan_type, "Pro 데모 결제", "kakao_pro_demo")

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
        _refresh_user_plan_in_session("pro")
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
