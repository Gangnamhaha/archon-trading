import os
import ipaddress
import re
import smtplib
import socket
import sys
from datetime import datetime
from email.message import EmailMessage
from urllib.parse import urlparse

import requests
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.auth import is_pro, require_auth
from config.styles import inject_pro_css, show_legal_disclaimer
from data.database import (
    add_marketing_automation_log,
    add_notice,
    get_marketing_automation_job,
    get_marketing_automation_logs,
    get_trades,
    is_marketing_automation_due,
    mark_marketing_automation_run,
    upsert_marketing_automation_job,
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


def _is_valid_http_url(url: str) -> bool:
    if not url:
        return True
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local") or host.endswith(".internal"):
        return False

    try:
        ip_obj = ipaddress.ip_address(host)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
            return False
    except ValueError:
        try:
            resolved = socket.gethostbyname(host)
            ip_obj = ipaddress.ip_address(resolved)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
                return False
        except Exception:
            return False
    return True


def _is_valid_email(email: str) -> bool:
    if not email:
        return True
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def _build_sns_post(df, platform: str, today: str) -> str:
    top3 = df.head(3)
    if platform == "트위터 (280자)":
        lines = [f"📊 Archon AI 종목추천 ({today})"]
        for _, row in top3.iterrows():
            lines.append(f"🔹 {row['종목명']} | {row['현재가']:,}원 | {row['추천']} (점수:{row['종합점수']:+.1f})")
        lines.append("")
        lines.append("🤖 AI가 분석한 오늘의 추천종목")
        lines.append("#주식 #AI자동매매 #Archon #종목추천")
        return "\n".join(lines)

    if platform == "인스타그램":
        lines = [f"📊 오늘의 AI 종목추천 ({today})", ""]
        for _, row in top3.iterrows():
            emoji = "🟢" if row["종합점수"] > 20 else "🟡"
            lines.append(f"{emoji} {row['종목명']}")
            lines.append(f"   현재가: {row['현재가']:,}원")
            lines.append(f"   추천: {row['추천']} (점수: {row['종합점수']:+.1f})")
            lines.append(f"   RSI: {row['RSI']}")
            lines.append("")
        lines.append("💡 Archon AI가 기술적 지표 + 모멘텀 + 거래량을 종합 분석했습니다.")
        lines.append("")
        lines.append("#주식투자 #AI주식 #종목추천 #자동매매 #Archon #주식분석 #투자 #재테크")
        return "\n".join(lines)

    if platform == "블로그 요약":
        lines = [f"# Archon AI 종목추천 리포트 ({today})", ""]
        lines.append("## 오늘의 추천 종목")
        lines.append("")
        lines.append("| 종목 | 현재가 | 추천 | 점수 | RSI |")
        lines.append("|---|---|---|---|---|")
        for _, row in df.head(5).iterrows():
            lines.append(
                f"| {row['종목명']} | {row['현재가']:,}원 | {row['추천']} | {row['종합점수']:+.1f} | {row['RSI']} |"
            )
        lines.append("")
        lines.append("## 분석 기준")
        lines.append("- 기술적 지표 (RSI, MACD, 볼린저밴드 등) 35%")
        lines.append("- 모멘텀 (5일/20일/60일 수익률) 25%")
        lines.append("- 거래량 (20일 평균 대비) 15%")
        lines.append("- 추세 일관성 (SMA5 vs SMA20) 15%")
        lines.append("- 변동성 조정 10%")
        lines.append("")
        lines.append("> ⚠️ 본 분석은 투자 참고용이며, 투자 판단의 책임은 본인에게 있습니다.")
        lines.append("")
        lines.append("**Archon** - AI 기반 주식 자동매매 플랫폼")
        return "\n".join(lines)

    lines = [f"[Archon AI 종목추천] {today}", ""]
    for _, row in top3.iterrows():
        lines.append(f"▶ {row['종목명']} | {row['현재가']:,}원 | {row['추천']}")
    lines.append("")
    lines.append("AI가 기술적 지표+모멘텀+거래량을 종합 분석한 결과입니다.")
    lines.append("archon-pro.streamlit.app")
    return "\n".join(lines)


def _generate_recommendation_post(platform: str, market: str) -> str:
    from analysis.recommender import recommend_stocks

    df = recommend_stocks(market=market, top_n=30, result_count=5)
    if df.empty:
        raise RuntimeError("추천 결과가 없습니다.")
    today = datetime.now().strftime("%Y.%m.%d")
    return _build_sns_post(df, platform, today)


def _generate_performance_report() -> str:
    trade_logs = st.session_state.get("trade_log", [])
    if not trade_logs:
        raise RuntimeError("현재 세션에 거래 로그가 없어 성과 리포트를 생성할 수 없습니다.")

    total_trades = len(trade_logs)
    buy_count = sum(1 for log in trade_logs if "매수" in str(log) or "BUY" in str(log))
    sell_count = sum(1 for log in trade_logs if "매도" in str(log) or "SELL" in str(log))
    today = datetime.now().strftime("%Y.%m.%d")
    return (
        "📊 Archon 자동매매 성과 리포트\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 기준일: {today}\n"
        f"🤖 총 거래 횟수: {total_trades}회\n"
        f"📈 매수: {buy_count}회 | 📉 매도: {sell_count}회\n\n"
        "💡 AI 기반 자동매매로 감정 없는 체계적 투자!\n"
        "🏛️ Archon - archon-pro.streamlit.app\n"
        "#자동매매 #AI투자 #Archon"
    )


def _build_channel_payload(channel: str, username: str, run_type: str, content: str) -> dict[str, object]:
    base_payload = {
        "username": username,
        "run_type": run_type,
        "content": content,
        "created_at": datetime.now().isoformat(),
    }
    if channel == "네이버 블로그":
        return {
            "channel": "naver_blog",
            "title": f"Archon 자동 콘텐츠 - {run_type}",
            "body_markdown": content,
            **base_payload,
        }
    if channel == "카카오채널":
        return {
            "channel": "kakao_channel",
            "message_text": content[:1000],
            **base_payload,
        }
    return {"channel": "generic", **base_payload}


def _publish_to_webhook_with_retry(
    webhook_url: str,
    channel: str,
    username: str,
    run_type: str,
    content: str,
    max_retries: int = 3,
) -> str:
    payload = _build_channel_payload(channel, username, run_type, content)
    wait_seconds = 1
    last_error = ""
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code < 400:
                return f"Webhook 전송 완료 ({resp.status_code}, 시도 {attempt}/{max_retries})"
            last_error = f"HTTP {resp.status_code}"
        except Exception as e:
            last_error = str(e)

        if attempt < max_retries:
            import time

            time.sleep(wait_seconds)
            wait_seconds *= 2
    raise RuntimeError(f"Webhook 전송 실패 (최대 재시도 초과): {last_error}")


def _send_failure_email_if_configured(alert_email: str, username: str, run_type: str, error_message: str):
    if not alert_email:
        return ""

    smtp_host = str(st.secrets.get("SMTP_HOST", "") or "").strip()
    smtp_port = int(st.secrets.get("SMTP_PORT", 587) or 587)
    smtp_user = str(st.secrets.get("SMTP_USER", "") or "").strip()
    smtp_password = str(st.secrets.get("SMTP_PASSWORD", "") or "").strip()
    smtp_from = str(st.secrets.get("SMTP_FROM", smtp_user) or "").strip()

    if not smtp_host or not smtp_user or not smtp_password or not smtp_from:
        return "이메일 설정 없음"

    msg = EmailMessage()
    msg["Subject"] = f"[Archon] 마케팅 자동화 실패 알림 - {run_type}"
    msg["From"] = smtp_from
    msg["To"] = alert_email
    msg.set_content(
        f"사용자: {username}\n유형: {run_type}\n시간: {datetime.now().isoformat()}\n오류: {error_message}"
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)
    return "실패 알림 이메일 전송 완료"


def _run_marketing_automation(
    username: str,
    run_type: str,
    platform: str,
    market: str,
    publish_channel: str,
    webhook_url: str,
    publish_notice: bool,
    notify_on_failure: bool,
    alert_email: str,
):
    content = ""
    try:
        if run_type == "성과 리포트":
            content = _generate_performance_report()
        else:
            content = _generate_recommendation_post(platform=platform, market=market)

        messages = ["콘텐츠 생성 완료"]
        if publish_notice:
            title = f"[자동마케팅] {run_type} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            add_notice(title, content, username)
            messages.append("공지사항 자동 발행 완료")

        if webhook_url:
            if not _is_valid_http_url(webhook_url):
                raise RuntimeError("Webhook URL 보안 검증 실패")
            webhook_msg = _publish_to_webhook_with_retry(
                webhook_url=webhook_url,
                channel=publish_channel,
                username=username,
                run_type=run_type,
                content=content,
            )
            messages.append(webhook_msg)

        add_marketing_automation_log(
            username=username,
            run_type=run_type,
            status="success",
            message=" | ".join(messages),
            content_preview=content[:400],
        )
        mark_marketing_automation_run(username)
        return True, content, " | ".join(messages)
    except Exception as e:
        fail_messages = []
        if notify_on_failure:
            fail_title = f"[자동마케팅 실패] {run_type} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            fail_body = f"사용자: {username}\n오류: {e}\n채널: {publish_channel}\n"
            add_notice(fail_title, fail_body, username)
            fail_messages.append("실패 공지 등록")
            try:
                email_msg = _send_failure_email_if_configured(alert_email, username, run_type, str(e))
                if email_msg:
                    fail_messages.append(email_msg)
            except Exception as mail_error:
                fail_messages.append(f"이메일 알림 실패: {mail_error}")

        add_marketing_automation_log(
            username=username,
            run_type=run_type,
            status="fail",
            message=f"{e} | {' | '.join(fail_messages)}" if fail_messages else str(e),
            content_preview=content[:400] if content else None,
        )
        mark_marketing_automation_run(username)
        return False, content, str(e)


st.set_page_config(page_title="마케팅 도구", page_icon="📣", layout="wide")
user = require_auth()
inject_pro_css()
_user_is_pro = is_pro(user)
username = user["username"]

st.title("📣 마케팅 콘텐츠 생성기")

tab1, tab2, tab3, tab4 = st.tabs(["SNS 포스트 생성", "투자 분석 글 생성", "성과 리포트", "마케팅 자동화"])

with tab1:
    st.subheader("📱 SNS 자동 포스팅 콘텐츠")
    st.caption("종목추천 결과를 SNS 포스트로 자동 변환합니다.")
    sns_market = str(st.selectbox("시장", MARKETS, key="sns_market") or MARKETS[0])
    sns_type = str(st.selectbox("플랫폼", PLATFORMS, key="sns_type") or PLATFORMS[0])

    if st.button("종목추천 기반 포스트 생성", type="primary", use_container_width=True, key="gen_sns"):
        with st.spinner("AI 종목 스캔 + 콘텐츠 생성 중..."):
            try:
                post = _generate_recommendation_post(platform=sns_type, market=sns_market)
                st.text_area("생성된 포스트 (복사해서 사용하세요)", post, height=300, key="sns_result")
            except Exception as e:
                st.error(f"생성 실패: {e}")

with tab2:
    st.subheader("📝 투자 분석 글 생성")
    st.caption("AI가 특정 종목의 투자 분석 글을 자동 작성합니다.")

    article_ticker = st.text_input("종목코드 (예: 005930)", key="article_ticker")
    article_style = st.selectbox("글 스타일", ["전문가 분석", "초보자 설명", "요약 브리핑"], key="article_style")

    if st.button("분석 글 생성", type="primary", use_container_width=True, key="gen_article"):
        if not article_ticker:
            st.warning("종목코드를 입력하세요.")
        else:
            with st.spinner("종목 분석 + 글 생성 중..."):
                try:
                    from analysis.recommender import _calc_all_indicators, _fetch_ohlcv
                    from analysis.technical import get_signal_summary
                    from pykrx import stock as krx

                    name = krx.get_market_ticker_name(article_ticker)
                    df = _fetch_ohlcv(article_ticker, days=120)

                    if df.empty:
                        st.error("데이터를 가져올 수 없습니다.")
                    else:
                        close = df["Close"]
                        curr = int(close.iloc[-1])
                        ret_5d = round((close.iloc[-1] / close.iloc[-6] - 1) * 100, 2) if len(close) >= 6 else 0
                        ret_20d = round((close.iloc[-1] / close.iloc[-21] - 1) * 100, 2) if len(close) >= 21 else 0

                        df_ind = _calc_all_indicators(df)
                        tech = get_signal_summary(df_ind)
                        rsi = round(float(df_ind["RSI"].iloc[-1]), 1) if "RSI" in df_ind.columns else 0
                        today = datetime.now().strftime("%Y.%m.%d")

                        if article_style == "전문가 분석":
                            article = f"""# {name} ({article_ticker}) 기술적 분석 리포트
**작성일**: {today} | **현재가**: {curr:,}원

## 가격 동향
- 5일 수익률: {ret_5d:+.2f}%
- 20일 수익률: {ret_20d:+.2f}%

## 기술적 지표 분석
- **RSI ({rsi})**: {"과매수 구간으로 조정 가능성" if rsi > 70 else "과매도 구간으로 반등 가능성" if rsi < 30 else "중립 구간"}
- **종합 시그널**: {tech["signal"]} (점수: {tech["score"]:+.1f})

## 투자 의견
기술적 지표 종합 분석 결과, {name}은 현재 **{tech["signal"]}** 시그널을 보이고 있습니다.
{"단기적으로 상승 모멘텀이 강하며 추가 상승 여력이 있습니다." if tech["score"] > 20 else "중립적인 흐름으로 추가 관찰이 필요합니다." if tech["score"] > -10 else "하락 압력이 있으므로 신중한 접근이 필요합니다."}

> ⚠️ 본 분석은 투자 참고용이며, 투자 판단의 책임은 본인에게 있습니다.
> Archon AI 분석 플랫폼 | archon-pro.streamlit.app"""
                        elif article_style == "초보자 설명":
                            article = f"""## {name} 쉽게 분석해볼까요? 🔍

오늘 {name}({article_ticker})의 주가는 **{curr:,}원**입니다.

📈 **최근 흐름**
- 지난 5일간 {ret_5d:+.2f}% {"올랐어요 📈" if ret_5d > 0 else "내렸어요 📉"}
- 지난 20일간 {ret_20d:+.2f}% {"올랐어요 📈" if ret_20d > 0 else "내렸어요 📉"}

🤖 **AI 분석 결과**
RSI라는 지표가 {rsi}인데, {"70 이상이면 너무 많이 올라서 조심해야 해요" if rsi > 70 else "30 이하면 너무 많이 떨어져서 반등할 수도 있어요" if rsi < 30 else "보통 수준이에요"}.

AI가 내린 결론: **{tech["signal"]}**

💡 투자는 항상 신중하게! 이 분석은 참고용입니다.

🏛️ Archon - AI 주식 분석 플랫폼"""
                        else:
                            article = f"""[{today}] {name} ({article_ticker}) 브리핑
현재가: {curr:,}원 | 5일: {ret_5d:+.2f}% | 20일: {ret_20d:+.2f}%
RSI: {rsi} | 시그널: {tech["signal"]} ({tech["score"]:+.1f}점)
— Archon AI"""

                        st.text_area("생성된 분석 글", article, height=400, key="article_result")
                except Exception as e:
                    st.error(f"생성 실패: {e}")

with tab3:
    st.subheader("📊 성과 리포트 생성")
    st.caption("현재 로그인 세션의 거래 로그를 공유 가능한 리포트로 변환합니다.")

    trade_logs = st.session_state.get("trade_log", [])
    if not trade_logs:
        st.info("현재 세션 거래 로그가 없습니다. 자동매매 페이지에서 거래를 실행한 후 생성하세요.")
    else:
        st.text_area("최근 세션 거래 로그", "\n".join(trade_logs[-30:]), height=200)
        if st.button("성과 리포트 생성", type="primary", use_container_width=True, key="gen_report"):
            try:
                report = _generate_performance_report()
                st.text_area("성과 리포트", report, height=250, key="report_result")
            except Exception as e:
                st.error(f"리포트 생성 실패: {e}")

with tab4:
    st.subheader("⚙️ 마케팅 자동화")
    st.caption("스케줄 기반으로 콘텐츠를 자동 생성하고 공지/웹훅으로 자동 배포합니다.")

    if not _user_is_pro:
        st.warning("자동화 기능은 Pro 플랜에서만 사용할 수 있습니다.")
    else:
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
        if auto_webhook and not _is_valid_http_url(auto_webhook):
            settings_error = "Webhook URL 형식이 올바르지 않습니다. http/https URL을 입력하세요."
        elif auto_alert_email and not _is_valid_email(auto_alert_email):
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
            ok, content, message = _run_marketing_automation(
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
            ok, content, message = _run_marketing_automation(
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

show_legal_disclaimer()
