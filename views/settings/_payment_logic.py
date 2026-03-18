import importlib
from typing import Any, Optional, Tuple, TypedDict

import streamlit as st

from config.auth import update_user_plan
from data.database import apply_verified_payment

try:
    stripe = importlib.import_module("stripe")
except ModuleNotFoundError:
    stripe = None


class PlanDetails(TypedDict):
    tier: str
    amount: int
    currency: str
    billing: str
    label: str
    price_label: str
    product_name: str
    description: str


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


def clear_payment_query_params_keep_auth() -> None:
    auth_token = str(st.query_params.get("_auth", "") or "")
    st.query_params.clear()
    if auth_token:
        st.query_params["_auth"] = auth_token


def get_plan_details(plan_type: str) -> PlanDetails:
    details = PLAN_CONFIG.get(plan_type)
    if details is None:
        raise ValueError(f"지원하지 않는 플랜입니다: {plan_type}")
    return details


def get_plan_tier(plan_type: str) -> str:
    details = PLAN_CONFIG.get(plan_type, {})
    return str(details.get("tier", "free"))


def get_plan_name(plan: str) -> str:
    return {"free": "Free", "plus": "Plus", "pro": "Pro"}.get(plan, "Free")


def get_current_plan(user: dict[str, Any]) -> str:
    if user.get("role") == "admin":
        return "pro"
    current_plan = str(user.get("plan", "free"))
    return current_plan if current_plan in {"free", "plus", "pro"} else "free"


def setup_payment_runtime() -> Tuple[Optional[object], str, bool]:
    stripe_api_key = ""
    allow_demo_payments = False

    try:
        stripe_api_key = st.secrets.get("STRIPE_SECRET_KEY", "")
    except Exception:
        stripe_api_key = ""

    if stripe is not None and stripe_api_key:
        setattr(stripe, "api_key", stripe_api_key)

    try:
        allow_demo_payments = str(st.secrets.get("ALLOW_DEMO_PAYMENTS", "false")).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    except Exception:
        allow_demo_payments = False

    return stripe, stripe_api_key, allow_demo_payments


def _verify_stripe_checkout_for_user(user: dict[str, Any], session_id: str, stripe_api_key: str):
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


def sync_payment_success(user: dict[str, Any], stripe_api_key: str, refresh_user_plan_in_session) -> None:
    payment_status = st.query_params.get("payment", "")
    provider = st.query_params.get("provider", "")

    if payment_status != "success":
        return

    if provider == "stripe":
        session_id = st.query_params.get("session_id", "")
        if not session_id:
            st.error("Stripe 결제 검증 정보가 누락되었습니다.")
            return

        verified, result, checkout_session = _verify_stripe_checkout_for_user(user, session_id, stripe_api_key)
        if verified:
            metadata = getattr(checkout_session, "metadata", {}) or {}
            plan_type = metadata.get("plan_type", "monthly")
            target_plan = get_plan_tier(plan_type)
            amount_total = int(getattr(checkout_session, "amount_total", 0) or 0)
            currency = str(getattr(checkout_session, "currency", "")).lower()
            payment_apply_status = apply_verified_payment(
                provider="stripe",
                payment_id=session_id,
                username=str(user["username"]),
                plan_type=plan_type,
                amount=amount_total,
                currency=currency,
            )
            if payment_apply_status == "duplicate":
                st.warning("이미 처리된 결제입니다. 중복 반영하지 않습니다.")
                clear_payment_query_params_keep_auth()
                return
            if payment_apply_status == "applied":
                update_user_plan(int(user["id"]), target_plan)
                refresh_user_plan_in_session(target_plan)
                st.success(f"Stripe 결제가 검증되어 {get_plan_name(target_plan)} 플랜으로 업그레이드되었습니다.")
                clear_payment_query_params_keep_auth()
                return
            if payment_apply_status == "user_not_found":
                st.error("결제 사용자 정보를 찾을 수 없습니다. 관리자에게 문의하세요.")
                clear_payment_query_params_keep_auth()
                return
            st.error("결제 반영 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
            clear_payment_query_params_keep_auth()
        else:
            st.error(f"결제 검증 실패: {result}")
            clear_payment_query_params_keep_auth()
        return

    plan_type = st.query_params.get("plan_type", "")
    target_plan = get_plan_tier(plan_type)
    if target_plan == "free":
        st.warning("자동 결제 확인이 지원되지 않는 결제수단입니다. 관리자 검증 후 플랜이 반영됩니다.")
    else:
        st.warning(f"선택한 {get_plan_name(target_plan)} 결제는 관리자 검증 후 플랜이 반영됩니다.")
    clear_payment_query_params_keep_auth()


def _create_checkout_session(user: dict[str, Any], plan_type: str):
    if stripe is None:
        raise RuntimeError("stripe 패키지가 설치되어 있지 않습니다.")

    plan_details = get_plan_details(plan_type)

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
            "username": str(user["username"]),
            "plan_type": plan_type,
        },
    )


def start_stripe_checkout(user: dict[str, Any], plan_type: str) -> None:
    try:
        checkout = _create_checkout_session(user, plan_type)
        st.link_button("Stripe Checkout으로 이동", checkout.url, use_container_width=True)
        st.markdown(
            f"<script>window.location.href='{checkout.url}';</script>",
            unsafe_allow_html=True,
        )
    except Exception as e:
        st.error(f"결제 세션 생성 실패: {e}")


def apply_demo_plan(user: dict[str, Any], plan_type: str, refresh_user_plan_in_session) -> None:
    target_plan = get_plan_tier(plan_type)
    update_user_plan(int(user["id"]), target_plan)
    refresh_user_plan_in_session(target_plan)
    st.success(f"데모 결제가 완료되어 {get_plan_name(target_plan)} 플랜으로 변경되었습니다.")
    st.rerun()
