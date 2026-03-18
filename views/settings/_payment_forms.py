from typing import Any

import streamlit as st

from views.settings._payment_logic import get_plan_details, get_plan_name, get_plan_tier


def render_plan_card(title: str, price: str, accent_color: str, features: list[str], badge: str = "") -> None:
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

    feature_rows = "".join(
        f"""
        <div style="display:flex;align-items:center;gap:0.55rem;margin-bottom:0.55rem;">
            <span style="color:{accent_color};font-size:0.95rem;flex-shrink:0;">✓</span>
            <span style="color:#CBD5E0;font-size:0.92rem;">{feature}</span>
        </div>"""
        for feature in features
    )

    glow = f"0 0 0 1px {accent_color}33, 0 8px 32px {accent_color}18, 0 24px 48px rgba(0,0,0,0.45)"
    top_border = f"3px solid {accent_color}" if not is_free else "3px solid #334155"
    bg = "linear-gradient(160deg, rgba(22,30,50,0.98) 0%, rgba(12,16,28,0.98) 100%)"

    st.markdown(
        f"""
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
    </div>""",
        unsafe_allow_html=True,
    )


def render_toss_button(plan_type: str, toss_client_key: str, username: str) -> None:
    plan_details = get_plan_details(plan_type)
    import streamlit.components.v1 as components

    button_suffix = plan_type.replace("_", "")
    button_label = f"토스 {get_plan_name(get_plan_tier(plan_type))} 결제"
    components.html(
        f"""
        <script src="https://js.tosspayments.com/v1/payment"></script>
        <button onclick="tossPayment{button_suffix}()" style="width:100%;padding:14px;background:#0064FF;color:white;border:none;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;">{button_label}</button>
        <script>
        var tossPayments{button_suffix} = TossPayments('{toss_client_key}');
        function tossPayment{button_suffix}() {{
            tossPayments{button_suffix}.requestPayment('카드', {{
                amount: {int(plan_details['amount'])},
                orderId: 'archon-{username}-{button_suffix}-' + Date.now(),
                orderName: '{str(plan_details['product_name'])}',
                customerName: '{username}',
                successUrl: window.location.origin + '?payment=success&provider=toss&plan_type={plan_type}',
                failUrl: window.location.origin + '?payment=fail',
            }});
        }}
        </script>
        """,
        height=72,
    )


def render_portone_button(plan_type: str, portone_code: str, username: str) -> None:
    plan_details = get_plan_details(plan_type)
    import streamlit.components.v1 as components

    button_suffix = plan_type.replace("_", "")
    button_label = f"아임포트 {get_plan_name(get_plan_tier(plan_type))} 결제"
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
                merchant_uid: 'archon-{username}-{button_suffix}-' + Date.now(),
                name: '{str(plan_details['product_name'])}',
                amount: {int(plan_details['amount'])},
                buyer_name: '{username}',
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


def render_kakao_button(plan_type: str, kakao_admin_key: str, button_key: str, username: str) -> None:
    plan_details = get_plan_details(plan_type)
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
                    "partner_order_id": f"archon-{username}-{plan_type}",
                    "partner_user_id": username,
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


def render_demo_button(enabled: bool, label: str, key: str, on_click) -> None:
    if enabled:
        if st.button(label, type="primary", use_container_width=True, key=key):
            on_click()
    else:
        st.info("데모 결제는 비활성화되어 있습니다. 운영 환경에서는 실제 결제 키를 사용하세요.")


def render_referral_section(username: str, user_id: int, refresh_user_plan_in_session) -> None:
    from config.auth import update_user_plan
    from data.database import get_referral_code, get_referral_stats, use_referral_code

    st.markdown("---")
    st.subheader("추천인 리워드")
    st.caption("친구 초대 시 양쪽 모두 Pro 7일 무료!")

    my_code = get_referral_code(username)
    success_count = get_referral_stats(username)

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
        ok, message = use_referral_code(input_code, username)
        if ok:
            update_user_plan(user_id, "pro")
            refresh_user_plan_in_session("pro")
            st.success(message)
            st.rerun()
        else:
            st.error(message)

    st.markdown("---")
    with st.expander("📋 환불 정책"):
        st.markdown(
            """
    - 전자상거래법에 따라 결제 후 **7일 이내** 청약철회 가능
    - 이미 이용한 기간은 **일할 계산**하여 차감
    - 환불 요청: 관리자에게 문의
    - 무료 체험(추천인 리워드) 기간은 환불 대상 아님
    """
        )
