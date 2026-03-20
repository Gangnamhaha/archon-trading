import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data.fetcher import fetch_stock


def render_pro_analytics(holdings: pd.DataFrame, user_is_pro: bool) -> None:
    if user_is_pro and len(holdings) >= 2:
        st.markdown("---")
        st.subheader("📊 분산투자 최적화 (효율적 프론티어)")
        if st.button("최적 포트폴리오 계산", use_container_width=True):
            with st.spinner("최적화 계산 중..."):
                tickers_list = holdings["ticker"].tolist()
                markets_list = holdings["market"].tolist()
                try:
                    returns_data = {}
                    for ticker, market in zip(tickers_list, markets_list):
                        stock_df = fetch_stock(ticker, market, "1y")
                        if not stock_df.empty:
                            returns_data[ticker] = stock_df["Close"].pct_change().dropna()
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
                                opt_df = pd.DataFrame(
                                    {
                                        "종목": list(returns_data.keys()),
                                        "현재비율(%)": [round(100.0 / n, 1)] * n,
                                        "최적비율(%)": [round(w * 100, 1) for w in best_w],
                                    }
                                )
                                st.dataframe(opt_df, use_container_width=True, hide_index=True)
                            with opt_col2:
                                fig_opt = go.Figure(
                                    data=[
                                        go.Pie(
                                            labels=list(returns_data.keys()),
                                            values=[round(w * 100, 1) for w in best_w],
                                            hole=0.4,
                                        )
                                    ]
                                )
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
            for ticker, market, name in zip(holdings["ticker"], holdings["market"], holdings["name"]):
                stock_df = fetch_stock(ticker, market, "1y")
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
                kelly_rows.append(
                    {
                        "종목": name,
                        "승률(%)": round(win_rate * 100, 1),
                        "평균수익(%)": round(avg_win * 100, 2),
                        "평균손실(%)": round(avg_loss * 100, 2),
                        "켈리비율(%)": round(kelly_fraction * 100, 1),
                        "권장비중(%)": round(recommended_weight * 100, 1),
                    }
                )

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
            for ticker, market in zip(holdings["ticker"], holdings["market"]):
                stock_df = fetch_stock(ticker, market, "1y")
                if stock_df.empty or "Close" not in stock_df.columns:
                    continue
                daily_ret = stock_df["Close"].pct_change().dropna()
                if len(daily_ret) > 0:
                    corr_returns[ticker] = daily_ret

            returns_df = pd.DataFrame(corr_returns).dropna()
            if returns_df.shape[1] >= 2:
                corr_matrix = returns_df.corr()
                fig_corr = px.imshow(
                    corr_matrix,
                    text_auto=True,
                    color_continuous_scale="RdBu_r",
                    zmin=-1,
                    zmax=1,
                    title="1년 일간 수익률 상관관계",
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
                    for ticker1, ticker2, corr_val in high_corr_pairs:
                        st.write(f"⚠️ 높은 상관: {ticker1} - {ticker2} (상관계수 {corr_val:.2f})")
                else:
                    st.write("상관계수 0.7 초과 조합이 없어 분산 효과가 상대적으로 양호합니다.")
            else:
                st.info("상관관계 분석을 위해 최소 2개 종목의 1년치 데이터가 필요합니다.")
        except Exception as e:
            st.error(f"상관관계 분석 실패: {e}")
    elif not user_is_pro:
        st.markdown("---")
        st.info("💎 분산투자 최적화는 Pro 전용 기능입니다.")
