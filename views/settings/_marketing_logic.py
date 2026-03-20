from datetime import datetime

import streamlit as st

from data.database import (
    get_marketing_automation_job,
    get_marketing_automation_logs,
    is_marketing_automation_due,
    upsert_marketing_automation_job,
)
from views.settings._marketing_content import (
    is_valid_email,
    is_valid_http_url,
    run_marketing_automation,
)

PLATFORMS = ["트위터 (280자)", "인스타그램", "블로그 요약", "카카오톡 메시지"]
MARKETS = ["KOSPI", "KOSDAQ"]
PUBLISH_CHANNELS = ["일반 웹훅", "네이버 블로그", "카카오채널"]


def _job_str(job: dict[str, object], key: str, default: str) -> str:
    value = job.get(key)
    return value if isinstance(value, str) else default


def _job_int(job: dict[str, object], key: str, default: int) -> int:
    value = job.get(key)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default


def render_marketing_automation_tab(username: str) -> None:
    st.subheader("⚙️ 마케팅 자동화")
    st.caption("스케줄 기반으로 콘텐츠를 자동 생성하고 공지/웹훅으로 자동 배포합니다.")

    job = get_marketing_automation_job(username) or {}
    default_market = _job_str(job, "market", "KOSPI")
    default_run_type = _job_str(job, "run_type", "SNS 포스트")
    default_platform = _job_str(job, "platform", "트위터 (280자)")
    default_channel = _job_str(job, "publish_channel", "일반 웹훅")
    default_interval = _job_int(job, "interval_minutes", 120)
    default_webhook = _job_str(job, "webhook_url", "")
    default_publish_notice = bool(job.get("publish_notice", False))
    default_notify_on_failure = bool(job.get("notify_on_failure", True))
    default_alert_email = _job_str(job, "alert_email", "")
    default_active = bool(job.get("is_active", False))

    col1, col2 = st.columns(2)
    with col1:
        auto_run_type = str(
            st.selectbox(
                "자동화 유형",
                ["SNS 포스트", "성과 리포트"],
                index=0 if default_run_type == "SNS 포스트" else 1,
                key="auto_run_type",
            )
            or "SNS 포스트"
        )
        auto_market = str(
            st.selectbox("추천 시장", MARKETS, index=MARKETS.index(default_market) if default_market in MARKETS else 0)
            or MARKETS[0]
        )
        auto_platform = str(
            st.selectbox("SNS 플랫폼", PLATFORMS, index=PLATFORMS.index(default_platform) if default_platform in PLATFORMS else 0)
            or PLATFORMS[0]
        )
        auto_channel = str(
            st.selectbox(
                "배포 채널",
                PUBLISH_CHANNELS,
                index=PUBLISH_CHANNELS.index(default_channel) if default_channel in PUBLISH_CHANNELS else 0,
            )
            or PUBLISH_CHANNELS[0]
        )
    with col2:
        interval_options = [30, 60, 120, 240, 720, 1440]
        auto_interval = int(
            st.selectbox(
                "실행 간격",
                interval_options,
                index=interval_options.index(default_interval) if default_interval in interval_options else 2,
            )
            or 120
        )
        auto_webhook = str(
            st.text_input("Webhook URL (선택)", value=default_webhook, placeholder="https://your-webhook-endpoint") or ""
        ).strip()
        auto_publish_notice = st.checkbox("생성 결과를 공지사항에 자동 발행", value=default_publish_notice)
        auto_notify_failure = st.checkbox("실패 시 알림 발행", value=default_notify_on_failure)
        auto_alert_email = str(st.text_input("실패 알림 이메일(선택)", value=default_alert_email) or "").strip()

    settings_error = ""
    if auto_webhook and not is_valid_http_url(auto_webhook):
        settings_error = "Webhook URL 형식이 올바르지 않습니다. http/https URL을 입력하세요."
    elif auto_alert_email and not is_valid_email(auto_alert_email):
        settings_error = "실패 알림 이메일 형식이 올바르지 않습니다."
    elif auto_notify_failure and not auto_alert_email:
        st.info("실패 알림 이메일이 비어있으면 공지 알림만 발행됩니다.")

    if settings_error:
        st.error(settings_error)

    status_col1, status_col2 = st.columns(2)
    with status_col1:
        if st.button("설정 저장", type="primary", use_container_width=True):
            if settings_error:
                st.stop()
            upsert_marketing_automation_job(
                username=username,
                run_type=auto_run_type,
                market=auto_market,
                platform=auto_platform,
                publish_channel=auto_channel,
                interval_minutes=auto_interval,
                webhook_url=auto_webhook,
                publish_notice=auto_publish_notice,
                notify_on_failure=auto_notify_failure,
                alert_email=auto_alert_email,
                is_active=default_active,
            )
            st.success("자동화 설정이 저장되었습니다.")
            st.rerun()
    with status_col2:
        toggle_label = "자동화 중지" if default_active else "자동화 시작"
        if st.button(toggle_label, use_container_width=True):
            if settings_error:
                st.stop()
            upsert_marketing_automation_job(
                username=username,
                run_type=auto_run_type,
                market=auto_market,
                platform=auto_platform,
                publish_channel=auto_channel,
                interval_minutes=auto_interval,
                webhook_url=auto_webhook,
                publish_notice=auto_publish_notice,
                notify_on_failure=auto_notify_failure,
                alert_email=auto_alert_email,
                is_active=not default_active,
            )
            st.success("자동화 상태가 변경되었습니다.")
            st.rerun()

    if st.button("지금 즉시 실행", use_container_width=True):
        if settings_error:
            st.stop()
        ok, content, message = run_marketing_automation(
            username=username,
            run_type=auto_run_type,
            platform=auto_platform,
            market=auto_market,
            publish_channel=auto_channel,
            webhook_url=auto_webhook,
            publish_notice=auto_publish_notice,
            notify_on_failure=auto_notify_failure,
            alert_email=auto_alert_email,
        )
        if ok:
            st.success(message)
            st.text_area("자동 생성 결과", content, height=260)
        else:
            st.error(message)

    current_job = get_marketing_automation_job(username)
    if current_job and current_job.get("is_active") and is_marketing_automation_due(username):
        run_type = _job_str(current_job, "run_type", auto_run_type)
        market = _job_str(current_job, "market", auto_market)
        platform = _job_str(current_job, "platform", auto_platform)
        publish_channel = _job_str(current_job, "publish_channel", auto_channel)
        webhook_url = _job_str(current_job, "webhook_url", auto_webhook)
        publish_notice = bool(current_job.get("publish_notice", auto_publish_notice))
        notify_on_failure = bool(current_job.get("notify_on_failure", auto_notify_failure))
        alert_email = _job_str(current_job, "alert_email", auto_alert_email)
        ok, content, message = run_marketing_automation(
            username=username,
            run_type=run_type,
            platform=platform,
            market=market,
            publish_channel=publish_channel,
            webhook_url=webhook_url,
            publish_notice=publish_notice,
            notify_on_failure=notify_on_failure,
            alert_email=alert_email,
        )
        if ok:
            st.info("예약된 자동 실행이 완료되었습니다.")
            st.text_area("최근 자동 실행 결과", content, height=220)
        else:
            st.warning(f"자동 실행 실패: {message}")

    current_job = get_marketing_automation_job(username)
    if current_job:
        st.markdown("---")
        st.caption(
            f"상태: {'동작중' if current_job['is_active'] else '중지'} | "
            f"마지막 실행: {current_job.get('last_run_at') or '-'} | "
            f"다음 실행: {current_job.get('next_run_at') or '-'}"
        )

    logs = get_marketing_automation_logs(username, limit=20)
    if not logs.empty:
        st.markdown("### 실행 로그")
        st.dataframe(logs, use_container_width=True, hide_index=True)
