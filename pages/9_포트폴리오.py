"""
포트폴리오 페이지
- 보유 종목 관리
- 수익률 추적, 자산 배분 분석
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from data.database import add_stock, remove_stock, get_portfolio
from data.fetcher import fetch_stock
from portfolio.tracker import PortfolioTracker
from config.styles import inject_pro_css
from config.auth import require_auth, is_paid, is_pro

st.set_page_config(page_title="포트폴리오", page_icon="💼", layout="wide")
require_auth()
inject_pro_css()
st.title("💼 포트폴리오 트래커")

_user_is_pro = is_pro()
_user_is_paid = is_paid()
_MAX_FREE_STOCKS = 5

tracker = PortfolioTracker()

# === 종목 추가 폼 ===
_current_portfolio = get_portfolio()
_portfolio_count = len(_current_portfolio) if not _current_portfolio.empty else 0

if not _user_is_paid and _portfolio_count >= _MAX_FREE_STOCKS:
    st.warning(f"🔒 Free 플랜: 포트폴리오 종목 최대 {_MAX_FREE_STOCKS}개 (현재 {_portfolio_count}개). Plus 업그레이드 시 무제한.")
    _can_add = False
else:
    _can_add = True
    if not _user_is_paid:
        st.info(f"Free 플랜: 포트폴리오 {_portfolio_count}/{_MAX_FREE_STOCKS}종목")

st.subheader("종목 추가")
with st.form("add_stock_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        add_market = str(st.selectbox("시장", ["KR", "US"]) or "KR")
        add_ticker = st.text_input("종목 코드/티커", placeholder="005930 또는 AAPL")
    with col2:
        add_name = st.text_input("종목명", placeholder="삼성전자")
        add_price = st.number_input("매수 단가", min_value=0.0, step=100.0, format="%.0f")
    with col3:
        add_qty = int(st.number_input("수량", min_value=1, step=1, value=1))
        add_date = st.date_input("매수일")

    submitted = st.form_submit_button("종목 추가", type="primary", use_container_width=True)
    if submitted and add_ticker and add_price > 0:
        if not _can_add:
            st.error(f"Free 플랜 종목 한도({_MAX_FREE_STOCKS}개)에 도달했습니다. Plus로 업그레이드하세요.")
        else:
            buy_date_value = add_date[0] if isinstance(add_date, tuple) and add_date else add_date
            if buy_date_value is None or isinstance(buy_date_value, tuple):
                st.error("매수일을 선택하세요.")
            else:
                tracker.add_holding(
                    ticker=add_ticker, market=add_market, name=add_name,
                    buy_price=add_price, quantity=add_qty,
                    buy_date=str(buy_date_value)
                )
                st.success(f"{add_name} ({add_ticker}) 추가 완료!")
                st.rerun()

st.markdown("---")

# === 포트폴리오 요약 ===
st.subheader("포트폴리오 현황")

portfolio_df = get_portfolio()
if portfolio_df.empty:
    st.info("아직 등록된 종목이 없습니다. 위에서 종목을 추가하세요.")
else:
    # 현재가 조회 및 수익률 계산
    with st.spinner("현재가 조회 중..."):
        holdings = tracker.get_holdings()

    if not holdings.empty:
        # 요약 지표
        summary = tracker.get_total_value()
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("보유 종목 수", f"{summary['종목수']}개")
        col2.metric("총 매수금액", f"{summary['총매수금액']:,.0f}")
        col3.metric("총 평가금액", f"{summary['총평가금액']:,.0f}")
        pnl_delta = f"{summary['총평가손익']:+,.0f}"
        col4.metric("총 평가손익", f"{summary['총평가손익']:,.0f}", pnl_delta)
        ret_color = "normal" if summary["총수익률"] >= 0 else "inverse"
        col5.metric("총 수익률", f"{summary['총수익률']:.2f}%")

        st.markdown("---")

        # 보유 종목 테이블
        st.subheader("보유 종목 상세")
        display_df = holdings[["id", "name", "ticker", "market", "buy_price", "quantity",
                                "현재가", "매수금액", "평가금액", "평가손익", "수익률(%)"]].copy()
        display_df.columns = ["ID", "종목명", "코드", "시장", "매수단가", "수량",
                              "현재가", "매수금액", "평가금액", "평가손익", "수익률(%)"]

        # 수익률에 따른 색상 표시
        st.dataframe(
            display_df.style.applymap(
                lambda v: "color: red" if isinstance(v, (int, float)) and v > 0 else (
                    "color: blue" if isinstance(v, (int, float)) and v < 0 else ""
                ),
                subset=["평가손익", "수익률(%)"]
            ),
            use_container_width=True,
            hide_index=True
        )

        # 종목 삭제
        col_del1, col_del2 = st.columns([3, 1])
        with col_del1:
            delete_id = st.number_input("삭제할 종목 ID", min_value=0, step=1, value=0)
        with col_del2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("종목 삭제", type="secondary"):
                if delete_id > 0:
                    remove_stock(int(delete_id))
                    st.success(f"ID {delete_id} 종목이 삭제되었습니다.")
                    st.rerun()

        st.markdown("---")

        # 자산 배분 파이차트
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.subheader("자산 배분")
            alloc = tracker.get_allocation()
            if not alloc.empty:
                fig_pie = px.pie(
                    alloc, values="평가금액", names="name",
                    title="종목별 비중",
                    hole=0.4
                )
                fig_pie.update_layout(height=400, template="plotly_dark")
                st.plotly_chart(fig_pie, use_container_width=True)

        with col_chart2:
            st.subheader("종목별 수익률")
            fig_bar = go.Figure(data=[
                go.Bar(
                    x=holdings["name"],
                    y=holdings["수익률(%)"],
                    marker_color=["red" if r >= 0 else "blue" for r in holdings["수익률(%)"]],
                    text=[f"{r:.1f}%" for r in holdings["수익률(%)"]],
                    textposition="auto"
                )
            ])
            fig_bar.update_layout(
                title="종목별 수익률 (%)",
                yaxis_title="수익률 (%)",
                height=400, template="plotly_dark",
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("---")

        # === 리밸런싱 알림 ===
        st.subheader("⚖️ 리밸런싱 분석")
        alloc_data = tracker.get_allocation()
        if not alloc_data.empty and len(alloc_data) >= 2:
            total_val = alloc_data["평가금액"].sum()
            alloc_data["현재비율(%)"] = (alloc_data["평가금액"] / total_val * 100).round(1)
            equal_target = round(100.0 / len(alloc_data), 1)
            alloc_data["목표비율(%)"] = equal_target
            alloc_data["차이(%)"] = (alloc_data["현재비율(%)"] - alloc_data["목표비율(%)"]).round(1)
            alloc_data["조정"] = alloc_data["차이(%)"].apply(
                lambda d: "🔴 매도 필요" if d > 5 else ("🟢 매수 필요" if d < -5 else "✅ 적정")
            )

            rebal_display = alloc_data[["name", "평가금액", "현재비율(%)", "목표비율(%)", "차이(%)", "조정"]].copy()
            rebal_display.columns = ["종목명", "평가금액", "현재비율(%)", "목표비율(%)", "차이(%)", "조정"]
            st.dataframe(rebal_display, use_container_width=True, hide_index=True)

            needs_rebal = alloc_data[alloc_data["차이(%)"].abs() > 5]
            if not needs_rebal.empty:
                st.warning(f"⚠️ {len(needs_rebal)}개 종목이 목표 비율 대비 5%p 이상 벗어났습니다. 리밸런싱을 검토하세요.")
            else:
                st.success("✅ 모든 종목이 균등 배분 기준 ±5%p 이내입니다.")

            st.caption("※ 목표비율은 균등 배분 기준입니다. 향후 사용자 지정 비율 설정 기능이 추가될 예정입니다.")

        # === 분산투자 최적화 ===
        if _user_is_pro and len(holdings) >= 2:
            st.markdown("---")
            st.subheader("📊 분산투자 최적화 (효율적 프론티어)")
            if st.button("최적 포트폴리오 계산", use_container_width=True):
                with st.spinner("최적화 계산 중..."):
                    tickers_list = holdings["ticker"].tolist()
                    markets_list = holdings["market"].tolist()
                    try:
                        returns_data = {}
                        for t, m in zip(tickers_list, markets_list):
                            stock_df = fetch_stock(t, m, "1y")
                            if not stock_df.empty:
                                returns_data[t] = stock_df["Close"].pct_change().dropna()
                        if len(returns_data) >= 2:
                            import numpy as np
                            returns_df = pd.DataFrame(returns_data).dropna()
                            mean_ret = returns_df.mean() * 252
                            cov_mat = returns_df.cov() * 252
                            n = len(returns_data)
                            best_sharpe, best_w = -999, None
                            np.random.seed(42)
                            for _ in range(5000):
                                w = np.random.dirichlet(np.ones(n))
                                p_ret = np.dot(w, mean_ret)
                                p_vol = np.sqrt(np.dot(w, np.dot(cov_mat, w)))
                                sharpe = (p_ret - 0.03) / p_vol if p_vol > 0 else 0
                                if sharpe > best_sharpe:
                                    best_sharpe, best_w = sharpe, w
                            if best_w is not None:
                                opt_col1, opt_col2 = st.columns(2)
                                with opt_col1:
                                    opt_df = pd.DataFrame({
                                        "종목": list(returns_data.keys()),
                                        "현재비율(%)": [round(100.0 / n, 1)] * n,
                                        "최적비율(%)": [round(w * 100, 1) for w in best_w],
                                    })
                                    st.dataframe(opt_df, use_container_width=True, hide_index=True)
                                with opt_col2:
                                    fig_opt = go.Figure(data=[go.Pie(
                                        labels=list(returns_data.keys()),
                                        values=[round(w * 100, 1) for w in best_w],
                                        hole=0.4
                                    )])
                                    fig_opt.update_layout(title="최적 포트폴리오 비율", height=350, template="plotly_dark")
                                    st.plotly_chart(fig_opt, use_container_width=True)
                                st.metric("최적 샤프 비율", f"{best_sharpe:.2f}")
                        else:
                            st.warning("최적화를 위해 최소 2개 종목의 1년치 데이터가 필요합니다.")
                    except Exception as e:
                        st.error(f"최적화 실패: {e}")

            st.markdown("---")
            st.subheader("🎯 켈리 기준 포지션 사이징")
            try:
                kelly_rows = []
                for t, m, n in zip(holdings["ticker"], holdings["market"], holdings["name"]):
                    stock_df = fetch_stock(t, m, "1y")
                    if stock_df.empty or "Close" not in stock_df.columns:
                        continue

                    daily_ret = stock_df["Close"].pct_change().dropna()
                    if len(daily_ret) == 0:
                        continue

                    win_returns = daily_ret[daily_ret > 0]
                    loss_returns = daily_ret[daily_ret < 0]

                    win_rate = len(win_returns) / len(daily_ret)
                    avg_win = win_returns.mean() if len(win_returns) > 0 else 0.0
                    avg_loss = abs(loss_returns.mean()) if len(loss_returns) > 0 else 0.0

                    if avg_win > 0:
                        kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
                    else:
                        kelly_fraction = 0.0

                    recommended_weight = max(0.0, min(0.25, kelly_fraction * 0.5))

                    kelly_rows.append({
                        "종목": n,
                        "승률(%)": round(win_rate * 100, 1),
                        "평균수익(%)": round(avg_win * 100, 2),
                        "평균손실(%)": round(avg_loss * 100, 2),
                        "켈리비율(%)": round(kelly_fraction * 100, 1),
                        "권장비중(%)": round(recommended_weight * 100, 1),
                    })

                if kelly_rows:
                    st.dataframe(pd.DataFrame(kelly_rows), use_container_width=True, hide_index=True)
                else:
                    st.info("켈리 기준 계산을 위한 수익률 데이터가 부족합니다.")
            except Exception as e:
                st.error(f"켈리 기준 계산 실패: {e}")

            st.warning("⚠️ 켈리 기준은 이론적 최적치입니다. 실전에서는 Half-Kelly (절반) 이하를 권장합니다.")

            st.markdown("---")
            st.subheader("🔗 종목간 상관관계")
            try:
                corr_returns = {}
                for t, m in zip(holdings["ticker"], holdings["market"]):
                    stock_df = fetch_stock(t, m, "1y")
                    if stock_df.empty or "Close" not in stock_df.columns:
                        continue
                    daily_ret = stock_df["Close"].pct_change().dropna()
                    if len(daily_ret) > 0:
                        corr_returns[t] = daily_ret

                returns_df = pd.DataFrame(corr_returns).dropna()

                if returns_df.shape[1] >= 2:
                    corr_matrix = returns_df.corr()
                    fig_corr = px.imshow(
                        corr_matrix,
                        text_auto=True,
                        color_continuous_scale="RdBu_r",
                        zmin=-1,
                        zmax=1,
                        title="1년 일간 수익률 상관관계"
                    )
                    fig_corr.update_layout(height=450, template="plotly_dark")
                    st.plotly_chart(fig_corr, use_container_width=True)

                    high_corr_pairs = []
                    tickers = list(corr_matrix.columns)
                    for i in range(len(tickers)):
                        for j in range(i + 1, len(tickers)):
                            corr_val = corr_matrix.iloc[i, j]
                            if pd.notna(corr_val) and corr_val > 0.7:
                                high_corr_pairs.append((tickers[i], tickers[j], corr_val))

                    st.markdown("**해석**")
                    if high_corr_pairs:
                        for t1, t2, corr_val in high_corr_pairs:
                            st.write(f"⚠️ 높은 상관: {t1} - {t2} (상관계수 {corr_val:.2f})")
                    else:
                        st.write("상관계수 0.7 초과 조합이 없어 분산 효과가 상대적으로 양호합니다.")
                else:
                    st.info("상관관계 분석을 위해 최소 2개 종목의 1년치 데이터가 필요합니다.")
            except Exception as e:
                st.error(f"상관관계 분석 실패: {e}")
        elif not _user_is_pro:
            st.markdown("---")
            st.info("💎 분산투자 최적화는 Pro 전용 기능입니다.")

st.markdown("---")
st.subheader("💱 FX · 🪙 코인 자산 현황")

_fx_tab, _crypto_tab, _alert_tab = st.tabs(["💱 외환 포지션", "🪙 코인 포지션", "🔔 가격 알림"])

with _fx_tab:
    _fx_log = st.session_state.get("fx_trade_log", [])
    _fx_pos = st.session_state.get("fx_position")
    if _fx_pos:
        from data.fetcher import get_fx_spot_rate
        _fx_pair = str(_fx_pos.get("pair", st.session_state.get("fx_pair", "")))
        _fx_entry = float(_fx_pos.get("entry_rate", 0))
        _fx_curr = get_fx_spot_rate(_fx_pair) if _fx_pair else 0.0
        _fx_pct = (_fx_curr / _fx_entry - 1) * 100 if _fx_entry else 0.0
        _direction = str(_fx_pos.get("direction", ""))
        _lot = int(_fx_pos.get("lot", 0))
        pc1, pc2, pc3, pc4 = st.columns(4)
        pc1.metric("보유 통화쌍", _fx_pair)
        pc2.metric("진입 환율", f"{_fx_entry:.4f}")
        pc3.metric("현재 환율", f"{_fx_curr:.4f}")
        pc4.metric("평가손익", f"{_fx_pct:+.2f}%", delta=f"{_direction} {_lot:,}단위")
    else:
        st.info("현재 FX 포지션이 없습니다. 외환자동매매 페이지에서 오토파일럿을 시작하세요.")
    if _fx_log:
        with st.expander(f"FX 거래 로그 ({len(_fx_log)}건)", expanded=False):
            st.text("\n".join(_fx_log[-20:]))

with _crypto_tab:
    _c_pos = st.session_state.get("c_position")
    _c_log = st.session_state.get("c_trade_log", [])
    if _c_pos:
        from data.fetcher import get_crypto_price
        _c_sym = str(_c_pos.get("symbol", st.session_state.get("c_symbol", "")))
        _c_entry = float(_c_pos.get("entry_price", 0))
        _c_curr = get_crypto_price(_c_sym) if _c_sym else 0.0
        _c_amt = float(_c_pos.get("amount", 0))
        _c_pct = (_c_curr / _c_entry - 1) * 100 if _c_entry else 0.0
        _c_pnl_usd = (_c_curr - _c_entry) * _c_amt
        cc1, cc2, cc3, cc4 = st.columns(4)
        cc1.metric("보유 코인", _c_sym)
        cc2.metric("매수가", f"${_c_entry:,.2f}")
        cc3.metric("현재가", f"${_c_curr:,.2f}")
        cc4.metric("평가손익", f"{_c_pct:+.2f}%", delta=f"${_c_pnl_usd:+.2f}")
    else:
        st.info("현재 코인 포지션이 없습니다. 코인자동매매 페이지에서 오토파일럿을 시작하세요.")
    if _c_log:
        with st.expander(f"코인 거래 로그 ({len(_c_log)}건)", expanded=False):
            st.text("\n".join(_c_log[-20:]))

with _alert_tab:
    st.caption("목표 가격 도달 시 화면에 알림을 표시합니다.")
    if "price_alerts" not in st.session_state:
        st.session_state["price_alerts"] = []

    with st.form("add_alert_form"):
        al_col1, al_col2, al_col3 = st.columns(3)
        with al_col1:
            _al_type = str(st.selectbox("자산 유형", ["코인", "외환"]) or "코인")
        with al_col2:
            from data.fetcher import CRYPTO_PAIRS, FX_PAIRS
            _al_symbols = list(CRYPTO_PAIRS.keys()) if _al_type == "코인" else list(FX_PAIRS.keys())
            _al_symbol = str(st.selectbox("종목", _al_symbols) or _al_symbols[0])
        with al_col3:
            _al_price = float(st.number_input("목표 가격", min_value=0.0001, value=100.0, step=1.0))
        _al_direction = str(st.selectbox("조건", ["이상 (상단 돌파)", "이하 (하단 이탈)"]) or "이상 (상단 돌파)")
        _al_submitted = st.form_submit_button("알림 추가", use_container_width=True)

    if _al_submitted:
        st.session_state["price_alerts"].append({
            "type": _al_type, "symbol": _al_symbol,
            "price": _al_price, "direction": _al_direction, "triggered": False,
        })
        st.success(f"알림 추가: {_al_symbol} {_al_direction} {_al_price:,.4f}")

    alerts = st.session_state.get("price_alerts", [])
    if alerts:
        from data.fetcher import get_crypto_price, get_fx_spot_rate
        for idx, alert in enumerate(alerts):
            if alert.get("triggered"):
                continue
            sym = str(alert["symbol"])
            curr = get_crypto_price(sym) if alert["type"] == "코인" else get_fx_spot_rate(sym)
            target = float(alert["price"])
            hit = (curr >= target) if "이상" in str(alert["direction"]) else (curr <= target)
            status = "✅ 도달" if hit else "⏳ 대기"
            if hit:
                st.toast(f"🔔 {sym} 알림 도달! 현재: {curr:,.4f} / 목표: {target:,.4f}")
                st.session_state["price_alerts"][idx]["triggered"] = True

        alert_df = pd.DataFrame([{
            "자산": a["symbol"], "유형": a["type"],
            "조건": a["direction"], "목표가": a["price"],
            "상태": "✅ 도달" if a.get("triggered") else "⏳ 대기",
        } for a in alerts])
        st.dataframe(alert_df, use_container_width=True, hide_index=True)

        if st.button("완료된 알림 삭제", use_container_width=True):
            st.session_state["price_alerts"] = [a for a in alerts if not a.get("triggered")]
            st.rerun()
    else:
        st.info("설정된 알림이 없습니다.")
